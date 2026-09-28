"""Deliberation 층(Nemotron System-2)과 Inhibitory Critic 3단.

작성자: Nemotron 이 근거 묶음만 보고 근거 ID 가 붙은 주장 JSON 을 쓴다.
크리틱 1단(규칙): 근거 ID 존재/실재, 빈 주장.  모델 미사용
크리틱 2단(숫자 오라클): 주장 속 숫자가 근거 묶음 숫자와 맞는가.  모델 미사용
크리틱 3단(과잉해석): Jev 가 주장마다 규칙 위반 확률을 한 번에 낸다.
반려되면 사유를 붙여 작성자에게 한 번 되돌린다.
"""
import asyncio
import json
import re
import time

from . import clients, config

OVERCLAIM_RULES = [
    ("R1", "Disproportionality (PRR, ROR, IC) shows a reporting association, never causation."),
    ("R2", "FAERS counts have no exposure denominator: no incidence, rate or risk estimates."),
    ("R3", "Do not rank or compare the safety of different drugs by disproportionality magnitude."),
    ("R4", "Absence of an SDR (signal of disproportionate reporting) is not evidence of safety."),
    ("R5", "A reaction listed in the label does not confirm causality in this individual case."),
    ("R6", "A single case report cannot establish or confirm a signal on its own."),
    ("R7", "Number of PubMed hits is not a measure of evidence strength."),
    ("R8", "Counts may include duplicates and stimulated reporting; do not treat them as exact."),
    ("R9", "Confounding by indication and co-medication must not be ignored when attributing the reaction."),
    ("R10", "Model probabilities are population-calibrated, not certainty about this case."),
    ("R11", "No individual treatment advice or dosing recommendations for the patient."),
    ("R12", "Quoted label text must actually appear in the cited label section."),
    ("R13", "An evidence grade is population-level context: never cite the grade without its basis, and never as proof of causality in this case."),
]

SYSTEM = """You are the System-2 pharmacovigilance assessor inside FlyVigilance.
Write a concise case-level safety assessment using ONLY the evidence bundle. Every claim must cite evidence IDs that
exist in the bundle. Copy numbers exactly as given. A disproportionality threshold crossing is an SDR (signal of
disproportionate reporting), not a validated signal; if statistics are unavailable say so, do not say 'no signal'.
Obey these interpretation limits:
""" + "\n".join(f"{k}: {v}" for k, v in OVERCLAIM_RULES) + """
Return ONLY JSON:
{"claims":[{"id":"c1","text":"...","evidence":["faers:2x2:..."]}],
 "assessment":"one of: expedite | signal_review | monitor | close",
 "narrative":"<=80 words case narrative for the safety reviewer",
 "open_questions":["..."]}
Write 3 to 6 claims. Every evidence entry must be one of the ALLOWED EVIDENCE IDS, copied exactly."""


def _numbers(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"(?<![\w.])(-?\d+(?:,\d{3})*(?:\.\d+)?)", text):
        try:
            out.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return out


def _bundle_numbers(state: str, bundle: dict) -> list[float]:
    nums = _numbers(state) + _numbers(json.dumps(bundle))
    return nums


def clean_evidence(claims: list[dict]) -> None:
    """모델이 근거 목록 줄(ID :: 설명)을 통째로 옮긴 경우 ID 부분만 남깁니다. ID 자체는 여전히 정확히 일치해야 합니다."""
    for c in claims:
        if isinstance(c.get("evidence"), list):
            c["evidence"] = [e.split(" :: ")[0].strip() if isinstance(e, str) else e for e in c["evidence"]]


def tier1_rules(claims: list[dict], bundle_ids: set) -> list[dict]:
    if not claims:  # 주장이 없는 메모(JSON 파싱 실패 포함)는 통과시키지 않고 작성자에게 되돌립니다
        return [{"claim": "memo", "tier": 1, "rule": "no_claims", "detail": "memo has no parseable claims"}]
    issues = []
    for c in claims:
        ev = c.get("evidence") or []
        if not c.get("text", "").strip():
            issues.append({"claim": c.get("id"), "tier": 1, "rule": "empty", "detail": "empty claim text"})
        if not ev:
            issues.append({"claim": c.get("id"), "tier": 1, "rule": "no_evidence", "detail": "claim has no evidence ID"})
        bad = [e for e in ev if e not in bundle_ids]
        if bad:
            issues.append({"claim": c.get("id"), "tier": 1, "rule": "unknown_evidence",
                           "detail": f"evidence IDs not in bundle: {bad}"})
    return issues


def tier2_oracle(claims: list[dict], allowed: list[float]) -> list[dict]:
    issues = []
    for c in claims:
        for x in _numbers(c.get("text", "")):
            if 1900 <= x <= 2100 and float(x).is_integer():
                continue  # 연도
            ok = any(abs(x - y) <= max(0.011, abs(y) * 0.011) for y in allowed)
            if not ok:
                issues.append({"claim": c.get("id"), "tier": 2, "rule": "number_mismatch",
                               "detail": f"{x:g} does not match any number in the evidence bundle"})
    return issues


async def tier3_judge(claims: list[dict], bundle: dict) -> tuple[list[dict], dict]:
    if not claims:
        return [], {}
    state = ("Pharmacovigilance interpretation rules:\n" +
             "\n".join(f"{k}: {v}" for k, v in OVERCLAIM_RULES) +
             "\n\nClaims written by an AI assessor:\n" +
             "\n".join(f"{c['id']}: {c['text']}" for c in claims))
    qs = {}
    for c in claims:
        qs[f"{c['id']}_violates"] = {"type": "noul", "instructions":
                                     f"Does claim {c['id']} violate any of the interpretation rules above?"}
        qs[f"{c['id']}_rule"] = {"type": "choice", "instructions": f"Which rule does claim {c['id']} most likely violate?",
                                 "criteria": {k: v for k, v in OVERCLAIM_RULES} | {"none": "no rule is violated"}}
    res = await clients.jev(state, qs)
    issues = []
    for c in claims:
        p = res["answers"][f"{c['id']}_violates"]["noul"]
        rule = res["answers"][f"{c['id']}_rule"]["choice"]
        c["overclaim_p"] = p
        if p >= 0.5 and rule != "none":
            issues.append({"claim": c["id"], "tier": 3, "rule": rule, "p": p,
                           "detail": dict(OVERCLAIM_RULES).get(rule, "")})
    return issues, res


def _user_prompt(state, triage_answers, bundle, feedback=None):
    cat = "\n".join(f"- {c['id']} :: {c['what']}" for c in bundle.get("catalog", []))
    txt = ("ALLOWED EVIDENCE IDS (cite these exact strings, nothing else; copy numbers exactly):\n" + cat +
           "\n\nCASE:\n" + state +
           "\n\nREFLEX JUDGMENTS (Jev, population-calibrated probabilities, not facts):\n" +
           json.dumps(triage_answers, ensure_ascii=False))
    if feedback:
        txt += "\n\nYour previous draft was REJECTED by the critic for these reasons. Fix every one:\n" + json.dumps(feedback)
    return txt


async def critic_only(claims: list[dict], case_state: str, bundle: dict) -> dict:
    """작성자 없이 주어진 주장만 크리틱 3단 + 가드에 통과시킨다 (적대적 주입 테스트용)."""
    t0 = time.perf_counter()
    t1 = tier1_rules(claims, set(bundle["ids"]))
    t2 = tier2_oracle(claims, _bundle_numbers(case_state, bundle))
    t3, judge = await tier3_judge(claims, bundle)
    g = await guard_claims(claims)
    issues = t1 + t2 + t3 + guard_issues(g)
    return {"claims": claims, "issues": issues, "guard": g, "judge_latency_ms": judge.get("latency_ms"),
            "total_ms": round((time.perf_counter() - t0) * 1000, 1)}


def parse_guard(content: str) -> dict:
    """가드 응답을 읽습니다. JSON({"User Safety": ...})과 한 줄 텍스트("User Safety: unsafe") 둘 다 받습니다.
    판정 줄을 찾지 못하면 safe 를 None 으로 둡니다. 읽지 못한 응답을 안전으로 치지 않습니다."""
    try:
        verdict = clients.parse_json_block(content)
    except Exception:
        verdict = {k: v.strip() for k, v in re.findall(r'"?(User Safety|Safety Categories)"?\s*:\s*"?([^"\n}]+)', content)}
    us = verdict.get("User Safety")
    return {"safe": None if us is None else str(us).strip().lower() == "safe", "categories": verdict.get("Safety Categories")}


async def guard(text: str, timeout_s: float = 20.0) -> dict:
    """NVIDIA Nemotron Safety Guard 로 메모 문장을 검사한다. 개별 치료 조언(Unauthorized Advice)을 막는다 (R11).
    기본 가드가 응답하지 않으면 대체 가드로 넘어가고, 둘 다 안 되면 timeout_s 안에 포기해 '사람 확인'으로 표시한다."""
    if not text.strip():
        return {"safe": True, "skipped": True}
    end = time.monotonic() + timeout_s
    errors = []
    for model in (config.MODEL_SAFETY, config.MODEL_SAFETY_FALLBACK):
        left = end - time.monotonic()
        if left < 2:
            break
        try:
            out = await clients.nim_chat([{"role": "user", "content": text[:4000]}], [model], max_tokens=60,
                                         temperature=0.0, deadline=time.monotonic() + min(left, timeout_s * 0.6))
        except Exception as e:
            errors.append(f"{model.split('/')[-1]}: {type(e).__name__}")
            continue
        v = parse_guard(out["content"])
        if v["safe"] is None:
            errors.append(f"{model.split('/')[-1]}: unreadable verdict")
            continue
        return {**v, "model": out["model"], "latency_ms": out["latency_ms"], "fallbacks": errors}
    return {"safe": None, "error": "; ".join(errors)[:200] or "time budget exhausted"}  # 가드 장애는 통과가 아니라 사람 확인


async def guard_claims(claims: list[dict], narrative: str = "", timeout_s: float = 20.0) -> dict:
    """주장마다 따로 가드에 넣습니다. 메모 전체를 이어 붙이면 치료 조언 한 문장이 다른 문장에 묻혀 통과했습니다."""
    items = [(c.get("id") or f"c{i + 1}", c.get("text", "")) for i, c in enumerate(claims)]
    if narrative.strip():
        items.append(("narrative", narrative))
    sem = asyncio.Semaphore(4)

    async def one(text):
        async with sem:
            return await guard(text, timeout_s)
    res = await asyncio.gather(*(one(t) for _, t in items))
    per = [{"claim": cid, **r} for (cid, _), r in zip(items, res)]
    flagged = [x for x in per if x.get("safe") is False]
    unknown = [x["claim"] for x in per if x.get("safe") is None]
    return {"safe": False if flagged else (None if unknown else True),
            "categories": ", ".join(sorted({str(x.get("categories")) for x in flagged})) or None,
            "flagged": [x["claim"] for x in flagged], "unchecked": unknown,
            "model": next((x.get("model") for x in per if x.get("model")), None), "items": len(per)}


def guard_issues(g: dict) -> list[dict]:
    return [{"claim": cid, "tier": 3, "rule": "R11", "detail": f"NVIDIA safety guard: {g.get('categories')}"}
            for cid in g.get("flagged", [])]


async def assess(case_state: str, triage_answers: dict, bundle: dict, max_rounds: int = 2, budget_s: float = 100.0) -> dict:
    """budget_s 안에 끝냅니다(서버리스 함수 제한 120초). 예산이 모자라면 재작성 없이 반려 사유를 그대로 돌려줍니다."""
    deadline = time.monotonic() + budget_s
    rounds = []
    feedback = None
    allowed = _bundle_numbers(case_state, bundle)
    ids = set(bundle["ids"])
    compact = {k: (v["noul"] if v["type"] == "noul" else v.get("choice", v.get("score")))
               for k, v in triage_answers.items()}
    t_start = time.perf_counter()
    stopped_early = False
    for rnd in range(1, max_rounds + 1):
        if rnd > 1 and deadline - time.monotonic() < 35:
            stopped_early = True
            break
        out = await clients.nim_chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": _user_prompt(case_state, compact, bundle, feedback)}],
            config.MODEL_DELIBERATE, max_tokens=1400, deadline=deadline - 15, json_mode=True)
        try:
            memo = clients.parse_json_block(out["content"])
        except Exception as e:
            memo = {"claims": [], "assessment": "signal_review", "narrative": "", "parse_error": str(e)}
        claims = memo.get("claims", [])
        clean_evidence(claims)
        t1 = tier1_rules(claims, ids)
        if memo.get("parse_error") and t1 and t1[0]["rule"] == "no_claims":
            t1[0]["detail"] += f" (JSON error: {memo['parse_error'][:80]}; return ONLY valid JSON)"
        t2 = tier2_oracle(claims, allowed)
        t3, judge = await tier3_judge(claims, bundle)
        issues = t1 + t2 + t3
        rounds.append({"round": rnd, "model": out["model"], "latency_ms": out["latency_ms"], "usage": out["usage"],
                       "fallbacks": out.get("fallbacks", []), "memo": memo, "issues": issues,
                       "judge_latency_ms": judge.get("latency_ms"), "judge_usage": judge.get("usage")})
        if not issues:
            break
        feedback = issues
    final = rounds[-1]
    g = await guard_claims(final["memo"].get("claims", []), final["memo"].get("narrative", ""),
                           timeout_s=max(5.0, min(20.0, deadline - time.monotonic())))
    final["issues"].extend(guard_issues(g))
    verdict = "pass" if not final["issues"] else "returned"
    return {"verdict": verdict, "rounds": rounds, "memo": final["memo"], "guard": g, "stopped_early": stopped_early,
            "total_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "rules": [{"id": k, "text": v} for k, v in OVERCLAIM_RULES]}
