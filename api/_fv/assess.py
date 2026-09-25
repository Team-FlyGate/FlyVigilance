"""Deliberation 층(Nemotron System-2)과 Inhibitory Critic 3단.

작성자: Nemotron 이 근거 묶음만 보고 근거 ID 가 붙은 주장 JSON 을 쓴다.
크리틱 1단(규칙): 근거 ID 존재/실재, 빈 주장.  모델 미사용
크리틱 2단(숫자 오라클): 주장 속 숫자가 근거 묶음 숫자와 맞는가.  모델 미사용
크리틱 3단(과잉해석): Jev 가 주장마다 규칙 위반 확률을 한 번에 낸다.
반려되면 사유를 붙여 작성자에게 한 번 되돌린다.
"""
import json
import re
import time

from . import clients, config

OVERCLAIM_RULES = [
    ("R1", "Disproportionality (PRR, ROR, IC) shows a reporting association, never causation."),
    ("R2", "FAERS counts have no exposure denominator: no incidence, rate or risk estimates."),
    ("R3", "Do not rank or compare the safety of different drugs by disproportionality magnitude."),
    ("R4", "Absence of a disproportionality signal is not evidence of safety."),
    ("R5", "A reaction listed in the label does not confirm causality in this individual case."),
    ("R6", "A single case report cannot establish or confirm a signal on its own."),
    ("R7", "Number of PubMed hits is not a measure of evidence strength."),
    ("R8", "Counts may include duplicates and stimulated reporting; do not treat them as exact."),
    ("R9", "Confounding by indication and co-medication must not be ignored when attributing the reaction."),
    ("R10", "Model probabilities are population-calibrated, not certainty about this case."),
    ("R11", "No individual treatment advice or dosing recommendations for the patient."),
    ("R12", "Quoted label text must actually appear in the cited label section."),
]

SYSTEM = """You are the System-2 pharmacovigilance assessor inside FlyVigilante.
Write a concise case-level safety assessment using ONLY the evidence bundle. Every claim must cite evidence IDs that
exist in the bundle. Copy numbers exactly as given. Obey these interpretation limits:
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


def tier1_rules(claims: list[dict], bundle_ids: set) -> list[dict]:
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
    g = await guard(" ".join(c.get("text", "") for c in claims))
    issues = t1 + t2 + t3
    if g.get("safe") is False:
        issues.append({"claim": "memo", "tier": 3, "rule": "R11", "detail": f"NVIDIA safety guard: {g.get('categories')}"})
    return {"claims": claims, "issues": issues, "guard": g, "judge_latency_ms": judge.get("latency_ms"),
            "total_ms": round((time.perf_counter() - t0) * 1000, 1)}


async def guard(text: str) -> dict:
    """NVIDIA Nemotron Safety Guard 로 메모 문장을 검사한다. 개별 치료 조언(Unauthorized Advice)을 막는다 (R11)."""
    if not text.strip():
        return {"safe": True, "skipped": True}
    try:
        out = await clients.nim_chat([{"role": "user", "content": text[:4000]}], [config.MODEL_SAFETY], max_tokens=60, temperature=0.0)
        verdict = clients.parse_json_block(out["content"])
        safe = str(verdict.get("User Safety", "safe")).lower() == "safe"
        return {"safe": safe, "categories": verdict.get("Safety Categories"), "model": out["model"],
                "latency_ms": out["latency_ms"]}
    except Exception as e:  # 가드 장애는 통과가 아니라 사람 확인으로 표시
        return {"safe": None, "error": f"{type(e).__name__}: {e}"[:160]}


async def assess(case_state: str, triage_answers: dict, bundle: dict, max_rounds: int = 2) -> dict:
    rounds = []
    feedback = None
    allowed = _bundle_numbers(case_state, bundle)
    ids = set(bundle["ids"])
    compact = {k: (v["noul"] if v["type"] == "noul" else v.get("choice", v.get("score")))
               for k, v in triage_answers.items()}
    t_start = time.perf_counter()
    for rnd in range(1, max_rounds + 1):
        out = await clients.nim_chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": _user_prompt(case_state, compact, bundle, feedback)}],
            config.MODEL_DELIBERATE, max_tokens=1400)
        try:
            memo = clients.parse_json_block(out["content"])
        except Exception as e:
            memo = {"claims": [], "assessment": "signal_review", "narrative": "", "parse_error": str(e)}
        claims = memo.get("claims", [])
        t1 = tier1_rules(claims, ids)
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
    memo_text = " ".join([final["memo"].get("narrative", "")] + [c.get("text", "") for c in final["memo"].get("claims", [])])
    g = await guard(memo_text)
    if g.get("safe") is False:
        final["issues"].append({"claim": "memo", "tier": 3, "rule": "R11",
                                "detail": f"NVIDIA safety guard: {g.get('categories')}"})
    verdict = "pass" if not final["issues"] else "returned"
    return {"verdict": verdict, "rounds": rounds, "memo": final["memo"], "guard": g,
            "total_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "rules": [{"id": k, "text": v} for k, v in OVERCLAIM_RULES]}
