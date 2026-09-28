"""PV BYO 정책 가드를 네트워크 없이 검증합니다: 응답 읽기, 두 가드 결합, 정책 JSON 스키마, 산출물 동기화."""
import asyncio
import importlib.util
import json
import pathlib

import pytest

from _fv import assess, clients, config

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "skills/pv-guardrail-policy"


def _policy():
    return json.loads((POLICY_DIR / "policy_taxonomy.json").read_text())


# ---------------------------------------------------------------- 응답 읽기
def test_policy_guard_reads_pv_category_by_id_and_name():
    v = assess.parse_policy_guard("User Safety: unsafe\nSafety Categories: PV-2")
    assert (v["safe"], v["pv"], v["rule"]) == (False, ["PV-2"], "R1")
    # 모델은 번호 없이 이름만 내기도 합니다
    v = assess.parse_policy_guard("User Safety: unsafe\nSafety Categories: Incidence Estimate from Spontaneous Reports")
    assert (v["pv"], v["rule"]) == (["PV-3"], "R2")
    v = assess.parse_policy_guard("User Safety: unsafe\nSafety Categories: PV-1 Individual Treatment Advice, PV4")
    assert (v["pv"], v["rule"]) == (["PV-1", "PV-4"], "R11")


def test_policy_guard_v2_only_category_and_safe():
    v = assess.parse_policy_guard("User Safety: unsafe\nSafety Categories: Unauthorized Advice")
    assert (v["safe"], v["pv"], v["rule"], v["categories"]) == (False, [], None, "Unauthorized Advice")
    v = assess.parse_policy_guard("User Safety: safe")
    assert (v["safe"], v["pv"]) == (True, [])


def test_policy_guard_strips_think_trace_and_rejects_unreadable():
    raw = "<think>\nUser Safety: safe would be wrong here.\n</think>User Safety: unsafe\nSafety Categories: PV-1"
    assert assess.parse_policy_guard(raw)["safe"] is False
    assert assess.parse_policy_guard("")["safe"] is None
    assert assess.parse_policy_guard("I cannot classify this.")["safe"] is None


# ---------------------------------------------------------------- 두 가드 결합
def test_combine_guards_or_and_fail_closed():
    ok, bad, err = {"safe": True}, {"safe": False, "categories": "PV-3", "pv": ["PV-3"], "rule": "R2"}, {"safe": None}
    assert assess.combine_guards(ok, ok)["safe"] is True
    assert assess.combine_guards(ok, bad)["safe"] is False
    assert assess.combine_guards({"safe": False, "categories": "Unauthorized Advice"}, ok)["safe"] is False
    assert assess.combine_guards(ok, err)["safe"] is None      # 한쪽 장애는 통과가 아니라 사람 확인
    assert assess.combine_guards(err, ok)["safe"] is None
    assert assess.combine_guards(err, bad)["safe"] is False    # 다른 쪽이 걸었으면 걸린 것
    c = assess.combine_guards(ok, bad)
    assert [f["guard"] for f in c["fired"]] == ["pv_policy"] and c["pv"] == ["PV-3"]


def test_guard_claims_records_which_guard_fired(monkeypatch):
    async def fake_default(text, timeout_s=20.0):
        if "stop" in text:
            return {"safe": False, "categories": "Unauthorized Advice", "model": "safety-guard-8b-v3"}
        return {"safe": True, "model": "safety-guard-8b-v3"}

    async def fake_policy(text, timeout_s=20.0, think=False):
        if "timeout" in text:
            return {"safe": None, "error": "pv-policy: ReadTimeout"}
        if "PRR" in text:
            return assess.parse_policy_guard("User Safety: unsafe\nSafety Categories: PV-2") | {"model": "ncs35"}
        if "stop" in text:
            return assess.parse_policy_guard("User Safety: unsafe\nSafety Categories: PV-1") | {"model": "ncs35"}
        return {"safe": True, "pv": [], "model": "ncs35"}

    monkeypatch.setattr(assess, "guard", fake_default)
    monkeypatch.setattr(assess, "policy_guard", fake_policy)
    claims = [{"id": "c1", "text": "A PRR of 9 proves causation."},
              {"id": "c2", "text": "The patient should stop the drug."},
              {"id": "c3", "text": "The case reports hepatic failure."},
              {"id": "c4", "text": "timeout please"}]
    g = asyncio.run(assess.guard_claims(claims, timeout_s=5))
    assert g["safe"] is False and g["flagged"] == ["c1", "c2"] and g["unchecked"] == ["c4"]
    assert g["by_guard"]["safety_guard"]["flagged"] == ["c2"]
    assert g["by_guard"]["pv_policy"]["flagged"] == ["c1", "c2"] and g["by_guard"]["pv_policy"]["unchecked"] == ["c4"]
    issues = {i["claim"]: i for i in assess.guard_issues(g)}
    assert issues["c1"]["rule"] == "R1" and issues["c1"]["guards"] == ["pv_policy"]
    assert issues["c2"]["rule"] == "R11" and issues["c2"]["guards"] == ["safety_guard", "pv_policy"]
    assert all(i["detail"].startswith("NVIDIA safety guard") for i in issues.values())  # critic_probe 의 출처 판별과 호환


def test_guard_issues_backward_compatible_without_fired():
    # 예전 형태의 가드 결과(fired 없음)도 R11 사유로 읽습니다
    assert assess.guard_issues({"flagged": ["c1"], "categories": "Unauthorized Advice"})[0]["rule"] == "R11"


def test_nim_chat_forwards_template_kwargs(monkeypatch):
    sent = {}

    class Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "User Safety: safe"}}], "usage": {}}

    class Client:
        async def post(self, url, json=None, headers=None, timeout=None):
            sent.update(json)
            return Resp()

    monkeypatch.setattr(config, "NVIDIA_API_KEY", "test-key")
    out = asyncio.run(clients.nim_chat([{"role": "user", "content": "x"}], ["m"], client=Client(),
                                       template_kwargs={"custom_policy": "P", "request_categories": "/categories"}))
    assert out["content"] == "User Safety: safe"
    assert sent["chat_template_kwargs"] == {"enable_thinking": False, "custom_policy": "P", "request_categories": "/categories"}


# ---------------------------------------------------------------- 정책 산출물
def test_policy_json_validates_against_skill_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((POLICY_DIR / "schema/policy_json_schema.json").read_text())
    jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker()).validate(_policy())


def test_policy_has_pv_categories_matching_runtime_map():
    p = _policy()
    pv = {c["pv_id"]: c for c in p["categories"] if c.get("pv_id")}
    assert set(pv) == set(assess.PV_CATEGORIES)
    for pid, (name, rule) in assess.PV_CATEGORIES.items():
        assert pv[pid]["display_name"] == f"{pid} {name}" and pv[pid]["flygate_rule"] == rule and pv[pid]["custom"]
    assert assess.PV_POLICY_NAME == f"{p['policy_name']} v{p['version']}"
    # 비협상 하한: S7 은 S4 로 남고 허용 목록이 S7 을 풀지 않습니다
    s7 = next(c for c in p["categories"] if c.get("sn_label") == "S7")
    assert s7["severity"] == "S4"


def test_rendered_prompt_and_md_are_in_sync():
    spec = importlib.util.spec_from_file_location("render_policy", POLICY_DIR / "render_policy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(check=True) == 0, "policy_taxonomy.json 을 고친 뒤 render_policy.py 를 다시 돌리십시오"
    prompt = assess.pv_policy()
    assert prompt == (POLICY_DIR / "system_prompt.txt").read_text()
    for c in _policy()["categories"]:
        assert c["display_name"] in prompt


def test_eval_set_shape():
    ev = json.loads((POLICY_DIR / "evals/evals.json").read_text())
    assert len(ev) == 50 and len({e["id"] for e in ev}) == 50
    for pid in assess.PV_CATEGORIES:
        rows = [e for e in ev if e["category"] == pid]
        assert len(rows) == 10 and sum(e["expected_label"] == "unsafe" for e in rows) == 6


def test_summarize_issues_merges_judge_and_guard():
    from _fv import assess
    issues = [{"claim": "c3", "tier": 3, "source": "judge", "rule": "R1"},
              {"claim": "c3", "tier": 3, "source": "guard", "rule": "R1"},
              {"claim": "c5", "tier": 1, "rule": "unknown_evidence"}]
    s = {r["claim"]: r for r in assess.summarize_issues(issues)}
    assert s["c3"]["rules"] == ["R1"] and s["c3"]["caught_by"] == ["judge", "guard"]
    assert s["c5"]["caught_by"] == ["T1"]
