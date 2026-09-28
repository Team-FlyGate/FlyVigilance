"""SIDER 파일럿 참조 세트 생성(pipeline/refsets/sider_refset.py)을 네트워크 없이 검증합니다.

작은 합성 SIDER 파일 둘과 인메모리 DuckDB 웨어하우스(etl_quarter, sig_drug_n, sig_signal)를 만듭니다.
이름 규칙이 공유 이름만 빼는지, 양성과 음성이 규칙대로 만들어지는지, 버린 수가 메타에 남는지,
.gz 로 쓴 참조 세트와 지표 표를 sider_evaluate.py 가 읽는지를 봅니다.
"""
import gzip
import importlib.util
import json
import pathlib
import sys

import pytest

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline/refsets"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline/refsets" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sr = _load("sider_refset")

NAMES = [("CID1", "aspirin"), ("CID2", "Lantus"), ("CID3", "sodium"), ("CID4", "sodium"),
         ("CID5", "warfarin"), ("CID6", "Fe"), ("CID7", "fe"), ("CID8", "zzzdrug")]
# (flat, 유형, 용어). 빈 유형 행과 LLT 행은 버려져야 합니다
SE = [("CID1", "PT", "Nausea"), ("CID1", "PT", "Headache"), ("CID1", "LLT", "Sick"),
      ("CID1", "", "Blood and lymphatic system disorders"),
      ("CID5", "PT", "Haemorrhage"), ("CID5", "PT", "Nausea"), ("CID5", "PT", "Rash"),
      ("CID3", "PT", "Dizziness")]
PAIRS = [("ASPIRIN", "nausea", 10), ("ASPIRIN", "headache", 5), ("ASPIRIN", "dizziness", 4),
         ("ASPIRIN", "off label use", 50),
         ("WARFARIN", "haemorrhage", 30), ("WARFARIN", "nausea", 3), ("WARFARIN", "headache", 3),
         ("WARFARIN", "dizziness", 6), ("WARFARIN", "death", 9),
         ("SODIUM", "nausea", 7)]
DRUG_N = [("SODIUM", 500), ("LANTUS", 20), ("ASPIRIN", 100), ("WARFARIN", 50), ("FE", 10)]


def _warehouse():
    """sig_signal 의 지표 열은 모두 a 값으로, 신호 플래그는 모두 참으로 채웁니다."""
    con = duckdb.connect()
    con.execute("CREATE TABLE etl_quarter(quarter VARCHAR)")
    con.execute("INSERT INTO etl_quarter VALUES ('2012Q4'), ('2026Q2')")
    con.execute("CREATE TABLE sig_drug_n(drug VARCHAR, n_drug BIGINT)")
    con.executemany("INSERT INTO sig_drug_n VALUES (?, ?)", DRUG_N)
    num = [c for c in sr.METRIC_COLS if not c.endswith("_signal") and c != "a"]
    flags = [c for c in sr.METRIC_COLS if c.endswith("_signal")]
    con.execute("CREATE TABLE sig_signal(drug VARCHAR, pt VARCHAR, a BIGINT, "
                + ", ".join(f"{c} DOUBLE" for c in num) + ", " + ", ".join(f"{c} BOOLEAN" for c in flags) + ")")
    for d, p, a in PAIRS:
        con.execute("INSERT INTO sig_signal VALUES (?, ?, ?" + ", ?" * (len(num) + len(flags)) + ")",
                    [d, p, a] + [float(a)] * len(num) + [True] * len(flags))
    return con


def _run(tmp_path: pathlib.Path, name: str = "refset.json") -> dict:
    sider = tmp_path / "sider"
    sider.mkdir()
    (sider / "drug_names.tsv").write_text("".join(f"{a}\t{b}\n" for a, b in NAMES))
    with gzip.open(sider / "meddra_all_se.tsv.gz", "wt") as fh:
        for flat, kind, term in SE:
            fh.write(f"{flat}\tCID0{flat[3:]}\tC000\t{kind}\t{'C001' if kind else ''}\t{term}\n")
    out = tmp_path / name
    rc = sr.main(["--sider-dir", str(sider), "--top-n", "1", "--extra-drugs", "WARFARIN", "MISSINGDRUG",
                  "--seed", "7", "--out", str(out), "--metrics-out", str(tmp_path / "metrics.parquet")],
                 con=_warehouse())
    assert rc == 0
    raw = out.read_bytes()
    return json.loads(gzip.decompress(raw) if name.endswith(".gz") else raw)


def test_exclusion_counts(tmp_path):
    meta = _run(tmp_path)["meta"]
    ex = meta["exclusions"]
    assert ex["excluded_shared_names"] == 2          # SODIUM, 그리고 대소문자만 다른 Fe/fe
    assert ex["excluded_shared_flat_ids"] == 4
    assert ex["excluded_capitalized_names"] == 0     # 규칙을 없앴으므로 Lantus 도 남습니다
    assert ex["eligible_names"] == 4                 # aspirin, Lantus, warfarin, zzzdrug
    assert ex["unmatched_in_warehouse"] == 1
    assert ex["matched_drugs"] == 3
    assert meta["extra_drugs_not_matched"] == ["MISSINGDRUG"]


def test_selection_is_top_n_plus_extra(tmp_path):
    meta = _run(tmp_path)["meta"]
    assert [(d["drug"], d["reason"]) for d in meta["drugs"]] == [("ASPIRIN", "top_n"), ("WARFARIN", "extra")]
    assert meta["seed"] == 7
    assert (meta["warehouse"]["asof"], meta["warehouse"]["first_quarter"], meta["warehouse"]["n_quarters"]) == ("2026Q2", "2012Q4", 2)
    assert not meta["sider"]["dir"].startswith("/")        # 저장소 밖 경로는 파일 이름만 남깁니다


def test_positive_and_negative_rows(tmp_path):
    doc = _run(tmp_path)
    got = {(r["drug"], r["pt"], r["class"]) for r in doc["rows"]}
    assert got == {("ASPIRIN", "nausea", "positive"), ("ASPIRIN", "headache", "positive"),
                   ("ASPIRIN", "dizziness", "negative"),
                   ("WARFARIN", "haemorrhage", "positive"), ("WARFARIN", "nausea", "positive"),
                   ("WARFARIN", "headache", "negative"), ("WARFARIN", "dizziness", "negative")}
    meta = doc["meta"]
    assert meta["dropped"]["sider_positive_without_warehouse_row"] == 1    # WARFARIN rash
    assert meta["dropped"]["warehouse_pairs_outside_sider_universe"] == 2  # off label use, death
    assert meta["dropped"]["outside_universe_examples_by_a"][0] == "off label use"
    assert meta["counts"] == {"positive": 4, "negative": 3, "prevalence": round(4 / 7, 6), "negative_per_positive": 0.75}
    assert meta["sider"]["pt_universe"] == 5     # nausea, headache, haemorrhage, rash, dizziness


def test_gz_output_and_metrics_are_read_by_evaluate(tmp_path):
    doc = _run(tmp_path, "refset.json.gz")
    assert len(doc["rows"]) == 7
    sev = _load("sider_evaluate")
    out = tmp_path / "result.json"
    mjson = tmp_path / "metrics.json"
    mjson.write_text(json.dumps({"asof": "2026Q2", "rules": {"triple": {"OMOP": {"sens": 0.5, "spec": 0.9, "ppv": 0.8, "n": 10}}}}))
    rc = sev.main(["--refset", str(tmp_path / "refset.json.gz"), "--metrics-file", str(tmp_path / "metrics.parquet"),
                   "--repeats", "2", "--out", str(out), "--no-plot", "--metrics-json", str(mjson)])
    assert rc == 0
    res = json.loads(out.read_text())
    assert (res["n_positive"], res["n_negative"]) == (4, 3)
    assert res["fixed_rules"]["triple"]["tp"] == 4          # 합성 웨어하우스는 모든 플래그가 참입니다
    m = json.loads(mjson.read_text())
    assert set(m["rules"]["triple"]) == {"OMOP", "sider-pilot"}
    assert m["sider"]["n"] == 7 and m["sider"]["asof"] == "2026Q2"
