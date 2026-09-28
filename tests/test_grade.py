"""근거 등급 규칙을 검증합니다. 팀 시제품의 세 쌍과 새로 추가한 칸(L, U)을 함께 봅니다."""
from _fv import grade


def test_boxed_warning_with_signal_is_A():
    assert grade.decide(3, "strong", False) == "A"


def test_labeled_with_signal_is_B():
    assert grade.decide(2, "strong", False) == "B" and grade.decide(1, "strong", False) == "B"


def test_reaction_specific_disclaimer_caps_at_C():
    assert grade.decide(3, "strong", True) == "C"


def test_signal_without_label_is_C():
    assert grade.decide(0, "strong", False) == "C"


def test_labeled_without_signal_is_L_not_D():
    # 신호 부재를 근거 부재로 읽지 않습니다 (R4)
    for sig in ("none", "weak", "insufficient", "unavailable"):
        assert grade.decide(2, sig, False) == "L"


def test_unlabeled_no_signal_is_D_but_unknowns_are_U():
    assert grade.decide(0, "none", False) == "D"
    assert grade.decide(0, "unavailable", False) == "U"
    assert grade.decide(-1, "none", False) == "U"


def test_grade_pair_keeps_basis_and_gaps():
    f = {"id": "faers:2x2:X:rash@2026Q2", "a": 50, "evans": True, "ror_sig": True, "ic_sig": True,
         "prr": 3.0, "prr_lo": 2.0, "prr_hi": 4.0, "ror_lo": 2.1, "ic025": 1.2, "chi2": 40}
    label = {"found": True, "hits": [{"id": "label:S#warnings_and_cautions", "pt": "rash"}],
             "by_pt": {"rash": {"sections": ["warnings_and_cautions"], "rank": 2, "disclaimer": None}}}
    g = grade.grade_pair("X", "rash", f, label, {"summary": {"read": 0}})
    assert g["grade"] == "B" and f["id"] in g["basis"] and any("문헌" in x for x in g["gaps"])
    assert "인과를 뜻하지 않" in g["caution"]
