"""FlyVigilance 실측 벤치마크. 모든 수치는 이 스크립트 실행 결과에서만 나온다.

A. Jev 전체 트리아지(판단 7개/호출, 유효성은 규칙)  : 전 케이스, 지연·토큰·행동 분포
B. 중대성 맹검 과제                   : 결과 코드(OUTC)를 가린 상태 문자열로 중대성 확률을 묻고
                                        FAERS 결과 코드 유무를 정답으로 채점 (AUROC, 정확도, 보정)
   - Jev noul 1문항 vs Nemotron(JSON 확률) 같은 상태 문자열
C. 라우팅 일치                        : Nemotron 에게 같은 7문항을 JSON 으로 받아 Jev 와 비교

산출물: web/public/data/bench.json
"""
import argparse
import asyncio
import gzip
import json
import pathlib
import statistics
import sys
import time

import httpx
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from _fv import clients, config, triage  # noqa: E402

import ablation  # noqa: E402  (같은 폴더)

OUT = ROOT / "web/public/data/bench.json"


def auroc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(gt / (len(pos) * len(neg)))


def calib(y, p, bins=5):
    y, p = np.asarray(y), np.asarray(p)
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if m.sum():
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()), "pred": float(p[m].mean()), "obs": float(y[m].mean())})
    ece = sum(b["n"] * abs(b["pred"] - b["obs"]) for b in out) / max(1, len(p))
    return out, ece


def lat_stats(xs):
    xs = sorted(xs)
    if not xs:
        return None
    q = lambda k: xs[min(len(xs) - 1, int(k * (len(xs) - 1)))]
    return {"n": len(xs), "p50": round(q(0.5), 1), "p90": round(q(0.9), 1), "p99": round(q(0.99), 1),
            "mean": round(statistics.mean(xs), 1), "min": round(xs[0], 1), "max": round(xs[-1], 1)}


async def gather_limited(coros, limit):
    sem = asyncio.Semaphore(limit)

    async def run(c):
        async with sem:
            try:
                return await c
            except Exception as e:  # 실패도 기록한다
                return {"error": f"{type(e).__name__}: {e}"[:200]}
    return await asyncio.gather(*(run(c) for c in coros))


BLIND_Q = {"serious": {"type": "noul", "instructions":
                       "Is this adverse event case serious by ICH E2A criteria (death, life-threatening, hospitalization, "
                       "disability, congenital anomaly, or other medically important condition)?"}}

NIM_BLIND = """You are a pharmacovigilance case triage assistant. Read the case and answer ONLY with JSON:
{"serious_probability": <number 0..1>}
The probability that the case is serious by ICH E2A criteria (death, life-threatening, hospitalization, disability,
congenital anomaly, or other medically important condition)."""

NIM_TRIAGE = """You are a pharmacovigilance case triage assistant. Answer ONLY with JSON with these keys:
{"serious": p, "expected": p, "causality": "certain|probable|possible|unlikely|unassessable",
 "special": "none|pregnancy|pediatric|elderly|misuse|offlabel|interaction", "priority": 0-3,
 "route": "close|monitor|signal_review|expedite", "deep": p}
p are probabilities 0..1. priority: 0 routine, 1 standard 30 days, 2 priority 7 days, 3 expedited.
expected = reactions already in labeling of the primary suspect drug;
deep = expert narrative assessment would change handling."""


async def main(args):
    with gzip.open(ROOT / "api/_data/cases.json.gz", "rt") as f:
        cases = json.load(f)
    if args.limit:
        cases = cases[: args.limit]
    print(f"cases {len(cases)}  jev={bool(config.TYPESAFE_API_KEY)} nim={bool(config.NVIDIA_API_KEY)}")
    y = [1 if c["outcomes"] else 0 for c in cases]

    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as cl:
        # A. Jev 전체 트리아지
        t0 = time.perf_counter()
        full = await gather_limited([triage.triage(c, client=cl) for c in cases], args.conc)
        wall_a = time.perf_counter() - t0
        # A0. 근거 주입 없는 FlyVigilance (이전 설정) · R. 그대로 쓴 Jev (질문 하나)
        t0 = time.perf_counter()
        ungrounded = await gather_limited([triage.triage(c, client=cl, grounded=False) for c in cases], args.conc)
        wall_a0 = time.perf_counter() - t0
        t0 = time.perf_counter()
        raw = await gather_limited([triage.raw_triage(c, client=cl) for c in cases], args.conc)
        wall_r = time.perf_counter() - t0
        # B. Jev 맹검 중대성
        t0 = time.perf_counter()
        blind = await gather_limited([clients.jev(triage.case_state(c, include_outcome=False), BLIND_Q, client=cl) for c in cases], args.conc)
        wall_b = time.perf_counter() - t0

    ok_full = [(c, r) for c, r in zip(cases, full) if "error" not in r]
    ok_blind = [(yy, r) for yy, r in zip(y, blind) if "error" not in r]
    jev_blind_p = [r["answers"]["serious"]["noul"] for _, r in ok_blind]
    jev_blind_y = [yy for yy, _ in ok_blind]
    cal, ece = calib(jev_blind_y, jev_blind_p)
    actions = {}
    for _, r in ok_full:
        a = r["decision"]["action"]
        actions[a] = actions.get(a, 0) + 1
    by_bucket = {}
    for c, r in ok_full:
        b = by_bucket.setdefault(c["bucket"], {})
        a = r["decision"]["action"]
        b[a] = b.get(a, 0) + 1
    in_tok = [r["jev"]["usage"].get("input_tokens", 0) for _, r in ok_full]
    out_tok = [r["jev"]["usage"].get("output_tokens", 0) for _, r in ok_full]
    jev_full_lat = [r["jev"]["latency_ms"] for _, r in ok_full]
    jev_blind_lat = [r["latency_ms"] for _, r in ok_blind]
    cost_case = statistics.mean(in_tok) * config.PRICE["jev"]["in"] / 1e6 if in_tok else None
    # 실제 FAERS 진단: 행동별 실제 중대성 비율
    serious_by_action = {}
    for c, r in ok_full:
        a = r["decision"]["action"]
        s = serious_by_action.setdefault(a, [0, 0])
        s[0] += 1 if c["outcomes"] else 0
        s[1] += 1
    # ---------------- 비교 실험: 그대로 쓴 Jev vs FlyVigilance (근거 주입 전후). 결과 코드를 가린 조건은 ablation.py 가 잽니다
    abl = ablation.summarize(cases, full, ungrounded, raw, include_outcome=True)
    abl["wall_s"] = {"flyvigilance": round(wall_a, 2), "flyvigilance_ungrounded": round(wall_a0, 2), "raw_jev": round(wall_r, 2)}

    res = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "ablation": abl,
        "dataset": {"source": "FAERS " + cases[0]["quarter"], "cases": len(cases),
                    "buckets": {b: sum(1 for c in cases if c["bucket"] == b) for b in sorted({c["bucket"] for c in cases})},
                    "serious_rate": sum(y) / len(y)},
        "jev_triage": {"ok": len(ok_full), "errors": len(cases) - len(ok_full), "questions_per_call": 7,
                       "latency_ms": lat_stats(jev_full_lat), "wall_s": round(wall_a, 2), "concurrency": args.conc,
                       "throughput_cases_per_s": round(len(ok_full) / wall_a, 2),
                       "tokens_in_mean": round(statistics.mean(in_tok), 1) if in_tok else None,
                       "tokens_out_mean": round(statistics.mean(out_tok), 1) if out_tok else None,
                       "usd_per_case": cost_case, "usd_per_1k": cost_case * 1000 if cost_case else None,
                       "price": config.PRICE["jev"],
                       "actions": actions, "actions_by_bucket": by_bucket,
                       "serious_rate_by_action": {a: {"serious": s[0], "n": s[1]} for a, s in serious_by_action.items()},
                       "examples": [{"primaryid": c["primaryid"], "bucket": c["bucket"], "action": r["decision"]["action"],
                                     "reasons": r["decision"]["reasons"], "answers": r["jev"]["answers"],
                                     "latency_ms": r["jev"]["latency_ms"], "suspect": r["suspect"],
                                     "reactions": c["reactions"][:4]} for c, r in ok_full[:200]]},
        "blind_serious": {"jev": {"n": len(jev_blind_p), "auroc": auroc(jev_blind_y, jev_blind_p),
                                  "acc": float(np.mean((np.array(jev_blind_p) >= 0.5) == np.array(jev_blind_y))) if jev_blind_p else None,
                                  "ece": ece, "calibration": cal, "latency_ms": lat_stats(jev_blind_lat),
                                  "wall_s": round(wall_b, 2)},
                          "majority_baseline_acc": max(np.mean(y), 1 - np.mean(y))},
    }

    # Nemotron 비교 (표본)
    if config.NVIDIA_API_KEY and args.nim:
        sub = list(range(0, len(cases), max(1, len(cases) // args.nim)))[: args.nim]
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as cl:
            async def nim_blind(i):
                out = await clients.nim_chat([{"role": "system", "content": NIM_BLIND},
                                              {"role": "user", "content": triage.case_state(cases[i], include_outcome=False)}],
                                             [args.nim_model], max_tokens=60, temperature=0.0, client=cl)
                return {"i": i, "p": float(clients.parse_json_block(out["content"])["serious_probability"]),
                        "latency_ms": out["latency_ms"], "usage": out["usage"], "model": out["model"]}

            async def nim_tri(i):
                out = await clients.nim_chat([{"role": "system", "content": NIM_TRIAGE},
                                              {"role": "user", "content": triage.case_state(cases[i])}],
                                             [args.nim_model], max_tokens=200, temperature=0.0, client=cl)
                return {"i": i, "json": clients.parse_json_block(out["content"]), "latency_ms": out["latency_ms"],
                        "usage": out["usage"], "model": out["model"]}
            t0 = time.perf_counter()
            nb = await gather_limited([nim_blind(i) for i in sub], args.nim_conc)
            wall_nb = time.perf_counter() - t0
            t0 = time.perf_counter()
            nt = await gather_limited([nim_tri(i) for i in sub], args.nim_conc)
            wall_nt = time.perf_counter() - t0
        nb_ok = [r for r in nb if "error" not in r]
        nt_ok = [r for r in nt if "error" not in r]
        yb = [y[r["i"]] for r in nb_ok]
        pb = [r["p"] for r in nb_ok]
        jev_same = {i: r for i, r in zip(range(len(cases)), blind) if "error" not in r}
        pj = [jev_same[r["i"]]["answers"]["serious"]["noul"] for r in nb_ok if r["i"] in jev_same]
        yj = [y[r["i"]] for r in nb_ok if r["i"] in jev_same]
        full_by_i = {i: r for i, r in enumerate(full) if "error" not in r}
        agree_route = agree_caus = n_cmp = 0
        for r in nt_ok:
            j = full_by_i.get(r["i"])
            if not j:
                continue
            n_cmp += 1
            agree_route += int(str(r["json"].get("route")) == j["jev"]["answers"]["route"]["choice"])
            agree_caus += int(str(r["json"].get("causality")) == j["jev"]["answers"]["causality"]["choice"])
        nim_in = [r["usage"].get("prompt_tokens", 0) for r in nt_ok]
        nim_out = [r["usage"].get("completion_tokens", 0) for r in nt_ok]
        res["nemotron"] = {
            "model": args.nim_model, "sample": len(sub), "errors": {"blind": len(nb) - len(nb_ok), "triage": len(nt) - len(nt_ok)},
            "blind": {"n": len(pb), "auroc": auroc(yb, pb), "acc": float(np.mean((np.array(pb) >= 0.5) == np.array(yb))) if pb else None,
                      "latency_ms": lat_stats([r["latency_ms"] for r in nb_ok]), "wall_s": round(wall_nb, 2),
                      "jev_same_subset_auroc": auroc(yj, pj),
                      "jev_same_subset_acc": float(np.mean((np.array(pj) >= 0.5) == np.array(yj))) if pj else None},
            "triage": {"n": len(nt_ok), "latency_ms": lat_stats([r["latency_ms"] for r in nt_ok]), "wall_s": round(wall_nt, 2),
                       "tokens_in_mean": round(statistics.mean(nim_in), 1) if nim_in else None,
                       "tokens_out_mean": round(statistics.mean(nim_out), 1) if nim_out else None,
                       "route_agreement": agree_route / n_cmp if n_cmp else None,
                       "causality_agreement": agree_caus / n_cmp if n_cmp else None, "compared": n_cmp},
            "concurrency": args.nim_conc,
        }
    if OUT.exists():  # 결과 코드를 가린 비교(ablation.py)는 이 스크립트가 다시 재지 않으므로 보존합니다
        prev = json.loads(OUT.read_text())
        for k in ("ablation_blind", "ablation_generated"):
            if k in prev:
                res[k] = prev[k]
    OUT.write_text(json.dumps(res, indent=1, default=float))
    hist = OUT.parent / "bench"
    hist.mkdir(exist_ok=True)
    (hist / f"bench_{time.strftime('%Y%m%d_%H%M')}.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in res.items() if k != "jev_triage"}, indent=1, default=float)[:3000])
    jt = res["jev_triage"]
    print("jev triage:", jt["latency_ms"], "throughput", jt["throughput_cases_per_s"], "actions", jt["actions"], "usd/1k", jt["usd_per_1k"])
    print("ablation:", json.dumps({k: v for k, v in res["ablation"].items() if k != "grounding"}, default=float))
    print("grounding:", json.dumps({k: v for k, v in res["ablation"]["grounding"].items() if k != "examples"}, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--conc", type=int, default=12)
    ap.add_argument("--nim", type=int, default=40)
    ap.add_argument("--nim-conc", type=int, default=4)
    ap.add_argument("--nim-model", default="nvidia/nemotron-3.5-lightning-30b-a3b")
    asyncio.run(main(ap.parse_args()))
