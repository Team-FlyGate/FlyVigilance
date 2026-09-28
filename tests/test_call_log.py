"""NVIDIA 호출 기록기(FV_CALL_LOG)가 메타데이터만 남기고 키·헤더·본문은 남기지 않는지 확인합니다. 네트워크 없이 돕니다."""
import asyncio
import json

import httpx
import pytest

from _fv import calllog, clients, config, docking

SECRET = "nvapi-TESTSECRET-0123456789abcdef"
PATIENT = "PATIENT-FREE-TEXT 72세 여성 김OO 님이 복용 후 발진"
ANSWER = "MODEL-ANSWER-BODY should never be logged"


@pytest.fixture
def log(tmp_path, monkeypatch):
    path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FV_CALL_LOG", str(path))
    monkeypatch.setattr(config, "NVIDIA_API_KEY", SECRET)
    return path


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def assert_clean(path):
    raw = path.read_text()
    for bad in (SECRET, "nvapi-", "Bearer", "Authorization", "authorization", PATIENT, "PATIENT-FREE-TEXT", ANSWER):
        assert bad not in raw, bad


def test_off_by_default_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("FV_CALL_LOG", raising=False)
    assert not calllog.enabled()
    calllog.record(url="https://integrate.api.nvidia.com/v1/chat/completions", model="m", purpose="p")
    assert list(tmp_path.iterdir()) == []


def test_chat_logs_metadata_only(log):
    seen = {}

    def handle(req):
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, headers={"nvcf-reqid": "req-abc-123"},
                              json={"id": "chatcmpl-1", "choices": [{"message": {"content": ANSWER}}],
                                    "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as c:
            return await clients.nim_chat([{"role": "user", "content": PATIENT}], ["nvidia/nemotron-3-super-120b-a12b"],
                                          client=c, json_mode=True, purpose="System-2 assessment memo")
    out = asyncio.run(go())
    assert out["content"] == ANSWER and seen["auth"] == f"Bearer {SECRET}"  # 호출 자체는 키를 씁니다
    (r,) = rows(log)
    assert r["service"] == "build.nvidia.com NIM" and r["endpoint"] == "/v1/chat/completions"
    assert r["model"] == "nvidia/nemotron-3-super-120b-a12b" and r["purpose"] == "System-2 assessment memo"
    assert r["http_status"] == 200 and r["nvcf_reqid"] == "req-abc-123" and r["json_mode"] is True
    assert r["usage"] == {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
    assert r["bytes_out"] > 0 and r["bytes_in"] > 0 and r["cache_hit"] is False and r["error"] is None
    assert r["code_path"].startswith("tests/test_call_log.py:")
    assert_clean(log)


def test_chat_failure_and_fallback_are_logged(log):
    def handle(req):
        body = json.loads(req.content)
        if body["model"] == "a":
            return httpx.Response(503, headers={"nvcf-reqid": "req-503"}, text=f"overloaded {PATIENT}")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as c:
            return await clients.nim_chat([{"role": "user", "content": PATIENT}], ["a", "b"], client=c)
    asyncio.run(go())
    rs = rows(log)
    assert [(r["model"], r["http_status"], r["error"]) for r in rs] == [("a", 503, "HTTP503"), ("a", 503, "HTTP503"), ("b", 200, None)]
    assert rs[-1]["fallback_of"] == "a"
    assert_clean(log)


def test_rerank_and_embed(log):
    def handle(req):
        if req.url.path.endswith("/reranking"):
            return httpx.Response(200, headers={"nvcf-reqid": "rr-1"}, json={"rankings": [{"index": 0, "logit": 1.0}], "usage": {"prompt_tokens": 5, "total_tokens": 5}})
        return httpx.Response(200, headers={"nvcf-reqid": "em-1"}, json={"data": [{"index": 0, "embedding": [0.1]}]})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as c:
            await clients.nim_rerank("q", [PATIENT], c)
            await clients.nim_embed_many([PATIENT], "passage", c)
    asyncio.run(go())
    rr, em = rows(log)
    assert rr["service"].startswith("NVIDIA Retrieval NIM") and rr["nvcf_reqid"] == "rr-1" and rr["n_inputs"] == 1
    assert rr["purpose"].startswith("literature rerank") and rr["usage"] == {"prompt_tokens": 5, "total_tokens": 5}
    assert em["endpoint"] == "/v1/embeddings" and em["input_type"] == "passage" and em["nvcf_reqid"] == "em-1"
    assert_clean(log)


def test_async_202_flow_records_request_id(log, tmp_path):
    p = tmp_path / "protein.pdb"
    p.write_text("ATOM      1  N   ALA A   1      0.0 0.0 0.0\n")

    def handle(req):
        if req.method == "POST":
            return httpx.Response(202, headers={"nvcf-reqid": "job-9"})
        return httpx.Response(200, json={"status": "success", "ligand_positions": ["pose\nM  END\n$$$$"], "position_confidence": [0.8]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as c:
        out = docking.execute(api_key=SECRET, protein_path=p, smiles="CCO", output_root=tmp_path / "runs", poll_interval=0, client=c)
    assert out["status"] == "completed"
    (r,) = rows(log)
    assert r["service"].startswith("BioNeMo NIM") and r["endpoint"] == "/v1/biology/mit/diffdock"
    assert r["nvcf_reqid"] == "job-9" and r["polls"] == 1 and r["http_status"] == 200 and r["error"] is None
    assert r["code_path"] == "api/_fv/docking.py:execute"
    assert_clean(log)


def test_extra_rejects_free_text_and_unknown_keys(log):
    calllog.record(url="https://health.api.nvidia.com/v1/biology/mit/boltz2/predict?key=x", model="mit/boltz2", purpose="t",
                   extra={"run_id": PATIENT, "template": "custom_policy", "prompt": PATIENT, "attempt": 1,
                          "response_id": f"Bearer {SECRET}"}, error=RuntimeError(PATIENT))
    (r,) = rows(log)
    assert "run_id" not in r and "prompt" not in r and "response_id" not in r
    assert r["template"] == "custom_policy" and r["attempt"] == 1 and r["error"] == "RuntimeError"
    assert r["endpoint"] == "/v1/biology/mit/boltz2/predict"  # 쿼리 문자열은 버립니다
    assert set(r) <= {"ts_utc", "service", "host", "endpoint", "model", "purpose", "http_status", "latency_ms", "nvcf_reqid",
                      "usage", "bytes_out", "bytes_in", "cache_hit", "error", "code_path"} | calllog.EXTRA_KEYS
    assert_clean(log)


def test_logging_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FV_CALL_LOG", str(tmp_path))  # 디렉터리라서 열 수 없습니다
    calllog.record(url="https://integrate.api.nvidia.com/v1/embeddings", model="m", purpose="p", response=object())
