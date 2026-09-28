"""문헌 읽기 단계입니다 (확장 계획 제안 2).

PubMed 검색 → 초록 가져오기(efetch) → 연구 설계 판정 → 연관 보고 여부와 결론 강도 판정.
- 연구 설계는 PubMed 가 붙인 출판 유형(PublicationType)이 있으면 규칙으로 정합니다.
- 출판 유형이 없거나 모호할 때만, 그리고 연관 보고 여부·결론 강도·중단 후 호전 기술 여부는 Jev 가 판단합니다.
- 초록 원문은 판정에만 쓰고 결과에는 남기지 않습니다(PMID, 연도, 제목, 판정만 남깁니다).
근거 ID: pubmed:<pmid>#<design>
"""
import re
import xml.etree.ElementTree as ET

import httpx

from . import clients, config, evidence

DESIGNS = {
    "meta_analysis": "meta-analysis or systematic review",
    "rct": "randomized controlled trial",
    "cohort": "cohort study (prospective or retrospective)",
    "case_control": "case-control study",
    "pharmacovigilance": "disproportionality / spontaneous-report database study",
    "case_series": "case series (several patients)",
    "case_report": "single case report",
    "review": "narrative review",
    "preclinical": "animal or in vitro study",
    "other": "other (letter, editorial, guideline, unrelated)",
}
ANALYTIC = {"meta_analysis", "rct", "cohort", "case_control"}
ANECDOTAL = {"case_report", "case_series"}

_PUBTYPE = [  # 앞에 있을수록 우선합니다
    ("Meta-Analysis", "meta_analysis"), ("Systematic Review", "meta_analysis"),
    ("Randomized Controlled Trial", "rct"),
    ("Case Reports", "case_report"),
    ("Review", "review"),
]
STRENGTH = ["no evidence of association", "anecdotal (single case)", "suggestive (case series or weak signal)",
            "consistent (analytic study supports association)", "established (multiple analytic studies or regulatory consensus)"]


def parse_efetch(xml_text: str) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for art in root.iter("PubmedArticle"):
        pmid = (art.findtext(".//PMID") or "").strip()
        title = re.sub(r"\s+", " ", "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else "").strip()
        abstract = " ".join(re.sub(r"\s+", " ", "".join(a.itertext())) for a in art.findall(".//Abstract/AbstractText"))
        year = art.findtext(".//PubDate/Year") or (art.findtext(".//PubDate/MedlineDate") or "")[:4] or None
        ptypes = [p.text for p in art.findall(".//PublicationType") if p.text]
        rule = next((d for name, d in _PUBTYPE if name in ptypes), None)
        out.append({"pmid": pmid, "title": title, "abstract": abstract, "year": year, "pubtypes": ptypes, "design_rule": rule})
    return out


async def read(drug: str, pt: str, client: httpx.AsyncClient, n: int = 6, use_jev: bool = True) -> dict:
    """약물–반응 쌍의 상위 문헌 n 편을 읽고 판정합니다."""
    search = await evidence.pubmed(drug, pt, client, retmax=n)
    res = {**search, "articles": [], "summary": {}}
    if not search.get("pmids"):
        res["summary"] = summarize([])
        return res
    status, body = await evidence.get_json(client, "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                                           {"db": "pubmed", "id": ",".join(search["pmids"]), "retmode": "xml"},
                                           evidence.PUBMED, key=f"pubmed_fetch_{'_'.join(search['pmids'])}")
    arts = parse_efetch(body) if status == 200 and isinstance(body, str) else []
    judged = {}
    if arts and use_jev and config.TYPESAFE_API_KEY:
        try:
            judged = await _judge(drug, pt, arts)
        except Exception as e:  # 판정 실패는 규칙 판정만 남깁니다
            res["judge_error"] = f"{type(e).__name__}"[:80]
    for i, a in enumerate(arts):
        j = judged.get(i, {})
        design = a["design_rule"] or j.get("design") or "other"
        res["articles"].append({
            "pmid": a["pmid"], "year": a["year"], "title": a["title"][:220], "pubtypes": a["pubtypes"][:4],
            "design": design, "design_source": "PubMed publication type" if a["design_rule"] else ("jev" if j else "none"),
            "supports": j.get("supports", 0.0), "strength": j.get("strength"), "dechallenge": j.get("dechal", 0.0),
            "id": f"pubmed:{a['pmid']}#{design}"})
    res["summary"] = summarize(res["articles"])
    res["ids"] = [a["id"] for a in res["articles"]] or search["ids"]
    res["judge_latency_ms"] = judged.get("_latency")
    return res


async def _judge(drug: str, pt: str, arts: list[dict]) -> dict:
    blocks = []
    for i, a in enumerate(arts):
        blocks.append(f"[Article {i}] PMID {a['pmid']} ({a['year']}). Publication types: {', '.join(a['pubtypes'][:4])}.\n"
                      f"Title: {a['title']}\nAbstract: {a['abstract'][:1600] or '(no abstract)'}")
    state = (f"Question: is {drug.lower()} associated with {pt} in humans?\n\n" + "\n\n".join(blocks))
    qs = {}
    for i, a in enumerate(arts):
        if not a["design_rule"]:
            qs[f"a{i}_design"] = {"type": "choice", "instructions": f"What is the study design of Article {i}?",
                                  "criteria": DESIGNS}
        qs[f"a{i}_supports"] = {"type": "noul", "instructions":
                                f"Does Article {i} report human evidence that {drug.lower()} is associated with {pt}?"}
        qs[f"a{i}_strength"] = {"type": "score", "instructions":
                                f"How strong is the evidence in Article {i} that {drug.lower()} causes {pt}?",
                                "criteria": STRENGTH}
        qs[f"a{i}_dechal"] = {"type": "noul", "instructions":
                              f"Does Article {i} describe improvement after stopping {drug.lower()} or recurrence on re-exposure?"}
    r = await clients.jev(state, qs)
    ans = r["answers"]
    out = {"_latency": r["latency_ms"]}
    for i, _ in enumerate(arts):
        out[i] = {"design": ans.get(f"a{i}_design", {}).get("choice"),
                  "supports": ans[f"a{i}_supports"]["noul"], "strength": round(ans[f"a{i}_strength"]["score"], 2),
                  "dechal": ans[f"a{i}_dechal"]["noul"]}
    return out


def summarize(articles: list[dict]) -> dict:
    sup = [a for a in articles if a.get("supports", 0) >= 0.5]
    analytic = [a for a in articles if a["design"] in ANALYTIC]
    a_sup = sum(1 for a in analytic if a.get("supports", 0) >= 0.5)
    status = ("no_analytic" if not analytic else "supports" if a_sup == len(analytic)
              else "not_supported" if a_sup == 0 else "mixed")
    return {
        "read": len(articles),
        "supportive": len(sup),
        "analytic_read": len(analytic),
        "analytic_status": status,
        "analytic_supportive": a_sup,
        "anecdotal_supportive": sum(1 for a in sup if a["design"] in ANECDOTAL),
        "dechallenge_reports": sum(1 for a in sup if a.get("dechallenge", 0) >= 0.5),
        "designs": {d: sum(1 for a in articles if a["design"] == d) for d in DESIGNS if any(a["design"] == d for a in articles)},
    }
