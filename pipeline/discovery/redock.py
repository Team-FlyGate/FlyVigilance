"""FlyDiscovery 재도킹: 공결정 구조의 리간드를 DiffDock NIM 으로 다시 도킹해 결정 포즈와의 RMSD 로 채점한다.

- 대상은 FlyVigilance 데모 케이스(FAERS 2026Q2 440건)에 주의심약물로 나오는 유명 소분자다
- 수용체는 리간드가 붙은 체인의 ATOM 만 쓰고, 리간드는 RCSB 화학 성분 사전의 SMILES 로 넣는다
- 채점은 대칭을 고려한 중원자 RMSD(정렬 없음). 2 Å 이하를 성공으로 보는 것이 재도킹의 전통 기준이다
- 원본 응답은 fly_discovery/measurements/nim/dd_<키>.json, 요약은 measurements/redock.json 에 남긴다

사용: NVIDIA_API_KEY=... .venv/bin/python pipeline/discovery/redock.py [--only dexamethasone ...]
"""
import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

from rdkit import Chem, RDLogger


RDLogger.DisableLog("rdApp.*")

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "fly_discovery/measurements"
CACHE = ROOT / "data/discovery/pdb"
DIFFDOCK_URL = "https://health.api.nvidia.com/v1/biology/mit/diffdock"
STATUS_URL = "https://health.api.nvidia.com/v1/status/"

# 약물, 타깃, 공결정 구조. PDB 와 리간드 코드는 RCSB 에서 확인했다 (2026-09-28).
TARGETS = [
    {"key": "gr-1m2z--dexamethasone", "drug": "dexamethasone", "target": "Glucocorticoid receptor LBD",
     "gene": "NR3C1", "pdb": "1M2Z", "ligand": "DEX", "note": ""},
    {"key": "d2-6cm4--risperidone", "drug": "risperidone", "target": "Dopamine D2 receptor",
     "gene": "DRD2", "pdb": "6CM4", "ligand": "8NU", "note": ""},
    {"key": "jak2-6vgl--ruxolitinib", "drug": "ruxolitinib", "target": "JAK2 JH1 kinase",
     "gene": "JAK2", "pdb": "6VGL", "ligand": "RXT", "note": ""},
    {"key": "crbn-4ci2--lenalidomide", "drug": "lenalidomide", "target": "Cereblon (DDB1-CRBN)",
     "gene": "CRBN", "pdb": "4CI2", "ligand": "LVY", "note": ""},
    {"key": "mpro-7si9--nirmatrelvir", "drug": "nirmatrelvir", "target": "SARS-CoV-2 main protease",
     "gene": "Mpro (nsp5)", "pdb": "7SI9", "ligand": "4WI",
     "note": "공유결합 억제제. DiffDock 은 비공유 결합만 모사하므로 참고용이다"},
]


def fetch(url, cache=None):
    if cache is not None and cache.exists():
        return cache.read_text()
    text = urllib.request.urlopen(url, timeout=60).read().decode()
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text)
    return text


def ligand_smiles(comp_id):
    d = json.loads(fetch(f"https://data.rcsb.org/rest/v1/core/chemcomp/{comp_id}"))
    desc = d.get("rcsb_chem_comp_descriptor", {})
    return desc.get("SMILES_stereo") or desc.get("SMILES")


def split_structure(pdb_text, comp_id):
    """리간드 첫 사본의 HETATM 과 그 체인의 ATOM 을 나눈다."""
    het = [ln for ln in pdb_text.splitlines() if ln.startswith("HETATM") and ln[17:20].strip() == comp_id]
    if not het:
        raise ValueError(f"{comp_id} 가 구조에 없다")
    chain, resseq = het[0][21], het[0][22:26]
    lig = [ln for ln in het if ln[21] == chain and ln[22:26] == resseq and ln[16] in " A"]
    protein = [ln for ln in pdb_text.splitlines() if ln.startswith("ATOM") and ln[21] == chain and ln[16] in " A"]
    return chain, "\n".join(protein) + "\nEND\n", "\n".join(lig) + "\nEND\n"


def skeleton(mol):
    """결합 차수·방향족성·전하를 지운 중원자 골격. 결정 구조와 도킹 포즈를 원소와 연결만으로 대응시킨다."""
    rw = Chem.RWMol(mol)
    for a in list(rw.GetAtoms())[::-1]:
        if a.GetAtomicNum() == 1:
            rw.RemoveAtom(a.GetIdx())
    for a in rw.GetAtoms():
        a.SetIsAromatic(False)
        a.SetFormalCharge(0)
        a.SetNoImplicit(True)
    for b in rw.GetBonds():
        b.SetBondType(Chem.BondType.SINGLE)
        b.SetIsAromatic(False)
    m = rw.GetMol()
    m.UpdatePropertyCache(strict=False)
    Chem.FastFindRings(m)
    return m


def crystal_ligand(lig_pdb, smiles):
    """결정 리간드. 결합은 PDB 거리 기반 추정이라 채점에는 골격만 쓴다."""
    return skeleton(Chem.MolFromPDBBlock(lig_pdb, removeHs=False, sanitize=False, proximityBonding=True))


def pose_rmsd(pose_sdf, ref):
    """대칭 대응을 모두 따져 가장 작은 중원자 RMSD. 정렬하지 않는다(재도킹 표준)."""
    pose = Chem.MolFromMolBlock(pose_sdf, removeHs=False, sanitize=False)
    if pose is None:
        return None
    pose = skeleton(pose)
    matches = ref.GetSubstructMatches(pose, uniquify=False, useChirality=False, maxMatches=5000)
    if not matches:
        return None
    pc, rc = pose.GetConformer(), ref.GetConformer()
    best = min(sum((pc.GetAtomPosition(i) - rc.GetAtomPosition(j)).LengthSq() for i, j in enumerate(m)) / len(m)
               for m in matches)
    return round(best ** 0.5, 3)


def diffdock(protein, smiles, num_poses=5):
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        sys.exit("NVIDIA_API_KEY 가 비어 있다")
    body = json.dumps({"protein": protein, "ligand": smiles, "ligand_file_type": "txt", "num_poses": num_poses,
                       "time_divisions": 20, "steps": 18, "save_trajectory": False}).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}", "NVCF-POLL-SECONDS": "300"}
    for attempt in range(5):
        try:
            req = urllib.request.Request(DIFFDOCK_URL, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=900) as r:
                status, raw, reqid = r.status, r.read().decode(), r.headers.get("nvcf-reqid")
            while status == 202:
                time.sleep(5)
                with urllib.request.urlopen(urllib.request.Request(STATUS_URL + reqid, headers=headers), timeout=900) as r:
                    status, raw = r.status, r.read().decode()
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:300]}") from None
            time.sleep(10 * 2 ** attempt)


def run(t):
    pdb_text = fetch(f"https://files.rcsb.org/download/{t['pdb']}.pdb", CACHE / f"{t['pdb']}.pdb")
    smiles = ligand_smiles(t["ligand"])
    chain, protein, lig_pdb = split_structure(pdb_text, t["ligand"])
    ref = crystal_ligand(lig_pdb, smiles)
    started = time.time()
    resp = diffdock(protein, smiles)
    seconds = round(time.time() - started, 1)
    (OUT / "nim" / f"dd_{t['key']}.json").write_text(json.dumps(resp))
    poses = resp.get("ligand_positions") or []
    conf = resp.get("position_confidence") or []
    rmsd = [pose_rmsd(p, ref) for p in poses]
    ok = [r for r in rmsd if r is not None]
    return {**{k: t[k] for k in ("drug", "target", "gene", "pdb", "ligand", "note")},
            "chain": chain, "smiles": smiles, "heavy_atoms": ref.GetNumAtoms(), "seconds": seconds,
            "poses": [{"rank": i + 1, "confidence": round(c, 3) if isinstance(c, (int, float)) else None,
                       "rmsd": r} for i, (c, r) in enumerate(zip(conf, rmsd))],
            "top1_rmsd": rmsd[0] if rmsd else None,
            "best_rmsd": min(ok) if ok else None,
            "top1_success": bool(rmsd and rmsd[0] is not None and rmsd[0] <= 2.0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="약물 이름으로 거른다")
    args = ap.parse_args()
    summary_path = OUT / "redock.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {"results": {}}
    for t in TARGETS:
        if args.only and t["drug"] not in args.only:
            continue
        try:
            res = run(t)
        except Exception as e:  # noqa: BLE001  실패도 기록한다. 0 이 아니라 사유를 남긴다
            res = {"drug": t["drug"], "pdb": t["pdb"], "error": str(e)[:300]}
        summary["results"][t["key"]] = res
        print(t["key"], res.get("top1_rmsd"), res.get("best_rmsd"), res.get("error", ""))
    summary.update({"endpoint": DIFFDOCK_URL, "criterion": "top-1 heavy-atom RMSD <= 2.0 A (symmetry-aware, no alignment)",
                    "updated": time.strftime("%Y-%m-%d %H:%M %Z")})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
