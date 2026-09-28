"""기전 타당성(pipeline/refsets/omics_plausibility.py)의 해석 규칙, 집계, 근거 ID 를 네트워크 없이 검증합니다.

HTTP 한 번을 맡는 _send 를 가짜로 바꿔 끼우고 캐시는 pytest 임시 폴더에 둡니다. 가짜 응답의 모양은 하네스가
Open Targets 에서 받은 조사 응답을 옮긴 것입니다. 점수 숫자는 모양을 맞추려는 값일 뿐 사실 주장이 아닙니다.
보는 것은 약 이름 정확 일치, PT 라벨 정확 일치, 표적별 최댓값과 literature 제외 점수, 근거 ID 와 설명 문장,
실패한 호출이 0 이 아닌 None 으로 남는지, 캐시 재생, 참조 세트 묶음 모드의 쪽 넘김과 조인입니다.
"""
import importlib.util
import json
import pathlib
import sys

import pytest

pytest.importorskip("numpy")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline/refsets"))
Path = pathlib.Path


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline/refsets" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


op = _load("omics_plausibility")

META = {"data": {"meta": {"apiVersion": {"x": "26", "y": "9", "z": "0"},
                          "dataVersion": {"year": "26", "month": "09", "iteration": None}}}}

DRUG_SEARCH = {
    "niraparib": [{"id": "CHEMBL4650351", "name": "PARPI", "entity": "drug"},
                  {"id": "CHEMBL3989922", "name": "NIRAPARIB TOSYLATE MONOHYDRATE", "entity": "drug"},
                  {"id": "CHEMBL1094636", "name": "NIRAPARIB", "entity": "drug"}],
    "unknownium": [{"id": "CHEMBL0000001", "name": "UNKNOWNIUM SODIUM", "entity": "drug"}],
}

MOA = {"CHEMBL1094636": {"id": "CHEMBL1094636", "name": "NIRAPARIB", "mechanismsOfAction": {"rows": [
    {"actionType": "INHIBITOR", "mechanismOfAction": "Poly [ADP-ribose] polymerase 2 inhibitor",
     "targets": [{"id": "ENSG00000129484", "approvedSymbol": "PARP2"}]},
    {"actionType": "INHIBITOR", "mechanismOfAction": "Poly [ADP-ribose] polymerase-1 inhibitor",
     "targets": [{"id": "ENSG00000143799", "approvedSymbol": "PARP1"}]}]}}}

DISEASE_SEARCH = {
    "thrombocytopenia": [{"id": "HP_0001873", "name": "Thrombocytopenia", "entity": "disease",
                          "score": 4886.2},
                         {"id": "MONDO_0100241", "name": "inherited thrombocytopenia",
                          "entity": "disease", "score": 525.9}],
    "neutrophil count decreased": [{"id": "HP_0001875", "name": "Decreased total neutrophil count",
                                    "entity": "disease", "score": 900.0}],
}


def assoc_row(disease_id: str, score: float, datatypes: dict[str, float]) -> dict:
    return {"disease": {"id": disease_id, "name": "x"}, "score": score,
            "datatypeScores": [{"id": k, "score": v} for k, v in datatypes.items()],
            "datasourceScores": [{"id": "europepmc", "score": datatypes.get("literature", 0.0)}]}


# 표적별 연관 응답입니다. 없는 표적은 호출 실패를 흉내 냅니다
ASSOC = {
    "ENSG00000143799": {"all": [assoc_row("HP_0001873", 0.0125, {"literature": 0.1028})],
                        "noLit": 0.0},
    "ENSG00000129484": {"all": [assoc_row("HP_0001873", 0.0055, {"literature": 0.0454,
                                                                 "animal_model": 0.3})],
                        "noLit": 0.004},
}


class FakeNet:
    def __init__(self, assoc=None, fail_ops=()):
        self.calls: list[dict] = []
        self.assoc = ASSOC if assoc is None else assoc
        self.fail_ops = set(fail_ops)

    def __call__(self, url, body):
        if body is None:                      # ChEMBL GET 입니다
            self.calls.append({"url": url})
            if "status.json" in url:
                return {"chembl_db_version": "ChEMBL_TEST"}
            return {"molecules": [], "page_meta": {"total_count": 0}}
        req = json.loads(body)
        name, v = req["operationName"], req["variables"] or {}
        self.calls.append({"op": name, "variables": v})
        if name in self.fail_ops:
            raise RuntimeError("HTTP 503: unavailable")
        if name == "Meta":
            return META
        if name == "DrugSearch":
            return {"data": {"search": {"hits": DRUG_SEARCH.get(v["q"].lower(), [])}}}
        if name == "DrugMechanisms":
            return {"data": {"drug": MOA.get(v["id"])}}
        if name == "DiseaseSearch":
            return {"data": {"search": {"hits": DISEASE_SEARCH.get(v["q"].lower(), [])}}}
        if name == "TargetDiseaseAssociation":
            spec = self.assoc.get(v["id"])
            if spec is None:
                raise RuntimeError("HTTP 500: boom")
            rows = spec["all"]
            nolit = [{"disease": r["disease"], "score": spec["noLit"]} for r in rows]
            return {"data": {"target": {"id": v["id"], "approvedSymbol": "S",
                                        "all": {"count": len(rows), "rows": rows},
                                        "noLiterature": {"count": len(nolit), "rows": nolit}}}}
        raise AssertionError(name)


@pytest.fixture
def net(monkeypatch, tmp_path):
    fake = FakeNet()
    monkeypatch.setattr(op, "_send", fake)
    monkeypatch.setenv(op.CACHE_ENV, str(tmp_path / "omics"))
    return fake


def fetcher(dry_run=False):
    return op.Fetcher(dry_run=dry_run, sleep=0.0)


def run_one(drug, pt, dry_run=False):
    f = fetcher(dry_run)
    return op.run([(drug, pt)], f, "2026-09-28"), f


def test_drug_name_must_match_exactly(net):
    drug = op.resolve_drug(fetcher(), "NIRAPARIB")
    assert drug["id"] == "CHEMBL1094636" and drug["match"] == "name_exact"
    assert [t["symbol"] for t in drug["targets"]] == ["PARP2", "PARP1"]
    assert drug["targets"][1] == {"symbol": "PARP1", "ensembl": "ENSG00000143799",
                                  "actionType": "INHIBITOR",
                                  "mechanism": "Poly [ADP-ribose] polymerase-1 inhibitor"}


def test_near_name_is_rejected_and_chembl_miss_means_no_target(net):
    result, _ = run_one("UNKNOWNIUM", "THROMBOCYTOPENIA")
    row = result["pairs"][0]
    assert row["drug_resolution"]["id"] is None
    assert row["drug_resolution"]["match"] == "none"
    assert row["has_target"] is False and row["n_targets"] == 0
    assert row["has_association"] is False and row["max_score"] is None
    assert any("pref_name__iexact=UNKNOWNIUM" in c.get("url", "") for c in net.calls)


def test_pt_maps_only_on_exact_label_of_first_hit(net):
    ok = op.resolve_pt(fetcher(), "THROMBOCYTOPENIA")
    assert ok["mapped"] == {"id": "HP_0001873", "name": "Thrombocytopenia", "match": "label"}
    miss = op.resolve_pt(fetcher(), "NEUTROPHIL COUNT DECREASED")
    assert miss["mapped"] is None
    assert miss["first_hit"]["id"] == "HP_0001875" and miss["first_hit"]["match"] == "none"


def test_unmapped_pt_leaves_scores_unknown(net):
    row = run_one("NIRAPARIB", "NEUTROPHIL COUNT DECREASED")[0]["pairs"][0]
    assert row["has_target"] is True
    assert row["has_association"] is None and row["max_score"] is None
    assert row["associations"] == []


def test_aggregation_takes_max_and_no_literature_scores(net):
    row = run_one("NIRAPARIB", "THROMBOCYTOPENIA")[0]["pairs"][0]
    by = {a["symbol"]: a for a in row["associations"]}
    assert by["PARP1"]["score"] == 0.0125 and by["PARP1"]["score_no_literature_local"] == 0.0
    assert by["PARP2"]["score_no_literature_local"] == 0.3
    assert row["max_score"] == 0.0125
    assert row["max_score_no_literature"] == 0.004
    assert row["max_score_no_literature_local"] == 0.3
    assert row["has_association"] is True and row["incomplete"] is False
    assoc_req = [r for r in row["requests"] if r["operation"] == "TargetDiseaseAssociation"][0]
    assert assoc_req["variables"]["noLit"] == op.NO_LITERATURE_DATASOURCES


def test_empty_association_is_zero_not_missing(monkeypatch, tmp_path):
    fake = FakeNet(assoc={"ENSG00000143799": {"all": [], "noLit": 0.0},
                          "ENSG00000129484": {"all": [], "noLit": 0.0}})
    monkeypatch.setattr(op, "_send", fake)
    monkeypatch.setenv(op.CACHE_ENV, str(tmp_path))
    row = run_one("NIRAPARIB", "THROMBOCYTOPENIA")[0]["pairs"][0]
    assert all(a["row_found"] is False and a["score"] == 0.0 for a in row["associations"])
    assert row["max_score"] == 0.0 and row["has_association"] is False


def test_evidence_id_and_what_text(net):
    row = run_one("NIRAPARIB", "THROMBOCYTOPENIA")[0]["pairs"][0]
    assert row["evidence"]["id"] == "omics:opentargets@26.09:NIRAPARIB:thrombocytopenia"
    what = row["evidence"]["what"]
    for piece in ("PARP1", "PARP2", "HP_0001873", "0.0125", "2026-09-28", "Open Targets Platform 26.09",
                  "개별 사례", "라벨 기재 예측"):
        assert piece in what


def test_failed_association_is_none_not_zero(monkeypatch, tmp_path):
    fake = FakeNet(assoc={"ENSG00000143799": ASSOC["ENSG00000143799"]})   # PARP2 호출은 실패합니다
    monkeypatch.setattr(op, "_send", fake)
    monkeypatch.setenv(op.CACHE_ENV, str(tmp_path))
    row = run_one("NIRAPARIB", "THROMBOCYTOPENIA")[0]["pairs"][0]
    parp2 = next(a for a in row["associations"] if a["ensembl"] == "ENSG00000129484")
    assert parp2["score"] is None and parp2["score_no_literature"] is None
    assert "HTTP 500" in parp2["error"]
    assert row["max_score"] == 0.0125 and row["incomplete"] is True
    assert not list((tmp_path / "opentargets").glob("*.tmp"))


def test_failed_search_leaves_everything_none(monkeypatch, tmp_path):
    fake = FakeNet(fail_ops={"DrugSearch"})
    monkeypatch.setattr(op, "_send", fake)
    monkeypatch.setenv(op.CACHE_ENV, str(tmp_path))
    row = run_one("NIRAPARIB", "THROMBOCYTOPENIA")[0]["pairs"][0]
    assert row["has_target"] is None and row["n_targets"] is None
    assert row["max_score"] is None and row["has_association"] is None
    assert "HTTP 503" in row["drug_resolution"]["error"]


def test_cache_replays_without_network(net, tmp_path):
    first, f1 = run_one("NIRAPARIB", "THROMBOCYTOPENIA")
    assert f1.http_calls == 6            # meta, 약 검색, 기전, 질환 검색, 표적 둘입니다
    n = len(net.calls)
    second, f2 = run_one("NIRAPARIB", "THROMBOCYTOPENIA", dry_run=True)
    assert len(net.calls) == n and f2.http_calls == 0
    assert second["pairs"][0]["max_score"] == first["pairs"][0]["max_score"]
    assert second["meta"]["data_version"] == "26.09"
    for rec in second["pairs"][0]["requests"]:
        assert rec["from_cache"] and Path(rec["cache_path"]).exists()


def test_dry_run_without_cache_records_not_cached(net):
    row = run_one("NIRAPARIB", "THROMBOCYTOPENIA", dry_run=True)[0]["pairs"][0]
    assert net.calls == []
    assert row["has_target"] is None and "not_cached" in row["drug_resolution"]["error"]


def test_refset_pairs_are_deduplicated(tmp_path):
    import gzip
    path = tmp_path / "r.json.gz"
    rows = [{"drug": "A", "pt": "x"}, {"drug": "A", "pt": "x"}, {"drug": "B", "pt": "y"}]
    path.write_bytes(gzip.compress(json.dumps({"meta": {}, "rows": rows}).encode()))
    assert op.load_refset_pairs(path) == [("A", "x"), ("B", "y")]


# ---------------------------------------------------------------- 참조 세트 묶음 모드


def test_pt_batch_query_and_parsing():
    query, variables = op.pt_batch_query(["thrombocytopenia", "neutrophil count decreased", "nope"])
    assert variables == {"q0": "thrombocytopenia", "q1": "neutrophil count decreased", "q2": "nope"}
    assert "q2: search(queryString: $q2" in query and "$q1: String!" in query
    data = {"q0": {"hits": DISEASE_SEARCH["thrombocytopenia"]},
            "q1": {"hits": DISEASE_SEARCH["neutrophil count decreased"]},
            "q2": {"hits": []}}
    terms = op.parse_pt_batch(data, ["thrombocytopenia", "neutrophil count decreased", "nope"], None)
    assert terms["thrombocytopenia"]["mapped"]["id"] == "HP_0001873"
    assert terms["thrombocytopenia"]["match"] == "label"
    assert terms["neutrophil count decreased"]["mapped"] is None
    assert terms["neutrophil count decreased"]["match"] == "none"
    assert terms["nope"]["match"] == "no_hits"
    failed = op.parse_pt_batch(None, ["a", "b"], "HTTP 503: x")
    assert all(t["match"] == "error" and t["mapped"] is None for t in failed.values())
    missing = op.parse_pt_batch({"q0": {"hits": []}}, ["a", "b"], None)
    assert missing["b"]["error"] == "alias_missing"


def _dump_page(all_rows, nolit_rows, count_all=None, count_nolit=None):
    return {"all": {"count": count_all if count_all is not None else len(all_rows), "rows": all_rows},
            "noLiterature": {"count": count_nolit if count_nolit is not None else len(nolit_rows),
                             "rows": nolit_rows}}


def test_dump_pages_join_by_disease_id_not_row_order():
    page0 = _dump_page([assoc_row("D1", 0.5, {"literature": 0.9, "animal_model": 0.2}),
                        assoc_row("D2", 0.3, {"literature": 0.4})],
                       [{"disease": {"id": "D3"}, "score": 0.1}, {"disease": {"id": "D1"}, "score": 0.25}],
                       count_all=3, count_nolit=3)
    page1 = _dump_page([assoc_row("D3", 0.05, {"genetic_association": 0.07})],
                       [{"disease": {"id": "D2"}, "score": 0}], count_all=3, count_nolit=3)
    merged = op.merge_dump_pages([page0, page1])
    by = merged["by_disease"]
    assert by["D1"] == {"score": 0.5, "no_literature_local": 0.2, "no_literature_api": 0.25}
    assert by["D2"]["no_literature_api"] == 0.0 and by["D2"]["no_literature_local"] == 0.0
    assert by["D3"]["no_literature_api"] == 0.1 and by["D3"]["no_literature_local"] == 0.07
    assert merged["n_rows"] == 3 and merged["datatype_scores_in_dump"] is True


def test_target_dump_pages_until_count(monkeypatch, tmp_path):
    rows = [assoc_row(f"D{i}", 0.1, {"literature": 0.1}) for i in range(5)]
    seen = []

    def fake(url, body):
        v = json.loads(body)["variables"]
        seen.append(v["page"])
        lo = v["page"]["index"] * v["page"]["size"]
        chunk = rows[lo:lo + v["page"]["size"]]
        return {"data": {"target": _dump_page(chunk, [], count_all=5, count_nolit=0)}}
    monkeypatch.setattr(op, "_send", fake)
    monkeypatch.setenv(op.CACHE_ENV, str(tmp_path))
    dump = op.fetch_target_dump(fetcher(), {"symbol": "S", "ensembl": "E1"}, page_size=2)
    assert [p["index"] for p in seen] == [0, 1, 2]
    assert dump["pages"] == 3 and dump["n_rows"] == 5 and dump["pagination_ok"] is True
    assert dump["by_disease"]["D4"]["no_literature_api"] == 0.0


def test_refset_row_aggregation():
    drug = {"targets": [{"symbol": "A", "ensembl": "E1"}, {"symbol": "B", "ensembl": "E2"}]}
    term = {"mapped": {"id": "D1"}}
    dumps = {"E1": {"by_disease": {"D1": {"score": 0.2, "no_literature_api": 0.0,
                                          "no_literature_local": 0.0}}},
             "E2": {"by_disease": {"D1": {"score": 0.1, "no_literature_api": 0.05,
                                          "no_literature_local": 0.3}}}}
    agg = op.aggregate_refset_row(drug, term, dumps)
    assert agg["n_targets"] == 2 and agg["mapped"] == "D1"
    assert agg["max_score"] == 0.2 and agg["max_score_no_literature_api"] == 0.05
    assert agg["max_score_no_literature_local"] == 0.3 and agg["has_association"] is True
    absent = op.aggregate_refset_row(drug, {"mapped": {"id": "D9"}}, dumps)
    assert absent["max_score"] == 0.0 and absent["has_association"] is False
    failed = op.aggregate_refset_row(drug, term, {"E1": dumps["E1"], "E2": {"by_disease": None}})
    assert failed["incomplete"] is True and failed["max_score"] == 0.2
    unmapped = op.aggregate_refset_row(drug, {"mapped": None}, dumps)
    assert unmapped["max_score"] is None and unmapped["has_association"] is None
    no_target = op.aggregate_refset_row({"targets": []}, term, dumps)
    assert no_target["has_target"] is False and no_target["max_score"] is None
    unresolved = op.aggregate_refset_row({"targets": None}, term, dumps)
    assert unresolved["has_target"] is None and unresolved["n_targets"] is None


def test_share_by_class_counts_scored_rows_only():
    rows = [{"class": "positive", "max_score": 0.2, "has_association": True,
             "max_score_no_literature_api": 0.1, "max_score_no_literature_local": 0.0},
            {"class": "positive", "max_score": 0.0, "has_association": False,
             "max_score_no_literature_api": 0.0, "max_score_no_literature_local": 0.0},
            {"class": "positive", "max_score": None, "has_association": None,
             "max_score_no_literature_api": None, "max_score_no_literature_local": None}]
    share = op.share_by_class(rows)["positive"]
    assert share["n_scored"] == 2
    assert share["has_association"] == {"n": 1, "share": 0.5}
    assert share["no_literature_api_gt0"]["n"] == 1 and share["no_literature_local_gt0"]["n"] == 0
