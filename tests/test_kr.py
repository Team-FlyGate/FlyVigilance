"""한국형 인과성 평가 알고리즘 ver 2.0 배점과 국내 서식 정규화를 검증합니다."""
from _fv import kr


def test_score_range_matches_published_table():
    assert sum(max(s for _, _, s in it["options"]) for it in kr.KR_ALGO) == kr.KR_MAX == 19
    assert sum(min(s for _, _, s in it["options"]) for it in kr.KR_ALGO) == kr.KR_MIN == -13


def test_grade_bands():
    assert kr.kr_grade(12)["grade"] == "확실함"
    assert kr.kr_grade(11)["grade"] == kr.kr_grade(6)["grade"] == "가능성 높음"
    assert kr.kr_grade(5)["grade"] == kr.kr_grade(2)["grade"] == "가능성 있음"
    assert kr.kr_grade(1)["grade"] == kr.kr_grade(-13)["grade"] == "가능성 낮음"


def test_team_doc_patient_a_scores_11():
    # 팀 문서의 가상 환자 A: +3 +3 0 +2 0 +3 0 0 = 11 (가능성 높음)
    picks = {"temporal": "consistent", "dechallenge": "improved", "history": "no_info", "concomitant": "cannot_explain",
             "nondrug": "no_info", "known": "label", "rechallenge": "not_done", "specific_test": "no_info"}
    total = sum(dict((k, s) for k, _, s in it["options"])[picks[it["id"]]] for it in kr.KR_ALGO)
    assert total == 11 and kr.kr_grade(total)["grade"] == "가능성 높음"


def test_norm_case_assigns_roles_and_codes_by_rule():
    form = {"가_환자정보": {"성별": "여"},
            "나_이상사례정보": {"중대성": {"입원_연장": True, "사망": False}},
            "다_의약품정보": {"의심약물": [{"성분명": "니라파립", "성분명_영문": "NIRAPARIB", "재투여": "안 함"}],
                          "병용약물": [{"성분명": "졸피뎀", "성분명_영문": "ZOLPIDEM"}]},
            "라_보고자정보": {"보고자_유형": "약사"}}
    model_case = {"age": 64, "drugs": [{"drug": "NIRAPARIB", "role": "SS", "dechal": "Y", "rechal": "N"}],
                  "reactions": ["thrombocytopenia"]}
    c = kr._norm_case(form, model_case)
    assert [(d["drug"], d["role"]) for d in c["drugs"]] == [("NIRAPARIB", "PS"), ("ZOLPIDEM", "C")]
    assert c["drugs"][0]["rechal"] is None          # '재투여 안 함'은 재투여 음성이 아닙니다
    assert c["occp_cod"] == "PH" and c["sex"] == "F" and c["outcomes"] == ["HO"]


# ---------------------------------------------------------------- '약물에 대해 알려진 정보' (규칙 전용)
def _score(choice: str) -> int:
    return dict((k, s) for k, _, s in next(it for it in kr.KR_ALGO if it["id"] == "known")["options"])[choice]


def _label(by_pt: dict, hits: list | None = None) -> dict:
    return {"found": True, "drug": "X", "setid": "S1", "brand": "B", "by_pt": by_pt, "hits": hits or [],
            "listed": {pt: v.get("rank", 0) >= 1 for pt, v in by_pt.items()}}


def test_known_label_listed_scores_3():
    lab = _label({"rash": {"sections": ["adverse_reactions"], "rank": 1}},
                 [{"id": "label:S1#adverse_reactions", "pt": "rash", "section": "adverse_reactions"}])
    k = kr.known_item(lab, None, "rash")
    assert k["choice"] == "label" and _score(k["choice"]) == 3 and k["source"] == kr.SRC_LABEL
    assert k["evidence"] == ["label:S1#adverse_reactions"] and k["needs_review"] and not k["mfds_checked"]


def test_known_contraindication_only_is_not_listed():
    # 지금 labeltext 는 금기 절도 rank 2 로 세고, 라벨 담당 변경 후에는 rank 0 + contraindication 표시입니다. 어느 쪽이든 +3 이 아닙니다
    for bp in ({"sections": ["contraindications"], "rank": 2}, {"sections": [], "rank": 0, "contraindication": True}):
        k = kr.known_item(_label({"hypersensitivity": bp}), None, "hypersensitivity")
        assert k["choice"] != "label" and _score(k["choice"]) == 0 and "금기" in k["scope"]


def test_known_case_report_pmid_scores_2():
    lit = {"query": '"x"[tiab] AND "rash"[tiab]', "count": 3, "articles": [], "summary": {"case_reports_rule": ["32598503"]}}
    k = kr.known_item({"found": False, "by_pt": {}, "hits": [], "listed": {}}, lit, "rash")
    assert k["choice"] == "case_reports" and _score(k["choice"]) == 2
    assert k["evidence"] == ["pubmed:32598503"] and "PMID 32598503" in k["source"] and k["needs_review"]
    # case_reports_rule 필드가 아직 없으면 PubMed 출판 유형으로 셉니다(모델의 supports 는 보지 않습니다)
    lit2 = {"query": "q", "count": 2, "summary": {"supportive": 2},
            "articles": [{"pmid": "1", "pubtypes": ["Review"], "design": "review", "supports": 0.99},
                         {"pmid": "2", "pubtypes": ["Case Reports", "Journal Article"], "design": "case_report", "supports": 0.1}]}
    assert kr.known_item(None, lit2, "rash")["evidence"] == ["pubmed:2"]


def test_known_nothing_scores_0_with_scope_and_review():
    lit = {"query": '"x"[tiab] AND "enuresis"[tiab]', "count": 0, "articles": [], "summary": {"case_reports_rule": []}}
    k = kr.known_item(_label({"enuresis": {"sections": [], "rank": 0}}), lit, "enuresis")
    assert k["choice"] == "unknown" and _score(k["choice"]) == 0 and k["needs_review"] and not k["lookup_failed"]
    assert "enuresis" in k["scope"] and "0건" in k["scope"] and k["source"] == kr.SRC_NONE


def test_known_lookup_failure_scores_0_and_flags():
    k = kr.known_item(None, None, "rash", label_error="ConnectError", lit_error="HTTP 503")
    assert k["choice"] == "unknown" and k["source"] == kr.SRC_FAIL and k["lookup_failed"] and k["needs_review"]
    assert kr.known_item(None, None, None)["source"] == kr.SRC_FAIL


def test_known_is_not_asked_to_jev():
    qs = kr.jev_questions()
    assert "known" not in qs and "who_umc" in qs
    assert set(qs) - {"who_umc"} == {it["id"] for it in kr.KR_ALGO} - {"known"}


def test_causality_uses_assessed_reaction_for_label_and_literature(monkeypatch):
    """라벨과 문헌을 같은 평가 반응(비임상 PT 를 거른 첫 반응)으로 봅니다. 다른 반응의 라벨 기재로 +3 을 주지 않습니다."""
    import asyncio
    seen = {}

    async def fake_jev(state, qs):
        seen["qs"] = set(qs)
        ans = {k: {"choice": next(iter(q["criteria"])), "confidence": 0.9, "probabilities": {}} for k, q in qs.items()}
        return {"answers": ans, "usage": {}, "model": "fake", "latency_ms": 1.0}

    async def fake_label(drug, pts, client, route=None):
        seen["label_pts"] = pts
        return _label({p: ({"sections": ["adverse_reactions"], "rank": 1} if p == "urinary incontinence" else {"sections": [], "rank": 0})
                       for p in pts})

    async def fake_read(drug, pt, client, **kw):
        seen["lit_pt"] = pt
        return {"query": f'"{drug.lower()}"[tiab] AND "{pt}"[tiab]', "count": 0, "articles": [], "summary": {"case_reports_rule": []}}

    monkeypatch.setattr(kr.clients, "jev", fake_jev)
    monkeypatch.setattr(kr.evidence, "label_lookup", fake_label)
    monkeypatch.setattr(kr.literature, "read", fake_read)
    case = {"drugs": [{"drug": "MIRTAZAPINE", "role": "PS", "route": "ORAL", "name_ko": "미르타자핀"}],
            "reactions": ["drug ineffective", "enuresis", "urinary incontinence"]}
    r = asyncio.run(kr.causality_kr(case, "state"))
    known = next(i for i in r["items"] if i["id"] == "known")
    assert "known" not in seen["qs"] and seen["label_pts"][0] == "enuresis" and seen["lit_pt"] == "enuresis"
    assert known["score"] == 0 and known["method"] == "rule" and known["needs_review"] and r["assessed_reaction"] == "enuresis"
    assert r["mfds_label"]["checked"] is False and "robots.txt" in r["mfds_label"]["reason"]
    assert r["mfds_label"]["search_url"].startswith("https://nedrug.mfds.go.kr/searchDrug?itemName=%EB%AF%B8")
    # 첫 선택지 점수 합: temporal 3 + dechallenge 3 + history 1 + concomitant 2 + nondrug 1 + known 0 + rechallenge 3 + specific_test 3
    assert r["total"] == 16


def test_known_case_report_scope_reflects_label_status():
    """라벨을 못 찾았거나 조회에 실패했는데 '기재 없음'으로 적지 않습니다. 라벨 조회 실패면 +2 여도 조회 실패로 표시합니다."""
    lit = {"query": "q", "count": 1, "articles": [], "summary": {"case_reports_rule": ["1"]}}
    k = kr.known_item({"found": False, "by_pt": {}, "hits": [], "listed": {}}, lit, "rash")
    assert k["choice"] == "case_reports" and "찾지 못했습니다" in k["scope"] and "기재 없음" not in k["scope"] and not k["lookup_failed"]
    k = kr.known_item(None, lit, "rash", label_error="ConnectError")
    assert k["choice"] == "case_reports" and k["lookup_failed"] and "조회 실패" in k["scope"]
    assert "조회하지 않았습니다" in kr.known_item(_label({"rash": {"sections": [], "rank": 0}}), None, "rash")["scope"]


def test_case_report_on_the_indication_does_not_score_plus_two():
    # 증례보고가 약의 적응증(치료 대상 질환)에 관한 글일 수 있으면 +2 를 주지 않습니다
    lit = {"query": "q", "count": 1, "articles": [], "summary": {"case_reports_rule": ["41430963"]}}
    k = kr.known_item(None, lit, "acute myeloid leukaemia", indication="Acute myeloid leukaemia")
    assert k["choice"] == "unknown" and k["needs_review"] and "적응증" in k["scope"]
    assert kr.known_item(None, lit, "rash", indication="acute myeloid leukaemia")["choice"] == "case_reports"
