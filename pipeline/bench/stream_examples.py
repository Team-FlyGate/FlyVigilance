"""관제 센터 스트림용 사례를 만듭니다: 데모 440건 전부를 현재 트리아지로 처리하고(결과 코드 가림), 정답과 함께 저장합니다.

층(사망 · 중대 · 비중대 · 소아)을 번갈아 섞어 재생 순서를 정하므로 화면에 한 종류만 몰려 나오지 않습니다.
정답은 FAERS 결과 코드(있으면 중대)이며, 판단 입력에서는 가립니다(bench.json ablation_blind 와 같은 조건).

사용: FV_CACHE_DIR=data/cache/api .venv/bin/python pipeline/bench/stream_examples.py [--conc 12]
산출물: web/public/data/stream.json
"""
import argparse
import asyncio
import gzip
import json
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from _fv import triage  # noqa: E402

BUCKETS = ["death", "serious", "nonserious", "pediatric"]
REVIEWED = {"expedite", "signal_review", "follow_up"}


def interleave(cases: list[dict]) -> list[dict]:
    """층마다 원래 순서를 지키면서 한 건씩 번갈아 꺼냅니다."""
    by = {b: [c for c in cases if c["bucket"] == b] for b in BUCKETS}
    out, k = [], 0
    while any(by.values()):
        b = BUCKETS[k % len(BUCKETS)]
        if by[b]:
            out.append(by[b].pop(0))
        k += 1
    return out


async def main(args):
    cases = interleave(json.load(gzip.open(ROOT / "api/_data/cases.json.gz", "rt")))
    sem = asyncio.Semaphore(args.conc)
    async with httpx.AsyncClient(timeout=60) as cl:
        async def one(c):
            async with sem:
                return await triage.triage(c, client=cl, include_outcome=False)
        res = await asyncio.gather(*[one(c) for c in cases])
    rows = []
    for c, r in zip(cases, res):
        if "error" in r:
            continue
        ps = next((d["drug"] for d in c["drugs"] if d.get("role") == "PS"), c["drugs"][0]["drug"] if c["drugs"] else "")
        d = r["decision"]
        rows.append({"primaryid": c["primaryid"], "bucket": c["bucket"], "outcomes": c["outcomes"], "serious_truth": bool(c["outcomes"]),
                     "action": d["action"], "reasons": d.get("reasons", [])[:2], "serious_p": round(r["jev"]["answers"]["serious"]["noul"], 2),
                     "latency_ms": round(r.get("latency_ms") or r["jev"].get("latency_ms") or 0), "suspect": ps,
                     "reactions": c["reactions"][:4]})
    s = [x for x in rows if x["serious_truth"]]
    summary = {"n": len(rows), "serious": len(s), "serious_reviewed": sum(x["action"] in REVIEWED for x in s),
               "actions": {a: sum(x["action"] == a for x in rows) for a in ["expedite", "signal_review", "follow_up", "monitor", "close"]}}
    out = {"source": "api/_data/cases.json.gz (FAERS 2026Q2, 440 cases)", "outcome_codes_in_input": False, "summary": summary, "rows": rows}
    (ROOT / "web/public/data/stream.json").write_text(json.dumps(out, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--conc", type=int, default=12)
    asyncio.run(main(ap.parse_args()))
