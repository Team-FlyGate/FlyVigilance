"""비교 실험: 모델 단독(질문 하나) vs FlyVigilance 워크플로(라벨 근거 주입 전후), 결과 코드를 보여 줄 때와 가릴 때.

정답은 FAERS 결과 코드(사망·입원 등)가 있으면 '중대'입니다. 주 측정은 모든 조건의 입력에서 결과 코드를 가린
조건(ablation_blind)이며, 서술만으로 중대성을 알아보는 능력을 잽니다. 결과 코드를 보여 준 조건(ablation)은 참고로 함께 냅니다.

두 조건의 차이는 같은 사례 짝으로 McNemar 정확 검정을 합니다.
DME 안전망(EMA 지정 의학적 사건이면 사람 검토)의 효과는 같은 판단 결과에 정책만 다시 적용해 잽니다(추가 호출 없음).

사용: FV_CACHE_DIR=data/cache/api .venv/bin/python pipeline/bench/ablation.py [--conc 12]
산출물: web/public/data/bench.json 의 ablation(결과 코드 공개), ablation_blind(결과 코드 가림) 키를 갱신합니다.
"""
import argparse
import asyncio
import gzip
import json
import math
import pathlib
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from _fv import triage  # noqa: E402

OUT = ROOT / "web/public/data/bench.json"
ACTIONS = ("expedite", "signal_review", "follow_up", "monitor", "close")


def mcnemar(a: list[bool], b: list[bool]) -> dict:
    """짝지은 이진 결과의 McNemar 정확 검정(양측)입니다. b01 = a 만 참, b10 = b 만 참."""
    b01 = sum(1 for x, y in zip(a, b) if x and not y)
    b10 = sum(1 for x, y in zip(a, b) if y and not x)
    n = b01 + b10
    if n == 0:
        return {"a_only": 0, "b_only": 0, "p": 1.0}
    k = min(b01, b10)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return {"a_only": b01, "b_only": b10, "p": p}


def lat_stats(xs: list[float]) -> dict | None:
    xs = sorted(xs)
    if not xs:
        return None
    q = lambda k: xs[min(len(xs) - 1, int(k * (len(xs) - 1)))]
    return {"n": len(xs), "p50": round(q(0.5), 1), "p90": round(q(0.9), 1), "p99": round(q(0.99), 1),
            "mean": round(sum(xs) / len(xs), 1), "min": round(xs[0], 1), "max": round(xs[-1], 1)}


def auroc(y: list[int], p: list[float]) -> float | None:
    pos = [s for s, t in zip(p, y) if t]
    neg = [s for s, t in zip(p, y) if not t]
    if not pos or not neg:
        return None
    gt = sum((1 if a > b else 0.5 if a == b else 0) for a in pos for b in neg)
    return gt / (len(pos) * len(neg))


async def gather_limited(coros, limit):
    sem = asyncio.Semaphore(limit)

    async def run(c):
        async with sem:
            try:
                return await c
            except Exception as e:  # 한 건 실패가 전체를 멈추지 않게 합니다
                return {"error": f"{type(e).__name__}: {e}"[:200]}
    return await asyncio.gather(*(run(c) for c in coros))


async def run_arms(cases: list[dict], cl: httpx.AsyncClient, conc: int, include_outcome: bool) -> tuple[list, list, list, dict]:
    walls = {}
    t0 = time.perf_counter()
    full = await gather_limited([triage.triage(c, client=cl, include_outcome=include_outcome) for c in cases], conc)
    walls["flyvigilance"] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    ungrounded = await gather_limited([triage.triage(c, client=cl, grounded=False, include_outcome=include_outcome)
                                       for c in cases], conc)
    walls["flyvigilance_ungrounded"] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    raw = await gather_limited([triage.raw_triage(c, client=cl, include_outcome=include_outcome) for c in cases], conc)
    walls["raw_jev"] = round(time.perf_counter() - t0, 2)
    return full, ungrounded, raw, walls


def summarize(cases: list[dict], full: list, ungrounded: list, raw: list, include_outcome: bool) -> dict:
    ok = [i for i in range(len(cases)) if all("error" not in r[i] for r in (full, ungrounded, raw))]
    y = [bool(cases[i]["outcomes"]) for i in ok]
    act = {"flyvigilance": [full[i]["decision"]["action"] for i in ok],
           "flyvigilance_ungrounded": [ungrounded[i]["decision"]["action"] for i in ok]}
    # 같은 Jev 답에 DME 안전망만 뺀 정책을 다시 적용합니다
    no_dme = []
    for i in ok:
        g = full[i].get("grounding")
        d = triage.route_policy(full[i]["jev"]["answers"], full[i]["validity"], "US", g["expected"] if g else None,
                                g["expected_source"] if g else "jev", None)
        no_dme.append(d["action"])
    act["flyvigilance_no_dme"] = no_dme
    esc = {k: [a == "expedite" for a in v] for k, v in act.items()}
    esc["raw_jev"] = [raw[i]["escalate"] for i in ok]
    unreviewed = {k: [a in ("monitor", "close") for a in v] for k, v in act.items()}
    unreviewed["raw_jev"] = [not raw[i]["escalate"] for i in ok]

    def arm(k):
        f = esc[k]
        tp = sum(1 for a, t in zip(f, y) if a and t)
        fn = sum(1 for a, t in zip(f, y) if not a and t)
        fp = sum(1 for a, t in zip(f, y) if a and not t)
        tn = sum(1 for a, t in zip(f, y) if not a and not t)
        out = {"sens": tp / (tp + fn) if tp + fn else None, "spec": tn / (tn + fp) if tn + fp else None,
               "missed_serious": fn, "over_escalated": fp, "escalated": tp + fp, "n": len(f),
               "serious_without_review": sum(1 for u, t in zip(unreviewed[k], y) if u and t)}
        if k in act:
            out["routes"] = {a: sum(1 for x in act[k] if x == a) for a in ACTIONS}
            out["routes_serious"] = {a: sum(1 for x, t in zip(act[k], y) if x == a and t) for a in ACTIONS}
        return out

    serious = [j for j, t in enumerate(y) if t]
    nonserious = [j for j, t in enumerate(y) if not t]
    pick = lambda xs, idx: [xs[j] for j in idx]
    tests = {
        # 사람 우선으로 올린 건수(업무량)
        "workload_fv_vs_raw": mcnemar(esc["flyvigilance"], esc["raw_jev"]),
        # 비중대 사례를 사람에게 올린 과잉 상향
        "over_escalation_fv_vs_raw": mcnemar(pick(esc["flyvigilance"], nonserious), pick(esc["raw_jev"], nonserious)),
        # 중대 사례가 사람도 System-2 도 거치지 않은 경우
        "serious_unreviewed_fv_vs_raw": mcnemar(pick(unreviewed["flyvigilance"], serious), pick(unreviewed["raw_jev"], serious)),
        # 라벨 근거 주입 전후, 중대 사례를 사람 우선으로 올린 경우
        "serious_escalation_grounded_vs_ungrounded": mcnemar(pick(esc["flyvigilance"], serious),
                                                             pick(esc["flyvigilance_ungrounded"], serious)),
        # DME 안전망 전후, 중대 사례를 사람 우선으로 올린 경우
        "serious_escalation_dme_vs_no_dme": mcnemar(pick(esc["flyvigilance"], serious), pick(esc["flyvigilance_no_dme"], serious)),
    }
    dme_cases = [j for j, i in enumerate(ok) if triage.dme_hits(cases[i])]
    res = {
        "n": len(ok), "serious": sum(y), "include_outcome": include_outcome,
        "definition": ("human-first = FlyVigilance action 'expedite' / raw Jev review_first p>=0.5; "
                       "truth = FAERS outcome code present (serious); "
                       + ("outcome codes shown in the triage input" if include_outcome else "outcome codes hidden from every arm")),
        "flyvigilance": arm("flyvigilance"), "flyvigilance_ungrounded": arm("flyvigilance_ungrounded"),
        "flyvigilance_no_dme": arm("flyvigilance_no_dme"), "raw_jev": arm("raw_jev"),
        "routes": {k: arm(k)["routes"] for k in ("flyvigilance", "flyvigilance_ungrounded")},
        "raw_auroc": auroc([int(t) for t in y], [raw[i]["p"] for i in ok]),
        "raw_latency_ms": lat_stats([raw[i]["jev"]["latency_ms"] for i in ok]),
        "tests": tests,
        "dme": {"cases_with_dme": len(dme_cases), "serious_among_dme": sum(1 for j in dme_cases if y[j]),
                "changed_by_dme": sum(1 for j in range(len(ok)) if act["flyvigilance"][j] != no_dme[j]),
                "serious_changed_by_dme": sum(1 for j in range(len(ok)) if act["flyvigilance"][j] != no_dme[j] and y[j])},
    }
    # 라벨 근거: 기억 속 예측성 vs 라벨 조회
    both = [(full[i], ungrounded[i], cases[i]) for i in ok if full[i].get("grounding") and full[i]["grounding"]["expected"] is not None]
    mem = [(u["jev"]["answers"]["expected"]["noul"] >= 0.5, g["grounding"]["expected"] >= 0.5) for g, u, _ in both]
    changed = [(full[i], ungrounded[i], cases[i]) for i in ok if full[i]["decision"]["action"] != ungrounded[i]["decision"]["action"]]
    res["grounding"] = {
        "label_found": len(both), "cases": len(ok),
        "memory_vs_label": {"both_expected": sum(1 for m, l in mem if m and l), "both_unexpected": sum(1 for m, l in mem if not m and not l),
                            "memory_expected_label_not": sum(1 for m, l in mem if m and not l),
                            "memory_unexpected_label_listed": sum(1 for m, l in mem if not m and l)},
        "actions_changed": len(changed),
        "changed_to_expedite": sum(1 for g, u, _ in changed if g["decision"]["action"] == "expedite"),
        "changed_from_expedite": sum(1 for g, u, _ in changed if u["decision"]["action"] == "expedite"),
        "changed_serious_to_expedite": sum(1 for g, u, c in changed if g["decision"]["action"] == "expedite" and c["outcomes"]),
        "label_latency_ms": lat_stats([full[i]["grounding"]["latency_ms"] for i in ok if full[i].get("grounding")]),
        "examples": [{"primaryid": c["primaryid"], "suspect": g["suspect"], "reactions": c["reactions"][:3],
                      "serious": bool(c["outcomes"]), "memory_expected": round(u["jev"]["answers"]["expected"]["noul"], 2),
                      "label": {pt: v["sections"] for pt, v in g["grounding"]["label"].get("by_pt", {}).items()},
                      "before": u["decision"]["action"], "after": g["decision"]["action"]}
                     for g, u, c in changed[:12] if g.get("grounding")],
    }
    return res


async def main(args):
    cases = json.load(gzip.open(ROOT / "api/_data/cases.json.gz", "rt"))
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as cl:
        for include_outcome, key in ((True, "ablation"), (False, "ablation_blind")):
            full, ungrounded, raw, walls = await run_arms(cases, cl, args.conc, include_outcome)
            res = summarize(cases, full, ungrounded, raw, include_outcome)
            res["wall_s"] = walls
            out[key] = res
            print(key, json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("routes", "routes_serious")}
                                   for k, v in res.items() if k.startswith(("flyvigilance", "raw_jev")) and isinstance(v, dict)},
                                  default=float))
            print("  tests", json.dumps(res["tests"]))
            print("  dme", res["dme"], "grounding", {k: v for k, v in res["grounding"].items() if k not in ("examples",)})
    out["ablation_generated"] = time.strftime("%Y-%m-%d %H:%M")
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--conc", type=int, default=12)
    asyncio.run(main(ap.parse_args()))
