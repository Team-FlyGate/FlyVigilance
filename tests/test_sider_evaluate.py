"""SIDER 지표 검증(pipeline/refsets/sider_evaluate.py)을 네트워크 없이 검증합니다.

손으로 셀 수 있는 작은 경우로 문턱 한 곳의 민감도와 특이도, NaN 행 처리, 고정 규칙과 세 기준 동시 충족,
귀무 뒤섞기의 시드 재현성, metrics.json 병합과 evidence.metric_catalog 의 근거 ID 를 봅니다.
AUC·ROC 자체는 test_pvstats.py 가 봅니다.
"""
import importlib.util
import json
import pathlib
import sys

import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline/refsets"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline/refsets" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sev = _load("sider_evaluate")


def test_sensitivity_specificity_at_threshold():
    r = sev.at_threshold(np.array([3.0, 2.0, 0.5, 2.5, 1.0, 0.1]), np.array([1, 1, 1, 0, 0, 0]), 2.0)
    assert (r["tp"], r["fn"], r["fp"], r["tn"]) == (2, 1, 1, 2)
    assert r["sens"] == 2 / 3 and r["spec"] == 2 / 3 and r["ppv"] == 2 / 3


def test_auc_wrapper_matches_hand_count():
    y = np.array([True, True, False, False])
    assert sev.auc(np.array([3.0, 2.0, 2.0, 1.0]), y) == 0.875   # 넷 중 셋은 이기고 하나는 동점
    assert sev.auc(np.array([np.inf, 1.0, 0.5, 0.2]), y) == 1.0   # 무한대는 가장 큰 값입니다


def _frame() -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(0)
    for d in ["A", "B", "C", "D"]:
        for k in range(8):
            label = k < 3
            rows.append({"drug": d, "pt": f"pt{k}", "class": "positive" if label else "negative", "label": label, "a": 3 + k})
    f = pd.DataFrame(rows)
    for m in sev.METRICS:
        f[m] = rng.normal(size=len(f)) + f["label"] * 1.0
    f.loc[0, "ic"] = np.nan
    f["evans_signal"] = f["prr"] > 0.5
    f["ror_signal"] = f["ror"] > 0.5
    f["ic_signal"] = True
    return f


def test_null_shuffle_reproducible_and_positive_sized():
    f = _frame()
    first = sev.null_positive_masks(f, seed=11, repeats=3)
    again = sev.null_positive_masks(f, seed=11, repeats=3)
    for x, y in zip(first, again):
        assert np.array_equal(x["mask"], y["mask"])
        assert x["n_null_positive"] == int(f["label"].sum())
    assert [x["seed"] for x in first] == [11, 12, 13]


def test_evaluate_counts_nan_and_fixed_rules():
    f = _frame()
    res = sev.evaluate(f, seed=5, repeats=4)
    assert res["metrics"]["ic"]["n_nan_excluded"] == 1 and res["metrics"]["ic"]["n_used"] == len(f) - 1
    assert res["metrics"]["prr"]["n_nan_excluded"] == 0
    assert [c["threshold"] for c in res["metrics"]["prr"]["conventional"]] == [1.0, 2.0, 3.0]
    y = f["label"].astype(int).tolist()
    assert res["fixed_rules"]["evans_signal"]["sens"] == sev.pvstats.sens_spec(f["prr"].gt(0.5).tolist(), y)["sens"]
    triple = (f["prr"] > 0.5) & (f["ror"] > 0.5)
    assert res["fixed_rules"]["triple"]["tp"] == sev.pvstats.sens_spec(triple.tolist(), y)["tp"]
    assert res["null"]["auc"]["prr"]["n"] == 4
    assert set(res["per_drug_auc"]["prr"]["by_drug"]) == {"A", "B", "C", "D"}


def _res(asof="2026Q2"):
    f = _frame()
    return {"warehouse_asof": asof, "refset_meta": {"n_drugs": 4}, **sev.evaluate(f, seed=5, repeats=2)}


def test_metrics_json_merge_keeps_other_refsets_and_feeds_metric_catalog(tmp_path, monkeypatch):
    path = tmp_path / "metrics.json"
    omop = {"sens": 0.55, "spec": 0.92, "ppv": 0.83, "tp": 90, "fp": 18, "tn": 205, "fn": 74, "n": 387}
    path.write_text(json.dumps({"asof": "2026Q2", "rules": {"evans": {"OMOP": omop}, "triple": {"OMOP": omop}}}))
    assert sev.update_metrics_json(_res(), "docs/images/x.png", path) is True
    m = json.loads(path.read_text())
    assert m["rules"]["triple"]["OMOP"] == omop
    assert set(m["rules"]["triple"]["sider-pilot"]) == {"sens", "spec", "ppv", "tp", "fp", "tn", "fn", "n"}
    assert m["sider"]["figure"] == "docs/images/x.png" and set(m["sider"]["auc"]) == set(sev.METRICS)

    from _fv import evidence
    monkeypatch.setattr(evidence, "DATA", tmp_path)
    evidence._metrics.cache_clear()
    try:
        ids = [c["id"] for c in evidence.metric_catalog()]
    finally:
        evidence._metrics.cache_clear()
    assert ids == ["metric:triple:OMOP@2026Q2", "metric:triple:sider-pilot@2026Q2"]


def test_metrics_json_other_asof_writes_summary_only(tmp_path):
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps({"asof": "2025Q4", "rules": {"triple": {}}}))
    assert sev.update_metrics_json(_res("2026Q2"), None, path) is False
    m = json.loads(path.read_text())
    assert "sider-pilot" not in m["rules"]["triple"] and m["sider"]["asof"] == "2026Q2"


def test_finite_drops_nan_and_numpy_types():
    assert sev.finite({"a": [np.float64(1.5), float("inf"), np.int64(3)], "b": float("nan")}) == {"a": [1.5, None, 3], "b": None}
