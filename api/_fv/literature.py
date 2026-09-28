"""문헌 읽기 단계입니다 (확장 계획 제안 2, 약사 검토 반영).

PubMed 검색 → 초록 가져오기(efetch) → Nemotron 리랭커로 후보 재정렬(상위 20편 중 6편) → 관문(이 약과 이 반응을 실제로 다루는가) → 연구 설계별 항목 추출.
- 연구 설계는 PubMed 가 붙인 출판 유형(PublicationType)이 있으면 규칙으로 정합니다. 없을 때만 Jev 가 고릅니다.
  설계 질문의 문구와 선택지(DESIGNS)는 pipeline/bench/literature_eval.py 의 사본과 한 글자도 다르지 않아야 합니다.
- 관문(addresses): 두 이름이 함께 나온다고 그 논문이 연관을 보고한 것은 아닙니다(부작용 목록에 한 줄 언급된 총설 등).
  focus·reported 만 relevant 로 세고, passing·unrelated 는 지지 편수에서 뺍니다.
- 증례보고·증례군: 발현 시간, 중단 후 경과, 재투여(따로 묻습니다), 대안 원인 배제와 객관적 확인, 저자가 쓴 인과성 척도.
- 비교 연구(메타분석·RCT·코호트·환자대조군·PV DB 연구): 효과 방향과 유의성, 환자 수, 비교군, 용량 관계.
- 공통: 작용 기전과 계열 효과. 초록에 없으면 not_stated 를 고르게 합니다.
- Jev 는 쌍마다 한 번만 부릅니다(최대 6편, 편당 최대 8문항). Jev 가 없거나 실패하면 판정하지 않은 것으로 남깁니다
  (supports=None, analytic_status='not_judged'). '지지 안 함'으로 읽지 않습니다.
- 초록 원문은 판정과 규칙 언급 확인(title_mentions, abstract_mentions)에만 쓰고 결과에는 남기지 않습니다.
근거 ID: pubmed:<pmid>#<design>
"""
import asyncio
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET

import httpx

from . import calllog, clients, config, evidence, labeltext

DESIGNS = {
    "meta_analysis": "meta-analysis or systematic review",
    "rct": "randomized controlled trial",
    "cohort": "cohort study (prospective or retrospective)",
    "case_control": "case-control study",
    "pharmacovigilance": "disproportionality / spontaneous-report database study",
    "case_series": "case series (several patients)",
    "case_report": "single case report",
    "review": "narrative review",
    "preclinical": "animal or in vitro study",
    "other": "other (letter, editorial, guideline, unrelated)",
}
ANALYTIC = {"meta_analysis", "rct", "cohort", "case_control"}
ANECDOTAL = {"case_report", "case_series"}
COMPARATIVE = ANALYTIC | {"pharmacovigilance"}   # 비교 항목을 묻는 설계입니다. 요약의 분석 연구(ANALYTIC)는 그대로 둡니다.

_PUBTYPE = [  # 앞에 있을수록 우선합니다
    ("Meta-Analysis", "meta_analysis"), ("Systematic Review", "meta_analysis"),
    ("Randomized Controlled Trial", "rct"),
    ("Case Reports", "case_report"),
    ("Review", "review"),
]
STRENGTH = ["no evidence of association", "anecdotal (single case)", "suggestive (case series or weak signal)",
            "consistent (analytic study supports association)", "established (multiple analytic studies or regulatory consensus)"]

# 문헌 증례와 FAERS 건수의 이중 계산 경고입니다(grade·kr 화면에 붙입니다).
DOUBLE_COUNT_NOTE = ("논문에 실린 증례는 제약사가 FAERS 에도 보고하는 경우가 많습니다. 미국 21 CFR 314.80 은 과학 문헌의 이상사례 정보를 "
                     "검토하도록 의무로 두기 때문입니다. 그래서 문헌 편수와 FAERS 건수를 서로 독립된 근거로 더하지 않습니다.")

# ---------------------------------------------------------------- 질문 선택지
# 관문 문구는 실측(15쌍 81편)에서 약물 안전성 총설을 passing 으로 떨어뜨리던 첫 문구를 고친 두 번째 문구입니다.
GATE = {
    "focus": "the association between this drug and this event is a main subject (title, aim, the described case, or a primary result)",
    "reported": "gives its own human data on this drug and this event among other outcomes, e.g. adverse-event rates in a trial, "
                "or a safety review or pooled analysis of this drug that discusses this event",
    "passing": "mentions both only in passing: a list of side effects without data, background text, the event is the disease "
               "being treated or the indication, or the event is attributed to a different drug",
    "unrelated": "does not concern this drug and this event in humans",
}
RELEVANT = {"focus", "reported"}
EXCLUDED = {"passing", "unrelated"}
ONSET = {"lt_1d": "within 24 hours of starting", "d1_7": "1 to 7 days", "w1_4": "1 to 4 weeks", "m1_6": "1 to 6 months",
         "gt_6m": "more than 6 months", "not_stated": "the abstract does not say"}
DECHAL = {"positive": "the event improved or resolved after the drug was stopped or its dose reduced",
          "negative": "the event persisted after the drug was stopped or reduced",
          "not_done": "the drug was continued unchanged",
          "not_stated": "the abstract does not say"}
RECHAL = {"positive": "the event recurred when the drug was given again",
          "negative": "the drug was given again without recurrence",
          "not_done": "the drug was not given again",
          "not_stated": "the abstract does not say"}
WORKUP = {
    "both": "other causes (underlying disease, co-medications) were excluded AND objective confirmation was reported "
            "(laboratory values, biopsy or histology, drug level, or a specific test)",
    "objective_only": "objective confirmation reported; exclusion of other causes not described",
    "exclusion_only": "other causes excluded; no objective confirmation described",
    "not_stated": "neither is described",
}
SCALE = {
    "naranjo_high": "the authors applied the Naranjo scale with result probable or definite",
    "naranjo_low": "the authors applied the Naranjo scale with result possible or doubtful",
    "who_umc_high": "the authors applied WHO-UMC with result certain or probable",
    "who_umc_low": "the authors applied WHO-UMC with result possible or lower",
    "other_scale": "another causality method (RUCAM, Liverpool, Begaud, national algorithm)",
    "not_stated": "no causality scale is mentioned",
}
EFFECT = {
    "increased_sig": "the event was more frequent with the drug and the difference was statistically significant "
                     "(95% CI excludes no effect, or p<0.05; for database studies a significant ROR/PRR/IC)",
    "increased_ns": "more frequent with the drug but not statistically significant",
    "null": "no difference between the drug and the comparator",
    "decreased": "less frequent with the drug",
    "not_stated": "no comparative estimate for this event",
}
PATIENTS = {"lt_100": "fewer than 100 patients (or reports) with the drug", "h100_999": "100 to 999", "k1_9": "1,000 to 9,999",
            "ge_10k": "10,000 or more", "not_stated": "the abstract does not say"}
COMPARATOR = {"placebo": "placebo or no treatment", "active": "another active drug", "unexposed": "unexposed people or non-users",
              "database": "all other drugs or reports in a spontaneous-report database", "none": "no comparison group (single arm)",
              "not_stated": "the abstract does not say"}
DOSE = {"dose_response": "the risk rises with dose or cumulative exposure",
        "no_dose_response": "the authors looked and found no dose relationship",
        "not_stated": "dose relationship not assessed or not stated"}
CONTEXT = {
    "mechanism_and_class": "proposes a mechanism AND notes the same event with other drugs of the same class",
    "class_only": "notes the same event with other drugs of the same class",
    "mechanism_only": "proposes a biological mechanism",
    "neither": "neither",
}
# (질문 문구, 선택지). {i}, {drug}, {pt} 를 채웁니다.
_ASK = {
    "addresses": ("Does Article {i} actually study {drug} and {pt}, or only mention them?", GATE),
    "context": ("Does Article {i} propose a mechanism for {pt} with {drug}, or report it with other drugs of the same class?", CONTEXT),
    "onset": ("In Article {i}, how long after starting {drug} did {pt} begin?", ONSET),
    "dechallenge": ("In Article {i}, what happened to {pt} after {drug} was stopped or its dose reduced?", DECHAL),
    "rechallenge": ("In Article {i}, was {drug} given again after {pt}, and did {pt} recur?", RECHAL),
    "workup": ("In Article {i}, were other causes of {pt} excluded, and was it objectively confirmed?", WORKUP),
    "scale": ("In Article {i}, which causality assessment did the authors apply to {drug} and {pt}, and with what result?", SCALE),
    "effect": ("In Article {i}, how did the frequency of {pt} with {drug} compare with the comparator?", EFFECT),
    "patients": ("In Article {i}, how many patients (or reports) with {drug} were studied?", PATIENTS),
    "comparator": ("In Article {i}, what was {drug} compared with?", COMPARATOR),
    "dose": ("In Article {i}, did the risk of {pt} depend on the dose of {drug}?", DOSE),
}
CASE_FIELDS = ["dechallenge", "rechallenge", "workup", "onset", "scale"]
COMPARATIVE_FIELDS = ["effect", "patients", "comparator", "dose"]
FIELDS = ["addresses", "context", *CASE_FIELDS, *COMPARATIVE_FIELDS]
MAX_PER_ARTICLE = 8
# 설계 묶음마다 공통 문항 뒤에 붙이는 순서입니다. 편당 8문항을 넘으면 뒤에서부터 뺍니다.
# 증례 묶음은 결론 강도(strength)를 묻지 않습니다. 증례의 강도는 설계로 정해지고, 그 자리를 증례 항목에 씁니다.
BLOCKS = {"case": CASE_FIELDS, "comparative": COMPARATIVE_FIELDS,
          "mixed": ["dechallenge", "effect", "patients"],   # 출판 유형도 제목 단서도 없을 때입니다
          "common": []}                                     # 총설은 공통 문항만 묻습니다
_COMPARATIVE_PT = re.compile(r"^(Clinical Trial|Controlled Clinical Trial|Pragmatic Clinical Trial|Equivalence Trial|"
                             r"Observational Study|Comparative Study|Multicenter Study|Clinical Study)", re.I)
_COMPARATIVE_TITLE = re.compile(r"randomi[sz]ed|\bcohort|case[- ]control|meta-analy|systematic review|nationwide|population-based|"
                                r"\bregistry|retrospective (study|analysis)|prospective|\btrial\b|disproportionality|"
                                r"pharmacovigilance|\bFAERS\b|VigiBase|EudraVigilance|\bJADER\b|spontaneous report", re.I)
_CASE_TITLE = re.compile(r"case report|a case of|case series|: a case|report of (a|two|three|\d+) (case|patient)s?|"
                         r"\bcase\b.*review of (the )?literature|in an? (\d+-year-old|child|infant|woman|man|patient|girl|boy)", re.I)
# 자발보고 DB 를 다시 분석한 연구입니다(규칙, 모델 미개입). FAERS 재분석은 FAERS 축과 같은 자료입니다.
# 'Adverse Event Reporting System' 앞에 Vaccine(VAERS)·Korea(KAERS)가 붙으면 FAERS 가 아닙니다.
_SOURCE_DB = [("faers", r"\bFAERS\b|(?<!vaccine )(?<!korea )(?<!korean )Adverse Event Reporting System"), ("vigibase", r"VigiBase|VigiAccess"),
              ("jader", r"\bJADER\b"), ("eudravigilance", r"EudraVigilance"), ("kaers", r"\bKAERS\b|KIDS-KD")]
REVIEW_CONF = 0.55          # 이보다 확신이 낮은 항목은 사람 확인 목록(review)에 올립니다
BORDERLINE = (0.3, 0.6)     # 관문 확률(focus+reported)이 이 사이면 addresses 도 확인 목록에 올립니다
CLIP = 2000                 # 초록 예산입니다. literature_eval.py 는 자기 사본에서 앞 1600자를 따로 씁니다.


# ---------------------------------------------------------------- 파싱과 규칙
def parse_efetch(xml_text: str) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for art in root.iter("PubmedArticle"):
        pmid = (art.findtext(".//PMID") or "").strip()
        title = re.sub(r"\s+", " ", "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else "").strip()
        parts = art.findall(".//Abstract/AbstractText")
        # abstract 는 예전과 같은 문자열입니다(literature_eval 입력이 바뀌지 않게). 절 이름은 sections 에 따로 둡니다.
        abstract = " ".join(re.sub(r"\s+", " ", "".join(a.itertext())) for a in parts)
        sections = [((a.get("Label") or "").strip().upper(), (a.get("NlmCategory") or "").upper(),
                     re.sub(r"\s+", " ", "".join(a.itertext())).strip()) for a in parts]
        year = art.findtext(".//PubDate/Year") or (art.findtext(".//PubDate/MedlineDate") or "")[:4] or None
        ptypes = [p.text for p in art.findall(".//PublicationType") if p.text]
        rule = next((d for name, d in _PUBTYPE if name in ptypes), None)
        src = next((k for k, rx in _SOURCE_DB if re.search(rx, title + " " + abstract, re.I)), None)
        out.append({"pmid": pmid, "title": title, "abstract": abstract, "sections": sections, "year": year,
                    "pubtypes": ptypes, "design_rule": rule, "data_source": src})
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _has(text_n: str, term: str) -> bool:
    t = _norm(term)
    return bool(t) and re.search(rf"\b{re.escape(t)}(?:s|es)?\b", text_n) is not None


def mentions(text: str, drug: str, pt: str) -> bool:
    """약물과 반응이 둘 다 글에 나오는지 규칙으로 봅니다. 반응은 영국·미국 철자와 뒤집힌 순서(labeltext.us_variants)를 함께 봅니다.
    복합제(A\\B)는 성분이 모두 나와야 합니다."""
    n = _norm(text)
    comps = [c for c in re.split(r"[\\/+]", drug or "") if c.strip()]
    return bool(comps) and all(_has(n, c) for c in comps) and any(_has(n, v) for v in labeltext.us_variants(pt))


_RANK = [  # (절 이름 정규식, 순위). 작을수록 먼저 남깁니다. 위에서부터 맞춰 봅니다.
    (re.compile(r"FUNDING|REGISTRATION|DISCLOSURE|CONFLICT|SPONSOR"), 5),
    (re.compile(r"BACKGROUND|INTRODUCTION|OBJECTIVE|PURPOSE|\bAIMS?\b|CONTEXT|RATIONALE|IMPORTANCE|HYPOTHES"), 4),
    (re.compile(r"METHOD|DESIGN|PARTICIPANT|SETTING|SOURCE|INTERVENTION|MEASURE|SELECTION|ELIGIB|SUBJECT|POPULATION|PATIENTS AND"), 2),
    (re.compile(r"RESULT|FINDING|OUTCOME|OBSERVATION|CASE|PRESENTATION|SYNTHESIS"), 0),
    (re.compile(r"CONCLU|INTERPRET|DISCUSS|IMPLICATION|RELEVANCE|SIGNIFICANCE"), 1),
]
_CAT_RANK = {"RESULTS": 0, "CONCLUSIONS": 1, "METHODS": 2, "UNASSIGNED": 3, "OBJECTIVE": 4, "BACKGROUND": 4}


def _rank(label: str, cat: str) -> int:
    return next((r for rx, r in _RANK if label and rx.search(label)), _CAT_RANK.get(cat, 3))


def _trim(text: str, n: int) -> str:
    """문장 단위로 앞 1/3 과 끝을 남겨 n 자 안으로 줄입니다. 결론과 수치는 대개 끝에 있습니다."""
    if len(text) <= n:
        return text
    sents = [s for s in re.split(r"(?<=[.;!?])\s+", text) if s]
    head, tail, used, i, j = [], [], 5, 0, len(sents) - 1
    while i <= j and used + len(sents[i]) + 1 <= n // 3:
        head.append(sents[i]); used += len(sents[i]) + 1; i += 1
    while j >= i and used + len(sents[j]) + 1 <= n:
        tail.insert(0, sents[j]); used += len(sents[j]) + 1; j -= 1
    if not tail:  # 끝 문장 하나가 예산보다 길면 글자 단위로 자릅니다
        h = n // 3
        return text[:h] + " ... " + text[-(n - h - 5):]
    return (" ".join(head) + " ... " if head else "... ") + " ".join(tail)


def clip(a: dict, budget: int = CLIP) -> tuple[str, bool]:
    """초록을 예산 안으로 줄입니다. 구조화 초록은 절 이름을 붙여 두고, 결과·증례·결론 절을 통째로 먼저 남긴 뒤
    남는 자리에 방법·기타 절을 통째로 넣습니다. 배경·목적·연구비 절이 가장 먼저 빠집니다. (본문, 잘렸는지)를 돌려줍니다."""
    secs = [(l, c, t) for l, c, t in (a.get("sections") or []) if t]
    if not (len(secs) > 1 or any(l for l, _, _ in secs)):
        flat = a.get("abstract") or ""
        return (flat, False) if len(flat) <= budget else (_trim(flat, budget), True)
    parts = [(f"{l}: " if l else "") + t for l, _, t in secs]
    whole = " ".join(parts)
    if len(whole) <= budget:
        return whole, False
    rank = [_rank(l, c) for l, c, _ in secs]
    order = sorted(range(len(secs)), key=lambda k: (rank[k], k))
    keep, room = {}, budget
    top = [k for k in order if rank[k] <= 1]
    for k in top:  # 결과·증례·결론 절을 통째로 넣습니다
        if len(parts[k]) + 1 <= room:
            keep[k] = parts[k]; room -= len(parts[k]) + 1
    # 방법 절의 첫 문장(대개 연구 설계를 밝힙니다)을 넣을 자리를 남겨 둡니다. 결과 절을 줄여 넣을 때도 남깁니다
    m = next((k for k in order if rank[k] == 2), None)
    lead = (re.split(r"(?<=[.;!?])\s+", parts[m])[0][:300] + " ...") if m is not None else ""
    reserve = len(lead) + 1 if m is not None and (len(parts[m]) + 1 > room or any(k not in keep for k in top)) else 0
    for k in top:  # 통째로 안 들어가는 결과 절은 남은 자리만큼 앞뒤를 남깁니다
        if k not in keep and room - reserve >= 200:
            keep[k] = _trim(parts[k], room - reserve - 1); room -= len(keep[k]) + 1
    for k in order:  # 나머지 절은 통째로 들어갈 때만 넣습니다. 방법 절이 빠져 있으면 배경 절 등이 그 첫 문장 자리를 쓰지 않습니다
        held = reserve if m is not None and m not in keep and k != m else 0
        if k not in keep and rank[k] < 5 and len(parts[k]) + 1 <= room - held:
            keep[k] = parts[k]; room -= len(parts[k]) + 1
    if m is not None and m not in keep and len(lead) + 1 <= room:
        keep[m] = lead; room -= len(lead) + 1
    if not keep:
        return _trim(whole, budget), True
    return " ".join(keep[k] for k in sorted(keep)), True


def block_for(a: dict) -> str:
    """추가로 물을 설계 묶음입니다. 출판 유형이 있으면 그것으로, 없으면 출판 유형 힌트와 제목 단서로 고릅니다."""
    d = a.get("design_rule")
    if d in ANECDOTAL:
        return "case"
    if d in COMPARATIVE:
        return "comparative"
    if d:
        return "common"
    if any(_COMPARATIVE_PT.match(p) for p in a.get("pubtypes", [])) or _COMPARATIVE_TITLE.search(a.get("title", "")):
        return "comparative"
    if _CASE_TITLE.search(a.get("title", "")):
        return "case"
    return "mixed"


def design_question(i: int) -> dict:
    """설계 질문입니다. literature_eval.py 가 같은 문구와 선택지로 검증했습니다(598편, 0.920). 바꾸지 않습니다."""
    return {"type": "choice", "instructions": f"What is the study design of Article {i}?", "criteria": DESIGNS}


def _choice(field: str, i: int, drug: str, pt: str) -> dict:
    text, crit = _ASK[field]
    return {"type": "choice", "criteria": crit,
            "instructions": text.format(i=i, drug=drug, pt=pt) + " Answer only from the title and abstract."}


def questions(i: int, a: dict, drug: str, pt: str) -> dict:
    """한 편에 묻는 질문입니다. 관문·(설계)·연관·(강도)·기전 뒤에 설계 묶음을 8문항까지 붙입니다."""
    d, block = drug.lower(), block_for(a)
    qs = {f"a{i}_addresses": _choice("addresses", i, d, pt)}
    if not a.get("design_rule"):
        qs[f"a{i}_design"] = design_question(i)
    # supports·strength 문구는 예전과 같습니다(화면·근거 카탈로그가 이 값을 씁니다)
    qs[f"a{i}_supports"] = {"type": "noul", "instructions": f"Does Article {i} report human evidence that {d} is associated with {pt}?"}
    if block != "case":
        qs[f"a{i}_strength"] = {"type": "score", "instructions": f"How strong is the evidence in Article {i} that {d} causes {pt}?",
                                "criteria": STRENGTH}
    qs[f"a{i}_context"] = _choice("context", i, d, pt)
    for f in BLOCKS[block][:max(0, MAX_PER_ARTICLE - len(qs))]:
        qs[f"a{i}_{f}"] = _choice(f, i, d, pt)
    return qs


# ---------------------------------------------------------------- 후보 재정렬(Nemotron 리랭커)
# PubMed 관련도순 상위 RERANK_POOL 편을 가져와 Nemotron 리랭커로 다시 줄 세우고, 위에서 n 편만 Jev 가 읽습니다.
# 실측(pipeline/bench/literature_rerank_eval.py, 30쌍 575편): 읽는 상위 6편 가운데 관문을 통과하는 논문 비율이
# PubMed 순서 0.65 에서 0.85 로 올랐습니다(21쌍 개선, 9쌍 같음, 0쌍 악화). 리랭커가 실패하면 PubMed 순서로 돌아갑니다.
RERANK_POOL = 20
RERANK_TIMEOUT = 2.0     # 초. 리랭커 한 번(20편)은 실측 중앙값 0.43~0.53 초, 최대 0.9 초였습니다
RERANK_QUERY = ("{drug}-induced {pt}: case reports, clinical trials, cohort or pharmacovigilance studies "
                "reporting {pt} as an adverse effect of {drug} in patients")
_RERANK_MEMO: dict[str, list[float]] = {}


def rerank_enabled() -> bool:
    """키가 있고 FV_RERANK=0 으로 끄지 않았으면 재정렬합니다."""
    return bool(config.NVIDIA_API_KEY) and os.environ.get("FV_RERANK", "1").strip().lower() not in ("0", "false", "off", "no")


def rerank_drug(drug: str) -> str:
    """질의에 넣는 약물명입니다. 복합제 구분자(A\\B)는 'a and b' 로 풉니다."""
    return " and ".join(c.strip().lower() for c in re.split(r"[\\/+]", drug or "") if c.strip())


def rerank_passage(a: dict, limit: int = 3000) -> str:
    """리랭커에 주는 글입니다. 제목과 초록 원문이고, 512 토큰을 넘는 뒤쪽은 서버가 자릅니다(truncate=END)."""
    return (f"{a.get('title') or ''}\n{a.get('abstract') or ''}")[:limit]


def rerank_query(drug: str, pt: str) -> str:
    return RERANK_QUERY.format(drug=rerank_drug(drug), pt=pt)


def top_by_score(scores: list[float], n: int) -> list[int]:
    """점수가 높은 순으로 n 편의 색인을 고릅니다. 동점이면 PubMed 순서를 따릅니다."""
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:n]


def _rerank_cache(key: str):
    d = evidence._cache_dir()
    return d / f"rerank_{key}.json" if d else None


async def rerank(drug: str, pt: str, arts: list[dict], n: int, client: httpx.AsyncClient) -> tuple[list[dict], dict]:
    """후보 arts(PubMed 순서)에서 읽을 n 편을 고릅니다. (고른 편, 메타)를 돌려줍니다.
    후보가 n 편 이하이거나, 재정렬이 꺼져 있거나, 리랭커가 실패하거나 제한 시간을 넘기면 PubMed 순서 앞 n 편입니다."""
    meta = {"order": "pubmed", "candidates": len(arts)}
    if len(arts) <= n or not rerank_enabled():
        return arts[:n], meta
    q = rerank_query(drug, pt)
    key = hashlib.sha1(json.dumps([config.MODEL_RERANK, q, [a["pmid"] for a in arts]]).encode()).hexdigest()[:20]
    cfile = _rerank_cache(key)
    scores, ms, t0 = _RERANK_MEMO.get(key), None, time.perf_counter()
    if scores is None and cfile and cfile.exists():
        try:
            scores = json.loads(cfile.read_text())["scores"]
        except (ValueError, KeyError, OSError):
            scores = None
    if scores is not None:
        calllog.record(url=config.RERANK_URL, model=config.MODEL_RERANK, purpose="literature rerank: PubMed top-20 -> read 6",
                       cache_hit=True, extra={"n_inputs": len(arts)})
    if scores is None:
        try:
            r = await asyncio.wait_for(clients.nim_rerank(q, [rerank_passage(a) for a in arts], client, timeout=RERANK_TIMEOUT),
                                       RERANK_TIMEOUT + 0.5)
            scores, ms = r["scores"], r["latency_ms"]
        except Exception as e:  # 실패는 PubMed 순서로 돌아갑니다(fail open)
            meta["rerank_error"] = type(e).__name__[:80]
            meta["rerank_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            return arts[:n], meta
        if len(scores) != len(arts):
            meta["rerank_error"] = "LengthMismatch"
            return arts[:n], meta
        _RERANK_MEMO[key] = scores
        if cfile:
            try:
                cfile.write_text(json.dumps({"scores": scores, "query": q, "model": config.MODEL_RERANK}))
            except OSError:
                pass
    idx = top_by_score(scores, n)
    out = [{**arts[i], "pubmed_rank": i + 1, "rerank_score": round(float(scores[i]), 3)} for i in idx]
    meta.update(order="nemotron_rerank", model=config.MODEL_RERANK, query=q, cached=ms is None,
                rerank_ms=ms, pubmed_ranks=[i + 1 for i in idx])
    return out, meta


# ---------------------------------------------------------------- 읽기
async def read(drug: str, pt: str, client: httpx.AsyncClient, n: int = 6, use_jev: bool = True) -> dict:
    """약물–반응 쌍의 상위 문헌 n 편을 읽고 판정합니다. error 는 PubMed 조회 실패에만 붙고, Jev 실패는 judge_error 에 남깁니다.
    재정렬이 켜져 있으면 PubMed 상위 RERANK_POOL 편을 후보로 가져와 Nemotron 리랭커로 n 편을 고릅니다.
    order 는 'nemotron_rerank' 또는 'pubmed' 이고, pmids 는 실제로 읽은 편입니다(후보 수는 rerank.candidates)."""
    pool = max(n, RERANK_POOL) if rerank_enabled() else n
    search = await evidence.pubmed(drug, pt, client, retmax=pool)
    res = {**search, "articles": [], "summary": {}, "order": "pubmed"}
    if not search.get("pmids"):
        res["summary"] = summarize([])
        return res
    status, body = await evidence.get_json(client, "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                                           {"db": "pubmed", "id": ",".join(search["pmids"]), "retmode": "xml"},
                                           evidence.PUBMED, key=f"pubmed_fetch_{'_'.join(search['pmids'])}")
    arts = parse_efetch(body) if status == 200 and isinstance(body, str) else []
    if status != 200:
        res["error"] = f"efetch HTTP {status}"
    by, want = {a["pmid"]: a for a in arts}, set(search["pmids"])   # PubMed 관련도 순서를 지킵니다
    arts = [by[p] for p in search["pmids"] if p in by] + [a for a in arts if a["pmid"] not in want]
    arts, rmeta = await rerank(drug, pt, arts, n, client)
    res["order"], res["rerank"] = rmeta["order"], rmeta
    res["pmids"] = [a["pmid"] for a in arts] or search["pmids"][:n]
    judged: dict = {}
    if arts and use_jev:
        if not config.TYPESAFE_API_KEY:
            res["judge_error"] = "NotConfigured"
        else:
            try:
                judged = await _judge(drug, pt, arts)
            except Exception as e:  # 판정 실패는 '판정 안 함'으로 남깁니다(지지 안 함으로 세지 않습니다)
                res["judge_error"] = f"{type(e).__name__}"[:80]
    for i, a in enumerate(arts):
        j = judged.get(i) or {}
        design = a["design_rule"] or j.get("design") or "other"
        res["articles"].append({
            "pmid": a["pmid"], "year": a["year"], "title": a["title"][:220], "pubtypes": a["pubtypes"][:4],
            "pubmed_rank": a.get("pubmed_rank", i + 1), "rerank_score": a.get("rerank_score"),
            "design": design, "design_source": "pubtype" if a["design_rule"] else ("jev" if j.get("design") else "none"),
            "judged": bool(j), "block": block_for(a), "clipped": j.get("clipped", False), "data_source": a.get("data_source"),
            "supports": j.get("supports"), "strength": j.get("strength"), "on_topic": j.get("on_topic"),
            **{f: j.get(f) for f in FIELDS},   # 묻지 않은 항목은 None, 초록에 없으면 not_stated 입니다
            "alternatives": _workup(j.get("workup"), "exclusion_only", "excluded"),
            "objective": _workup(j.get("workup"), "objective_only", "confirmed"),
            "review": j.get("review", []),
            # 규칙 판정입니다. 초록은 여기서만 보고 버립니다.
            "title_mentions": mentions(a["title"], drug, pt), "abstract_mentions": mentions(a["abstract"], drug, pt),
            "id": f"pubmed:{a['pmid']}#{design}"})
    res["summary"] = summarize(res["articles"])
    res["ids"] = [a["id"] for a in res["articles"]] or search["ids"][:n]
    res["judge_latency_ms"] = judged.get("_latency")
    res["judge_questions"] = judged.get("_n_questions")
    return res


def _workup(w: str | None, one: str, yes: str) -> str | None:
    return None if w is None else (yes if w in ("both", one) else "not_stated")


def _num(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


async def _judge(drug: str, pt: str, arts: list[dict]) -> dict:
    blocks, qs, clipped = [], {}, {}
    for i, a in enumerate(arts):
        text, clipped[i] = clip(a)
        blocks.append(f"[Article {i}] PMID {a['pmid']} ({a['year']}). Publication types: {', '.join(a['pubtypes'][:4])}.\n"
                      f"Title: {a['title']}\nAbstract: {text or '(no abstract)'}")
        qs.update(questions(i, a, drug, pt))
    state = (f"Question: is {drug.lower()} associated with {pt} in humans?\n"
             "Answer each question only from that article's title and abstract. Choose not_stated when the abstract does not say.\n\n"
             + "\n\n".join(blocks))
    r = await clients.jev(state, qs)
    out = {"_latency": r.get("latency_ms"), "_n_questions": len(qs)}
    for i, rec in parse_answers(r.get("answers") or {}, len(arts)).items():
        out[i] = {**rec, "clipped": clipped[i]}
    return out


def parse_answers(ans: dict, n: int) -> dict[int, dict]:
    """Jev 답을 편마다 풉니다. 관문과 연관 답이 모두 있는 편만 판정한 것으로 둡니다. 한 편의 답이 빠져도 나머지는 살립니다."""
    out = {}
    for i in range(n):
        def get(f):
            x = ans.get(f"a{i}_{f}")
            return x if isinstance(x, dict) else {}
        gate, sup = get("addresses"), _num(get("supports").get("noul"))
        if gate.get("choice") not in GATE or sup is None:
            continue
        gp = gate.get("probabilities") or {}
        st = _num(get("strength").get("score"))
        rec = {"design": get("design").get("choice") if get("design").get("choice") in DESIGNS else None,
               "supports": round(sup, 3), "strength": round(st, 2) if st is not None else None,
               "on_topic": round(sum(_num(gp.get(k)) or 0.0 for k in RELEVANT), 3) if gp else None, "review": []}
        for f in FIELDS:
            x = get(f)
            rec[f] = x.get("choice") if x.get("choice") in _ASK[f][1] else None
            conf = _num(x.get("confidence"))
            if rec[f] is not None and conf is not None and conf < REVIEW_CONF:
                rec["review"].append(f)
        if rec["on_topic"] is not None and BORDERLINE[0] <= rec["on_topic"] < BORDERLINE[1] and "addresses" not in rec["review"]:
            rec["review"].append("addresses")
        out[i] = rec
    return out


# ---------------------------------------------------------------- 요약
def is_judged(a: dict) -> bool:
    return bool(a.get("judged", True)) and _num(a.get("supports")) is not None


def is_relevant(a: dict) -> bool:
    """관문을 통과했는가(focus·reported). 관문이 없던 옛 기록(addresses 키 없음)은 통과로 봅니다."""
    return a.get("addresses") in RELEVANT or "addresses" not in a


def is_supportive(a: dict) -> bool:
    return is_judged(a) and is_relevant(a) and (_num(a.get("supports")) or 0.0) >= 0.5


def supportive_ids(lit: dict | None, k: int = 4) -> list[str]:
    """근거 목록(basis)에 넣을 문헌 ID 입니다. 판정했고, 관문을 통과했고, 연관을 보고한 문헌만 넣습니다."""
    return [a["id"] for a in (lit or {}).get("articles", []) if is_supportive(a)][:k]


def case_reports_rule(articles: list[dict]) -> list[str]:
    """규칙만으로 고른 증례보고 PMID 입니다(모델 미개입). PubMed 출판 유형이 증례이고 약물·반응이 제목이나 초록에 함께 나온 문헌입니다.
    한국형 인과성 '약물에 대해 알려진 정보' +2 에 씁니다."""
    return [a["pmid"] for a in articles if a.get("design_source") == "pubtype" and a.get("design") in ANECDOTAL
            and (a.get("title_mentions") or a.get("abstract_mentions"))]


def summarize(articles: list[dict]) -> dict:
    """지지 편수는 판정했고 관문을 통과한(relevant) 문헌만 셉니다. passing·unrelated 는 excluded_passing 으로 따로 셉니다."""
    judged = [a for a in articles if is_judged(a)]
    rel = [a for a in judged if is_relevant(a)]
    sup = [a for a in rel if (_num(a.get("supports")) or 0.0) >= 0.5]
    analytic = [a for a in rel if a["design"] in ANALYTIC]
    a_sup = sum(1 for a in analytic if (_num(a.get("supports")) or 0.0) >= 0.5)
    status = ("not_judged" if articles and not judged else "no_analytic" if not analytic
              else "supports" if a_sup == len(analytic) else "not_supported" if a_sup == 0 else "mixed")
    cases = [a for a in sup if a["design"] in ANECDOTAL]

    def dechal(a):  # 옛 기록은 dechallenge 가 확률(float)입니다
        v = a.get("dechallenge")
        return v == "positive" or (_num(v) or 0.0) >= 0.5
    return {
        "read": len(articles),
        "judged": bool(judged),
        "judged_n": len(judged),
        "relevant": len(rel),
        "excluded_passing": sum(1 for a in judged if a.get("addresses") in EXCLUDED),   # passing + unrelated
        "excluded_unrelated": sum(1 for a in judged if a.get("addresses") == "unrelated"),
        "supportive": len(sup),
        "analytic_read": len(analytic),
        "analytic_status": status,
        "analytic_supportive": a_sup,
        "analytic_significant": sum(1 for a in analytic if a.get("effect") == "increased_sig"),
        "analytic_null": sum(1 for a in analytic if a.get("effect") in ("null", "decreased")),
        "dose_response": sum(1 for a in rel if a.get("dose") == "dose_response"),
        "anecdotal_supportive": len(cases),
        "dechallenge_reports": sum(1 for a in rel if dechal(a)),
        "rechallenge_reports": sum(1 for a in rel if a.get("rechallenge") == "positive"),
        "documented_cases": sum(1 for a in cases if a.get("workup") == "both"),
        "class_effect": sum(1 for a in rel if a.get("context") in ("mechanism_and_class", "class_only")),
        "mechanism": sum(1 for a in rel if a.get("context") in ("mechanism_and_class", "mechanism_only")),
        "faers_reanalysis": sum(1 for a in sup if a.get("data_source") == "faers"),
        "designs": {d: sum(1 for a in articles if a["design"] == d) for d in DESIGNS if any(a["design"] == d for a in articles)},
        "case_reports_rule": case_reports_rule(articles),
    }
