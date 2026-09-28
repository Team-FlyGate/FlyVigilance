"""라벨 원문 처리(철자·동의어, 비임상 PT, 절 나누기, 맥락 가드, 반응별 인과 미확립 단서)를 검증합니다."""
import json

from _fv import labeltext as lt
from _fv.config import DATA

ISO_WARNINGS = ("Inflammatory Bowel Disease Isotretinoin capsules have been associated with inflammatory bowel disease "
                "(including regional ileitis) in patients without a prior history of intestinal disorders. In some instances, "
                "symptoms have been reported to persist after treatment has been stopped. Hearing Impairment Impaired hearing "
                "has been reported in patients taking isotretinoin; in some cases, the hearing impairment has been reported to "
                "persist after therapy has been discontinued. Mechanism(s) and causality for this reaction have not been established.")
BOILER = ("The following adverse reactions have been identified during post-approval use. Because these reactions are "
          "reported voluntarily from a population of uncertain size, it is not always possible to reliably estimate their "
          "frequency or establish a causal relationship to drug exposure. Pancreatitis, rash.")
PM62 = ("6.2 Postmarketing Experience The following adverse reactions have been reported during post-approval use of X. "
        "Because these reactions are reported voluntarily from a population of uncertain size, it is not always possible to "
        "reliably estimate their frequency or establish a causal relationship to drug exposure. Angioedema, pancreatitis.")


def listed(sections: dict, pt: str) -> list[str]:
    return [h["section"] for h in lt.find_mentions(sections, pt)]


# ---------------------------------------------------------------- 철자·어순·동의어
def test_british_to_us_spelling():
    assert "gastrointestinal hemorrhage" in lt.us_variants("gastrointestinal haemorrhage")
    assert "diarrhea" in lt.us_variants("diarrhoea") and "anemia" in lt.us_variants("anaemia")
    for gb, us in [("paraesthesia", "paresthesia"), ("rhinorrhoea", "rhinorrhea"), ("abnormal behaviour", "abnormal behavior"),
                   ("generalised tonic-clonic seizure", "generalized tonic clonic seizure"), ("necrotising fasciitis",
                   "necrotizing fasciitis"), ("abdominal distension", "abdominal distention"), ("faecaloma", "fecaloma")]:
        assert us in lt.us_variants(gb), gb


def test_fever_is_pyrexia_both_ways():
    assert listed({"adverse_reactions_ct": "Most common: headache, fever, rash."}, "pyrexia") == ["adverse_reactions_ct"]
    assert listed({"adverse_reactions_ct": "Pyrexia 12% 3%"}, "fever") == ["adverse_reactions_ct"]
    h = lt.find_mentions({"adverse_reactions_ct": "Most common: fever."}, "pyrexia")[0]
    assert h["matched_via"] == "synonym"


def test_acute_renal_failure_is_acute_kidney_injury_both_ways():
    arf = {"warnings_and_cautions": "Cases of acute renal failure have been reported."}
    aki = {"warnings_and_cautions": "Acute kidney injury occurred in 2% of patients."}
    assert listed(arf, "acute kidney injury") and listed(aki, "renal failure acute") and listed(arf, "renal failure acute")
    assert lt.find_mentions(arf, "renal failure acute")[0]["matched_via"] == "reorder"


def test_synonyms_are_exact_equivalents_only():
    # 넓은 개념으로 넘어가지 않습니다(ICH E2A): 신부전 ↔ 급성 신손상, 간염 ↔ 간손상은 같은 개념이 아닙니다
    assert "renal failure" not in lt.us_variants("acute kidney injury")
    assert not listed({"warnings_and_cautions": "Drug-induced liver injury has been reported."}, "hepatitis")
    assert lt.equivalents("pyrexia") == ["pyrexia", "fever"] and lt.equivalents("rash") == ["rash"]


def test_plural_hyphen_and_blood_lab_terms():
    assert listed({"warnings_and_cautions": "Infusion-related reactions can occur."}, "infusion related reaction")
    assert listed({"adverse_reactions_ct": "Seizures were reported."}, "seizure")
    assert listed({"adverse_reactions_ct": "muscle spasm, nausea"}, "muscle spasms")
    for text in ("elevated creatinine", "increased creatinine", "serum creatinine increased"):
        assert listed({"adverse_reactions_ct": text}, "blood creatinine increased"), text
    assert listed({"adverse_reactions_ct": "upper abdominal pain"}, "abdominal pain upper")


def test_icH_specificity_more_severe_term_is_not_matched_by_milder_text():
    # 라벨에 간염만 있으면 전격성 간염은 예상되지 않은 반응입니다 (ICH E2A 예시)
    assert not listed({"warnings_and_cautions": "Hepatitis and elevated liver enzymes have been reported."}, "hepatitis fulminant")
    assert not listed({"adverse_reactions_ct": "acute renal failure"}, "tubulointerstitial nephritis")
    assert listed({"adverse_reactions_ct": "fulminant hepatitis"}, "hepatitis fulminant")


# ---------------------------------------------------------------- 맥락 가드
def test_hepatitis_b_reactivation_is_not_hepatitis():
    text = ("5.3 Hepatitis B Virus Reactivation: Screen patients for hepatitis B infection before starting. "
            "Autoimmune hepatitis has been reported.")
    assert not listed({"warnings_and_cautions": text}, "hepatitis")
    assert listed({"warnings_and_cautions": text + " Cases of drug-induced hepatitis occurred."}, "hepatitis")


def test_population_context_is_not_a_listing():
    assert not listed({"warnings_and_cautions": "Use with caution in patients with heart failure."}, "cardiac failure")
    assert not listed({"warnings_and_cautions": "It is indicated in adults with heart failure (NYHA II-IV)."}, "cardiac failure")
    assert not listed({"warnings_and_cautions": "Patients with a history of seizures may be at risk."}, "seizure")
    assert not listed({"warnings": "Ask a doctor before use if you have • nausea, vomiting or abdominal pain"}, "vomiting")
    # 가드 뒤에 사건 표현이 오면 약물 반응 서술입니다
    assert listed({"warnings_and_cautions": "Monitor patients who develop heart failure."}, "cardiac failure")
    assert listed({"warnings_and_cautions": "Heart failure: new or worsening heart failure has occurred."}, "cardiac failure")


def test_negation_and_compound_terms():
    assert not listed({"adverse_reactions_ct": "There were no cases of pancreatitis in the trials."}, "pancreatitis")
    assert not listed({"adverse_reactions_ct": "Rash, erythema multiforme and urticaria."}, "erythema")
    assert not listed({"adverse_reactions_ct": "herpes infections, but excludes eczema herpeticum."}, "eczema")
    assert not listed({"adverse_reactions_pm": "Gastrointestinal Disorders: nausea, vomiting"}, "gastrointestinal disorder")
    assert listed({"warnings_and_cautions": "Anaphylaxis, with or without rash, has occurred."}, "rash")


def test_contraindications_and_indications_are_not_listings():
    secs = {"contraindications": "Contraindicated in patients with known hypersensitivity to X.",
            "indications_and_usage": "X is indicated for the treatment of plaque psoriasis in adults.",
            "adverse_reactions_ct": "In psoriasis trials, headache occurred in 5%."}
    assert listed(secs, "hypersensitivity") == [] and listed(secs, "psoriasis") == []
    f = lt.pt_facts(secs, "psoriasis")
    assert f["indication_term"] is True and f["rank"] == 0
    secs["adverse_reactions_pm"] = "New onset or worsening of psoriasis has been reported."
    assert lt.pt_facts(secs, "psoriasis")["label_status"] == "ar_postmarketing"
    assert lt.pt_facts(secs, "hypersensitivity")["contraindication"]


# ---------------------------------------------------------------- 이상반응 절 나누기
def test_split_duplicated_postmarketing_block_keeps_boilerplate_out_of_trials():
    ar = ("6 ADVERSE REACTIONS 6.1 Clinical Trials Experience Nausea 20% 5%. " + PM62 +
          " 6 ADVERSE REACTIONS 6.1 Clinical Trials Experience Nausea 20% 5%. " + PM62)
    s = lt.split_adverse_reactions(ar, plr=True)
    assert not lt.PM_BOILER_EN.search(s["adverse_reactions_ct"]) and s["adverse_reactions_pm"].count("6.2 Postmarketing") == 2
    assert listed(s, "angioedema") == ["adverse_reactions_pm"] and listed(s, "nausea") == ["adverse_reactions_ct"]


def test_split_matches_postmarketing_heading_by_name_not_number():
    ar = ("6.1 Clinical Trials Experience Headache 10%. 6.2 Immunogenicity Anti-drug antibodies developed in 5%. "
          "6.3 Postmarketing Experience The following adverse reactions have been identified during postapproval use: alopecia.")
    s = lt.split_adverse_reactions(ar, plr=True)
    assert "Immunogenicity" in s["adverse_reactions_ct"] and "alopecia" in s["adverse_reactions_pm"]
    assert "alopecia" not in s["adverse_reactions_ct"]


def test_split_unnumbered_heading_lead_sentence_and_pooled_text():
    old = ("Leukopenia occurred in 28%. Postmarketing Experience The following adverse reactions have been identified during "
           "postapproval use of azathioprine: progressive multifocal leukoencephalopathy.")
    s = lt.split_adverse_reactions(old, plr=False)
    assert "Leukopenia" in s["adverse_reactions_ct"] and "leukoencephalopathy" in s["adverse_reactions_pm"]
    lead = ("Hypoglycemia is the most common adverse reaction. The following additional adverse reactions have been identified "
            "during post-approval use: lipodystrophy.")
    assert "lipodystrophy" in lt.split_adverse_reactions(lead, plr=True)["adverse_reactions_pm"]
    pooled = ("The following adverse reactions have been identified in clinical trials or postmarketing reports. Because some of "
              "these reactions were reported voluntarily from a population of uncertain size... Dry skin, cheilitis.")
    assert list(lt.split_adverse_reactions(pooled, plr=True)) == ["adverse_reactions_mixed"]
    assert list(lt.split_adverse_reactions("Nausea, dizziness.", plr=False)) == ["adverse_reactions"]


def test_old_format_precautions_subsections_are_not_listings():
    d = {"precautions": ["PRECAUTIONS General Hypotension may occur. Information for Patients Report rash. "
                         "Drug Interactions Concomitant use may cause syncope (see PRECAUTIONS: Drug Interactions ). "
                         "Pregnancy Teratogenic Effects No increase in spontaneous abortion was seen. Pediatric Use Not studied."]}
    s = lt.label_sections(d)
    assert listed(s, "hypotension") == ["precautions"] and listed(s, "rash") == ["precautions"]
    assert listed(s, "syncope") == [] and "syncope" in s["precautions_other"]


# ---------------------------------------------------------------- 인과 미확립 단서
def test_disclaimer_is_scoped_to_the_reaction():
    # 청력 손상에 붙은 단서를 염증성장질환에 붙이면 안 됩니다 (팀 시제품의 오귀속 사례)
    assert lt.causality_disclaimer({"warnings": ISO_WARNINGS}, "inflammatory bowel disease") is None
    assert lt.causality_disclaimer({"warnings": ISO_WARNINGS}, "hearing impairment") is not None


def test_boilerplate_is_not_a_disclaimer():
    assert lt.causality_disclaimer({"adverse_reactions": BOILER}, "pancreatitis") is None


def test_list_level_qualifiers_are_not_reaction_disclaimers():
    nsaid = ("Incidence Greater than 1% (Probable Causal Relationship) Nausea, heartburn. Precise Incidence Unknown "
             "(but less than 1%) Causal Relationship Unknown Arrhythmia.")
    assert lt.causality_disclaimer({"adverse_reactions": nsaid}, "nausea") is None
    amlo = ("Edema 10.8%. The following events occurred in <1% but >0.1% of patients in controlled clinical trials or under "
            "conditions of open trials or marketing experience where a causal relationship is uncertain; they are listed to "
            "alert the physician to a possible relationship: Flushing.")
    assert lt.causality_disclaimer({"adverse_reactions_ct": amlo}, "oedema") is None
    ritux = "Infection risk. The favorable risk-benefit relationship has not been established in this population."
    assert lt.causality_disclaimer({"warnings_and_cautions": ritux}, "infection") is None


def test_korean_boilerplate_is_not_a_disclaimer_but_korean_disclaimer_is():
    kaers = ("국내 자발적 유해사례 보고자료(1989-2013년)를 분석한 결과 통계적으로 유의하게 많이 보고된 유해사례는 다음과 같다. "
             "AST 증가. 다만, 이로써 곧 해당성분과 다음의 이상사례 간에 인과관계가 입증된 것을 의미하는 것은 아니다.")
    assert lt.causality_disclaimer({"adverse_reactions_pm": kaers}, "AST 증가") is None
    real = "간부전이 보고되었다. 이 약과 간부전의 인과관계는 확립되지 않았다."
    assert lt.causality_disclaimer({"warnings_and_cautions": real}, "간부전") is not None
    assert len(lt._sentences(real)) == 2   # 한글 문장 앞에서도 나눕니다


# ---------------------------------------------------------------- 비임상 PT
def test_nonclinical_terms():
    assert lt.is_nonclinical("drug ineffective") and lt.is_nonclinical("off label use")
    assert not lt.is_nonclinical("thrombocytopenia")
    for pt in ("death", "hospitalisation", "illness", "adverse event", "disease progression", "malignant neoplasm progression",
               "product packaging quantity issue", "manufacturing issue", "toxicity to various agents", "accidental overdose",
               "overdose", "complication associated with device", "tachyphylaxis", "therapeutic response changed"):
        assert lt.is_nonclinical(pt), pt
    for pt in ("sudden death", "foetal death", "inappropriate antidiuretic hormone secretion", "device related infection"):
        assert not lt.is_nonclinical(pt), pt


def test_no_designated_medical_event_is_nonclinical():
    # DME 는 한 건만으로도 의심해야 하는 사건입니다. 비임상으로 빠지면 라벨 조회와 등급에서 사라집니다
    dme = json.loads((DATA / "dme_pts.json").read_text())["pts"]
    assert len(dme) >= 60 and "sudden cardiac death" in dme
    assert [p for p in dme if lt.is_nonclinical(p)] == []
    assert not lt._NONCLINICAL.search("product contamination microbial")   # 파일이 없어도 정규식만으로 임상입니다


def test_mentions_sorted_by_regulatory_rank():
    hits = lt.find_mentions({"adverse_reactions": "rash, nausea", "boxed_warning": "WARNING: severe rash"}, "rash")
    assert [h["section"] for h in hits] == ["boxed_warning", "adverse_reactions"]
    assert all(isinstance(h["rank"], int) for h in hits)
