"""SIDER Jev 비교 팔(pipeline/refsets/sider_jev.py)을 네트워크 없이 검증합니다.

가짜 Jev 호출이 정해 둔 확률을 돌려줍니다. blind 팔이 이름을 가리는지, dry-run 이 비용 세 줄을 찍고 네트워크로
나가지 않는지, --yes 없이는 멈추는지, 결과 JSON 의 모양, 실패한 호출이 None 으로 남는지, 캐시 재생,
clients.jev 응답과 오류를 기록 모양으로 바꾸는지를 봅니다.
"""
import asyncio
import importlib.util
import json
import pathlib
import sys

import httpx
import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline/refsets"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline/refsets" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mj = _load("sider_jev")
sev = mj.sev

# 두 약, 쌍 여덟 개. 양성 넷, 음성 넷. 확률은 양성이 대체로 높게 두되 하나는 뒤집어 AUC 가 1 이 아니게 합니다
PAIRS = [("DRUGX", "nausea", "positive", 0.9), ("DRUGX", "rash", "positive", 0.4),
         ("DRUGX", "fatigue", "negative", 0.5), ("DRUGX", "cough", "negative", 0.2),
         ("DRUGY", "nausea", "negative", 0.3), ("DRUGY", "headache", "positive", 0.8),
         ("DRUGY", "rash", "negative", 0.1), ("DRUGY", "cough", "positive", 0.7)]
PROB = {(d, p): pr for d, p, _, pr in PAIRS}


def _write_inputs(tmp: pathlib.Path) -> list[str]:
    refset = {"meta": {"name": "sider-pilot", "seed": 7, "null_repeats": 3, "warehouse": {"asof": "2026Q2"}},
              "rows": [{"drug": d, "pt": p, "class": c, "source": "t"} for d, p, c, _ in PAIRS]}
    (tmp / "refset.json").write_text(json.dumps(refset))
    rows = []
    for i, (d, p, c, _) in enumerate(PAIRS):
        rows.append({"drug": d, "pt": p, "class": c, "a": 3 + i, "b": 100, "c": 200, "d": 10000, "expected": 1.5,
                     "prr": 1.0 + i, "prr_lo": 0.5, "prr_hi": 2.0, "ror": 1.1 + i, "ror_lo": 0.6, "ror_hi": 2.1,
                     "chi2_yates": 4.0 + i, "ic": 0.1 * i, "ic025": -0.5 + 0.1 * i,
                     "evans_signal": False, "ror_signal": bool(i % 2), "ic_signal": False})
    pd.DataFrame(rows).to_parquet(tmp / "metrics.parquet", index=False)
    return ["--refset", str(tmp / "refset.json"), "--metrics-file", str(tmp / "metrics.parquet")]


def _fake_call(fail=None, seen=None):
    """state 의 이름으로 정해 둔 확률을 돌려주는 가짜 호출입니다. fail 에 든 쌍은 HTTP 500 을 돌려줍니다."""
    fail = fail or set()

    def call(state, qs, *, timeout):
        if seen is not None:
            seen.append(state)
        key = (state["drug"], state["reaction"])
        if key in fail:
            return {"status": 500, "seconds": 0.1, "error": "boom"}
        return {"status": 200, "seconds": 0.2, "request_id": f"r-{key[0]}-{key[1]}",
                "body": {"model": "jev-test-1", "usage": {"input_tokens": 120, "output_tokens": 5},
                         "answers": {"needs_human": {"noul": PROB[key]}}}}
    return call


def test_state_blind_swaps_names_and_keeps_numbers():
    row = {"drug": "DRUGX", "pt": "nausea", "a": 5, "b": 10, "c": 20, "d": 1000, "prr": 2.5, "ror": 2.7, "chi2_yates": 9.0}
    named = mj.pair_state(row, blind=False)
    blind = mj.pair_state(row, blind=True)
    assert (named["drug"], named["reaction"]) == ("DRUGX", "nausea")
    assert (blind["drug"], blind["reaction"]) == ("DRUG_A", "REACTION_1")
    assert blind["contingency_2x2"] == {"a": 5, "b": 10, "c": 20, "d": 1000}
    assert blind["measures"] == {"PRR": 2.5, "ROR": 2.7, "chi_square_yates": 9.0}
    assert blind["reports_with_this_reaction"] == 5
    assert "reaction_in_product_label" not in blind      # 라벨 여부는 맞힐 대상이라 보내지 않습니다


def test_dry_run_prints_cost_and_never_calls(tmp_path, capsys):
    args = _write_inputs(tmp_path)

    def boom(*_a, **_k):
        raise AssertionError("dry-run 에서 네트워크를 불렀습니다")

    out = tmp_path / "dry.json"
    assert mj.main(args + ["--dry-run", "--limit", "5", "--out", str(out)], call=boom) == 0
    text = capsys.readouterr().out
    assert "쌍 수: 5" in text and "/ 4 의 어림" in text and "예상 비용: USD" in text
    doc = json.loads(out.read_text())
    assert doc["dry_run"] is True and doc["n_pairs"] == 5 and doc["jev"] is None
    assert all(p["probability"] is None for p in doc["pairs"]) and doc["estimate"]["input_tokens"] > 0


def test_live_run_requires_yes(tmp_path, capsys):
    args = _write_inputs(tmp_path)
    calls: list = []
    assert mj.main(args + ["--out", str(tmp_path / "x.json")], call=_fake_call(seen=calls)) == 2
    assert not calls and "--yes" in capsys.readouterr().out
    assert not (tmp_path / "x.json").exists()


def test_live_schema_failed_call_none_and_auc_matches(tmp_path, monkeypatch):
    args = _write_inputs(tmp_path)
    monkeypatch.setattr(mj.config, "TYPESAFE_API_KEY", "fake")
    out, cache = tmp_path / "live.json", tmp_path / "cache.json"
    failed = ("DRUGY", "rash")
    assert mj.main(args + ["--yes", "--out", str(out), "--jev-cache", str(cache)], call=_fake_call(fail={failed})) == 0
    doc = json.loads(out.read_text())
    for key in ("arm", "blind", "question", "model_requested", "n_pairs", "n_with_probability", "estimate",
                "seconds", "jev", "pairs", "warehouse_asof", "seed"):
        assert key in doc
    assert doc["arm"] == "novel" and doc["n_pairs"] == 8 and doc["n_with_probability"] == 7
    rows = {(p["drug"], p["pt"]): p for p in doc["pairs"]}
    bad = rows[failed]
    assert bad["probability"] is None and bad["http_status"] == 500 and bad["error"] == "boom"
    good = rows[("DRUGX", "nausea")]
    assert good["probability"] == 0.9 and good["request_id"] == "r-DRUGX-nausea"
    assert good["model"] == "jev-test-1" and good["seconds"] == 0.2 and good["input_tokens"] == 120

    kept = [(d, p, c, pr) for d, p, c, pr in PAIRS if (d, p) != failed]
    s = np.array([pr for *_, pr in kept])
    y = np.array([c == "positive" for _, _, c, _ in kept])
    jev = doc["jev"]
    assert jev["auc"] == sev.auc(s, y) and jev["auc_inverted"] == sev.auc(-s, y)
    assert jev["n_used"] == 7 and jev["n_positive"] == 4 and jev["n_negative"] == 3
    assert jev["null"]["repeats"] == 3 and jev["null"]["auc"]["n"] >= 1
    assert set(jev["metrics_auc_same_rows"]) == set(sev.METRICS)
    assert jev["roc"][0] == [0.0, 0.0] and jev["roc"][-1] == [1.0, 1.0]

    # 성공 응답만 캐시에 남고, 다시 돌리면 캐시에서 재생해 네트워크를 부르지 않습니다
    assert len(json.loads(cache.read_text())) == 7
    calls: list = []
    assert mj.main(args + ["--dry-run", "--out", str(tmp_path / "replay.json"), "--jev-cache", str(cache)],
                   call=_fake_call(seen=calls)) == 0
    assert not calls and json.loads((tmp_path / "replay.json").read_text())["jev"]["auc"] == jev["auc"]


def test_blind_arm_sends_placeholders(tmp_path, monkeypatch):
    args = _write_inputs(tmp_path)
    monkeypatch.setattr(mj.config, "TYPESAFE_API_KEY", "fake")
    seen: list = []

    def call(state, qs, *, timeout):
        seen.append(state)
        return {"status": 200, "seconds": 0.1, "body": {"answers": {"needs_human": {"noul": 0.5}}}}

    assert mj.main(args + ["--arm", "blind", "--yes", "--limit", "3", "--out", str(tmp_path / "b.json")], call=call) == 0
    assert len(seen) == 3 and {(s["drug"], s["reaction"]) for s in seen} == {("DRUG_A", "REACTION_1")}


def test_jev_call_wraps_clients_jev(monkeypatch):
    sent = {}

    async def fake_jev(state, questions, client=None):
        sent["state"] = state
        return {"answers": {"needs_human": {"noul": 0.25}}, "usage": {"input_tokens": 9}, "model": "jev-x", "latency_ms": 150.0}

    monkeypatch.setattr(mj.clients, "jev", fake_jev)
    r = mj.jev_call({"drug": "D"}, mj.questions())
    assert sent["state"] == {"drug": "D"}                       # 문자열이 아니라 객체로 보냅니다
    assert r["status"] == 200 and r["seconds"] == 0.15 and mj.noul_probability(r) == 0.25 and mj.input_tokens(r) == 9

    async def refused(state, questions, client=None):
        req = httpx.Request("POST", "https://example.invalid")
        raise httpx.HTTPStatusError("x", request=req, response=httpx.Response(402, text="no credit", request=req))

    monkeypatch.setattr(mj.clients, "jev", refused)
    r = mj.jev_call({"drug": "D"}, mj.questions())
    assert r["status"] == 402 and r["error"] == "no credit" and mj.noul_probability(r) is None

    async def no_key(state, questions, client=None):
        raise mj.clients.NotConfigured("TYPESAFE_API_KEY")

    monkeypatch.setattr(mj.clients, "jev", no_key)
    assert mj.jev_call({}, mj.questions())["status"] == 0
    assert asyncio.iscoroutinefunction(no_key)
