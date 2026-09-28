"""라우팅 정책과 규정 모드(US/KR), 라벨 근거 덮어쓰기를 검증합니다."""
from _fv import triage


def answers(serious=0.9, expected=0.2, deep=0.2, priority=1.0, route="monitor", route_conf=0.9, caus_conf=0.9):
    return {
        "serious": {"type": "noul", "noul": serious}, "expected": {"type": "noul", "noul": expected},
        "deep": {"type": "noul", "noul": deep},
        "priority": {"type": "score", "score": priority, "confidence": 0.9, "legend": {}, "probabilities": {}},
        "route": {"type": "choice", "choice": route, "confidence": route_conf, "probabilities": {}},
        "causality": {"type": "choice", "choice": "possible", "confidence": caus_conf, "probabilities": {}},
    }


VALID = {"valid": True, "checks": {}}


def test_us_serious_unexpected_gets_15_day_deadline():
    d = triage.route_policy(answers(serious=0.9, expected=0.1), VALID, "US")
    assert d["action"] == "expedite" and "15 calendar days" in d["deadline"]


def test_us_serious_expected_is_not_15_day():
    d = triage.route_policy(answers(serious=0.9, expected=0.9, priority=2.9), VALID, "US")
    assert d["action"] == "expedite"
    assert "does not meet the 15-day" in d["deadline"]


def test_kr_serious_is_15_day_regardless_of_expectedness():
    d = triage.route_policy(answers(serious=0.9, expected=0.95), VALID, "KR")
    assert d["action"] == "expedite" and d["deadline"].startswith("15일 이내")


def test_label_grounding_overrides_memory():
    # Jev 기억은 '예상된 반응'(0.9)이라 했지만 라벨 조회에서 없으면(0.0) 미국 기준 신속보고 후보가 됩니다
    d = triage.route_policy(answers(serious=0.9, expected=0.9), VALID, "US", expected=0.0, expected_source="openFDA label")
    assert d["action"] == "expedite" and "openFDA label" in d["reasons"][0]


def test_missing_ich_elements_request_follow_up():
    d = triage.route_policy(answers(), {"valid": False, "checks": {"reporter": False, "patient": True,
                                                                     "suspect_drug": True, "adverse_event": True}})
    assert d["action"] == "follow_up" and "reporter" in d["reasons"][0]


def test_low_confidence_escalates_to_system2():
    d = triage.route_policy(answers(serious=0.2, expected=0.9, caus_conf=0.3), VALID, "US")
    assert d["action"] == "signal_review" and d["system2"]


def test_validity_rule():
    case = {"occp_cod": "MD", "age": 40, "drugs": [{"drug": "X", "role": "PS"}], "reactions": ["rash"]}
    assert triage.validity(case)["valid"]
    assert not triage.validity({**case, "reactions": []})["valid"]
