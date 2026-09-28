"""FlyDiscovery 대표 장면: OpenFold3 가 예측한 PARP1 + 니라파립 복합체에 결정 구조(4R6E)와 DiffDock 포즈를 겹친다.

- 예측: fly_discovery/measurements/nim/of3_parp1_niraparib.pdb (OpenFold3 NIM 응답, B-factor = 잔기별 pLDDT)
- 정답: RCSB 4R6E chain A 와 결정 리간드 3JD(니라파립)
- DiffDock: nim/niraparib_diffdock_pose{1..5}.sdf (4R6E 좌표계)
- 4R6E 를 OpenFold3 좌표계로 옮긴다: 잔기 번호(4R6E = 예측 + 660)와 잔기 이름이 같은 Cα 로 Kabsch 정렬
- 정렬 뒤 Cα RMSD 가 저장된 값(measurements.json 의 ca_rmsd_vs_4R6E)과 맞는지 확인하고 파일에 남긴다
- 좌표는 OpenFold3 리간드 중심을 원점으로 옮긴다. 결과는 fly_discovery/measurements/hero_scene.json

사용: .venv/bin/python pipeline/discovery/build_hero_scene.py
"""
import json
import pathlib
import sys

import numpy as np
from rdkit import Chem

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import redock  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
MEAS = ROOT / "fly_discovery/measurements"
OUT = MEAS / "hero_scene.json"
OFFSET = 660  # 4R6E 잔기 번호 = OpenFold3 잔기 번호 + 660 (둘 다 MET 에서 시작)


def ca_table(pdb_text, chain):
    out = {}
    for ln in pdb_text.splitlines():
        if ln.startswith("ATOM") and ln[12:16].strip() == "CA" and ln[21] == chain and ln[16] in " A":
            out[int(ln[22:26])] = (ln[17:20], np.array([float(ln[30:38]), float(ln[38:46]), float(ln[46:54])]), float(ln[60:66]))
    return out


def kabsch(P, Q):
    """P 를 Q 에 겹치는 회전 R 과 이동 t (Q ≈ P @ R.T + t)."""
    pc, qc = P.mean(0), Q.mean(0)
    H = (P - pc).T @ (Q - qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    return R, qc - pc @ R.T


def mol_atoms(mol):
    mol = Chem.RemoveHs(mol, sanitize=False)
    conf = mol.GetConformer()
    xyz = np.array([[conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z] for i in range(mol.GetNumAtoms())])
    return xyz, [a.GetSymbol() for a in mol.GetAtoms()], [[b.GetBeginAtomIdx(), b.GetEndAtomIdx()] for b in mol.GetBonds()]


def pack(xyz, el, bonds, c):
    return {"atoms": [[*map(lambda v: round(float(v), 2), p - c), e] for p, e in zip(xyz, el)], "bonds": bonds}


def main():
    of3_text = (MEAS / "nim/of3_parp1_niraparib.pdb").read_text()
    of3 = ca_table(of3_text, "A")
    x_text = redock.fetch_structure("4R6E")
    xtal = ca_table(x_text, "A")
    pairs = [(k, k + OFFSET) for k in of3 if k + OFFSET in xtal and of3[k][0] == xtal[k + OFFSET][0]]
    P = np.array([xtal[b][1] for _, b in pairs])  # 결정 구조
    Q = np.array([of3[a][1] for a, _ in pairs])  # 예측
    R, t = kabsch(P, Q)
    rmsd = float(np.sqrt(((P @ R.T + t - Q) ** 2).sum(1).mean()))
    stored = json.loads((MEAS / "measurements.json").read_text())["openfold3_msa"]["ca_rmsd_vs_4R6E"]
    print(f"matched CA {len(pairs)} / pred {len(of3)} · Kabsch CA RMSD {rmsd:.2f} Å (stored {stored})")

    # 예측 리간드(OpenFold3 가 함께 접은 니라파립, chain B)
    lig_lines = "\n".join(ln for ln in of3_text.splitlines() if ln.startswith("HETATM") and ln[21] == "B") + "\nEND\n"
    p_xyz, p_el, p_b = mol_atoms(Chem.MolFromPDBBlock(lig_lines, removeHs=False, sanitize=False, proximityBonding=True))
    c = p_xyz.mean(0)
    # 결정 리간드와 DiffDock 포즈(둘 다 4R6E 좌표계) → 예측 좌표계
    _, _, lig_pdb = redock.split_structure(x_text, "3JD")
    x_xyz, x_el, x_b = mol_atoms(Chem.MolFromPDBBlock(lig_pdb, removeHs=False, sanitize=False, proximityBonding=True))
    x_xyz = x_xyz @ R.T + t
    poses = []
    for i in range(1, 6):
        f = MEAS / f"nim/niraparib_diffdock_pose{i}.sdf"
        if f.exists():
            d_xyz, d_el, d_b = mol_atoms(Chem.MolFromMolBlock(f.read_text(), removeHs=False, sanitize=False))
            poses.append(pack(d_xyz @ R.T + t, d_el, d_b, c))
    lig_rmsd_centroid = float(np.linalg.norm(p_xyz.mean(0) - x_xyz.mean(0)))
    ev = json.loads((MEAS / "nim/dd_eval_all.json").read_text())["parp1-4r6e-chain-a--niraparib"]
    evals = json.loads((MEAS / "nim/diffdock_eval.json").read_text())["poses"]  # [rank, conf, rmsd, pocket_dist]
    ms = json.loads((MEAS / "measurements.json").read_text())

    ribbon = [[*map(lambda v: round(float(v), 2), of3[k][1] - c), k, round(of3[k][2], 1)] for k in sorted(of3)]
    crystal = [[*map(lambda v: round(float(v), 2), xtal[b][1] @ R.T + t - c), b] for b in sorted(xtal)]
    OUT.write_text(json.dumps({
        "source": {"prediction": "OpenFold3 NIM (MSA-Search input) · of3_parp1_niraparib.pdb", "crystal": "RCSB 4R6E chain A · ligand 3JD",
                   "docking": "DiffDock NIM · niraparib_diffdock_pose1-5.sdf"},
        "metrics": {"ca_rmsd_kabsch": round(rmsd, 2), "ca_rmsd_stored": stored, "matched_ca": len(pairs),
                    "plddt": ms["openfold3_msa"]["plddt"], "ptm": ms["openfold3_msa"]["ptm"], "iptm": ms["openfold3_msa"]["iptm"],
                    "of3_ligand_rmsd": ms["openfold3_msa"]["ligand_rmsd"], "of3_ligand_centroid_shift": round(lig_rmsd_centroid, 2),
                    "msa_homologs": ms["openfold3_msa"]["msa_homologs"], "of3_seconds": ms["openfold3_msa"]["seconds"],
                    "diffdock_rmsd": ev["rmsd_xtal"], "diffdock_conf": ev["top_conf"], "vina": ev["vina"]},
        "pose_eval": [{"rank": r[0], "confidence": r[1], "rmsd": r[2]} for r in evals],
        "ribbon": ribbon, "crystal_ca": crystal,
        "of3_ligand": pack(p_xyz, p_el, p_b, c), "xtal_ligand": pack(x_xyz, x_el, x_b, c), "diffdock_poses": poses,
    }, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(OUT, OUT.stat().st_size // 1024, "KB", "· poses", len(poses), "· OF3 ligand vs crystal centroid", round(lig_rmsd_centroid, 2), "Å")


if __name__ == "__main__":
    main()
