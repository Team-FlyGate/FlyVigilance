"""evidence.label_facts 계약(by_pt 필드, 정수 rank, listed == rank >= 1)과 라벨·문헌 조회 경로를 네트워크 없이 검증합니다."""
import asyncio

from _fv import evidence, labeltext

AR = ("6 ADVERSE REACTIONS 6.1 Clinical Trials Experience Most common adverse reactions: nausea, headache. "
      "6.2 Postmarketing Experience The following adverse reactions have been identified during post-approval use. Because "
      "these reactions are reported voluntarily from a population of uncertain size, it is not always possible to reliably "
      "estimate their frequency or establish a causal relationship to drug exposure. Alopecia, pancreatitis.")
OPENFDA = {"set_id": "S1", "effective_time": "20260101", "openfda": {"brand_name": ["Brandx"], "route": ["ORAL"],
                                                                        "generic_name": ["DRUGX"]},
           "boxed_warning": ["WARNING: HEPATOTOXICITY Severe hepatotoxicity has occurred."],
           "warnings_and_cautions": ["5.1 Hepatotoxicity 5.2 Hypotension Use with caution in patients with heart failure. "
                                     "5.3 Acute Kidney Injury Acute kidney injury has been reported."],
           "contraindications": ["Patients with known hypersensitivity to Drugx."],
           "indications_and_usage": ["Drugx is indicated for the treatment of adults with rheumatoid arthritis."],
           "adverse_reactions": [AR]}
PTS = ["hepatotoxicity", "renal failure acute", "nausea", "alopecia", "hypersensitivity", "cardiac failure",
       "rheumatoid arthritis", "pyrexia"]


def doc():
    return {"setid": "S1", "effective": "20260101", "brand": "Brandx", "route": ["ORAL"],
            "sections": labeltext.label_sections(OPENFDA)}


def test_label_facts_contract():
    lab = evidence.label_facts(doc(), "DRUGX", PTS)
    assert lab["found"] and set(lab["by_pt"]) == set(PTS) and set(lab["listed"]) == set(PTS)
    for pt, v in lab["by_pt"].items():
        assert type(v["rank"]) is int and v["rank"] in (0, 1, 2, 3)   # grade.decide 와 화면 4단계가 정수를 씁니다
        assert lab["listed"][pt] == (v["rank"] >= 1)
        assert v["label_status"] in ("boxed", "warnings_precautions", "ar_clinical_trials", "ar_unspecified",
                                     "ar_postmarketing", "unlisted")
        assert set(v) >= {"sections", "disclaimer", "contraindication", "indication_term", "matched_via"}
    by = lab["by_pt"]
    assert (by["hepatotoxicity"]["rank"], by["hepatotoxicity"]["label_status"]) == (3, "boxed")
    assert by["hepatotoxicity"]["sections"][0] == "boxed_warning"
    assert (by["renal failure acute"]["rank"], by["renal failure acute"]["matched_via"]) == (2, "synonym")
    assert (by["nausea"]["rank"], by["nausea"]["label_status"]) == (1, "ar_clinical_trials")
    assert (by["alopecia"]["rank"], by["alopecia"]["label_status"]) == (1, "ar_postmarketing")
    assert by["pyrexia"]["label_status"] == "unlisted" and by["pyrexia"]["matched_via"] is None


def test_contraindication_only_hypersensitivity_is_not_listed():
    lab = evidence.label_facts(doc(), "DRUGX", ["hypersensitivity"])
    v = lab["by_pt"]["hypersensitivity"]
    assert lab["listed"]["hypersensitivity"] is False and v["rank"] == 0 and v["sections"] == []
    assert "hypersensitivity" in v["contraindication"].lower()
    assert not any(h["section"] == "contraindications" for h in lab["hits"])


def test_population_and_indication_mentions_are_not_listed():
    lab = evidence.label_facts(doc(), "DRUGX", ["cardiac failure", "rheumatoid arthritis"])
    assert lab["listed"] == {"cardiac failure": False, "rheumatoid arthritis": False}
    assert lab["by_pt"]["rheumatoid arthritis"]["indication_term"] is True
    assert lab["by_pt"]["cardiac failure"]["indication_term"] is False


def test_hits_carry_section_id_and_match_basis():
    lab = evidence.label_facts(doc(), "DRUGX", ["alopecia", "renal failure acute"])
    ids = {h["pt"]: h for h in lab["hits"]}
    assert ids["alopecia"]["id"] == "label:S1#adverse_reactions_pm" and ids["alopecia"]["matched_via"] == "literal"
    assert ids["renal failure acute"]["id"] == "label:S1#warnings_and_cautions"


def test_no_label_shape():
    assert evidence.label_facts(None, "X", ["rash"]) == {"found": False, "drug": "X", "hits": [], "listed": {}, "by_pt": {}}


def test_get_label_builds_split_sections(monkeypatch):
    async def fake(client, url, params, spacer, key=None, retries=4):
        return 200, {"results": [OPENFDA]}
    monkeypatch.setattr(evidence, "get_json", fake)
    evidence._LABEL_MEM.clear()
    d = asyncio.run(evidence.get_label("DRUGX", None, "ORAL"))
    evidence._LABEL_MEM.clear()
    assert {"adverse_reactions_ct", "adverse_reactions_pm", "contraindications", "indications_and_usage"} <= set(d["sections"])
    assert "adverse_reactions" not in d["sections"] and "uncertain size" not in d["sections"]["adverse_reactions_ct"]


def test_pubmed_ors_exact_equivalents(monkeypatch):
    seen = []

    async def fake(client, url, params, spacer, key=None, retries=4):
        seen.append((params["term"], key))
        return 200, {"esearchresult": {"count": "0", "idlist": []}}
    monkeypatch.setattr(evidence, "get_json", fake)
    asyncio.run(evidence.pubmed("DrugX", "Pyrexia", None))
    asyncio.run(evidence.pubmed("DrugX", "rash", None))
    assert seen[0] == ('"drugx"[tiab] AND ("pyrexia"[tiab] OR "fever"[tiab])', "pubmed_search_DRUGX_pyrexia_5_eq")
    assert seen[1] == ('"drugx"[tiab] AND "rash"[tiab]', "pubmed_search_DRUGX_rash_5")   # 동의어가 없으면 예전 캐시 키 그대로입니다


def test_bundle_catalog_states_search_scope(monkeypatch):
    from _fv import literature

    async def fake_lookup(drug, pts, client, route=None):
        return evidence.label_facts(doc(), drug, pts)

    async def fake_read(drug, pt, client, *a, **k):
        return {"query": "q", "count": 0, "pmids": [], "ids": [], "articles": [], "summary": {}}
    monkeypatch.setattr(evidence, "label_lookup", fake_lookup)
    monkeypatch.setattr(literature, "read", fake_read)
    case = {"primaryid": "1", "reactions": ["death", "hypersensitivity", "alopecia"], "drugs": [{"drug": "DRUGX", "role": "PS"}]}
    b = asyncio.run(evidence.bundle(case, "DRUGX"))
    assert b["reactions"] == ["hypersensitivity", "alopecia"]   # 'death' 는 결과 PT 라 근거 묶음에서 뺍니다
    what = next(c["what"] for c in b["catalog"] if c["id"] == "label:S1")
    assert "contraindications and indications are context only" in what and "alopecia=ar_postmarketing" in what
    assert "hypersensitivity=unlisted (named in contraindications only as a patient condition)" in what
    assert any(c["id"] == "label:S1#adverse_reactions_pm" for c in b["catalog"])
