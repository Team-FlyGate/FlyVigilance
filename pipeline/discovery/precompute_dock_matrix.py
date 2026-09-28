"""FlyDiscovery 직접 도킹 미리 계산: 표적 14 × 약물 20 조합을 DiffDock NIM 으로 미리 도킹해 둔다.

대시보드는 이 파일을 먼저 찾고, 없는 조합만 서버(/api/dock)를 부른다. NVIDIA 키가 없는 배포에서도
직접 도킹 화면이 저장된 결과로 동작하게 하려는 것이다. 이미 받아 둔 재도킹 조합(표적의 원래 리간드)은 건너뛴다.
실패한 조합은 기록만 하고 다시 실행하면 이어서 채운다.

사용: NVIDIA_API_KEY=... .venv/bin/python pipeline/discovery/precompute_dock_matrix.py
결과: fly_discovery/measurements/dock_matrix.json
"""
import asyncio
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from _fv import dock  # noqa: E402

MEAS = ROOT / "fly_discovery/measurements"
OUT = MEAS / "dock_matrix.json"


async def main():
    lib = json.loads((MEAS / "dock_library.json").read_text())
    out = json.loads(OUT.read_text()) if OUT.exists() else {"results": {}, "failed": {}}
    combos = [(t["key"], l) for t in lib["targets"] for l in lib["ligands"] if t["native"] != l["name"]]
    todo = [(k, l) for k, l in combos if f"{k}|{l['name']}" not in out["results"]]
    print(f"{len(combos)} combos · {len(todo)} to run", flush=True)
    for i, (key, lig) in enumerate(todo, 1):
        name = f"{key}|{lig['name']}"
        for attempt in range(3):
            try:
                r = await dock.dock(key, lig["smiles"])
                out["results"][name] = {"poses": r["poses"], "confidence": r["confidence"], "seconds": r["seconds"]}
                out["failed"].pop(name, None)
                break
            except Exception as e:  # noqa: BLE001  429 · 5xx 는 잠시 쉬고 다시
                out["failed"][name] = str(e)[:200]
                await asyncio.sleep(8 * (attempt + 1))
        if i % 10 == 0 or i == len(todo):
            out["updated"] = time.strftime("%Y-%m-%d %H:%M %Z")
            OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
            print(f"{i}/{len(todo)} · ok {len(out['results'])} · failed {len(out['failed'])}", flush=True)
        await asyncio.sleep(1.5)  # NIM 분당 40회 안쪽으로


if __name__ == "__main__":
    asyncio.run(main())
