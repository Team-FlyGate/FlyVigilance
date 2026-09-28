"""PubMed efetch XML 파싱과 문헌 요약 상태를 검증합니다. 네트워크와 Jev 는 쓰지 않습니다."""
import asyncio
import pathlib

from _fv import literature

XML = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>A case of X-induced rash</ArticleTitle>
<Abstract><AbstractText>We report a patient.</AbstractText></Abstract>
<PublicationTypeList><PublicationType>Case Reports</PublicationType><PublicationType>Journal Article</PublicationType></PublicationTypeList>
<Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""


def _art(pmid, title, abstract, ptypes, year="2021"):
    pts = "".join(f"<PublicationType>{p}</PublicationType>" for p in ptypes)
    return (f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><ArticleTitle>{title}</ArticleTitle>"
            f"<Abstract>{abstract}</Abstract><PublicationTypeList>{pts}</PublicationTypeList>"
            f"<Journal><JournalIssue><PubDate><Year>{year}</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation></PubmedArticle>")


# 세 편: 제목에 둘 다 나오는 증례보고(영국식 PT 와 미국식 철자), 초록에만 나오는 증례보고, 출판 유형이 없는 문헌
XML3 = ("<PubmedArticleSet>"
        + _art("1", "Cytarabine-associated acute myeloid leukemia: a case report", "<AbstractText>A woman developed it.</AbstractText>",
               ["Case Reports", "Journal Article"])
        + _art("2", "An unusual course", "<AbstractText>After cytarabine, acute myeloid leukaemia recurred.</AbstractText>",
               ["Case Reports"])
        + _art("3", "Outcomes of cytarabine in acute myeloid leukemia", "<AbstractText Label=\"RESULTS\" NlmCategory=\"RESULTS\">"
               "OR 2.1 (95% CI 1.4-3.0).</AbstractText>", ["Journal Article"])
        + "</PubmedArticleSet>")


def _patch_pubmed(monkeypatch, xml=XML3):
    async def fake_pubmed(drug, pt, client, retmax=5):
        return {"query": f'"{drug}"[tiab] AND "{pt}"[tiab]', "count": 3, "pmids": ["1", "2", "3"], "ids": ["pubmed:1", "pubmed:2", "pubmed:3"]}

    async def fake_get_json(client, url, params, spacer, key=None, retries=4):
        return 200, xml
    monkeypatch.setattr(literature.evidence, "pubmed", fake_pubmed)
    monkeypatch.setattr(literature.evidence, "get_json", fake_get_json)


def test_publication_type_decides_design_by_rule():
    a = literature.parse_efetch(XML)[0]
    assert a["pmid"] == "123" and a["design_rule"] == "case_report" and a["year"] == "2020"


def test_summary_status():
    # 관문·judged 키가 없는 옛 기록도 예전처럼 셉니다
    arts = [{"design": "meta_analysis", "supports": 0.1}, {"design": "case_control", "supports": 0.9},
            {"design": "case_report", "supports": 0.95}]
    s = literature.summarize(arts)
    assert s["analytic_status"] == "mixed" and s["analytic_read"] == 2 and s["anecdotal_supportive"] == 1
    assert literature.summarize([])["analytic_status"] == "no_analytic"


# ---------------------------------------------------------------- 약사 검토 반영
def test_design_question_is_identical_to_literature_eval_copy():
    # pipeline/bench/literature_eval.py 가 같은 문구·선택지로 0.920 을 냈습니다. 두 사본이 갈라지면 그 수치가 무효가 됩니다.
    q = literature.design_question(3)
    assert q == {"type": "choice", "instructions": "What is the study design of Article 3?", "criteria": literature.DESIGNS}
    assert list(literature.DESIGNS) == ["meta_analysis", "rct", "cohort", "case_control", "pharmacovigilance",
                                        "case_series", "case_report", "review", "preclinical", "other"]
    src = (pathlib.Path(__file__).resolve().parents[1] / "pipeline/bench/literature_eval.py").read_text()
    assert '"instructions": f"What is the study design of Article {i}?"' in src and '"criteria": literature.DESIGNS' in src
    # eval 입력인 abstract 문자열은 절 이름 없이 예전과 같게 둡니다
    a = literature.parse_efetch(XML3)[2]
    assert a["abstract"] == "OR 2.1 (95% CI 1.4-3.0)." and a["sections"][0][0] == "RESULTS"


def test_question_budget_and_design_blocks():
    cr = literature.parse_efetch(XML)[0]
    q = literature.questions(0, cr, "X", "rash")
    assert len(q) == 8 and "a0_design" not in q and "a0_strength" not in q
    assert {"a0_addresses", "a0_supports", "a0_context", "a0_onset", "a0_dechallenge", "a0_rechallenge", "a0_workup", "a0_scale"} == set(q)
    # 증례 항목은 모두 '초록에 없음'을 고를 수 있어야 합니다
    assert all("not_stated" in q[f"a0_{f}"]["criteria"] for f in literature.CASE_FIELDS)
    rct = {**cr, "design_rule": "rct", "title": "A trial"}
    assert {"a0_effect", "a0_patients", "a0_comparator", "a0_dose", "a0_strength"} <= set(literature.questions(0, rct, "X", "rash"))
    rev = {**cr, "design_rule": "review"}
    assert set(literature.questions(0, rev, "X", "rash")) == {"a0_addresses", "a0_supports", "a0_strength", "a0_context"}
    unk = {**cr, "design_rule": None, "pubtypes": ["Journal Article"], "title": "Outcomes in users"}
    q = literature.questions(0, unk, "X", "rash")
    assert len(q) == 8 and "a0_design" in q and {"a0_dechallenge", "a0_effect", "a0_patients"} <= set(q)
    pv = {**unk, "title": "Rash with X: a disproportionality analysis of FAERS"}
    assert literature.block_for(pv) == "comparative"
    for a in (cr, rct, rev, unk, pv, {**unk, "title": "A case of X-induced rash"}):
        assert len(literature.questions(5, a, "X", "rash")) <= literature.MAX_PER_ARTICLE
    assert literature.questions(0, cr, "X", "rash")["a0_addresses"]["criteria"] is literature.GATE
    assert "safety review" in literature.GATE["reported"]   # 두 번째 문구입니다(안전성 총설을 되살립니다)


def test_passing_and_unrelated_do_not_count():
    arts = [{"design": "review", "supports": 0.9, "addresses": "passing", "judged": True},
            {"design": "cohort", "supports": 0.8, "addresses": "unrelated", "judged": True},
            {"design": "case_report", "supports": 0.9, "addresses": "focus", "judged": True,
             "dechallenge": "positive", "rechallenge": "positive", "workup": "both"}]
    s = literature.summarize(arts)
    assert s["supportive"] == 1 and s["relevant"] == 1 and s["excluded_passing"] == 2 and s["excluded_unrelated"] == 1
    assert s["analytic_status"] == "no_analytic" and s["analytic_read"] == 0
    assert s["dechallenge_reports"] == 1 and s["rechallenge_reports"] == 1 and s["documented_cases"] == 1
    assert literature.supportive_ids({"articles": [{**a, "id": f"pubmed:{i}"} for i, a in enumerate(arts)]}) == ["pubmed:2"]


def test_unjudged_is_not_read_as_not_supported():
    arts = [{"design": "rct", "supports": None, "judged": False, "addresses": None},
            {"design": "meta_analysis", "supports": None, "judged": False, "addresses": None}]
    s = literature.summarize(arts)
    assert s["analytic_status"] == "not_judged" and s["judged"] is False and s["supportive"] == 0


def test_read_without_jev_leaves_articles_unjudged_but_keeps_rule_fields(monkeypatch):
    _patch_pubmed(monkeypatch)
    monkeypatch.setattr(literature.config, "TYPESAFE_API_KEY", None)
    r = asyncio.run(literature.read("cytarabine", "acute myeloid leukaemia", None))
    assert "error" not in r and r["judge_error"] == "NotConfigured"
    a1, a2, a3 = r["articles"]
    assert all(a["supports"] is None and a["judged"] is False and a["addresses"] is None for a in r["articles"])
    assert r["summary"]["analytic_status"] == "not_judged" and r["summary"]["judged"] is False
    # 규칙 판정: 제목(미국식 leukemia)과 초록(영국식 leukaemia) 모두 PT 와 같은 반응으로 봅니다
    assert a1["title_mentions"] and not a2["title_mentions"] and a2["abstract_mentions"]
    assert a1["design_source"] == "pubtype" and a3["design_source"] == "none" and a3["design"] == "other"
    assert r["summary"]["case_reports_rule"] == ["1", "2"]
    assert all("abstract" not in a and "sections" not in a for a in r["articles"])   # 초록 원문은 남기지 않습니다
    # use_jev=False 는 오류가 아닙니다
    r2 = asyncio.run(literature.read("cytarabine", "acute myeloid leukaemia", None, use_jev=False))
    assert "error" not in r2 and "judge_error" not in r2 and r2["summary"]["case_reports_rule"] == ["1", "2"]


def test_case_reports_rule_needs_pubtype_and_mentions():
    arts = [{"pmid": "1", "design": "case_report", "design_source": "pubtype", "title_mentions": False, "abstract_mentions": False},
            {"pmid": "2", "design": "case_report", "design_source": "jev", "title_mentions": True, "abstract_mentions": True},
            {"pmid": "3", "design": "case_report", "design_source": "pubtype", "title_mentions": False, "abstract_mentions": True}]
    assert literature.case_reports_rule(arts) == ["3"]
    assert literature.mentions("Cytarabine and daunorubicin in AML", "CYTARABINE\\DAUNORUBICIN", "aml")
    assert not literature.mentions("Cytarabine in AML", "CYTARABINE\\DAUNORUBICIN", "aml")
    assert literature.mentions("Dermatitis, atopic, after X", "X", "atopic dermatitis")


def test_missing_answers_lose_only_that_article(monkeypatch):
    _patch_pubmed(monkeypatch)
    monkeypatch.setattr(literature.config, "TYPESAFE_API_KEY", "test")
    seen = {}

    async def fake_jev(state, qs, client=None):
        seen["qs"] = qs
        ans = {"a0_addresses": {"choice": "focus", "confidence": 0.9, "probabilities": {"focus": 0.8, "reported": 0.1, "passing": 0.1}},
               "a0_supports": {"noul": 0.92}, "a0_context": {"choice": "neither", "confidence": 0.9},
               "a0_dechallenge": {"choice": "positive", "confidence": 0.8}, "a0_rechallenge": {"choice": "not_stated", "confidence": 0.9},
               "a0_workup": {"choice": "objective_only", "confidence": 0.4},
               # 1번 편은 supports 가 빠졌습니다
               "a1_addresses": {"choice": "focus", "confidence": 0.9},
               "a2_addresses": {"choice": "reported", "confidence": 0.9, "probabilities": {"focus": 0.2, "reported": 0.3}},
               "a2_design": {"choice": "cohort", "confidence": 0.9}, "a2_supports": {"noul": 0.2}, "a2_strength": {"score": 0.1},
               "a2_effect": {"choice": "null", "confidence": 0.9}, "a2_patients": {"choice": "bogus"}}
        return {"answers": ans, "latency_ms": 321.0}
    monkeypatch.setattr(literature.clients, "jev", fake_jev)
    r = asyncio.run(literature.read("cytarabine", "acute myeloid leukaemia", None))
    a0, a1, a2 = r["articles"]
    assert a0["judged"] and a0["supports"] == 0.92 and a0["dechallenge"] == "positive" and a0["rechallenge"] == "not_stated"
    assert a0["objective"] == "confirmed" and a0["alternatives"] == "not_stated" and "workup" in a0["review"]
    assert a0["strength"] is None and a0["onset"] is None     # 묻지 않았거나 답이 없는 항목은 None 입니다
    assert not a1["judged"] and a1["supports"] is None
    assert a2["design"] == "cohort" and a2["design_source"] == "jev" and a2["effect"] == "null" and a2["patients"] is None
    assert a2["id"] == "pubmed:3#cohort" and "addresses" in a2["review"]   # 관문 확률 0.5 는 사람 확인 대상입니다
    s = r["summary"]
    assert s["judged"] is True and s["relevant"] == 2 and s["analytic_status"] == "not_supported" and s["analytic_null"] == 1
    assert s["dechallenge_reports"] == 1 and r["judge_latency_ms"] == 321.0
    assert all(len([k for k in seen["qs"] if k.startswith(f"a{i}_")]) <= 8 for i in range(3))


def test_jev_failure_is_not_judged(monkeypatch):
    _patch_pubmed(monkeypatch)
    monkeypatch.setattr(literature.config, "TYPESAFE_API_KEY", "test")

    async def boom(state, qs, client=None):
        raise RuntimeError("down")
    monkeypatch.setattr(literature.clients, "jev", boom)
    r = asyncio.run(literature.read("cytarabine", "acute myeloid leukaemia", None))
    assert r["judge_error"] == "RuntimeError" and r["summary"]["analytic_status"] == "not_judged"
    assert r["summary"]["case_reports_rule"] == ["1", "2"]


def test_clip_keeps_labels_and_results_near_budget():
    secs = [("BACKGROUND", "BACKGROUND", "b" * 900 + "."), ("METHODS", "METHODS", "We studied a cohort. " * 30),
            ("RESULTS", "RESULTS", "OR 2.1 (95% CI 1.4-3.0). " * 20), ("CONCLUSIONS", "CONCLUSIONS", "X raises the risk.")]
    a = {"abstract": " ".join(t for _, _, t in secs), "sections": secs}
    text, cut = literature.clip(a)
    assert cut and len(text) <= literature.CLIP and "RESULTS: OR 2.1" in text and "CONCLUSIONS: X raises" in text
    assert "bbbb" not in text                                  # 배경 절이 먼저 빠집니다
    short = {"abstract": "a b", "sections": [("METHODS", "METHODS", "a"), ("RESULTS", "RESULTS", "b")]}
    assert literature.clip(short) == ("METHODS: a RESULTS: b", False)
    flat = {"abstract": "First sentence here. " + "Middle words go on. " * 200 + "Final conclusion.", "sections": [("", "", "x")]}
    text, cut = literature.clip(flat)
    assert cut and len(text) <= literature.CLIP and text.startswith("First sentence") and text.endswith("Final conclusion.")
    big = {"abstract": "y", "sections": [("RESULTS", "RESULTS", "OR 3.0. " + "z" * 5000)]}
    assert len(literature.clip(big)[0]) <= literature.CLIP


def test_double_count_note_and_faers_reanalysis_rule():
    assert "21 CFR 314.80" in literature.DOUBLE_COUNT_NOTE and "FAERS" in literature.DOUBLE_COUNT_NOTE
    xml = XML.replace("We report a patient.", "We analysed the FDA Adverse Event Reporting System (FAERS).")
    assert literature.parse_efetch(xml)[0]["data_source"] == "faers"
