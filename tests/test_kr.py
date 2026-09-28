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
