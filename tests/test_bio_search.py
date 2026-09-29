"""단백질·리간드 조회의 파싱과 검사를 네트워크 없이 시험합니다.

응답 본보기는 실제 UniProt·PubChem 응답에서 필요한 부분만 줄여 옮겼습니다.
"""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "api"))
from _fv import bio_search as bio  # noqa: E402
from _fv import discovery as disc  # noqa: E402

UNIPROT_SEARCH = {
    "results": [
        {"entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": "P00533", "uniProtkbId": "EGFR_HUMAN",
         "organism": {"scientificName": "Homo sapiens"},
         "proteinDescription": {"recommendedName": {"fullName": {"value": "Epidermal growth factor receptor"}}},
         "genes": [{"geneName": {"value": "EGFR"}}], "sequence": {"length": 1210},
         "uniProtKBCrossReferences": [{"database": "PDB", "id": "1M17"}, {"database": "PDB", "id": "1M14"}]},
        {"entryType": "UniProtKB unreviewed (TrEMBL)", "primaryAccession": "C9JYS6", "uniProtkbId": "C9JYS6_HUMAN",
         "organism": {"scientificName": "Homo sapiens"},
         "proteinDescription": {"submissionNames": [{"fullName": {"value": "Epidermal growth factor receptor"}}]},
         "genes": [{"geneName": {"value": "EGFR"}}], "sequence": {"length": 705},
         "uniProtKBCrossReferences": []},
        {"entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": "Q01279", "uniProtkbId": "EGFR_MOUSE",
         "organism": {"scientificName": "Mus musculus"},
         "proteinDescription": {"recommendedName": {"fullName": {"value": "Epidermal growth factor receptor"}}},
         "genes": [{"geneName": {"value": "Egfr"}}], "sequence": {"length": 1210},
         "uniProtKBCrossReferences": []},
    ]
}

UNIPROT_ENTRY = {
    "entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": "P00533", "uniProtkbId": "EGFR_HUMAN",
    "organism": {"scientificName": "Homo sapiens"},
    "proteinDescription": {"recommendedName": {"fullName": {"value": "Epidermal growth factor receptor"}}},
    "genes": [{"geneName": {"value": "EGFR"}}],
    "features": [
        {"type": "Domain", "location": {"start": {"value": 712}, "end": {"value": 979}},
         "description": "Protein kinase"},
        {"type": "Region", "location": {"start": {"value": 1000}, "end": {"value": 1010}}, "description": "짧아서 제외"},
    ],
    "uniProtKBCrossReferences": [
        {"database": "PDB", "id": "1IVO", "properties": [{"key": "Method", "value": "X-ray"},
                                                          {"key": "Resolution", "value": "3.30 A"},
                                                          {"key": "Chains", "value": "A/B=25-646"}]},
        {"database": "PDB", "id": "1M17", "properties": [{"key": "Method", "value": "X-ray"},
                                                          {"key": "Resolution", "value": "2.60 A"},
                                                          {"key": "Chains", "value": "A=695-1022"}]},
        {"database": "PDB", "id": "2GS6", "properties": [{"key": "Method", "value": "X-ray"},
                                                          {"key": "Resolution", "value": "2.60 A"},
                                                          {"key": "Chains", "value": "A=696-1022"}]},
        {"database": "PDB", "id": "5UG9", "properties": [{"key": "Method", "value": "X-ray"},
                                                          {"key": "Resolution", "value": "1.33 A"},
                                                          {"key": "Chains", "value": "A=696-1022"}]},
        {"database": "AlphaFoldDB", "id": "P00533", "properties": []},
    ],
    "sequence": {"value": "M" + "AGKLPTWVQ" * 134 + "K", "length": 1207},
}

PUBCHEM = {"PropertyTable": {"Properties": [{"CID": 176870, "MolecularWeight": "393.4", "Title": "Erlotinib",
                                              "SMILES": "COCCOC1=C(C=C2C(=C1)C(=NC=N2)NC3=CC=CC(=C3)C#C)OCCOC"}]}}
PUBCHEM_AC = {"status": {"code": 0}, "total": 3, "dictionary_terms": {"compound": ["Erlotinib", "Erlotinib hydrochloride", "Erlose"]}}

PDB_TEXT = """\
ATOM      1  N   ALA A  10      11.000  10.000  10.000  1.00 20.00           N
ATOM      2  CA  ALA A  10      12.000  10.000  10.000  1.00 20.00           C
ATOM      3  C   ALA A  10      13.000  10.000  10.000  1.00 20.00           C
ATOM      4  N   GLY B  10      50.000  50.000  50.000  1.00 20.00           N
HETATM  100  O   HOH A 301       1.000   1.000   1.000  1.00 20.00           O
HETATM  101  C1  AQ4 A 401       5.000   5.000   5.000  1.00 20.00           C
HETATM  102  C2  AQ4 A 401       6.400   5.000   5.000  1.00 20.00           C
HETATM  103  N3  AQ4 A 401       7.700   5.100   5.200  1.00 20.00           N
HETATM  104  O4  AQ4 A 401       8.900   5.200   5.300  1.00 20.00           O
HETATM  105  C5  AQ4 A 401      10.200   5.300   5.400  1.00 20.00           C
HETATM  106  C6  AQ4 A 401      11.500   5.400   5.500  1.00 20.00           C
HETATM  110 ZN    ZN A 501      20.000  20.000  20.000  1.00 20.00          ZN
END
"""


# ---------------------------------------------------------------- 입력 판별
def test_input_kind_is_recognised():
    assert bio.looks_like_pdb_id("1M17") and bio.looks_like_pdb_id("4r6e")
    assert not bio.looks_like_pdb_id("EGFR") and not bio.looks_like_pdb_id("P00533")
    assert bio.looks_like_accession("P00533") and bio.looks_like_accession("q01279")
    assert not bio.looks_like_accession("EGFR")


@pytest.mark.parametrize("s,ok", [
    ("COCCOC1=C(C=C2C(=C1)C(=NC=N2)NC3=CC=CC(=C3)C#C)OCCOC", True),
    ("CC(=O)OC1=CC=CC=C1C(=O)O", True),
    ("", False), ("CC(=O", False), ("CC(=O)O ethanol", False), ("한글", False), ("C" * 700, False),
])
def test_smiles_validation(s, ok):
    assert bio.valid_smiles(s)[0] is ok


def test_sequence_check_follows_nim_limits():
    ok = bio.check_sequence("ACDEFGHIKLMNPQRSTVWY" * 10)
    assert ok["ok"] and ok["openfold3_ok"] and ok["length"] == 200
    mid = bio.check_sequence("A" * 2000)
    assert mid["ok"] and not mid["openfold3_ok"] and "1800" in mid["reason"]
    big = bio.check_sequence("A" * 5000)
    assert not big["ok"] and "4096" in big["reason"]
    bad = bio.check_sequence("ACDEF123!!")
    assert not bad["ok"]
    assert bio.clean_sequence("acd efg\n123") == "ACDEFG"


# ---------------------------------------------------------------- UniProt
def test_search_puts_reviewed_human_entries_first():
    hits = bio.parse_uniprot_search(UNIPROT_SEARCH)
    assert [h["id"] for h in hits][0] == "P00533"
    top = hits[0]
    assert top["gene"] == "EGFR" and top["organism"] == "Homo sapiens" and top["reviewed"]
    assert top["length"] == 1210 and top["n_pdb"] == 2 and top["pdb"] == "1M17"
    assert hits[1]["id"] == "Q01279"     # 검토된 쥐 항목이 미검토 사람 항목보다 앞
    assert not hits[2]["reviewed"]


def test_entry_parsing_gives_sequence_structures_and_ranges():
    rec = bio.parse_uniprot_entry(UNIPROT_ENTRY)
    assert rec["id"] == "P00533" and rec["gene"] == "EGFR" and rec["organism"] == "Homo sapiens"
    assert rec["length"] == 1208 and rec["sequence"].startswith("MAGKLP")
    assert rec["best_structure"]["pdb"] == "5UG9" and rec["best_structure"]["resolution"] == 1.33
    assert rec["best_structure"]["chain"] == "A" and rec["best_structure"]["start"] == 696
    kinds = [r["kind"] for r in rec["ranges"]]
    assert kinds[0] == "structure" and "full" in kinds and "domain" in kinds
    assert rec["recommended_range"]["end"] - rec["recommended_range"]["start"] + 1 <= bio.OF3_SOFT_MAX_AA
    assert [d["label"] for d in rec["domains"]] == ["Protein kinase"]   # 40잔기 미만 구간은 뺍니다
    assert rec["check"]["ok"] and rec["check"]["openfold3_ok"]


def test_structure_pick_prefers_resolution_then_method():
    s = [{"pdb": "AAAA", "method": "NMR", "resolution": None, "chain": "A", "start": 1, "end": 100},
         {"pdb": "BBBB", "method": "X-ray", "resolution": 2.8, "chain": "A", "start": 1, "end": 100},
         {"pdb": "CCCC", "method": "Electron microscopy", "resolution": 3.1, "chain": "A", "start": 1, "end": 100}]
    assert bio.pick_structure(s)["pdb"] == "BBBB"
    assert bio.pick_structure([]) is None


def test_structure_pick_skips_short_peptide_chains():
    # BRAF: 8VSO 는 해상도가 가장 좋지만 BRAF 체인이 9잔기 펩타이드(361–369)라 대표 구조로 쓰지 않습니다
    s = [{"pdb": "8VSO", "method": "X-ray", "resolution": 1.5, "chain": "P", "start": 361, "end": 369},
         {"pdb": "4MNE", "method": "X-ray", "resolution": 2.1, "chain": "A", "start": 432, "end": 726}]
    assert bio.pick_structure(s)["pdb"] == "4MNE"
    # 짧은 구조밖에 없으면 그거라도 씁니다
    assert bio.pick_structure(s[:1])["pdb"] == "8VSO"


# ---------------------------------------------------------------- PubChem
def test_pubchem_properties_and_autocomplete():
    lig = bio.parse_pubchem_properties(PUBCHEM)
    assert lig["cid"] == 176870 and lig["name"] == "Erlotinib" and lig["mw"] == pytest.approx(393.4)
    assert bio.valid_smiles(lig["smiles"])[0]
    assert bio.parse_pubchem_properties({"PropertyTable": {"Properties": []}}) is None
    assert bio.parse_pubchem_autocomplete(PUBCHEM_AC)[0] == "Erlotinib"
    assert bio.parse_pubchem_autocomplete({}) == []


# ---------------------------------------------------------------- 구조 파일
def test_chain_atoms_and_cocrystal_ligand():
    rec = bio.chain_atoms(PDB_TEXT, "A")
    lines = [ln for ln in rec.splitlines() if ln.startswith("ATOM")]
    assert len(lines) == 3 and all(ln[21] == "A" for ln in lines)
    assert "HETATM" not in rec
    lig = bio.cocrystal_ligand(PDB_TEXT, "A")
    assert lig["code"] == "AQ4" and len(lig["atoms"]) == 6      # 물·아연은 제외합니다
    assert len(lig["center"]) == 3 and lig["bonds"]
    assert bio.cocrystal_ligand("ATOM      1  N   ALA A  10      11.000  10.000  10.000\n", "A") is None


# ---------------------------------------------------------------- 파이프라인 연결
def test_custom_target_slices_the_chosen_range_and_has_no_reference():
    seq = "ACDEFGHIKL" * 30
    t = disc.custom_target({"id": "P00533", "gene": "EGFR", "name": "Epidermal growth factor receptor",
                            "organism": "Homo sapiens", "sequence": seq, "pdb": "1m17", "chain": "A",
                            "start": 11, "end": 40})
    assert t["label"] == "EGFR" and t["pdb"] == "1M17" and t["kind"] == "custom"
    assert t["sequence"] == seq[10:40] and len(t["sequence"]) == 30
    assert t["xtal_ca"] == [] and t["xtal_drug"] is None and t["reference"] == "none"
    body = disc.build_msa(t)
    assert body["sequence"] == t["sequence"] and body["databases"] == ["Uniref30_2302"]
    of3 = disc.build_openfold3(t, disc.custom_ligand({"name": "erlotinib", "smiles": "CC#CC"}), None)
    mols = of3["inputs"][0]["molecules"]
    assert mols[0]["sequence"] == t["sequence"] and mols[1]["smiles"] == "CC#CC"
    bz = disc.build_boltz2(t, disc.custom_ligand({"name": "erlotinib", "smiles": "CC#CC"}), ">q\nAC")
    assert bz["ligands"][0]["predict_affinity"] is True and bz["polymers"][0]["msa"]["msa_search"]["a3m"]["rank"] == 0


def test_custom_target_never_reports_a_redock_rmsd():
    """사용자가 고른 표적에는 공결정 대조가 없습니다. 구조의 다른 리간드와 비교해 RMSD 를 만들어 내지 않습니다."""
    raw = json.loads((pathlib.Path(__file__).resolve().parents[1]
                      / "fly_discovery/measurements/nim/diffdock_niraparib_parp1.json").read_text())
    t = disc.custom_target({"id": "P00533", "gene": "EGFR", "organism": "Homo sapiens",
                            "sequence": "ACDEFGHIKL" * 30, "pdb": "1M17", "chain": "A"})
    t["xtal_ligand"] = {"atoms": [["C", 0.0, 0.0, 0.0]], "bonds": []}   # 구조의 공결정 리간드(다른 분자)
    t["pocket_ligand_code"] = "AQ4"
    out = disc.process_diffdock(raw, {"target_obj": t, "ligand": None})
    assert out["redock"] is False and out["reference"] == "none"
    assert out["top1_rmsd"] is None and out["best_rmsd"] is None and out["top1_success"] is False
    assert "기준 결정 구조 없음" in out["reference_note"] and "AQ4" in out["reference_note"]
    assert out["poses"][0]["pocket_dist"] is not None    # 주머니 위치는 참고로 남깁니다
    assert out["target_label"] == "EGFR"


def test_openfold3_input_id_stays_within_the_nim_limit():
    """input_id 는 128자 제한입니다. 고른 표적·리간드를 통째로 문자열로 만들면 넘어갑니다."""
    t = disc.custom_target({"id": "P00533", "gene": "EGFR", "name": "Epidermal growth factor receptor",
                            "organism": "Homo sapiens", "sequence": "ACDEFGHIKL" * 40, "pdb": "8A27", "chain": "A"})
    lg = disc.custom_ligand({"name": "Erlotinib", "smiles": "CC#CC", "cid": 176870})
    body = disc.build_openfold3(t, lg, None)
    iid = body["inputs"][0]["input_id"]
    assert iid == "EGFR_Erlotinib" and len(iid) <= 128
    assert len(disc.build_openfold3(t, disc.custom_ligand({"name": "x" * 300, "smiles": "CC#CC"}), None)
               ["inputs"][0]["input_id"]) <= 128
    assert disc.build_openfold3("parp1", "niraparib", None)["inputs"][0]["input_id"] == "parp1_niraparib"


def test_custom_ligand_rejects_a_bad_smiles():
    with pytest.raises(KeyError):
        disc.custom_ligand({"name": "x", "smiles": "CC(=O"})


def test_resolve_target_and_ligand_prefer_the_user_choice():
    params = {"target": "parp1", "ligand": "niraparib",
              "custom_target": {"id": "P00533", "gene": "EGFR", "sequence": "ACDEFGHIKL" * 5},
              "custom_ligand": {"name": "erlotinib", "smiles": "CC#CC"}}
    t = disc.resolve_target(params)
    assert isinstance(t, dict) and t["label"] == "EGFR"
    assert disc.resolve_ligand(params)["smiles"] == "CC#CC"
    assert disc.resolve_target({"target": "parp1"}) == "parp1"
    assert disc.resolve_ligand({"ligand": "niraparib"}) == "niraparib"


def test_custom_run_is_refused_when_the_sequence_is_too_long():
    import asyncio
    params = {"custom_target": {"id": "X", "gene": "LONG", "sequence": "A" * 5000},
              "custom_ligand": {"name": "x", "smiles": "CC#CC"}}
    with pytest.raises(ValueError):
        asyncio.run(disc.run("msa", params))


def test_request_summary_hides_long_inputs():
    safe = disc._safe_params({"a3m": "x" * 500, "custom_target": {"sequence": "A" * 300, "gene": "EGFR"},
                              "ligand": "erlotinib"})
    assert safe["a3m"] == "<500 chars>" and "sequence" not in safe["custom_target"]
    assert safe["custom_target"]["sequence_len"] == 300 and safe["ligand"] == "erlotinib"
    assert "A" * 50 not in json.dumps(safe)
