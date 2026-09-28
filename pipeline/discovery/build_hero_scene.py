"""FlyDiscovery 대표 장면: OpenFold3 가 예측한 PARP1 + 니라파립 복합체에 결정 구조(4R6E)와 DiffDock 포즈를 겹친다.

- 예측: fly_discovery/measurements/nim/of3_parp1_niraparib.pdb (OpenFold3 NIM 응답, B-factor = 잔기별 pLDDT)
- 정답: RCSB 4R6E chain A 와 결정 리간드 3JD(니라파립)
- DiffDock: nim/niraparib_diffdock_pose{1..5}.sdf (4R6E 좌표계)
- 4R6E 를 OpenFold3 좌표계로 옮긴다: 잔기 번호(4R6E = 예측 + 660)와 잔기 이름이 같은 Cα 로 Kabsch 정렬
- 정렬 뒤 Cα RMSD 가 저장된 값(measurements.json 의 ca_rmsd_vs_4R6E)과 맞는지 확인하고 파일에 남긴다
- 좌표는 OpenFold3 리간드 중심을 원점으로 옮긴다. 결과는 fly_discovery/measurements/hero_scene.json
- 단계별 장면 데이터도 함께 만든다
  - MSA-Search: nim/parp1.a3m(상동 서열 101개)의 잔기별 보존도(쿼리와 같은 아미노산 비율)와 정렬 띠 그림용 행렬,
    OpenFold3 리간드 5 Å 안의 포켓 잔기
  - Boltz-2: 같은 4R6E 포켓에 DiffDock 으로 넣은 PARP1 억제제 4종(15R · 파미파립 · 니라파립 · 루카파립)과 Boltz-2 예측 pIC50
  - 크리틱: 니라파립을 Factor Xa(2P16)에 넣은 DiffDock 포즈와 그 수용체 (PARP1 과 나란히 보여 줄 분할 장면)
- 장면에서 고를 수 있는 약물(drugs): 니라파립 · 탈라조파립 · 루카파립. 모두 같은 4R6E 수용체에 DiffDock 으로 넣고,
  정답 자리는 각 약물의 PARP1 결정 구조(4R6E · 7KK3 · 6VKK)를 Cα 로 4R6E 에 겹쳐 가져온다. Factor Xa 포즈도 약물마다 둔다.
  빠진 DiffDock 응답만 NVIDIA_API_KEY 가 있을 때 새로 부른다(nim/dd_<키>.json)

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


# 장면에서 고를 수 있는 약물: 결정 구조(PDB, 리간드 코드). 니라파립 결정 구조는 수용체와 같은 4R6E
HERO_DRUGS = {"niraparib": ("4R6E", "3JD"), "talazoparib": ("7KK3", "2YQ"), "rucaparib": ("6VKK", "RPB")}


def dd_cached(key, protein, smiles):
    f = MEAS / f"nim/dd_{key}.json"
    if not f.exists():
        print("DiffDock NIM →", key)
        f.write_text(json.dumps(redock.diffdock(protein, smiles)))
    return json.loads(f.read_text())


def crystal_in_4r6e(pdb_id, comp, x4):
    """다른 PARP1 결정 구조의 리간드를 Cα Kabsch 로 4R6E 좌표계에 옮긴 PDB 블록과 겹친 Cα RMSD."""
    text = redock.fetch_structure(pdb_id)
    chain, _, lig = redock.split_structure(text, comp)
    other = ca_table(text, chain)
    pairs = [k for k in other if k in x4 and other[k][0] == x4[k][0]]
    R2, t2 = kabsch(np.array([other[k][1] for k in pairs]), np.array([x4[k][1] for k in pairs]))
    rm = float(np.sqrt(((np.array([other[k][1] for k in pairs]) @ R2.T + t2 - np.array([x4[k][1] for k in pairs])) ** 2).sum(1).mean()))
    out = []
    for ln in lig.splitlines():
        if ln.startswith("HETATM"):
            q = np.array([float(ln[30:38]), float(ln[38:46]), float(ln[46:54])]) @ R2.T + t2
            ln = f"{ln[:30]}{q[0]:8.3f}{q[1]:8.3f}{q[2]:8.3f}{ln[54:]}"
        out.append(ln)
    return "\n".join(out) + "\n", len(pairs), rm


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

    # MSA-Search: a3m 의 소문자(삽입)를 빼면 모든 서열이 쿼리 위치에 맞춰진다
    seqs, cur, heads = [], [], []
    for ln in (MEAS / "nim/parp1.a3m").read_text().splitlines():
        if ln.startswith(">"):
            if cur: seqs.append("".join(cur))
            cur = []
            f = ln[1:].split()
            heads.append([f[0].split("|")[0], float(f[2]) if len(f) > 2 and f[2].replace(".", "", 1).isdigit() else None])
        else:
            cur.append("".join(ch for ch in ln.strip() if not ch.islower()))
    if cur: seqs.append("".join(cur))
    query, homologs = seqs[0], seqs[1:]
    cons = []
    for i, q in enumerate(query):
        col = [h[i] for h in homologs if i < len(h)]
        aligned = [x for x in col if x != "-"]
        cons.append(round(sum(x == q for x in aligned) / max(1, len(col)), 3))
    strip = ["".join("1" if (i < len(h) and h[i] == q) else ("-" if i >= len(h) or h[i] == "-" else "0") for i, q in enumerate(query)) for h in homologs]
    # 포켓 잔기: OpenFold3 리간드 중원자 5 Å 안에 원자가 있는 잔기
    pocket_res = sorted({int(ln[22:26]) for ln in of3_text.splitlines() if ln.startswith("ATOM") and ln[21] == "A"
                         and min(np.linalg.norm(np.array([float(ln[30:38]), float(ln[38:46]), float(ln[46:54])]) - q) for q in p_xyz) <= 5.0})
    pocket_cons = [cons[r - 1] for r in pocket_res if 0 < r <= len(cons)]
    print(f"MSA {len(homologs)} homologs · query {len(query)} aa · mean conservation {np.mean(cons):.2f} · pocket {len(pocket_res)} res mean {np.mean(pocket_cons):.2f}")

    # Boltz-2: 같은 4R6E 포켓의 PARP1 억제제 4종 (DiffDock 1순위 포즈, 4R6E 좌표계 → 예측 좌표계)
    combos = {r[0]: r for r in ms["diffdock_boltz2_chembl"]}
    parp_set = []
    for lig in ["15r", "pamiparib", "niraparib", "rucaparib"]:
        f = MEAS / f"nim/dd_parp1-4r6e-chain-a--{lig}.json"
        sdf = json.loads(f.read_text())["ligand_positions"][0] if f.exists() else (MEAS / "nim/niraparib_diffdock_pose1.sdf").read_text()
        xyz, el, bd = mol_atoms(Chem.MolFromMolBlock(sdf, removeHs=False, sanitize=False))
        r = combos.get(f"{lig}@parp1")
        parp_set.append({"name": lig, "pose": pack(xyz @ R.T + t, el, bd, c), "vina": r[1] if r else None, "dd_conf": r[2] if r else None,
                         "boltz_pic50": r[3] if r else None, "boltz_p": r[4] if r else None, "chembl": r[5] if r else None, "chembl_n": r[6] if r else None})

    # 크리틱: 니라파립 → Factor Xa (2P16). 아픽사반 결정 자리 중심을 원점으로
    xa_text = redock.fetch_structure("2P16")
    xa_chain, xa_prot, xa_lig = redock.split_structure(xa_text, "GG2")
    xa_c = np.array([[float(l[30:38]), float(l[38:46]), float(l[46:54])] for l in xa_lig.splitlines() if l.startswith("HETATM")]).mean(0)
    xa_ca = [[*map(lambda v: round(float(v), 2), np.array([float(l[30:38]), float(l[38:46]), float(l[46:54])]) - xa_c), int(l[22:26])]
             for l in xa_prot.splitlines() if l.startswith("ATOM") and l[12:16].strip() == "CA"]
    nx_xyz, nx_el, nx_b = mol_atoms(Chem.MolFromMolBlock(json.loads((MEAS / "nim/dd_factor-xa-2p16--niraparib.json").read_text())["ligand_positions"][0], removeHs=False, sanitize=False))
    ev_all = json.loads((MEAS / "nim/dd_eval_all.json").read_text())
    critic_split = {"xa": {"pdb": "2P16", "chain": xa_chain, "ca": xa_ca, "niraparib": pack(nx_xyz, nx_el, nx_b, xa_c),
                           "dd_conf": ev_all["factor-xa-2p16--niraparib"]["top_conf"], "vina": ev_all["factor-xa-2p16--niraparib"]["vina"]},
                    "parp1": {"dd_conf": ev_all["parp1-4r6e-chain-a--niraparib"]["top_conf"], "vina": ev_all["parp1-4r6e-chain-a--niraparib"]["vina"]}}

    # 고를 수 있는 약물 3종 (4R6E 수용체 · 4R6E 좌표계 → 예측 좌표계)
    _, x_prot, _ = redock.split_structure(x_text, "3JD")
    bench = json.loads((MEAS / "nim/parp1_boltz2_set.json").read_text())
    drugs = {}
    for name, (pdb_id, comp) in HERO_DRUGS.items():
        smiles = redock.ligand_smiles(comp)
        # 니라파립은 페이지 다른 곳의 수치와 맞도록 처음 받은 포즈 5개(niraparib_diffdock_pose*.sdf)를 그대로 쓴다
        resp = ({"ligand_positions": [(MEAS / f"nim/niraparib_diffdock_pose{i}.sdf").read_text() for i in range(1, 6)],
                 "position_confidence": [r[1] for r in evals]} if name == "niraparib"
                else dd_cached(f"parp1-4r6e-chain-a--{name}", x_prot, smiles))
        lig_pdb, n_ca, ca_rm = crystal_in_4r6e(pdb_id, comp, xtal) if pdb_id != "4R6E" else (redock.split_structure(x_text, "3JD")[2], len(xtal), 0.0)
        ref = redock.crystal_ligand(lig_pdb, smiles)
        sdfs = resp["ligand_positions"][:5]
        conf = resp["position_confidence"][:5]
        rms = [redock.pose_rmsd(p, ref) for p in sdfs]
        d_poses = [pack(mol_atoms(Chem.MolFromMolBlock(p, removeHs=False, sanitize=False))[0] @ R.T + t,
                        *mol_atoms(Chem.MolFromMolBlock(p, removeHs=False, sanitize=False))[1:], c) for p in sdfs]
        cx_xyz, cx_el, cx_b = mol_atoms(Chem.MolFromPDBBlock(lig_pdb, removeHs=False, sanitize=False, proximityBonding=True))
        xa_resp = dd_cached(f"factor-xa-2p16--{name}", xa_prot, smiles)
        xa_xyz, xa_el, xa_b = mol_atoms(Chem.MolFromMolBlock(xa_resp["ligand_positions"][0], removeHs=False, sanitize=False))
        combo = combos.get(f"{name}@parp1")
        chembl_id = {"talazoparib": "CHEMBL3137320", "rucaparib": "CHEMBL1173055"}.get(name)
        bz = combo[3] if combo else bench.get(chembl_id, {}).get("pic50")
        exp = combo[5] if combo else bench.get(chembl_id, {}).get("exp")
        drugs[name] = {"name": name, "crystal_pdb": pdb_id, "crystal_ca_matched": n_ca, "crystal_ca_rmsd": round(ca_rm, 2),
                       "poses": d_poses, "pose_eval": [{"rank": i + 1, "confidence": round(cf, 3), "rmsd": r} for i, (cf, r) in enumerate(zip(conf, rms))],
                       "xtal": pack(cx_xyz @ R.T + t, cx_el, cx_b, c), "dd_rmsd": rms[0], "dd_conf": round(conf[0], 3),
                       "vina": combo[1] if combo else None, "boltz_pic50": round(bz, 3) if bz else None,
                       "chembl": exp, "chembl_n": combo[6] if combo else None,
                       "xa": {"ligand": pack(xa_xyz, xa_el, xa_b, xa_c), "dd_conf": round(xa_resp["position_confidence"][0], 3),
                              "vina": ev_all["factor-xa-2p16--niraparib"]["vina"] if name == "niraparib" else None}}
        print(f"{name}: crystal {pdb_id} Cα {n_ca} RMSD {ca_rm:.2f} · pose RMSD {rms} · conf {[round(x, 2) for x in conf]} · Xa {drugs[name]['xa']['dd_conf']}")
    # Boltz-2 장면에 탈라조파립도 같은 포켓 포즈로 넣는다
    if not any(x["name"] == "talazoparib" for x in parp_set):
        d = drugs["talazoparib"]
        parp_set.append({"name": "talazoparib", "pose": d["poses"][0], "vina": None, "dd_conf": d["dd_conf"], "boltz_pic50": d["boltz_pic50"],
                         "boltz_p": bench["CHEMBL3137320"].get("p"), "chembl": d["chembl"], "chembl_n": None})

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
        "msa": {"labels": heads[1:], "query": query, "n_homologs": len(homologs), "query_len": len(query), "conservation": cons, "strip": strip,
                "pocket_residues": pocket_res, "pocket_mean": round(float(np.mean(pocket_cons)), 3), "overall_mean": round(float(np.mean(cons)), 3)},
        "parp_set": parp_set, "critic_split": critic_split, "drugs": drugs,
    }, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(OUT, OUT.stat().st_size // 1024, "KB", "· poses", len(poses), "· OF3 ligand vs crystal centroid", round(lig_rmsd_centroid, 2), "Å")


if __name__ == "__main__":
    main()
