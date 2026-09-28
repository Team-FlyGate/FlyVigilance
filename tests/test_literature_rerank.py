"""Nemotron 리랭커 응답 파싱과 PubMed 순서 폴백을 검증합니다. 네트워크, NVIDIA 키, Jev 는 쓰지 않습니다."""
import asyncio

import pytest

from _fv import clients, config, literature


def _art(pmid, title):
    return (f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><ArticleTitle>{title}</ArticleTitle>"
            f"<Abstract><AbstractText>Abstract {pmid}.</AbstractText></Abstract>"
            f"<PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>"
            f"<Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation></PubmedArticle>")


PMIDS = [str(100 + i) for i in range(10)]
# efetch 는 PubMed 관련도 순서와 다르게 돌려줄 수 있으므로 일부러 뒤집어 둡니다
XML = "<PubmedArticleSet>" + "".join(_art(p, f"Title {p}") for p in reversed(PMIDS)) + "</PubmedArticleSet>"


@pytest.fixture
def pubmed(monkeypatch):
    """PubMed 를 가짜로 바꾸고, 재정렬을 켠 상태(가짜 키)로 둡니다. 요청한 retmax 를 기록합니다."""
    seen = {}

    async def fake_pubmed(drug, pt, client, retmax=5):
        seen["retmax"] = retmax
        ids = PMIDS[:retmax]
        return {"query": "q", "count": len(PMIDS), "pmids": ids, "ids": [f"pubmed:{i}" for i in ids]}

    async def fake_get_json(client, url, params, spacer, key=None, retries=4):
        return 200, XML
    monkeypatch.setattr(literature.evidence, "pubmed", fake_pubmed)
    monkeypatch.setattr(literature.evidence, "get_json", fake_get_json)
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "test-key")
    monkeypatch.delenv("FV_CACHE_DIR", raising=False)
    monkeypatch.delenv("FV_RERANK", raising=False)
    literature._RERANK_MEMO.clear()
    return seen


def _fake_rerank(scores, calls=None):
    async def f(query, passages, client, timeout=4.0):
        if calls is not None:
            calls.append((query, len(passages)))
        return {"scores": scores[:len(passages)], "model": config.MODEL_RERANK, "latency_ms": 12.0}
    return f


# ---------------------------------------------------------------- 응답 파싱
def test_parse_rerank_restores_input_order():
    body = {"rankings": [{"index": 2, "logit": 3.5}, {"index": 0, "logit": -1.0}, {"index": 1, "logit": 0.25}]}
    assert clients.parse_rerank(body, 3) == [-1.0, 0.25, 3.5]


def test_parse_rerank_accepts_score_key():
    assert clients.parse_rerank({"rankings": [{"index": 0, "score": 0.9}]}, 1) == [0.9]


@pytest.mark.parametrize("body", [
    None, {}, {"rankings": None}, {"detail": "Gone"},
    {"rankings": [{"index": 0, "logit": 1.0}]},                                  # 한 편이 빠짐
    {"rankings": [{"index": 0, "logit": 1.0}, {"index": 0, "logit": 2.0}]},      # 색인 중복
    {"rankings": [{"index": 0, "logit": 1.0}, {"index": 5, "logit": 2.0}]},      # 범위 밖
    {"rankings": [{"index": 0, "logit": 1.0}, {"index": True, "logit": 2.0}]},   # bool 색인
    {"rankings": [{"index": 0, "logit": 1.0}, {"index": 1, "logit": "high"}]},   # 숫자가 아닌 점수
    {"rankings": [{"index": 0, "logit": 1.0}, {"index": 1, "logit": float("nan")}]},
])
def test_parse_rerank_rejects_malformed(body):
    with pytest.raises(ValueError):
        clients.parse_rerank(body, 2)


def test_top_by_score_breaks_ties_by_pubmed_order():
    assert literature.top_by_score([1.0, 5.0, 5.0, -2.0, 5.0], 3) == [1, 2, 4]


def test_query_and_passage_text():
    assert literature.rerank_drug("HYDROCHLOROTHIAZIDE\\OLMESARTAN MEDOXOMIL") == "hydrochlorothiazide and olmesartan medoxomil"
    q = literature.rerank_query("PEMBROLIZUMAB", "myocarditis")
    assert q.startswith("pembrolizumab-induced myocarditis:") and "adverse effect of pembrolizumab" in q
    assert literature.rerank_passage({"title": "T", "abstract": "A" * 5000}).startswith("T\nA") and \
        len(literature.rerank_passage({"title": "T", "abstract": "A" * 5000})) == 3000


# ---------------------------------------------------------------- read() 연동
def test_read_reranks_wider_pool(pubmed, monkeypatch):
    calls = []
    scores = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]    # 뒤쪽 PubMed 순위일수록 높게
    monkeypatch.setattr(clients, "nim_rerank", _fake_rerank(scores, calls))
    r = asyncio.run(literature.read("cytarabine", "rash", None, n=6, use_jev=False))
    assert pubmed["retmax"] == literature.RERANK_POOL
    assert calls == [(literature.rerank_query("cytarabine", "rash"), 10)]
    assert r["order"] == "nemotron_rerank" and r["rerank"]["order"] == "nemotron_rerank"
    assert r["rerank"]["candidates"] == 10 and r["rerank"]["model"] == config.MODEL_RERANK
    want = ["109", "108", "107", "106", "105", "104"]
    assert r["pmids"] == want and [a["pmid"] for a in r["articles"]] == want
    assert [a["pubmed_rank"] for a in r["articles"]] == [10, 9, 8, 7, 6, 5]
    assert r["articles"][0]["rerank_score"] == 9.0
    assert r["ids"] == [a["id"] for a in r["articles"]] and len(r["ids"]) == 6
    assert r["summary"]["read"] == 6


def test_read_falls_back_to_pubmed_on_error(pubmed, monkeypatch):
    async def boom(query, passages, client, timeout=4.0):
        raise ValueError("bad rerank index 7")
    monkeypatch.setattr(clients, "nim_rerank", boom)
    r = asyncio.run(literature.read("cytarabine", "rash", None, n=6, use_jev=False))
    assert r["order"] == "pubmed" and r["rerank"]["rerank_error"] == "ValueError"
    assert r["pmids"] == PMIDS[:6] and [a["pmid"] for a in r["articles"]] == PMIDS[:6]
    assert [a["pubmed_rank"] for a in r["articles"]] == [1, 2, 3, 4, 5, 6]
    assert all(a["rerank_score"] is None for a in r["articles"])


def test_read_falls_back_on_timeout(pubmed, monkeypatch):
    async def slow(query, passages, client, timeout=4.0):
        await asyncio.sleep(5)
    monkeypatch.setattr(clients, "nim_rerank", slow)
    monkeypatch.setattr(literature, "RERANK_TIMEOUT", 0.01)
    r = asyncio.run(literature.read("cytarabine", "rash", None, n=6, use_jev=False))
    assert r["order"] == "pubmed" and r["rerank"]["rerank_error"] == "TimeoutError"
    assert r["pmids"] == PMIDS[:6]


def test_read_rejects_score_length_mismatch(pubmed, monkeypatch):
    async def short(query, passages, client, timeout=4.0):
        return {"scores": [1.0, 2.0], "latency_ms": 1.0}
    monkeypatch.setattr(clients, "nim_rerank", short)
    r = asyncio.run(literature.read("cytarabine", "rash", None, n=6, use_jev=False))
    assert r["order"] == "pubmed" and r["rerank"]["rerank_error"] == "LengthMismatch"


@pytest.mark.parametrize("off", ["env", "nokey"])
def test_read_without_rerank_keeps_pubmed_top_n(pubmed, monkeypatch, off):
    if off == "env":
        monkeypatch.setenv("FV_RERANK", "0")
    else:
        monkeypatch.setattr(config, "NVIDIA_API_KEY", None)

    async def never(*a, **k):
        raise AssertionError("reranker must not be called")
    monkeypatch.setattr(clients, "nim_rerank", never)
    r = asyncio.run(literature.read("cytarabine", "rash", None, n=6, use_jev=False))
    assert pubmed["retmax"] == 6
    assert r["order"] == "pubmed" and "rerank_error" not in r["rerank"]
    assert r["pmids"] == PMIDS[:6]


def test_small_pool_skips_rerank(pubmed, monkeypatch):
    async def never(*a, **k):
        raise AssertionError("reranker must not be called")
    monkeypatch.setattr(clients, "nim_rerank", never)
    r = asyncio.run(literature.read("cytarabine", "rash", None, n=12, use_jev=False))
    assert r["order"] == "pubmed" and len(r["articles"]) == 10


def test_rerank_scores_are_memoized(pubmed, monkeypatch):
    calls = []
    monkeypatch.setattr(clients, "nim_rerank", _fake_rerank([float(i) for i in range(10)], calls))
    a = asyncio.run(literature.read("cytarabine", "rash", None, n=6, use_jev=False))
    b = asyncio.run(literature.read("cytarabine", "rash", None, n=6, use_jev=False))
    assert len(calls) == 1 and a["pmids"] == b["pmids"]
    assert a["rerank"]["cached"] is False and b["rerank"]["cached"] is True
