"""실제 케이스 한 건을 전 경로(트리아지 -> 근거 -> Nemotron -> 크리틱)로 돌려 기록한다. 쇼릴과 README 용."""
import asyncio
import gzip
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from _fv import assess, evidence, triage  # noqa: E402


async def main(pid=None, out_path=None):
    cases = json.load(gzip.open(ROOT / "api/_data/cases.json.gz", "rt"))
    sig = evidence._signals()["drugs"]
    if pid:
        case = next(c for c in cases if c["primaryid"] == int(pid))
    else:
        # 사망/중대 케이스 중 주 의심약이 신호 표에 있고 반응이 2개 이상인 것
        case = next(c for c in cases if c["bucket"] in ("serious", "death") and len(c["reactions"]) >= 2
                    and c["drugs"] and c["drugs"][0]["role"] == "PS" and c["drugs"][0]["drug"] in sig)
    t0 = time.perf_counter()
    tri = await triage.triage(case)
    bundle = await evidence.bundle(case, tri["suspect"])
    res = await assess.assess(tri["state"], tri["jev"]["answers"], bundle)
    res["evidence"] = bundle
    out = {"case": case, "triage": tri, "assess": res, "total_ms": round((time.perf_counter() - t0) * 1000, 1),
           "recorded": time.strftime("%Y-%m-%d %H:%M")}
    (pathlib.Path(out_path) if out_path else ROOT / "web/public/data/demo_case.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(case["primaryid"], tri["suspect"], case["reactions"][:3], tri["decision"])
    for r in res["rounds"]:
        print("round", r["round"], r["model"], r["latency_ms"], "issues", [(i["tier"], i["rule"], i["detail"][:80]) for i in r["issues"]])
    print("verdict", res["verdict"], "guard", res.get("guard"))


if __name__ == "__main__":
    # 사용법: demo_case.py [primaryid] [출력 경로]
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None, sys.argv[2] if len(sys.argv) > 2 else None))
