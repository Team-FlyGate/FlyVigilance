"""FlyDiscovery Boltz-2 표적 확대 벤치마크: PARP1 밖에서도 예측 친화도가 맞는지, 실행마다 얼마나 흔들리는지 잽니다.

지금까지 Boltz-2 정확도는 PARP1 39종에서만 쟀습니다(Spearman 0.767). 나머지 표적에서는 모르는 채로
예측값을 화면에 띄우고 있었습니다. 재도킹한 공결정 쌍(약물이 그 표적에 실제로 붙는 것이 확인된 쌍)에
같은 예측을 돌려 ChEMBL 실측과 대조합니다.

- 대상: redock.py 의 TARGETS + 니라파립 4R6E. 각 쌍은 "그 약물의 원래 표적" 이라 실측 친화도가 있을 가능성이 높습니다
- 단백질 서열은 결정 구조에서 그 체인의 CA 잔기를 읽어 만듭니다(도킹 수용체와 같은 체인)
- 실측은 build_selectivity_evidence.py 가 만든 selectivity_evidence.json 의 ChEMBL pChEMBL 중앙값을 그대로 씁니다
- 같은 입력을 RUNS 번 돌려 실행 간 표준편차를 함께 냅니다(스킬 문서에 적힌 실행 간 변동을 수치로 남깁니다)
- MSA 는 넣지 않습니다(단일 서열). 표적마다 MSA-Search 를 또 돌려야 해서 호출이 배로 늘기 때문입니다.
  결과에 msa: "none" 으로 남깁니다

**이 측정으로는 "PARP1 밖에서 얼마나 맞는가" 에 답할 수 없습니다.** 돌려 보고 알았습니다.
기존 PARP1 39종 벤치마크(Spearman 0.767)는 MSA 를 쓴 값이라 조건이 다릅니다. 대조로 탈라조파립@PARP1 을 재 보니
MSA 없이 6.28, MSA 넣고 8.00(실측 9.15)으로 벌어졌고, 4R6E · 7KK3 서열 모두 MSA 없이는 6.2 부근이라
구조가 아니라 MSA 유무가 원인이었습니다. 그래서 아래 14쌍 수치는 참고용이며 39종 벤치마크와 나란히 놓지 않습니다.
제대로 비교하려면 표적마다 MSA-Search 를 먼저 돌려 그 정렬을 넣어야 합니다(측정 당시 NVIDIA 호출 제한에 걸려 하지 못했습니다).

곁가지로 얻은 것: MSA 를 넣으면 같은 입력 3회가 7.46 · 9.06 · 7.47 로 1.6 log 벌어졌습니다.
MSA 없을 때(표준편차 0.03~0.20)보다 훨씬 큽니다. 예측값 한 번을 뽑아 인용하면 안 되는 이유입니다(D3).

결과: fly_discovery/measurements/boltz2_targets.json (msa_control 에 위 대조를 함께 남깁니다)

사용: NVIDIA_API_KEY=... .venv/bin/python pipeline/discovery/benchmark_boltz2_targets.py [--runs 3] [--only niraparib ...]
"""
import argparse
import json
import pathlib
import statistics
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "api"))
import redock  # noqa: E402
from _fv import molgeom as mg  # noqa: E402


OUT = redock.OUT
ENDPOINT = "https://health.api.nvidia.com/v1/biology/mit/boltz2/predict"
NIRAPARIB = {"key": "parp1-4r6e--niraparib", "drug": "niraparib", "target": "PARP1 catalytic domain",
             "gene": "PARP1", "pdb": "4R6E", "ligand": "3JD", "note": ""}
STRONG = 6.0


def chain_sequence(pdb_text: str, chain: str) -> str:
    """도킹 수용체와 같은 체인의 CA 잔기로 서열을 만듭니다."""
    atoms = mg.parse_pdb(pdb_text)
    return "".join(r["aa"] for r in mg.ca_trace([a for a in atoms if a["chain"] == chain and not a["het"]]))


def boltz2(seq: str, smiles: str) -> dict:
    body = json.dumps({"polymers": [{"id": "A", "molecule_type": "protein", "sequence": seq}],
                       "ligands": [{"id": "L", "smiles": smiles, "predict_affinity": True}],
                       "recycling_steps": 3, "sampling_steps": 50, "diffusion_samples": 1,
                       "step_scale": 1.638, "output_format": "mmcif"}).encode()
    key = redock.os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        sys.exit("NVIDIA_API_KEY 가 비어 있다")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}", "NVCF-POLL-SECONDS": "300"}
    for attempt in range(4):
        try:
            req = urllib.request.Request(ENDPOINT, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=900) as r:
                status, raw, reqid = r.status, r.read().decode(), r.headers.get("nvcf-reqid")
            while status == 202:
                time.sleep(5)
                with urllib.request.urlopen(urllib.request.Request(redock.STATUS_URL + reqid, headers=headers), timeout=900) as r:
                    status, raw = r.status, r.read().decode()
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:200]}") from None
            time.sleep(10 * 2 ** attempt)
    raise RuntimeError("unreachable")


def pic50_of(resp: dict):
    aff = (resp.get("affinities") or {}).get("L") or {}
    def first(name):
        v = aff.get(name)
        return v[0] if isinstance(v, list) and v else v
    return first("affinity_pic50"), first("affinity_probability_binary"), (resp.get("iptm_scores") or [None])[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", nargs="*", help="약물 이름으로 거른다")
    args = ap.parse_args()
    ev = json.loads((OUT / "selectivity_evidence.json").read_text())["cells"]
    path = OUT / "boltz2_targets.json"
    out = json.loads(path.read_text()) if path.exists() else {"results": {}}
    targets = [t for t in [*redock.TARGETS, NIRAPARIB] if not args.only or t["drug"] in args.only]
    for t in targets:
        try:
            smiles = redock.ligand_smiles(t["ligand"])
            text = redock.fetch_structure(t["pdb"])
            chain, _, _ = redock.split_structure(text, t["ligand"] if len(t["ligand"]) <= 3 else "LIG")
            seq = chain_sequence(text, chain)
            started = time.time()
            reps = []
            for _ in range(args.runs):
                p, prob, iptm = pic50_of(boltz2(seq, smiles))
                reps.append({"pic50": round(p, 3) if p is not None else None,
                             "probability_binary": round(prob, 3) if prob is not None else None,
                             "iptm": round(iptm, 3) if iptm is not None else None})
            vals = [r["pic50"] for r in reps if r["pic50"] is not None]
            cell = ev.get(f"{t['gene']}|{t['drug']}")
            mean = round(statistics.mean(vals), 3) if vals else None
            res = {**{k: t[k] for k in ("key", "drug", "gene", "pdb")}, "chain": chain, "seq_len": len(seq),
                   "msa": "none", "runs": args.runs, "seconds": round(time.time() - started, 1),
                   "predictions": reps, "pic50_mean": mean,
                   "pic50_sd": round(statistics.pstdev(vals), 3) if len(vals) > 1 else None,
                   "pic50_range": [min(vals), max(vals)] if vals else None,
                   "chembl": {"median": cell["median"], "n": cell["n"], "types": cell["types"]} if cell else None,
                   "error_log": round(mean - cell["median"], 3) if (mean is not None and cell) else None}
        except Exception as e:  # noqa: BLE001  실패도 사유와 함께 남긴다
            res = {"key": t["key"], "drug": t["drug"], "gene": t["gene"], "pdb": t["pdb"], "error": str(e)[:300]}
        out["results"][t["key"]] = res
        print(t["key"], res.get("pic50_mean"), "±", res.get("pic50_sd"),
              "실측", (res.get("chembl") or {}).get("median"), "오차", res.get("error_log"), res.get("error", ""), flush=True)
    ok = [r for r in out["results"].values() if r.get("error_log") is not None]
    if ok:
        errs = [abs(r["error_log"]) for r in ok]
        sds = [r["pic50_sd"] for r in ok if r.get("pic50_sd") is not None]
        out["summary"] = {"n_pairs": len(ok), "mae": round(statistics.mean(errs), 3),
                          "within_1_log": sum(1 for e in errs if e <= 1.0),
                          "sd_median": round(statistics.median(sds), 3) if sds else None,
                          "sd_max": round(max(sds), 3) if sds else None}
        print("요약:", out["summary"])
    out.update({"endpoint": ENDPOINT, "runs": args.runs, "msa": "none (single sequence)",
                "strong_pchembl": STRONG, "updated": time.strftime("%Y-%m-%d %H:%M %Z")})
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
