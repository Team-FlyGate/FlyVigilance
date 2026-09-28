"""PubMed efetch XML 파싱과 문헌 요약 상태를 검증합니다."""
from _fv import literature

XML = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>A case of X-induced rash</ArticleTitle>
<Abstract><AbstractText>We report a patient.</AbstractText></Abstract>
<PublicationTypeList><PublicationType>Case Reports</PublicationType><PublicationType>Journal Article</PublicationType></PublicationTypeList>
<Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""


def test_publication_type_decides_design_by_rule():
    a = literature.parse_efetch(XML)[0]
    assert a["pmid"] == "123" and a["design_rule"] == "case_report" and a["year"] == "2020"


def test_summary_status():
    arts = [{"design": "meta_analysis", "supports": 0.1}, {"design": "case_control", "supports": 0.9},
            {"design": "case_report", "supports": 0.95}]
    s = literature.summarize(arts)
    assert s["analytic_status"] == "mixed" and s["analytic_read"] == 2 and s["anecdotal_supportive"] == 1
    assert literature.summarize([])["analytic_status"] == "no_analytic"
