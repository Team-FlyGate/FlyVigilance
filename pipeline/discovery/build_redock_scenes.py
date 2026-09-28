"""FlyDiscovery 재도킹 장면: 대시보드의 도킹 애니메이션이 쓰는 3D 좌표를 한 파일로 만든다.

- 재도킹 13종(measurements/redock.json)과 니라파립 케이스 스터디(4R6E)를 담는다
- 수용체는 리간드가 붙은 체인의 Cα 뼈대와, 결정 리간드 중심 9 Å 안의 포켓 중원자만 남긴다
- 결정 리간드(정답)와 DiffDock 포즈 5개(1순위 + 나머지)의 중원자 좌표·원소·결합을 함께 넣는다
- 좌표는 결정 리간드 중심을 원점으로 옮기고 0.01 Å 단위로 반올림한다
- 결과는 fly_discovery/measurements/redock_scenes.json

사용: .venv/bin/python pipeline/discovery/build_redock_scenes.py   (먼저 redock.py 가 PDB 를 data/discovery/pdb 에 받아 둔다)
"""
import json
import pathlib
import sys

from rdkit import Chem

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import redock  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
MEAS = ROOT / "fly_discovery/measurements"
OUT = MEAS / "redock_scenes.json"
POCKET_A = 9.0
# 세포막 단백질(GPCR·수송체). 막단백질에서 재도킹이 약했던 결과를 화면에서 구분하려고 표시한다
MEMBRANE = {"DRD2", "HTR2A", "SLC5A2", "OPRM1"}

NIRAPARIB = {"key": "parp1-4r6e--niraparib", "drug": "niraparib", "target": "PARP1 catalytic domain", "gene": "PARP1",
             "pdb": "4R6E", "ligand": "3JD", "note": "케이스 스터디 데모 약물",
             "pose_sdf": "nim/niraparib_diffdock_pose1.sdf", "eval": ("nim/dd_eval_all.json", "parp1-4r6e-chain-a--niraparib")}


def heavy(mol):
    """중원자만 남긴 좌표·원소·결합."""
    mol = Chem.RemoveHs(mol, sanitize=False)
    conf = mol.GetConformer()
    atoms = [[round(conf.GetAtomPosition(i).x, 2), round(conf.GetAtomPosition(i).y, 2), round(conf.GetAtomPosition(i).z, 2),
              a.GetSymbol()] for i, a in enumerate(mol.GetAtoms())]
    bonds = [[b.GetBeginAtomIdx(), b.GetEndAtomIdx()] for b in mol.GetBonds()]
    return atoms, bonds


def shift(atoms, c):
    return [[round(x - c[0], 2), round(y - c[1], 2), round(z - c[2], 2), *rest] for x, y, z, *rest in atoms]


def scene(t, pose_sdfs, rmsd, poses, success):
    pdb_text = redock.fetch_structure(t["pdb"])
    code = t["ligand"] if len(t["ligand"]) <= 3 else "LIG"
    chain, protein, lig_pdb = redock.split_structure(pdb_text, code)
    ref = Chem.MolFromPDBBlock(lig_pdb, removeHs=False, sanitize=False, proximityBonding=True)
    xtal, xtal_bonds = heavy(ref)
    c = [sum(a[i] for a in xtal) / len(xtal) for i in range(3)]
    preds = [heavy(Chem.MolFromMolBlock(sdf, removeHs=False, sanitize=False)) for sdf in pose_sdfs]
    ca, pocket = [], []
    for ln in protein.splitlines():
        if not ln.startswith("ATOM"):
            continue
        x, y, z = float(ln[30:38]), float(ln[38:46]), float(ln[46:54])
        el = (ln[76:78].strip() or ln[12:16].strip()[0]).capitalize()
        if ln[12:16].strip() == "CA":
            ca.append([round(x - c[0], 2), round(y - c[1], 2), round(z - c[2], 2), int(ln[22:26])])
        if el != "H" and ((x - c[0]) ** 2 + (y - c[1]) ** 2 + (z - c[2]) ** 2) ** 0.5 <= POCKET_A:
            pocket.append([round(x - c[0], 2), round(y - c[1], 2), round(z - c[2], 2), el])
    return {"drug": t["drug"], "target": t["target"], "gene": t["gene"], "pdb": t["pdb"], "chain": chain,
            "note": t.get("note", ""), "membrane": t["gene"] in MEMBRANE,
            "top1_rmsd": rmsd, "success": success, "poses": poses,
            "ca": ca, "pocket": pocket, "xtal": {"atoms": shift(xtal, c), "bonds": xtal_bonds},
            "pose": {"atoms": shift(preds[0][0], c), "bonds": preds[0][1]},
            "alt_poses": [{"atoms": shift(a, c), "bonds": b} for a, b in preds[1:]]}


def main():
    results = json.loads((MEAS / "redock.json").read_text())["results"]
    targets = {t["key"]: t for t in redock.TARGETS}
    scenes = {}
    # 니라파립 케이스 스터디가 먼저 나오게 한다
    ev = json.loads((MEAS / NIRAPARIB["eval"][0]).read_text())[NIRAPARIB["eval"][1]]
    nir_sdfs = [(MEAS / f"nim/niraparib_diffdock_pose{i}.sdf").read_text() for i in range(1, 6) if (MEAS / f"nim/niraparib_diffdock_pose{i}.sdf").exists()]
    scenes[NIRAPARIB["key"]] = scene(NIRAPARIB, nir_sdfs, ev["rmsd_xtal"],
                                     [{"rank": 1, "confidence": ev["top_conf"], "rmsd": ev["rmsd_xtal"]}],
                                     ev["rmsd_xtal"] <= 2.0)
    for key, r in results.items():
        if "top1_rmsd" not in r or key not in targets:
            continue
        resp = json.loads((MEAS / "nim" / f"dd_{key}.json").read_text())
        scenes[key] = scene(targets[key], resp["ligand_positions"], r["top1_rmsd"], r["poses"], r["top1_success"])
        print(key, len(scenes[key]["ca"]), "CA", len(scenes[key]["pocket"]), "pocket", r["top1_rmsd"])
    OUT.write_text(json.dumps({"pocket_radius_A": POCKET_A, "scenes": scenes}, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
