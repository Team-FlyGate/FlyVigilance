"""라벨 원문을 다루는 순수 함수 모음입니다. 네트워크를 쓰지 않아 테스트하기 쉽습니다.

- us_variants: MedDRA(영국식 철자)와 미국 라벨(미국식 철자)의 표기 차이를 메웁니다
- is_nonclinical: 'drug ineffective', 'off label use' 같은 비임상 PT 를 가려냅니다
- find_mentions: 라벨 절마다 반응 언급 위치와 인용문을 찾습니다
- causality_disclaimer: 그 반응에 붙은 "인과관계 미확립" 단서를 찾되, 이상반응 절 첫머리의 상투 문구는 세지 않습니다
"""
import re

# 규제 강도 순서입니다. 앞일수록 강합니다.
SECTION_RANK = {
    "boxed_warning": 3,
    "warnings_and_cautions": 2, "warnings": 2, "precautions": 2, "contraindications": 2,
    "adverse_reactions": 1, "postmarketing": 1,
}
SEARCH_SECTIONS = ["boxed_warning", "warnings_and_cautions", "warnings", "contraindications", "precautions",
                   "adverse_reactions"]

_BRIT_US = [("haem", "hem"), ("anaem", "anem"), ("aemia", "emia"), ("oedema", "edema"), ("oesophag", "esophag"),
            ("diarrhoea", "diarrhea"), ("leukaem", "leukem"), ("oestr", "estr"), ("isation", "ization"),
            ("paediatr", "pediatr"), ("foetal", "fetal"), ("haemorrhag", "hemorrhag"), ("ischaem", "ischem"),
            ("tumour", "tumor"), ("dyspnoea", "dyspnea"), ("apnoea", "apnea"), ("coeliac", "celiac"),
            ("anaesthe", "anesthe"), ("oedematous", "edematous")]

_NONCLINICAL = re.compile(
    r"(drug ineffective|off label use|product (use|dose|administ|quality|storage|substitution|label|prescrib|dispens|"
    r"complaint|contamination|physical|odour|taste abnormal)|no adverse event|wrong (technique|drug|product|dose|patient)|"
    r"inappropriate schedule|dose omission|therapy (interrupted|cessation|non-responder|change)|therapeutic product effect|"
    r"intentional product|incorrect (dose|route|product)|expired product|device |drug administered|"
    r"medication error|underdose|drug dose omission|treatment noncompliance|condition aggravated|"
    r"unevaluable event|drug interaction|exposure during pregnancy|maternal exposure|foetal exposure|"
    r"accidental exposure|intercepted|drug effect (less|decreased|incomplete|delayed|variable)|"
    r"therapeutic response (decreased|unexpected|delayed|shortened)|treatment failure|titration not performed|"
    r"dose titration|drug level (decreased|increased|below|above)|inappropriate|off-label)")

_BOILERPLATE = re.compile(r"(reported voluntarily|population of uncertain size|uncertain size|clinical trials are conducted under widely varying)",
                          re.I)
_DISCLAIMER = re.compile(
    r"(caus\w*[^.]{0,80}(has|have|had) not been (established|determined|confirmed|demonstrated)"
    r"|(has|have) not been (established|determined|confirmed)[^.]{0,60}caus"
    r"|mechanism\(s\) and causality"
    r"|no caus\w* (relationship|association|link) (has|have) been (established|determined)"
    r"|relationship[^.]{0,80}(is|has|have) not (been )?(established|known|determined)"
    r"|causal (role|relationship|association)[^.]{0,40}(is |remains )?(unknown|unclear|uncertain))", re.I)


def us_variants(term: str) -> list[str]:
    """MedDRA 영국식 PT 와 미국식 철자를 함께 돌려줍니다."""
    t = term.lower().strip()
    out = {t}
    u = t
    for a, b in _BRIT_US:
        u = u.replace(a, b)
    out.add(u)
    # MedDRA 는 'dermatitis atopic' 처럼 뒤집힌 순서를 자주 씁니다. 두 단어 PT 는 순서를 바꾼 표기도 찾습니다
    for v in list(out):
        w = v.split()
        if len(w) == 2:
            out.add(f"{w[1]} {w[0]}")
    return sorted(out, key=len, reverse=True)


def is_nonclinical(pt: str) -> bool:
    return bool(_NONCLINICAL.search(pt.lower()))


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z0-9(•\-])", text) if s.strip()]


def find_mentions(sections: dict[str, str], term: str) -> list[dict]:
    """절마다 반응 언급을 찾습니다. 결과는 규제 강도가 센 절부터 정렬됩니다."""
    hits = []
    variants = us_variants(term)
    for sec, text in sections.items():
        if not text:
            continue
        low = text.lower()
        for v in variants:
            m = re.search(r"(?<![a-z])" + re.escape(v) + r"(?![a-z])", low)
            if m:
                i = m.start()
                quote = re.sub(r"\s+", " ", text[max(0, i - 90): i + len(v) + 110]).strip()
                hits.append({"section": sec, "rank": SECTION_RANK.get(sec, 1), "term": v, "quote": quote})
                break
    return sorted(hits, key=lambda h: -h["rank"])


def causality_disclaimer(sections: dict[str, str], term: str) -> dict | None:
    """그 반응을 언급한 문장과 뒤따르는 두 문장 안에서 인과 미확립 단서를 찾습니다.
    이상반응 절 첫머리의 '자발 보고라 인과를 확정할 수 없다'는 상투 문구는 제외합니다."""
    variants = us_variants(term)
    for sec, text in sections.items():
        if not text:
            continue
        sents = _sentences(text)
        for i, s in enumerate(sents):
            sl = s.lower()
            if not any(re.search(r"(?<![a-z])" + re.escape(v) + r"(?![a-z])", sl) for v in variants):
                continue
            for w in sents[i: i + 3]:
                if _BOILERPLATE.search(w):
                    continue
                if _DISCLAIMER.search(w):
                    return {"section": sec, "quote": w[:300]}
    return None
