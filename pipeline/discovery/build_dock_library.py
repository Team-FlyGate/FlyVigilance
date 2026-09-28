"""FlyDiscovery 직접 도킹: 대시보드에서 고를 수 있는 표적과 약물, 서버가 DiffDock NIM 에 보낼 수용체 좌표를 만든다.

- 표적: 재도킹한 결정 구조 14개(니라파립 4R6E 포함). 리간드가 붙은 체인의 ATOM 과 결정 리간드 중심을 담는다
  → api/_data/dock_receptors.json.gz (서버 전용)
- 약물: 결정 리간드 14개(RCSB SMILES) + 약물 패널 소분자(ChEMBL canonical SMILES)
  → fly_discovery/measurements/dock_library.json (화면이 목록으로 씀)
- 표적 × 약물 중 재도킹으로 이미 받아 둔 조합은 화면이 redock_scenes.json 을 그대로 쓰고, 나머지만 서버가 실시간으로 부른다

사용: .venv/bin/python pipeline/discovery/build_dock_library.py
"""
import gzip
import json
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_redock_scenes as scenes_mod  # noqa: E402
import redock  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
MEAS = ROOT / "fly_discovery/measurements"


def chembl_smiles(chembl_id):
    url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json"
    d = json.load(urllib.request.urlopen(url, timeout=60))
    parent = (d.get("molecule_hierarchy") or {}).get("parent_chembl_id")
    if parent and parent != chembl_id:  # 염이면 모 분자 구조를 씁니다
        d = json.load(urllib.request.urlopen(f"https://www.ebi.ac.uk/chembl/api/data/molecule/{parent}.json", timeout=60))
    return (d.get("molecule_structures") or {}).get("canonical_smiles")


def main():
    targets = {t["key"]: t for t in redock.TARGETS}
    targets[scenes_mod.NIRAPARIB["key"]] = scenes_mod.NIRAPARIB
    scene_keys = list(json.loads((MEAS / "redock_scenes.json").read_text())["scenes"])
    receptors, tlist, ligands = {}, [], {}
    for key in scene_keys:
        t = targets[key]
        text = redock.fetch_structure(t["pdb"])
        code = t["ligand"] if len(t["ligand"]) <= 3 else "LIG"
        chain, protein, lig_pdb = redock.split_structure(text, code)
        xyz = [(float(ln[30:38]), float(ln[38:46]), float(ln[46:54])) for ln in lig_pdb.splitlines() if ln.startswith("HETATM")]
        center = [round(sum(p[i] for p in xyz) / len(xyz), 3) for i in range(3)]
        receptors[key] = {"pdb": t["pdb"], "chain": chain, "center": center, "protein": protein}
        tlist.append({"key": key, "gene": t["gene"], "target": t["target"], "pdb": t["pdb"], "native": t["drug"]})
        smiles = redock.ligand_smiles(t["ligand"])
        ligands.setdefault(t["drug"].lower(), {"name": t["drug"].lower(), "smiles": smiles, "source": f"RCSB {t['ligand']}", "native_target": key})
    panel = json.loads((MEAS / "drug_panel.json").read_text())["rows"]
    for r in panel:
        if r.get("molecule_type") != "Small molecule" or not r.get("chembl_id"):
            continue
        name = r["drug"].split("\\")[0].strip().lower()
        if name in ligands:
            continue
        smi = chembl_smiles(r["chembl_id"])
        if smi and len(smi) <= 300:
            ligands[name] = {"name": name, "smiles": smi, "source": f"ChEMBL {r['chembl_id']}", "native_target": None}
        print(name, bool(smi))
    out = ROOT / "api/_data/dock_receptors.json.gz"
    with gzip.open(out, "wt") as f:
        json.dump(receptors, f, separators=(",", ":"))
    (MEAS / "dock_library.json").write_text(json.dumps({"targets": tlist, "ligands": sorted(ligands.values(), key=lambda x: x["name"])},
                                                       ensure_ascii=False, indent=1) + "\n")
    print(out, out.stat().st_size // 1024, "KB ·", len(tlist), "targets ·", len(ligands), "ligands")


if __name__ == "__main__":
    main()
