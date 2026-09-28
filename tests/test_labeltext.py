"""라벨 원문 처리(철자 차이, 비임상 PT, 절 순위, 반응별 인과 미확립 단서)를 검증합니다."""
from _fv import labeltext as lt

ISO_WARNINGS = ("Inflammatory Bowel Disease Isotretinoin capsules have been associated with inflammatory bowel disease "
                "(including regional ileitis) in patients without a prior history of intestinal disorders. In some instances, "
                "symptoms have been reported to persist after treatment has been stopped. Hearing Impairment Impaired hearing "
                "has been reported in patients taking isotretinoin; in some cases, the hearing impairment has been reported to "
                "persist after therapy has been discontinued. Mechanism(s) and causality for this reaction have not been established.")
BOILER = ("The following adverse reactions have been identified during post-approval use. Because these reactions are "
          "reported voluntarily from a population of uncertain size, it is not always possible to reliably estimate their "
          "frequency or establish a causal relationship to drug exposure. Pancreatitis, rash.")


def test_british_to_us_spelling():
    assert "gastrointestinal hemorrhage" in lt.us_variants("gastrointestinal haemorrhage")
    assert "diarrhea" in lt.us_variants("diarrhoea") and "anemia" in lt.us_variants("anaemia")


def test_nonclinical_terms():
    assert lt.is_nonclinical("drug ineffective") and lt.is_nonclinical("off label use")
    assert not lt.is_nonclinical("thrombocytopenia")


def test_mentions_sorted_by_regulatory_rank():
    hits = lt.find_mentions({"adverse_reactions": "rash, nausea", "boxed_warning": "WARNING: severe rash"}, "rash")
    assert [h["section"] for h in hits] == ["boxed_warning", "adverse_reactions"]


def test_disclaimer_is_scoped_to_the_reaction():
    # 청력 손상에 붙은 단서를 염증성장질환에 붙이면 안 됩니다 (팀 시제품의 오귀속 사례)
    assert lt.causality_disclaimer({"warnings": ISO_WARNINGS}, "inflammatory bowel disease") is None
    assert lt.causality_disclaimer({"warnings": ISO_WARNINGS}, "hearing impairment") is not None


def test_boilerplate_is_not_a_disclaimer():
    assert lt.causality_disclaimer({"adverse_reactions": BOILER}, "pancreatitis") is None
