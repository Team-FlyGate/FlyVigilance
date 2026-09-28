"""크리틱 1단(근거 ID)과 2단(숫자 오라클)을 검증합니다. 모델을 부르지 않습니다."""
from _fv import assess


def test_tier1_flags_missing_and_unknown_ids():
    claims = [{"id": "c1", "text": "x", "evidence": []}, {"id": "c2", "text": "y", "evidence": ["label:fake"]}]
    rules = {i["rule"] for i in assess.tier1_rules(claims, {"faers:case:1"})}
    assert rules == {"no_evidence", "unknown_evidence"}


def test_tier1_rejects_memo_without_claims():
    # Nemotron 출력이 JSON 으로 읽히지 않으면 주장 목록이 비어 있습니다. 빈 메모는 통과하면 안 됩니다
    issues = assess.tier1_rules([], {"faers:case:1"})
    assert [(i["claim"], i["rule"]) for i in issues] == [("memo", "no_claims")]


def test_tier2_numbers_must_match_bundle():
    claims = [{"id": "c1", "text": "PRR was 94.17 in 2019 with 42% of patients", "evidence": ["x"]}]
    issues = assess.tier2_oracle(claims, [94.173, 88.06])
    assert [i["detail"].split()[0] for i in issues] == ["42"]   # 94.17 은 맞고, 2019 는 연도라 건너뜁니다


def test_rules_include_grade_rule():
    assert any(k == "R13" for k, _ in assess.OVERCLAIM_RULES)


def test_guard_verdict_parsing():
    # 기본 가드는 JSON, 대체 가드는 한 줄 텍스트로 답합니다. 읽지 못한 응답은 안전으로 치지 않습니다
    assert assess.parse_guard('{"User Safety": "unsafe", "Safety Categories": "Unauthorized Advice"}') == \
        {"safe": False, "categories": "Unauthorized Advice"}
    assert assess.parse_guard("User Safety: safe")["safe"] is True
    assert assess.parse_guard("User Safety: unsafe")["safe"] is False
    assert assess.parse_guard("I cannot help with that.")["safe"] is None


def test_parse_json_block_repairs_lone_backslash():
    # FAERS 복합제 이름의 역슬래시를 모델이 이스케이프 없이 옮겨도 읽습니다. 이미 이스케이프된 쌍은 그대로 둡니다
    from _fv import clients
    raw = '{"evidence": ["faers:2x2:DARATUMUMAB\\HYALURONIDASE:gastroenteritis@2026Q2"], "ok": "a\\\\b"}'
    d = clients.parse_json_block(raw)
    assert d["evidence"] == ["faers:2x2:DARATUMUMAB\\HYALURONIDASE:gastroenteritis@2026Q2"]
    assert d["ok"] == "a\\b"


def test_evidence_ids_are_normalized():
    # 복합제 이름은 ID 에서 + 로 씁니다. 모델이 근거 목록 줄(ID :: 설명)을 통째로 옮기면 ID 만 남깁니다
    from _fv import evidence
    assert evidence.id_drug("daratumumab\\hyaluronidase") == "DARATUMUMAB+HYALURONIDASE"
    claims = [{"id": "c1", "text": "x", "evidence": ["faers:case:1 :: this ICSR (demographics)", "label:abc"]}]
    assess.clean_evidence(claims)
    assert claims[0]["evidence"] == ["faers:case:1", "label:abc"]
    assert assess.tier1_rules(claims, {"faers:case:1", "label:abc"}) == []
