"""FlyDiscovery 도킹 검증 관문: 도킹 결과를 믿어도 되는지 구조 품질 · 반복 수렴 · 결정 포즈 대조로 판정한다.

- 표적: 재도킹한 결정 구조 14개(redock.py TARGETS 13개 + 니라파립 4R6E)
- 구조 품질: RCSB 에서 실험 방법, 해상도, 생물종, 결합 자리 근처 잔기 번호 끊김을 읽어 도킹 가능 / 주의로 나눈다
- 반복 수렴: 같은 입력으로 DiffDock NIM 을 RUNS 번 부르고(매번 확산 샘플링이 달라진다), 1순위 포즈끼리의 RMSD 로 수렴을 본다.
  결정 구조가 없는 새 표적에서도 계산할 수 있는 신호다
- 결정 포즈 대조: 1순위 포즈와 결정 리간드의 중원자 RMSD(대칭 고려, 정렬 없음). 2 Å 이하 = 성공
- 등급: HIGH / MEDIUM / LOW. 규칙은 GRADE_RULES 에 적고 화면에도 그대로 보여 준다
- 원본 응답은 저장하지 않고(용량), 반복마다 포즈별 신뢰도 · RMSD 와 1순위 포즈 좌표만 남긴다 → measurements/validation.json

사용: NVIDIA_API_KEY=... .venv/bin/python pipeline/discovery/validate_docking.py [--runs 5] [--only niraparib ...]
"""
import argparse
import json
import pathlib
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from rdkit import Chem

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from redock import (OUT, TARGETS, crystal_ligand, diffdock, fetch, fetch_structure, ligand_smiles,  # noqa: E402
                    pose_rmsd, skeleton, split_structure)


NIRAPARIB = {"key": "parp1-4r6e--niraparib", "drug": "niraparib", "target": "PARP1 catalytic domain",
             "gene": "PARP1", "pdb": "4R6E", "ligand": "3JD", "note": "FlyGate 데모 약물"}
# 표적의 원래 생물종. 사람 약의 표적이 사람이 아니면 주의로 본다(Mpro 는 바이러스 표적이 맞다)
HOST = {"parp1-4r6e--niraparib": "Homo sapiens", "mpro-7si9--nirmatrelvir": "Severe acute respiratory syndrome coronavirus 2"}
SUCCESS_A = 2.0
CONVERGED_A = 3.0  # 같은 자리에 모였는지(정확히 같은 자세인지가 아니라)
GRADE_RULES = [
    ["구조", "X-ray 2.5 Å 이하 또는 cryo-EM 3.0 Å 이하, 표적 생물종 일치, 결합 자리 8 Å 안 잔기 끊김 없음 → 도킹 가능. 하나라도 어긋나면 주의"],
    ["수렴", f"반복 1순위 포즈끼리의 RMSD 중앙값 ≤ {CONVERGED_A} Å → 같은 자리로 수렴 (결정 구조 없이도 알 수 있음)"],
    ["결정 대조", f"반복마다 1순위 포즈가 결정 리간드와 {SUCCESS_A} Å 이하인 비율"],
    ["HIGH", "결정 대조 4/5 이상 + 수렴 + 구조 도킹 가능"],
    ["MEDIUM", "결정 대조 2/5 이상 (구조 주의 또는 수렴 실패가 섞임)"],
    ["LOW", "결정 대조 1/5 이하. 수렴했더라도 틀린 자리로 모인 것"],
]


def structure_quality(t, chain, protein_pdb, lig_pdb):
    e = json.loads(fetch(f"https://data.rcsb.org/rest/v1/core/entry/{t['pdb']}"))
    method = e["exptl"][0]["method"]
    res = (e.get("rcsb_entry_info", {}).get("resolution_combined") or [None])[0]
    # 리간드가 붙은 체인의 생물종
    organism = None
    for eid in e.get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids", []):
        p = json.loads(fetch(f"https://data.rcsb.org/rest/v1/core/polymer_entity/{t['pdb']}/{eid}"))
        chains = p.get("rcsb_polymer_entity_container_identifiers", {}).get("auth_asym_ids", [])
        if chain in chains:
            src = (p.get("rcsb_entity_source_organism") or [{}])[0]
            organism = src.get("ncbi_scientific_name") or src.get("scientific_name")
            break
    # 결합 자리 8 Å 안의 잔기 번호가 연속인지(구조에 안 보이는 잔기가 자리에 걸려 있는지)
    lig = [(float(ln[30:38]), float(ln[38:46]), float(ln[46:54])) for ln in lig_pdb.splitlines() if ln.startswith("HETATM")]
    near = set()
    for ln in protein_pdb.splitlines():
        if not ln.startswith("ATOM"):
            continue
        x, y, z = float(ln[30:38]), float(ln[38:46]), float(ln[46:54])
        if any((x - a) ** 2 + (y - b) ** 2 + (z - c) ** 2 <= 64 for a, b, c in lig):
            near.add(int(ln[22:26]))
    seen = {int(ln[22:26]) for ln in protein_pdb.splitlines() if ln.startswith("ATOM")}
    gaps = sorted({r + d for r in near for d in (-1, 1) if r + d not in seen and min(seen) < r + d < max(seen)})
    host = HOST.get(t["key"], "Homo sapiens")
    em = "ELECTRON" in method
    reasons = []
    if res is None or res > (3.0 if em else 2.5):
        reasons.append(f"해상도 {res} Å" if res else "해상도 없음")
    if organism and organism != host:
        reasons.append(f"생물종 {organism}")
    if gaps:
        reasons.append(f"결합 자리 옆 잔기 {len(gaps)}개가 구조에 없음")
    return {"method": "cryo-EM" if em else "X-ray" if "X-RAY" in method else method, "resolution": res,
            "organism": organism, "pocket_residues": len(near), "pocket_gaps": gaps,
            "verdict": "주의" if reasons else "도킹 가능", "reasons": reasons}


def judge(hits, pair_med, verdict):
    converged = pair_med is not None and pair_med <= CONVERGED_A
    if hits >= 4 and converged and verdict == "도킹 가능":
        return converged, "HIGH"
    return converged, "MEDIUM" if hits >= 2 else "LOW"


def pose_mol(sdf):
    m = Chem.MolFromMolBlock(sdf, removeHs=False, sanitize=False)
    return skeleton(m) if m is not None else None


def one_run(protein, smiles, ref):
    resp = diffdock(protein, smiles)
    poses = resp.get("ligand_positions") or []
    conf = resp.get("position_confidence") or []
    rmsd = [pose_rmsd(p, ref) for p in poses]
    return {"poses": [{"confidence": round(c, 3) if isinstance(c, (int, float)) else None, "rmsd": r}
                      for c, r in zip(conf, rmsd)], "top1_sdf": poses[0] if poses else None}


def validate(t, runs):
    pdb_text = fetch_structure(t["pdb"])
    smiles = ligand_smiles(t["ligand"])
    chain, protein, lig_pdb = split_structure(pdb_text, t["ligand"] if len(t["ligand"]) <= 3 else "LIG")
    ref = crystal_ligand(lig_pdb, smiles)
    sq = structure_quality(t, chain, protein, lig_pdb)
    started = time.time()
    with ThreadPoolExecutor(max_workers=runs) as ex:
        reps = list(ex.map(lambda _: one_run(protein, smiles, ref), range(runs)))
    top1 = [r["poses"][0]["rmsd"] if r["poses"] else None for r in reps]
    conf1 = [r["poses"][0]["confidence"] if r["poses"] else None for r in reps]
    # 반복끼리 1순위 포즈 RMSD (결정 구조 없이 계산할 수 있는 수렴 신호)
    mols = [pose_mol(r["top1_sdf"]) if r["top1_sdf"] else None for r in reps]
    pair = []
    for i in range(runs):
        for j in range(i + 1, runs):
            if mols[i] is not None and reps[j]["top1_sdf"]:
                v = pose_rmsd(reps[j]["top1_sdf"], mols[i])
                if v is not None:
                    pair.append(v)
    hits = sum(1 for v in top1 if v is not None and v <= SUCCESS_A)
    pair_med = round(statistics.median(pair), 2) if pair else None
    converged, grade = judge(hits, pair_med, sq["verdict"])
    ok = [c for c in conf1 if c is not None]
    return {**{k: t[k] for k in ("key", "drug", "target", "gene", "pdb", "ligand")}, "chain": chain,
            "structure": sq, "runs": runs, "seconds": round(time.time() - started, 1),
            "top1_rmsd": top1, "top1_confidence": conf1,
            "confidence_mean": round(statistics.mean(ok), 3) if ok else None,
            "confidence_sd": round(statistics.pstdev(ok), 3) if len(ok) > 1 else None,
            "pairwise_top1_rmsd": pair, "pairwise_median": pair_med, "converged": converged,
            "crystal_hits": hits, "grade": grade,
            "runs_detail": [r["poses"] for r in reps]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--only", nargs="*", help="약물 이름으로 거른다")
    ap.add_argument("--regrade", action="store_true", help="NIM 을 다시 부르지 않고 저장된 값으로 등급만 다시 매긴다")
    args = ap.parse_args()
    path = OUT / "validation.json"
    out = json.loads(path.read_text()) if path.exists() else {"results": {}}
    if args.regrade:
        for r in out["results"].values():
            if "error" not in r:
                r["converged"], r["grade"] = judge(r["crystal_hits"], r["pairwise_median"], r["structure"]["verdict"])
        out.update({"converged_A": CONVERGED_A, "rules": GRADE_RULES})
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
        return
    targets = [t for t in [*TARGETS, NIRAPARIB] if not args.only or t["drug"] in args.only]
    for t in targets:
        try:
            res = validate(t, args.runs)
        except Exception as e:  # noqa: BLE001  실패도 사유와 함께 남긴다
            res = {"key": t["key"], "drug": t["drug"], "pdb": t["pdb"], "error": str(e)[:300]}
        out["results"][t["key"]] = res
        print(t["key"], res.get("grade"), res.get("crystal_hits"), res.get("pairwise_median"),
              res.get("structure", {}).get("verdict"), res.get("error", ""), flush=True)
    out.update({"endpoint": "https://health.api.nvidia.com/v1/biology/mit/diffdock", "runs": args.runs,
                "success_A": SUCCESS_A, "converged_A": CONVERGED_A, "rules": GRADE_RULES,
                "updated": time.strftime("%Y-%m-%d %H:%M %Z")})
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
