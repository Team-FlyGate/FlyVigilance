"""라벨 원문을 다루는 순수 함수 모음입니다. 네트워크를 쓰지 않아 테스트하기 쉽습니다.

- label_sections: openFDA 라벨을 '기재 절'과 '맥락 절'로 나눕니다. 이상반응은 임상시험(6.1)·시판 후(6.2)로 가르고,
  구형 PRECAUTIONS 는 약물상호작용·임부·수유부·소아·고령자·발암성 소항목을 기재에서 뺍니다.
  금기와 효능·효과는 환자·적응증을 적는 절이라 반응 기재로 세지 않습니다(약사 검토, 21 CFR 201.57).
- us_variants / equivalents: 영국·미국 철자, 어순, 정확히 같은 개념의 동의어(EQUIV)를 함께 봅니다
- is_nonclinical: 'drug ineffective', 'death', 'overdose' 같은 비임상·결과 PT 를 가려냅니다(DME 는 늘 임상으로 둡니다)
- find_mentions: 기재 절마다 반응 언급 위치와 인용문을 찾되, 환자군·적응증·부정·복합어 맥락의 언급은 세지 않습니다
- causality_disclaimer: 그 반응에 붙은 "인과관계 미확립" 단서를 찾되, 절·목록·표 머리의 상투 문구는 세지 않습니다
"""
import functools
import json
import re

# 기재 절입니다. 앞일수록 강합니다. 이상반응은 임상시험 > 구분 없음(구형) > 혼합 > 시판 후 순입니다.
LISTING_SECTIONS = ["boxed_warning", "warnings_and_cautions", "warnings", "precautions",
                    "adverse_reactions_ct", "adverse_reactions", "adverse_reactions_mixed", "adverse_reactions_pm"]
# 맥락 절입니다. 환자·적응증을 적는 절이라 이상반응 기재로 세지 않습니다.
CONTEXT_SECTIONS = ["contraindications", "indications_and_usage", "precautions_other"]
# 규제 강도(정수)입니다. grade.decide 와 화면의 4단계가 정수를 씁니다.
SECTION_RANK = {"boxed_warning": 3, "warnings_and_cautions": 2, "warnings": 2, "precautions": 2,
                "adverse_reactions_ct": 1, "adverse_reactions": 1, "adverse_reactions_mixed": 1, "adverse_reactions_pm": 1}
SECTION_STATUS = {"boxed_warning": "boxed", "warnings_and_cautions": "warnings_precautions", "warnings": "warnings_precautions",
                  "precautions": "warnings_precautions", "adverse_reactions_ct": "ar_clinical_trials",
                  "adverse_reactions": "ar_unspecified", "adverse_reactions_mixed": "ar_unspecified",
                  "adverse_reactions_pm": "ar_postmarketing"}
# openFDA 라벨에서 읽는 필드입니다(get_label). general_precautions 는 구형 PRECAUTIONS 의 General 소항목입니다.
SEARCH_SECTIONS = ["boxed_warning", "warnings_and_cautions", "warnings", "precautions", "general_precautions",
                   "adverse_reactions", "contraindications", "indications_and_usage"]

_BRIT_US = [("haem", "hem"), ("aemia", "emia"), ("oedema", "edema"), ("oesophag", "esophag"), ("rrhoea", "rrhea"),
            ("leukaem", "leukem"), ("leucocyt", "leukocyt"), ("oestr", "estr"), ("isation", "ization"), ("ised", "ized"),
            ("ising", "izing"), ("paed", "ped"), ("foet", "fet"), ("ischaem", "ischem"), ("tumour", "tumor"),
            ("pnoea", "pnea"), ("coeliac", "celiac"), ("aesthe", "esthe"), ("behaviour", "behavior"),
            ("distension", "distention"), ("faec", "fec"), ("caesar", "cesar"), ("colour", "color"), ("odour", "odor")]

# 정확히 같은 개념만 묶습니다. 한쪽이 다른 쪽 PT 아래의 MedDRA LLT 이거나(예: LLT Fever → PT Pyrexia),
# 버전이 바뀌며 PT 이름만 달라진 경우(PT Renal failure acute → PT Acute kidney injury, MedDRA 18.0)입니다.
# 넓거나 좁은 개념(간염 ↔ 간손상, 신부전 ↔ 급성 신손상, 백혈구감소 ↔ 호중구감소)은 넣지 않습니다(ICH E2A 특이성).
EQUIV = [
    ("pyrexia", "fever"),                                                   # LLT Fever → PT Pyrexia
    ("acute kidney injury", "acute renal failure", "renal failure acute"),  # 옛 PT Renal failure acute, LLT Acute renal failure
    ("cardiac failure", "heart failure"),                                   # LLT Heart failure → PT Cardiac failure
    ("cardiac failure congestive", "congestive heart failure", "congestive cardiac failure"),  # LLT Congestive heart failure
    ("cerebrovascular accident", "stroke"),                                 # LLT Stroke → PT Cerebrovascular accident
    ("weight increased", "weight gain"),                                    # LLT Weight gain → PT Weight increased
    ("weight decreased", "weight loss"),                                    # LLT Weight loss → PT Weight decreased
    ("somnolence", "drowsiness"),                                           # LLT Drowsiness → PT Somnolence
    ("hyperhidrosis", "sweating", "excessive sweating", "increased sweating", "sweating increased"),  # LLT Sweating 등
    ("influenza", "flu"),                                                   # LLT Flu → PT Influenza
    ("infusion related reaction", "infusion reaction"),                     # LLT Infusion reaction → PT Infusion related reaction
    ("pruritus", "itching"),                                                # LLT Itching → PT Pruritus
    ("urticaria", "hives"),                                                 # LLT Hives → PT Urticaria
    ("alopecia", "hair loss"),                                              # LLT Hair loss → PT Alopecia
    ("dyspnea", "shortness of breath"),                                     # LLT Shortness of breath → PT Dyspnoea
    ("myalgia", "muscle pain", "muscle ache"),                              # LLT Muscle pain → PT Myalgia
    ("arthralgia", "joint pain"),                                           # LLT Joint pain → PT Arthralgia
    ("epistaxis", "nosebleed", "nose bleed"),                               # LLT Nosebleed → PT Epistaxis
    ("syncope", "fainting"),                                                # LLT Fainting → PT Syncope
    ("hot flush", "hot flash"),                                             # LLT Hot flashes → PT Hot flush
    ("myocardial infarction", "heart attack"),                              # LLT Heart attack → PT Myocardial infarction
    ("multiple organ dysfunction syndrome", "multiple organ failure", "multiorgan failure", "multi organ failure"),
    ("decreased appetite", "loss of appetite"),                             # LLT Loss of appetite → PT Decreased appetite
    ("abdominal distention", "bloating"),                                   # LLT Bloating → PT Abdominal distension
    ("hypertension", "high blood pressure"),                                # LLT High blood pressure → PT Hypertension
    ("hypotension", "low blood pressure"),                                  # LLT Low blood pressure → PT Hypotension
    ("fatigue", "tiredness"),                                               # LLT Tiredness → PT Fatigue
    ("dysphagia", "difficulty swallowing"),                                 # LLT Difficulty swallowing → PT Dysphagia
    ("rhinorrhea", "runny nose"),                                           # LLT Runny nose → PT Rhinorrhoea
    ("pain in extremity", "limb pain", "pain in limb"),                     # LLT Limb pain → PT Pain in extremity
    ("brain edema", "cerebral edema"),                                      # LLT Cerebral oedema → PT Brain oedema
    ("skin exfoliation", "skin peeling"),                                   # LLT Skin peeling → PT Skin exfoliation
    ("ocular hyperemia", "eye redness", "red eye"),                         # LLT Red eye → PT Ocular hyperaemia
    ("road traffic accident", "motor vehicle accident"),                    # LLT Motor vehicle accident → PT Road traffic accident
    ("depressed level of consciousness", "decreased level of consciousness"),
]
_QUAL = {"increased", "decreased", "abnormal", "acute", "chronic", "upper", "lower", "positive"}

_NONCLINICAL = re.compile(
    r"(drug ineffective|off label use|product (use|dose|administ|quality|storage|substitution|label|prescrib|dispens|"
    r"complaint|contamination(?! microbial)|physical|odour|taste abnormal)|no adverse event|wrong (technique|drug|product|dose|patient)|"
    r"inappropriate (schedule|prescrib)|dose omission|therapy (interrupted|cessation|non-responder|change)|therapeutic product effect|"
    r"intentional product|incorrect (dose|route|product)|expired product|device |drug administered|"
    r"medication error|underdose|drug dose omission|treatment noncompliance|condition aggravated|"
    r"unevaluable event|drug interaction|exposure during pregnancy|maternal exposure|foetal exposure|"
    r"accidental exposure|intercepted|drug effect (less|decreased|incomplete|delayed|variable)|"
    r"therapeutic response (decreased|unexpected|delayed|shortened)|treatment failure|titration not performed|"
    r"dose titration|drug level (decreased|increased|below|above)|product administered to patient of inappropriate|off-label)")
# 결과·경과·제품 문제 PT 입니다. 이름 전체가 같을 때만 비임상으로 봅니다('sudden cardiac death' 는 임상 사건입니다).
_OUTCOME_PT = re.compile(
    r"^(death|hospitali[sz]ation|illness|adverse (event|drug reaction|reaction)|disease progression|"
    r"(malignant )?neoplasm progression|product (ineffective|availability issue|preparation (issue|error)|supply issue|packaging\b.*)|"
    r"manufacturing\b.*issue|toxicity to various agents|(accidental |intentional |prescribed )?overdose|"
    r"complication associated with device|tachyphylaxis|therapeutic response changed)$")
# 감염·혈전 같은 임상 사건이 기기·제품 PT 이름 안에 있으면 임상으로 둡니다
_CLINICAL_EVENT = re.compile(r"(infection|sepsis|bacter(a)?emia|thrombosis|abscess|cellulitis|ha?ematoma|contamination microbial|"
                             r"transmission of an infectious agent|antidiuretic hormone)")

# ---------------------------------------------------------------- 이상반응 절 나누기 (6.1 임상시험 / 6.2 시판 후)
# 시판 후 소항목 머리글입니다. 번호가 아니라 이름으로 찾습니다(6.2 가 면역원성이고 6.3 이 시판 후인 라벨이 있습니다).
PM_HEAD = re.compile(
    r"(?<!\band )(?<!\bor )(?<!\bsee )(?<!\bSee )"
    r"(?:\b6\.\d{1,2}\s+)?"
    r"(?:Adverse (?:Reactions|Events) (?:Reported )?(?:[Dd]uring|from|in the) )?"
    r"(?:Post[- ]?[Mm]arketing|POST[- ]?MARKETING|PostMarketing|Post[- ]?[Aa]pproval|POST[- ]?APPROVAL)\s+"
    r"(?:Experiences?|EXPERIENCES?|Spontaneous Reports|Reports|REPORTS|Adverse (?:Events|Reactions|Drug Reactions)|"
    r"ADVERSE (?:EVENTS|REACTIONS)|Serious Adverse Reactions|Surveillance|SURVEILLANCE|Events|Use|Data)\b")
# 머리글 없이 시판 후 목록이 시작되는 라벨의 첫 문장입니다
PM_LEAD = re.compile(r"The following (?:additional )?adverse (?:reactions|events|drug reactions) (?:have been|were|has been) "
                     r"(?:identified|reported) during (?:the )?(?:post[- ]?approval|post[- ]?marketing) (?:use|experience|period|surveillance)",
                     re.I)
# 임상시험과 자발보고를 한데 묶은 절입니다. 나눌 수 없습니다
MIXED = re.compile(r"(clinical (?:trials?|studies)(?: experience)? (?:and|or) (?:from )?post[- ]?(?:marketing|approval)"
                   r"|voluntary reports or clinical (?:studies|trials)|clinical (?:studies|trials) or voluntary reports"
                   r"|(?:clinical (?:trials?|studies)|premarketing)[^.]{0,40}(?:and|or) (?:in |from |during )?post[- ]?marketing (?:reports|experience|surveillance|use))",
                   re.I)
# 다음 번호 소항목 머리글("6.3 Immunogenicity")입니다. "(6.3)" 같은 참조는 뺍니다
NEXT_NUM = re.compile(r"(?<![(\[])(?<![(\[] )\b6\.\d{1,2}\s+[A-Z][a-z]")
PM_BOILER_EN = re.compile(r"(reported voluntarily|population of uncertain size|not always possible to (?:reliably )?estimate)", re.I)


def split_adverse_reactions(text: str, plr: bool = False) -> dict[str, str]:
    """이상반응 절을 임상시험(_ct)·시판 후(_pm)·혼합(_mixed)·구분 없음(adverse_reactions) 조각으로 나눕니다.
    openFDA 는 절을 두 번 싣기도 해서 머리글을 모두(finditer) 찾습니다."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t:
        return {}
    anchors = list(PM_HEAD.finditer(t)) or list(PM_LEAD.finditer(t))
    spans: list[tuple[int, int]] = []
    for m in anchors:
        if spans and m.start() < spans[-1][1]:
            continue
        nxt = NEXT_NUM.search(t, m.end())
        spans.append((m.start(), nxt.start() if nxt else len(t)))
    pm = " ".join(t[a:b] for a, b in spans).strip()
    rest, last = [], 0
    for a, b in spans:
        rest.append(t[last:a])
        last = b
    rest = " ".join(x.strip() for x in rest + [t[last:]] if x.strip())
    out = {"adverse_reactions_pm": pm} if pm else {}
    if rest:
        if MIXED.search(rest) or (not spans and PM_BOILER_EN.search(rest)):
            out["adverse_reactions_mixed"] = rest
        elif plr or spans:
            out["adverse_reactions_ct"] = rest   # PLR 6 절에서 시판 후 소항목을 뺀 나머지는 임상시험 근거입니다
        else:
            out["adverse_reactions"] = rest      # 구형 라벨: 출처를 알 수 없습니다
    return out


# ---------------------------------------------------------------- 구형 PRECAUTIONS 나누기
# 환자군·병용약 소항목입니다. 이 안의 언급은 경고·주의 수준의 기재로 세지 않습니다.
_PREC_OTHER = (r"(?:Clinically Significant )?Drug(?:[-/ ](?:Drug|Laboratory Test|Lab Test))? [Ii]nteractions?(?: with [A-Z]\w+)?"
               r"|DRUG(?:/LABORATORY TEST)? INTERACTIONS|Drug-Laboratory Test Interactions|Pregnancy|PREGNANCY|Teratogenic Effects"
               r"|Nonteratogenic Effects|Non-teratogenic Effects|Labor and [Dd]elivery|LABOR AND DELIVERY|Nursing(?: [Mm]others)?"
               r"|NURSING MOTHERS|Lactation|LACTATION|Pediatric Use|PEDIATRIC USE|Geriatric Use|GERIATRIC USE"
               r"|Carcinogenesis(?:,? (?:and )?Mutagenesis)?|CARCINOGENESIS")
_PREC_KEEP = (r"General(?: Precautions)?|GENERAL(?: PRECAUTIONS)?|Information for Patients(?:/Caregivers)?|INFORMATION FOR PATIENTS"
              r"|Laboratory [Tt]ests|LABORATORY TESTS")
_PREC_HEAD = re.compile(r"(?:^|(?<=[.:;)\]]\s)|(?<=PRECAUTIONS\s)|(?<=PRECAUTIONS:\s)|(?<=\b[A-Z]\.\s)|(?<=\b\d\.\s)|(?<=\b\d\d\.\s))"
                        rf"(?:(?P<other>{_PREC_OTHER})|(?P<keep>{_PREC_KEEP}))(?=[\s:;,.]|$)(?!\s*\))")


def split_precautions(text: str) -> tuple[str, str]:
    """구형 PRECAUTIONS 를 (일반 주의, 환자군·상호작용 소항목)으로 나눕니다. 머리글 앞의 본문은 일반 주의로 둡니다."""
    t = re.sub(r"\s+", " ", text or "").strip()
    keep, other, cur, last = [], [], "keep", 0
    for m in _PREC_HEAD.finditer(t):
        if re.search(r"\b(?:see|See|SEE)\b[^.)]{0,30}$", t[max(0, m.start() - 40):m.start()]):
            continue   # "(see PRECAUTIONS: Drug Interactions)" 같은 참조입니다
        (keep if cur == "keep" else other).append(t[last:m.start()])
        cur, last = ("other" if m.group("other") else "keep"), m.start()
    (keep if cur == "keep" else other).append(t[last:])
    return " ".join(x.strip() for x in keep if x.strip()), " ".join(x.strip() for x in other if x.strip())


def label_sections(d: dict) -> dict[str, str]:
    """openFDA 라벨 한 건을 절 이름 → 본문으로 바꿉니다. 기재 절(LISTING_SECTIONS)과 맥락 절(CONTEXT_SECTIONS)을 함께 돌려줍니다."""
    def j(k):
        v = d.get(k) or []
        return re.sub(r"\s+", " ", " ".join([v] if isinstance(v, str) else v)).strip()
    out = {k: j(k) for k in ("boxed_warning", "warnings_and_cautions", "warnings", "contraindications", "indications_and_usage")}
    prec, other = split_precautions(j("precautions"))
    gp = j("general_precautions")
    if gp and gp[:80] not in prec:
        prec = (prec + " " + gp).strip()
    out.update({"precautions": prec, "precautions_other": other})
    ar = j("adverse_reactions")
    if ar:
        plr = bool(d.get("warnings_and_cautions")) or bool(re.match(r"\s*6\s+ADVERSE", ar, re.I)) or bool(re.search(r"\b6\.1\s+[A-Z]", ar))
        out.update(split_adverse_reactions(ar, plr))
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------- 반응명 변형
def _us(t: str) -> str:
    for a, b in _BRIT_US:
        t = t.replace(a, b)
    return t


def _norm(term: str) -> str:
    return re.sub(r"\s+", " ", term.lower().replace("-", " ")).strip()


@functools.lru_cache(maxsize=1)
def _equiv_index() -> dict[str, tuple[str, ...]]:
    idx = {}
    for grp in EQUIV:
        g = tuple(_norm(x) for x in grp)
        for x in g:
            idx[_us(x)] = g
    return idx


@functools.lru_cache(maxsize=4096)
def variants(term: str) -> tuple[tuple[str, str], ...]:
    """반응명의 표기 변형과 그 근거입니다. ('literal'|'spelling'|'reorder'|'synonym') 순으로, 앞의 것이 우선합니다."""
    t = _norm(term)
    out: dict[str, str] = {}

    def add(v, via):
        v = _norm(v)
        if v and v not in out:
            out[v] = via
    add(t, "literal")
    u = _us(t)
    add(u, "spelling")
    for base in dict.fromkeys([t, u]):
        w = base.split()
        if len(w) == 2:
            add(f"{w[1]} {w[0]}", "reorder")        # MedDRA 는 'dermatitis atopic' 처럼 뒤집힌 순서를 자주 씁니다
        if len(w) >= 3 and w[-1] in _QUAL:
            add(" ".join([w[-1]] + w[:-1]), "reorder")   # 'renal failure acute' → 'acute renal failure'
        if w and w[-1] in ("increased", "decreased") and len(w) >= 2:
            x = w[:-1]
            if x[0] == "blood" and len(x) >= 2 and x[1] != "pressure":
                x = x[1:]                                # 'blood creatinine increased' → 'creatinine increased'
                add(" ".join(x + [w[-1]]), "reorder")
            add(" ".join([w[-1]] + x), "reorder")
            if w[-1] == "increased":
                add("elevated " + " ".join(x), "reorder")
    for base in dict.fromkeys([t, u]):
        for s in _equiv_index().get(_us(base), ()):
            add(s, "synonym")
            add(_us(s), "synonym")
    return tuple(out.items())


def us_variants(term: str) -> list[str]:
    """MedDRA 영국식 PT 와 미국식 철자, 어순 변형, 정확한 동의어를 함께 돌려줍니다(긴 것부터)."""
    return sorted({v for v, _ in variants(term)}, key=len, reverse=True)


def equivalents(term: str) -> list[str]:
    """문헌 검색에 OR 로 넣을 정확한 동의어입니다(PT 자체 + EQUIV 묶음). 어순·'elevated X' 변형은 넣지 않습니다."""
    t = _norm(term)
    out = [term.lower().strip()]
    for v in _equiv_index().get(_us(t), ()):
        if v != t and v not in out:
            out.append(v)
    return out


def is_nonclinical(pt: str) -> bool:
    p = pt.lower().strip()
    if _CLINICAL_EVENT.search(p) or p in _dme():
        return False
    return bool(_NONCLINICAL.search(p) or _OUTCOME_PT.match(p))


@functools.lru_cache(maxsize=1)
def _dme() -> frozenset:
    """EMA 지정 의학적 사건(DME)입니다. 한 건만으로도 의심해야 하는 사건이라 어떤 규칙으로도 비임상으로 빼지 않습니다."""
    try:
        from .config import DATA
        return frozenset(t.lower() for t in json.loads((DATA / "dme_pts.json").read_text())["pts"])
    except Exception:  # noqa: BLE001  목록 파일이 없어도 정규식만으로 동작합니다
        return frozenset()


# ---------------------------------------------------------------- 언급 찾기와 맥락 가드
@functools.lru_cache(maxsize=8192)
def _pattern(v: str) -> re.Pattern:
    toks = v.split()
    parts = [re.escape(x).replace("'", "['’]?") for x in toks]
    last = toks[-1]
    if re.search(r"[^aeiou]y$", last):
        parts[-1] = re.escape(last[:-1]) + "(?:y|ies)"              # neuropathy → neuropathies
    elif re.search(r"(is|us|ys|ss)$", last):
        parts[-1] = parts[-1] + ("(?:es)?" if last.endswith("ss") else "")
    elif last.endswith("s") and len(last) > 3:
        parts[-1] = re.escape(last[:-1]) + "(?:s|es)?"               # muscle spasms → muscle spasm
    else:
        parts[-1] = parts[-1] + "(?:s|es)?"                          # seizure → seizures, rash → rashes
    # 단어 사이는 공백·하이픈을 모두 받습니다('infusion-related'). 'pre-eclampsia' 안의 'eclampsia' 는 세지 않습니다
    return re.compile(r"(?<![a-z])(?<![a-z]-)" + r"[\s\-]+".join(parts) + r"(?![a-z])", re.I)


# 환자군·적응증·기왕력 맥락입니다. 이 말 뒤에 온 반응명은 그 약이 일으킨 반응이 아니라 환자 상태입니다.
_POP = re.compile(
    r"\b(?:(?:patients?|subjects?|adults?|children|adolescents?|women|men|infants|neonates|individuals|those|people|persons)"
    r"\s+(?:(?!treated|dosed|administered|given|receiving|taking|randomi[sz]ed|exposed|who|had|has|have|was|were|is|are|"
    r"present|develop|experienc|report|[\w-]*ed\b)[\w-]+\s+){0,6}"
    r"(?:with|who (?:have|had|are|were)|on|undergoing|requiring)"
    r"|history of|pre-?existing|preexisting|underlying|co-?existing|co-?morbid\w*|predisposed to|predisposition to"
    r"|treatment of|to treat|management of|prevention of|prophylaxis of|indicated (?:for|in|as)|indication"
    r"|known (?!to\b)|prior (?!to\b)|previous|screen\w*(?: \w+)? for|test\w*(?: \w+)? for|if you (?:have|had|are)|diagnosed with"
    r"|diagnosis of)\b", re.I)
# 가드 뒤에 이 말이 오면 약물 반응 서술입니다("patients who develop hepatitis")
_EVENT = re.compile(r"\b(?:develop\w*|experienc\w*|report\w*|occur\w*|observ\w*|present(?:ed|ing|s)? with|signs?|symptoms?|onset|"
                    r"new|worsening|worsened|induced|caused|associated|incidence|frequenc\w*|rates?|reactions?|events?|"
                    r"episodes?|cases?|toxicit\w*|adverse|exception)\b", re.I)
_NEG = re.compile(r"(?:\b(?:no|(?<!with or )without|neither|nor|absence of|lack of|free of|rule out|ruled out|exclud\w*)\b(?:\s+\S+){0,6}\s*$"
                  r"|\b(?:did|was|were|has|have|had)\s+not\b(?!\s+(?:always|necessarily|only|limited))(?:\s+\S+){0,4}\s*$)",
                  re.I)
# 'psoriasis trials', 'Asthma Trials' 처럼 이어지면 환자군입니다. 소항목 머리글 뒤의 'Patients should ...' 는 제외하려고
# patients·subjects 는 소문자일 때만 봅니다
_FOLLOW_POP = re.compile(r"^[\s\-]+(?:[Cc]linical\s+)?(?:[Tt]rials?|[Ss]tudies|[Ss]tudy|patients|subjects|[Pp]opulations?|[Pp]rogram|"
                         r"[Rr]egistry)\b")
# 적응증과 같은 반응명은 이런 사건 표현이 붙을 때만 기재로 셉니다('worsening of psoriasis', 'asthma exacerbation')
_IND_EVENT_PRE = re.compile(r"(?:worsening|worsened|exacerbation|exacerbated|new[\s-]onset|de novo|flares?|paradoxical|aggravat\w*|"
                            r"induced|reactivation|onset of|development of|occurrence of|cases of|reports? of|developed|"
                            r"potential for|risk (?:of|for))"
                            r"(?:\s+(?:or|and|of|in|the|new|a|an|symptoms?|signs?)){0,4}[\s:,(]*$", re.I)
_IND_EVENT_POST = re.compile(r"^[\s,]*(?:\([^)]{1,15}\)\s*)?(?:\(?\s*(?:worsening|exacerbations?|flares?|aggravated|events?)\b|(?:was|were|has been|have been) "
                             r"(?:reported|observed)|occurred)|^\s*(?:\(?\s*\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s+\(\s*\d)", re.I)  # 표·목록의 발생률
_FOLLOW_NEG = re.compile(r"^[\s,]*(?:was|were|has been|have been)\s+(?:not|never)\s+(?:observed|reported|seen|noted|associated)", re.I)
# 반응명 뒤·앞에 붙어 다른 개념이 되는 복합어입니다(ICH E2A 특이성: 'hepatitis B reactivation' 은 약물 간염이 아닙니다)
_COMPOUND = {
    "hepatitis": (r"(?:autoimmune|viral|alcoholic|chronic|neonatal)", r"(?:[a-e]\b|virus|viral|b/c)"),
    "eczema": (None, r"herpeticum"),
    "erythema": (None, r"(?:multiforme|nodosum|migrans|infectiosum|annulare|marginatum)"),
    "dermatitis": (r"(?:atopic|seborrh?o?eic)", r"herpetiformis"),
    "injury": (r"(?:kidney|renal|liver|hepatic|lung|brain|spinal cord|nerve|tissue|myocardial)", None),
    "death": (r"(?:programmed(?: cell)?|cell)", r"(?:receptor|ligand)"),
    "fever": (r"(?:hay|rheumatic|typhoid|paratyphoid|yellow|dengue|scarlet|q|glandular|spotted|valley|lassa|mediterranean|relapsing)",
              r"blisters?"),
    "stroke": (r"(?:heat|sun)", r"volume"),
    "flu": (None, r"(?:like|vaccin\w*|syndrome)"),
    "influenza": (None, r"(?:like|vaccin\w*|syndrome)"),
    "sweating": (r"(?:night|cold)", None),
    "inflammation": (r"(?:mediates?|mediated|mediating)", None),
    "myocardial infarction": (r"thrombolysis in", None),   # TIMI 출혈 척도 이름입니다
    "fall": (None, r"(?:below|to|within|outside|by|under|into|between)\b"),   # 'eGFR falls below 45'
}
# MedDRA 기관계(SOC) 머리글입니다. 'Gastrointestinal Disorders:' 는 반응명이 아니라 목록의 분류 이름입니다
_SOC = re.compile(
    r"(?:infections and infestations|blood and lymphatic system disorders|cardiac disorders|congenital, familial and genetic disorders"
    r"|ear and labyrinth disorders|endocrine disorders|eye disorders|gastrointestinal disorders|general disorders(?: and administration "
    r"site conditions)?|hepatobiliary disorders|immune system disorders|injury, poisoning and procedural complications|investigations"
    r"|metabolism and nutrition(?:al)? disorders|musculoskeletal(?: system)?(?: and connective tissue)? disorders|neoplasms benign"
    r"|nervous system disorders|psychiatric disorders|renal(?: and urinary)? disorders|reproductive system and breast disorders"
    r"|respiratory, thoracic and mediastinal disorders|skin and subcutaneous tissue disorders|vascular disorders"
    r"|statistical manual of mental disorders)", re.I)
# 환자군 가드는 글머리표에서 끊지 않습니다(일반의약품 'Ask a doctor before use if you have • nausea • ...')
_BREAK = re.compile(r"[.;:!?](?=\s|$)|[()\[\]]")
_BREAK_NEG = re.compile(r"[.;:!?,](?=\s|$)|[()\[\]•▪◦]")


def _guard(text: str, s: int, e: int, v: str) -> str | None:
    """이 언급을 세지 말아야 하면 이유를, 세도 되면 None 을 돌려줍니다."""
    pre = text[max(0, s - 100):s]
    cut = [m.end() for m in _BREAK.finditer(pre)]
    clause = pre[cut[-1]:] if cut else pre
    post = text[e:e + 40]
    for m in _SOC.finditer(text, max(0, s - 60), min(len(text), e + 60)):
        if m.start() <= s and m.end() >= e:
            return "compound"
    before, after = _COMPOUND.get(v, (None, None))
    if before and re.search(r"\b" + before + r"[\s\-]+$", pre, re.I):
        return "compound"
    if after and re.match(r"^[\s\-]+" + after, post, re.I):
        return "compound"
    ncut = [m.end() for m in _BREAK_NEG.finditer(pre)]
    if _NEG.search(pre[ncut[-1]:] if ncut else pre) or _FOLLOW_NEG.match(post):
        return "negation"
    for m in reversed(list(_POP.finditer(clause))):
        gap = clause[m.end():]
        if not _EVENT.search(gap) and len(gap.split()) <= 8:   # 가드 말과 반응명 사이가 멀면 다른 구절로 봅니다
            return "population"
        break
    if _FOLLOW_POP.match(post):
        return "population"
    return None


def scan(text: str, term: str, compound_only: bool = False, indication: bool = False) -> list[dict]:
    """본문에서 반응명(변형 포함) 언급을 모두 찾습니다. 각 언급에 guard(세지 않는 이유 또는 None)를 붙입니다.
    indication=True 는 반응명이 그 약의 적응증일 때입니다. 악화·새 발생 같은 사건 표현이 붙은 언급만 셉니다."""
    out, seen = [], set()
    for v, via in variants(term):
        for m in _pattern(v).finditer(text):
            if m.start() in seen:
                continue
            seen.add(m.start())
            g = _guard(text, m.start(), m.end(), v)
            if compound_only and g != "compound":
                g = None
            if g is None and indication and not (_IND_EVENT_PRE.search(text[max(0, m.start() - 60):m.start()])
                                                 or _IND_EVENT_POST.match(text[m.end():m.end() + 40])):
                g = "indication"
            out.append({"start": m.start(), "end": m.end(), "variant": v, "via": via, "guard": g})
    return out


_VIA_ORDER = {"literal": 0, "spelling": 1, "reorder": 2, "synonym": 3}


def _quote(text: str, s: int, e: int, before: int = 90, after: int = 110) -> str:
    return re.sub(r"\s+", " ", text[max(0, s - before): e + after]).strip()


def find_mentions(sections: dict[str, str], term: str, indication: bool = False) -> list[dict]:
    """기재 절마다 반응 언급을 찾습니다. 맥락 가드를 통과한 언급만 세고, 규제 강도가 센 절부터 정렬합니다.
    금기·효능효과처럼 기재 절이 아닌 키는 보지 않습니다."""
    hits = []
    for sec in LISTING_SECTIONS:
        text = sections.get(sec)
        if not text:
            continue
        occ = [o for o in scan(text, term, indication=indication) if o["guard"] is None]
        if not occ:
            continue
        o = min(occ, key=lambda x: (_VIA_ORDER[x["via"]], x["start"]))
        hits.append({"section": sec, "rank": SECTION_RANK[sec], "status": SECTION_STATUS[sec], "term": o["variant"],
                     "matched_via": o["via"], "quote": _quote(text, o["start"], o["end"])})
    return hits


def context_mention(sections: dict[str, str], term: str, section: str) -> str | None:
    """맥락 절(금기, 효능·효과)에 반응명이 나오면 짧은 인용문을 돌려줍니다. 환자군 가드는 쓰지 않고 복합어만 거릅니다."""
    text = sections.get(section)
    if not text:
        return None
    occ = [o for o in scan(text, term, compound_only=True) if o["guard"] is None]
    if not occ:
        return None
    o = min(occ, key=lambda x: x["start"])
    return _quote(text, o["start"], o["end"], 60, 90)


def indication_disease(sections: dict[str, str], term: str) -> bool:
    """반응명이 그 약의 적응증 질환인지 봅니다. 효능·효과 절에서 'treatment of X', 'patients with X', '1.1 X' 처럼
    적응증 자리에 나올 때만 참입니다. 공황 발작 증상 목록의 'palpitations' 같은 증상 나열은 질환으로 보지 않습니다."""
    text = sections.get("indications_and_usage")
    if not text:
        return False
    for o in scan(text, term):
        if o["guard"] == "population":
            return True
        if o["guard"] is None and re.search(r"(?:\b\d{1,2}(?:\.\d{1,2})?\s+|indicated:?\s+|•\s*)$", text[max(0, o["start"] - 20):o["start"]]):
            return True
    return False


def pt_facts(sections: dict[str, str], pt: str) -> dict:
    """PT 하나의 라벨 사실입니다. evidence.label_facts 의 by_pt 항목과 대표 인용(primary)을 함께 돌려줍니다."""
    ind_term = context_mention(sections, pt, "indications_and_usage") is not None
    ind = ind_term and indication_disease(sections, pt)
    m = find_mentions(sections, pt, indication=ind)
    rank = max((h["rank"] for h in m), default=0)
    status = m[0]["status"] if m else "unlisted"
    if m and rank == 1:   # 이상반응 안에서는 임상시험 > 구분 없음 > 시판 후 순입니다
        secs = {h["section"] for h in m}
        status = ("ar_clinical_trials" if "adverse_reactions_ct" in secs else
                  "ar_unspecified" if secs & {"adverse_reactions", "adverse_reactions_mixed"} else "ar_postmarketing")
    return {"sections": [h["section"] for h in m], "rank": int(rank), "label_status": status,
            "disclaimer": causality_disclaimer(sections, pt, indication=ind) if m else None,
            "contraindication": context_mention(sections, pt, "contraindications"),
            "indication_term": ind_term,
            "matched_via": m[0]["matched_via"] if m else None, "primary": m[0] if m else None}


# ---------------------------------------------------------------- 인과 미확립 단서
# 절·목록·표 머리의 상투 문구입니다. 특정 반응에 붙은 단서가 아닙니다(국내 KAERS·실마리정보 문구 포함).
_BOILERPLATE = re.compile(
    r"(reported voluntarily|population of uncertain size|uncertain size|clinical trials are conducted under widely varying"
    r"|causal relationship unknown|probable causal relationship|(?:events?|reactions?) (?:occurred|were reported|reported) in [<≤]"
    r"|listed to alert|where a causal relationship is uncertain"
    r"|인과\s*관계가\s*입증된\s*것을\s*의미하는\s*것은\s*아니)", re.I)
_DISCLAIMER = re.compile(
    r"(caus\w*[^.]{0,80}(has|have|had) not been (established|determined|confirmed|demonstrated)"
    r"|(has|have) not been (established|determined|confirmed)[^.]{0,60}caus"
    r"|mechanism\(s\) and causality"
    r"|no caus\w* (relationship|association|link) (has|have) been (established|determined)"
    r"|(?<!benefit )(?<!risk )(?<!benefit-)(?<!risk-)(?<!response )(?<!dose-)relationship[^.]{0,80}(is|has|have) not (been )?"
    r"(established|known|determined)"
    r"|causal (role|relationship|association)[^.]{0,40}(is |remains )?(unknown|unclear|uncertain)"
    r"|인과\s*관계(?:가|는)?\s*(?:확립|입증|규명)되지\s*않)", re.I)


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z0-9(•\-가-힣])", text) if s.strip()]


def causality_disclaimer(sections: dict[str, str], term: str, indication: bool = False) -> dict | None:
    """기재 절에서 그 반응을 언급한 문장과 뒤따르는 두 문장 안에서 인과 미확립 단서를 찾습니다.
    절 첫머리의 '자발 보고라 인과를 확정할 수 없다'는 문구와 목록·표 머리의 단서는 제외합니다."""
    for sec in LISTING_SECTIONS:
        text = sections.get(sec)
        if not text:
            continue
        sents = _sentences(text)
        for i, s in enumerate(sents):
            if not any(o["guard"] is None for o in scan(s, term, indication=indication)):
                continue
            for w in sents[i: i + 3]:
                if _BOILERPLATE.search(w):
                    continue
                if _DISCLAIMER.search(w):
                    return {"section": sec, "quote": w[:300]}
    return None
