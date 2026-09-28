"""FlyDiscovery 라이브 API(api/_fv/discovery.py)가 쓰는 입력 묶음을 만듭니다.

- api/_data/discovery.json.gz : 타깃(서열, DiffDock 수용체, 결정 구조 CA · 공결정 리간드), 리간드 SMILES, 쌍, 벤치마크, 크리틱 주장
- api/_data/discovery_measured.json.gz : fly_discovery/measurements/nim/ 의 원본 응답을 라이브 응답과 같은 가공 함수로 처리한 '지난 측정'

원본(fly_discovery/measurements)은 읽기만 합니다. 결정 구조는 RCSB 에서 받아 --pdb-dir 에 캐시합니다.
사용: .venv/bin/python scripts/build_discovery_data.py [--pdb-dir /tmp/pdb]
"""
import argparse
import gzip
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
from _fv import molgeom as mg  # noqa: E402

MEAS = ROOT / "fly_discovery" / "measurements"
NIM = MEAS / "nim"
OUT = ROOT / "api" / "_data" / "discovery.json.gz"
OUT_MEASURED = ROOT / "api" / "_data" / "discovery_measured.json.gz"

# 타깃: DiffDock 수용체는 측정에 쓴 응답의 protein 필드를 그대로 씁니다(같은 입력으로 다시 부르기 위해서입니다)
TARGETS = {
    "parp1": {"label": "PARP1", "gene": "PARP1", "pdb": "4R6E", "chain": "A", "organism": "Homo sapiens",
              "desc": "PARP1 촉매 도메인 · 4R6E 체인 A", "xtal_ligand": {"code": "3JD", "drug": "niraparib"},
              "dd_file": "diffdock_niraparib_parp1.json", "boltz_file": "boltz2_parp1-4r6e-chain-a--niraparib.json"},
    "xa": {"label": "Factor Xa", "gene": "F10", "pdb": "2P16", "chain": "A", "organism": "Homo sapiens",
           "desc": "혈액응고 인자 Xa · 2P16", "xtal_ligand": {"code": "GG2", "drug": "apixaban"},
           "dd_file": "dd_factor-xa-2p16--apixaban.json", "boltz_file": "boltz2_factor-xa-2p16--apixaban.json"},
    "cox2": {"label": "COX-2", "gene": "Ptgs2", "pdb": "3LN1", "chain": "A", "organism": "Mus musculus",
             "desc": "COX-2 · 3LN1 (쥐 단백질)", "xtal_ligand": {"code": "CEL", "drug": "celecoxib"},
             "dd_file": "dd_cox2-3ln1--celecoxib.json", "boltz_file": "boltz2_cox2-3ln1--celecoxib.json"},
}
# 재도킹 패널(pipeline/discovery/redock.py 의 대상, 결과 redock.json). DiffDock 페이지에서만 씁니다
PANEL = ["gr-1m2z--dexamethasone", "d2-6cm4--risperidone", "jak2-6vgl--ruxolitinib", "crbn-4ci2--lenalidomide",
         "mpro-7si9--nirmatrelvir"]
LIGAND_KO = {"niraparib": "니라파립", "rucaparib": "루카파립", "pamiparib": "파미파립", "15r": "15R (PARP1 공결정 리간드)",
             "apixaban": "아픽사반", "celecoxib": "셀레콕시브", "dexamethasone": "덱사메타손", "risperidone": "리스페리돈",
             "ruxolitinib": "룩솔리티닙", "lenalidomide": "레날리도마이드", "nirmatrelvir": "니르마트렐비르"}


def fetch_pdb(code: str, pdb_dir: pathlib.Path) -> str:
    p = pdb_dir / f"{code}.pdb"
    if not p.exists():
        pdb_dir.mkdir(parents=True, exist_ok=True)
        p.write_text(urllib.request.urlopen(f"https://files.rcsb.org/download/{code}.pdb", timeout=60).read().decode())
    return p.read_text()


def xtal_ligand(atoms, code, chain=None):
    """리간드 첫 사본(체인을 주면 그 체인의 첫 사본)."""
    het = [a for a in atoms if a["het"] and a["resn"] == code and (chain is None or a["chain"] == chain)]
    first = het[0]
    lig = [a for a in het if a["chain"] == first["chain"] and a["resi"] == first["resi"]]
    lig, _ = mg.heavy(lig)
    bonds = mg.proximity_bonds(lig)
    return {"code": code, "chain": first["chain"], "atoms": [[a["el"], *[round(v, 3) for v in a["xyz"]]] for a in lig],
            "bonds": [[i, j] for i, j, _ in bonds]}


def load(name):
    return json.loads((NIM / name).read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdb-dir", default=str(ROOT / "data" / "discovery" / "pdb"))
    pdb_dir = pathlib.Path(ap.parse_args().pdb_dir)
    m = json.loads((MEAS / "measurements.json").read_text())
    redock = json.loads((MEAS / "redock.json").read_text())["results"]
    dd_eval = load("dd_eval_all.json")

    targets, ligands, pairs = {}, {}, {}
    for key, t in TARGETS.items():
        dd = load(t["dd_file"])
        receptor = dd["protein"]
        rec_atoms = mg.parse_pdb(receptor)
        xt = mg.parse_pdb(fetch_pdb(t["pdb"], pdb_dir))
        ca = mg.ca_trace(xt, t["chain"])
        # Boltz-2 · OpenFold3 에 넣은 서열(측정 응답의 구조에서 읽음). PARP1 은 measurements/nim/parp1_seq.txt 와 같습니다
        cif_ca = mg.ca_trace(mg.parse_mmcif(load(t["boltz_file"])["structures"][0]["structure"]))
        seq = "".join(r["aa"] for r in cif_ca)
        if key == "parp1":
            assert seq == (NIM / "parp1_seq.txt").read_text().strip()
        targets[key] = {k: t[k] for k in ("label", "gene", "pdb", "chain", "organism", "desc")} | {
            "sequence": seq, "receptor_pdb": receptor, "n_receptor_atoms": len(rec_atoms),
            "xtal_ca": [[r["resi"], r["aa"], *[round(v, 3) for v in r["xyz"]]] for r in ca],
            "xtal_ligand": xtal_ligand(xt, t["xtal_ligand"]["code"], t["chain"]),
            "xtal_drug": t["xtal_ligand"]["drug"], "kind": "core"}
    for key in PANEL:
        r = redock[key]
        dd = load(f"dd_{key}.json")
        tkey = key.split("--")[0]
        xt = mg.parse_pdb(fetch_pdb(r["pdb"], pdb_dir))
        targets[tkey] = {"label": r["target"], "gene": r["gene"], "pdb": r["pdb"], "chain": r["chain"],
                         "organism": "SARS-CoV-2" if "Mpro" in r["gene"] else "Homo sapiens",
                         "desc": f"{r['target']} · {r['pdb']}", "sequence": None, "receptor_pdb": dd["protein"],
                         "xtal_ligand": xtal_ligand(xt, r["ligand"], r["chain"]), "xtal_drug": r["drug"],
                         "xtal_ca": [], "kind": "panel", "note": r.get("note", "")}
        ligands[r["drug"]] = {"smiles": dd["ligand"]}

    # 리간드 SMILES: 측정 DiffDock 요청에 들어간 값(응답의 ligand 필드)
    for f in sorted(NIM.glob("dd_*--*.json")):
        k = f.stem[3:]
        lig = k.split("--")[1]
        ligands.setdefault(lig, {"smiles": load(f.name)["ligand"]})
    ligands.setdefault("niraparib", {"smiles": load("diffdock_niraparib_parp1.json")["ligand"]})
    for lig, v in ligands.items():
        v["ko"] = LIGAND_KO.get(lig, lig)

    # 쌍: 측정 파일 이름(타깃-구조--리간드)을 키로 씁니다
    tfile = {"parp1": "parp1-4r6e-chain-a", "xa": "factor-xa-2p16", "cox2": "cox2-3ln1"}
    roles = {"niraparib@parp1": "데모 약물 · 공결정 재도킹", "rucaparib@parp1": "같은 계열 PARP 억제제",
             "pamiparib@parp1": "같은 계열 PARP 억제제", "15r@parp1": "PARP1 공결정 리간드(다른 구조)",
             "apixaban@xa": "공결정 재도킹 대조", "niraparib@xa": "탐색적 교차 도킹",
             "celecoxib@cox2": "공결정 재도킹 대조", "niraparib@cox2": "탐색적 교차 도킹"}
    vina = {r[0]: r for r in m["diffdock_boltz2_chembl"]}
    boltz_all = load("boltz2_all.json")
    for pk, role in roles.items():
        lig, tk = pk.split("@")
        fkey = f"{tfile[tk]}--{lig}"
        row = vina.get(pk)
        pairs[f"{tk}--{lig}"] = {
            "target": tk, "ligand": lig, "role": role, "redock": targets[tk]["xtal_drug"] == lig,
            "measured_files": {"diffdock": "diffdock_niraparib_parp1.json" if pk == "niraparib@parp1" else f"dd_{fkey}.json",
                               "boltz2": f"boltz2_{fkey}.json"},
            "vina": row[1] if row else None, "chembl_median": row[5] if row else None, "chembl_n": row[6] if row else None,
            "dd_eval": dd_eval.get(fkey), "boltz2_4r6e": boltz_all.get(fkey), "boltz2_ref": boltz_all.get(pk)}
    for key in PANEL:
        tk, lig = key.split("--")
        pairs[f"{tk}--{lig}"] = {"target": tk, "ligand": lig, "role": "재도킹 패널(FAERS 데모 약물)", "redock": True,
                                 "measured_files": {"diffdock": f"dd_{key}.json"}, "redock_eval": redock[key]}

    sset = {x["id"]: x for x in json.loads((MEAS / "pub" / "parp1_set.json").read_text())}
    bset = load("parp1_boltz2_set.json")
    bench_m = m["parp1_affinity_benchmark"]
    bench = {k: bench_m[k] for k in ("n", "spearman", "pearson", "mae", "rmse", "bias", "ef_top25", "hit", "k", "sens", "spec")}
    bench["points"] = [{"id": cid, "smiles": sset.get(cid, {}).get("smiles"), "exp": v["exp"], "pred": v["pic50"],
                        "p": v["p"], "n": sset.get(cid, {}).get("n")} for cid, v in bset.items()]
    chembl = json.loads((MEAS / "pub" / "chembl_affinity.json").read_text())
    critic = m["critic_eval"]["nvidia/nemotron-3-super-120b-a12b"]

    data = {"targets": targets, "ligands": ligands, "pairs": pairs, "benchmark": bench, "chembl": chembl,
            "vina_table": m["diffdock_boltz2_chembl"], "openfold3_measured": m["openfold3_msa"],
            "openfold2_failed": m["openfold2"], "critic_measured": {"model": "nvidia/nemotron-3-super-120b-a12b",
                                                                   **{k: critic[k] for k in ("sec", "caught", "n_over", "passed", "n_valid")},
                                                                   "rows": critic["rows"]},
            "critic_lightning": {k: m["critic_eval"]["nvidia/nemotron-3.5-lightning-30b-a3b"][k] for k in ("sec", "caught", "n_over", "passed", "n_valid")},
            "msa_measured": {"homologs": m["openfold3_msa"]["msa_homologs"], "seconds": 63.6, "database": "Uniref30_2302"},
            "a3m_measured": (NIM / "parp1.a3m").read_text(),
            "source": "fly_discovery/measurements (raw NVIDIA NIM responses, 2026-09-28) + RCSB PDB"}
    OUT.write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(), 9))
    print(f"{OUT.relative_to(ROOT)} {OUT.stat().st_size / 1e3:.0f} KB · targets {len(targets)} · pairs {len(pairs)}")

    # 지난 측정: 라이브 응답과 같은 가공 함수를 원본 응답에 적용합니다
    from _fv import discovery as disc
    disc._DATA = None
    measured = {"msa": {}, "openfold3": {}, "diffdock": {}, "boltz2": {}}
    a3m = data["a3m_measured"]
    measured["msa"]["parp1"] = disc.process_msa({"alignments": {"Uniref30_2302": {"a3m": {"alignment": a3m, "format": "a3m"}}}},
                                                {"target": "parp1"}) | {"seconds": 63.6}
    of3 = load("openfold3_parp1_niraparib.json")
    measured["openfold3"]["parp1--niraparib"] = disc.process_openfold3(of3, {"target": "parp1", "ligand": "niraparib",
                                                                              "msa_source": "measured"}) | {"seconds": 7.1}
    for pk, p in pairs.items():
        f = p["measured_files"].get("diffdock")
        if f and (NIM / f).exists():
            secs = (p.get("redock_eval") or {}).get("seconds")
            measured["diffdock"][pk] = disc.process_diffdock(load(f), {"target": p["target"], "ligand": p["ligand"],
                                                                        "receptor_source": "crystal"}) | {"seconds": secs}
        f = p["measured_files"].get("boltz2")
        if f and (NIM / f).exists():
            b = load(f)
            measured["boltz2"][pk] = disc.process_boltz2(b, {"target": p["target"], "ligand": p["ligand"], "msa_source": "unknown"}) | {
                "seconds": round(b.get("metrics", {}).get("total_time_seconds", 0), 1)}
    OUT_MEASURED.write_bytes(gzip.compress(json.dumps(measured, ensure_ascii=False, separators=(",", ":")).encode(), 9))
    print(f"{OUT_MEASURED.relative_to(ROOT)} {OUT_MEASURED.stat().st_size / 1e3:.0f} KB")
    for pk, v in measured["diffdock"].items():
        print("  diffdock", pk, [(p["rank"], p["confidence"], p["rmsd"]) for p in v["poses"][:2]])
    of = measured["openfold3"]["parp1--niraparib"]
    print("  openfold3", of["scores"], of["ca_rmsd"], of["ligand_rmsd"])
    print("  msa", measured["msa"]["parp1"]["homologs"], measured["msa"]["parp1"]["query_len"])


if __name__ == "__main__":
    main()
