"""국내 약물감시 모듈입니다.

1. intake: 의약전문가용·일반인 보고서식이나 자유 서술(병원·약사 사례 기사)을 Nemotron 으로 구조화합니다.
   결과는 두 가지입니다. 식약처 공고 제2023-057호 의약전문가용 서식의 가~바 섹션(kr_form)과,
   기존 트리아지가 그대로 받을 수 있는 영문 정규화 케이스(case)입니다.
2. causality_kr: 한국형 인과성 평가 알고리즘 ver 2.0 의 8개 항목 중 7개를 Jev 선택형 질문으로 판단하고,
   '약물에 대해 알려진 정보' 항목은 모델에 묻지 않고 허가 라벨·문헌 조회 규칙으로만 정합니다(known_item).
   점수는 아래 배점표로 규칙 합산합니다. 모델은 점수를 만들지 않습니다.
   WHO-UMC 등급과 한국형 등급은 이름과 체계가 달라 섞지 않습니다.
"""
import asyncio
import json
import re
import time
from urllib.parse import quote

import httpx

from . import clients, config, evidence, labeltext, literature

# 한국형 인과성 평가 알고리즘 ver 2.0 (팀 자료 「약물부작용 인과성평가 기준 및 도구」). 최고 19점, 최저 -13점.
KR_ALGO = [
    {"id": "temporal", "name": "시간적 선후관계", "q": "Is there information on the temporal relationship between drug administration and onset of the adverse event?",
     "options": [("consistent", "선후관계 합당", 3), ("contradictory", "선후관계 모순", -3), ("no_info", "정보없음", 0)]},
    {"id": "dechallenge", "name": "감량 또는 중단", "q": "What happened after the suspect drug was reduced or stopped?",
     "options": [("improved", "감량 또는 중단 후 임상적 호전이 관찰됨", 3), ("unrelated", "감량 또는 중단과 무관한 임상경과를 보임", -2),
                 ("not_done", "감량 또는 중단을 시행하지 않음", 0), ("no_info", "정보없음", 0)]},
    {"id": "history", "name": "이상사례의 과거력", "q": "Has the patient previously experienced the same or a similar adverse event with the same or a similar drug?",
     "options": [("yes", "예", 1), ("no", "아니오", -1), ("no_info", "정보없음", 0)]},
    {"id": "concomitant", "name": "병용약물", "q": "How do concomitant drugs relate to the adverse event?",
     "options": [("cannot_explain", "병용약물 단독으로 유해사례를 설명할 수 없는 경우", 2), ("can_explain", "병용약물 단독으로 유해사례를 설명할 수 있는 경우", -3),
                 ("interaction", "의심약물과 상호작용으로 설명되는 경우", 2), ("none", "병용약물에 대한 설명이 없는 경우", 0), ("no_info", "정보없음", 0)]},
    {"id": "nondrug", "name": "비약물요인", "q": "Do non-drug factors (underlying disease, other causes) explain the adverse event?",
     "options": [("not_explained", "비약물요인으로 유해사례가 설명되지 않음", 1), ("explained", "비약물요인으로 유해사례가 설명됨", -1), ("no_info", "정보없음", 0)]},
    {"id": "known", "name": "약물에 대해 알려진 정보", "q": "Is this adverse reaction known for the suspect drug?", "rule": True,
     "options": [("label", "허가사항(label, insert 등)에 반영되어 있음", 3), ("case_reports", "허가사항에 반영되어 있지 않으나 증례보고가 있었음", 2),
                 ("unknown", "알려진 바 없음", 0)]},
    {"id": "rechallenge", "name": "재투약", "q": "What happened on re-administration of the suspect drug?",
     "options": [("recurred", "재투약으로 동일한 유해사례가 발생함", 3), ("not_recurred", "재투약으로 동일한 유해사례가 발생하지 않음", -2),
                 ("not_done", "재투약하지 않음", 0), ("no_info", "정보없음", 0)]},
    {"id": "specific_test", "name": "특이적인 검사", "q": "Was a specific test done (provocation test, drug concentration, skin test)?",
     "options": [("positive", "양성", 3), ("negative", "음성", -1), ("unknown_result", "결과를 알 수 없음", 0), ("no_info", "정보없음", 0)]},
]
KR_MAX, KR_MIN = 19, -13

# '약물에 대해 알려진 정보'는 조회 결과로만 정합니다(약사 검토: +2 는 모델 판단이 아니라 실제 문헌 검색 결과로 정합니다)
SRC_LABEL = "미국 FDA 허가사항(openFDA drug/label)"
SRC_NONE = "미국 FDA 허가사항·PubMed 조회"
SRC_FAIL = "조회 실패"
MFDS_REASON = "식약처 허가사항은 자동 조회하지 않았습니다(의약품안전나라 robots.txt 가 자동 수집을 막습니다)"
NEDRUG_SEARCH = "https://nedrug.mfds.go.kr/searchDrug?itemName="


def kr_grade(score: int) -> dict:
    if score >= 12:
        return {"grade": "확실함", "band": "12점 이상", "approx": ">90%"}
    if score >= 6:
        return {"grade": "가능성 높음", "band": "6~11점", "approx": ">70%"}
    if score >= 2:
        return {"grade": "가능성 있음", "band": "2~5점", "approx": "50%"}
    return {"grade": "가능성 낮음", "band": "1점 이하", "approx": "<30%"}


FORMS = {
    "professional": "의약전문가용 보고서식 (식약처 공고 제2023-057호)",
    "consumer": "일반인 보고 (의약품안전나라 온라인)",
    "narrative": "자유 서술 (병원·약사 사례 기사, 진료 기록 요약)",
}

INTAKE_SYSTEM = """You structure Korean adverse drug event reports for pharmacovigilance.
Input is Korean text: a professional report form, a consumer report, or a free narrative (hospital or pharmacist case write-up).
Extract ONLY what is stated. Never invent values; use null and list missing items.
Return ONLY JSON with this shape:
{
 "kr_form": {
  "가_환자정보": {"이니셜": str|null, "나이": str|null, "성별": "남"|"여"|null, "체중": str|null, "원질환_병력": str|null, "알레르기_과거력": str|null},
  "나_이상사례정보": {"이상사례명": [str], "발현일": str|null, "종료일": str|null, "경과_결과": str|null,
                   "중대성": {"사망": bool, "생명위협": bool, "입원_연장": bool, "장애": bool, "선천기형": bool, "기타_의학적중요": bool}},
  "다_의약품정보": {"의심약물": [{"성분명": str, "성분명_영문": "INN UPPERCASE", "제품명": str|null, "용량_용법": str|null, "투여경로": str|null, "투여기간": str|null, "투여목적": str|null, "조치": str|null, "재투여": str|null}],
                  "병용약물": [{"성분명": str, "성분명_영문": "INN UPPERCASE", "용량_용법": str|null, "투여목적": str|null}]},
  "라_보고자정보": {"보고자_유형": "의사"|"약사"|"간호사"|"기타 의료인"|"환자·소비자"|null, "소속_기관": str|null},
  "마_보고서정보": {"보고유형": "자발보고"|"연구"|"문헌"|null, "최초_추가": "최초"|"추가"|null},
  "바_종합의견": str|null
 },
 "case": {
  "age": number|null, "sex": "M"|"F"|null, "weight": number|null,
  "occp_cod": "MD"|"PH"|"OT"|"CN"|null, "country": "KR",
  "drugs": [{"drug": "INN IN ENGLISH UPPERCASE", "role": "PS"|"SS"|"C", "route": str|null,
             "dechal": "Y"|"N"|null, "rechal": "Y"|"N"|null, "indication": "english lowercase"|null}],
  "reactions": ["MedDRA preferred term in English lowercase"],
  "outcomes": ["DE"|"LT"|"HO"|"DS"|"CA"|"RI"|"OT"]
 },
 "narrative_en": "<= 90 words English clinical narrative of the case",
 "missing": ["한국어로 빠진 필수 정보"]
}
Rules for "case":
- 성분명_영문 must be the exact INN spelling (e.g. 테고프라잔 -> TEGOPRAZAN, 에소메프라졸 -> ESOMEPRAZOLE, 철분제 -> IRON, 졸피뎀 -> ZOLPIDEM).
- Drugs started only after the event (treatment of the reaction, or a replacement drug switched to) are NOT concomitant drugs; mention them in 조치.
- The first suspect drug is PS, other suspects SS, and EVERY concomitant drug must be listed with role "C"
  (use the English generic name, e.g. 철분제 -> "IRON", 졸피뎀 -> "ZOLPIDEM").
- route in English uppercase (ORAL, INTRAVENOUS, SUBCUTANEOUS, TOPICAL ...) or null.
- dechal: "Y" improved after stopping/reducing, "N" did not improve, null if not stopped or unknown.
- rechal: "Y" recurred on re-administration, "N" re-administered without recurrence, null if NOT re-administered or unknown.
- outcomes only for met seriousness criteria (hospitalization=HO etc.); empty list if none."""


OCCP = {"의사": "MD", "약사": "PH", "간호사": "OT", "기타 의료인": "OT", "환자·소비자": "CN"}
SERIOUS = {"사망": "DE", "생명위협": "LT", "입원_연장": "HO", "장애": "DS", "선천기형": "CA", "기타_의학적중요": "OT"}
NOT_DONE = ("안 함", "안함", "하지 않", "않음", "없음", "미시행", "not ")


def _hangul(*names: str | None) -> str | None:
    """한글이 든 첫 이름입니다. 모델이 성분명 칸에 영문 INN 을 넣는 경우가 있어 제품명까지 봅니다."""
    return next((n.strip() for n in names if isinstance(n, str) and re.search(r"[가-힣]", n)), None)


def _norm_case(kr_form: dict, model_case: dict) -> dict:
    """모델이 채운 서식(kr_form)에서 트리아지용 케이스를 규칙으로 만듭니다. 역할·코드는 모델에 맡기지 않습니다."""
    pat = kr_form.get("가_환자정보", {}) or {}
    ev = kr_form.get("나_이상사례정보", {}) or {}
    med = kr_form.get("다_의약품정보", {}) or {}
    rep = kr_form.get("라_보고자정보", {}) or {}
    by_name = {(d.get("drug") or "").upper(): d for d in model_case.get("drugs", [])}
    drugs = []
    for i, d in enumerate(med.get("의심약물") or []):
        name = (d.get("성분명_영문") or d.get("성분명") or "").upper().strip()
        m = by_name.get(name, {})
        re_txt = (d.get("재투여") or "")
        rechal = None if (not re_txt or any(k in re_txt for k in NOT_DONE)) else m.get("rechal")
        drugs.append({"drug": name, "role": "PS" if i == 0 else "SS", "route": m.get("route"),
                      "dechal": m.get("dechal"), "rechal": rechal, "indication": m.get("indication"),
                      "name_ko": _hangul(d.get("성분명"), d.get("제품명"))})  # 의약품안전나라 검색 링크에 씁니다
    for d in med.get("병용약물") or []:
        name = (d.get("성분명_영문") or d.get("성분명") or "").upper().strip()
        if name and all(x["drug"] != name for x in drugs):
            drugs.append({"drug": name, "role": "C", "route": None, "dechal": None, "rechal": None, "indication": None})
    sev = ev.get("중대성") or {}
    return {
        "age": model_case.get("age"), "sex": {"남": "M", "여": "F"}.get(pat.get("성별") or "", model_case.get("sex")),
        "weight": model_case.get("weight"), "occp_cod": OCCP.get(rep.get("보고자_유형") or "", model_case.get("occp_cod")),
        "country": "KR", "drugs": drugs or model_case.get("drugs", []), "reactions": model_case.get("reactions", []),
        "outcomes": [code for k, code in SERIOUS.items() if sev.get(k)],
    }


async def intake(text: str, form: str) -> dict:
    out = await clients.nim_chat(
        [{"role": "system", "content": INTAKE_SYSTEM},
         {"role": "user", "content": f"FORM TYPE: {FORMS.get(form, form)}\n\nREPORT:\n{text[:12000]}"}],
        config.MODEL_DELIBERATE, max_tokens=2000, temperature=0.0, deadline=time.monotonic() + 100, json_mode=True,
        purpose="KR report intake: structure a Korean AE form (JSON)")
    data = clients.parse_json_block(out["content"])
    case = _norm_case(data.get("kr_form", {}), data.get("case", {}))
    case["primaryid"] = "KR-DEMO"
    case["caseid"] = "KR-DEMO"
    case["quarter"] = "KR"
    data["case"] = case
    return {**data, "model": out["model"], "latency_ms": out["latency_ms"], "usage": out["usage"], "form": form}


def clinical_pts(reactions: list[str]) -> list[str]:
    """비임상 PT(drug ineffective 등)를 뺀 반응입니다. 모두 비임상이면 원래 목록을 씁니다(evidence.bundle 과 같은 규칙)."""
    return [r for r in reactions if not labeltext.is_nonclinical(r)] or list(reactions)


def label_listed(label: dict | None, pt: str) -> bool:
    """허가 라벨에 그 반응이 기재되어 있는지 봅니다(rank >= 1). 금기 절에만 있는 언급(예: 과민반응 환자)은 기재로 보지 않습니다."""
    if not (label and label.get("found")):
        return False
    bp = (label.get("by_pt") or {}).get(pt) or {}
    secs = [x for x in bp.get("sections") or [] if x != "contraindications"]
    return bool(secs) and float(bp.get("rank") or 0) >= 1


def case_report_pmids(lit: dict | None) -> list[str]:
    """약물과 반응을 함께 언급한 PubMed 증례보고·증례군의 PMID 입니다. 문헌 모듈의 규칙 판정(summary.case_reports_rule)을 쓰고,
    그 필드가 없으면 PubMed 출판 유형(Case Reports)으로 셉니다. 모델의 초록 판정은 쓰지 않습니다."""
    if not lit:
        return []
    summ = lit.get("summary") or {}
    if "case_reports_rule" in summ:
        return [str(x.get("pmid") if isinstance(x, dict) else x) for x in summ.get("case_reports_rule") or []]
    return [a["pmid"] for a in lit.get("articles", []) if "Case Reports" in (a.get("pubtypes") or [])]


def known_item(label: dict | None, lit: dict | None, pt: str | None, label_error: str | None = None,
               lit_error: str | None = None, indication: str | None = None) -> dict:
    """'약물에 대해 알려진 정보' 항목을 규칙으로만 정합니다. 라벨과 문헌은 같은 평가 반응(pt)으로 봅니다.
    +3 미국 FDA 허가 라벨에 기재(금기 절만은 제외) / +2 라벨에는 없으나 PubMed 증례보고 있음 / 0 알려진 바 없음(조회 범위를 남깁니다).
    국내 평가 기준인 식약처 허가사항은 확인하지 않았으므로 결과와 상관없이 평가자 검토 대상입니다."""
    base = {"needs_review": True, "mfds_checked": False, "reaction": pt}
    if not pt:
        return {**base, "choice": "unknown", "source": SRC_FAIL, "evidence": [], "lookup_failed": True,
                "scope": "의심약물이나 평가할 반응명이 없어 허가사항·문헌을 조회하지 못했습니다"}
    found = bool(label and label.get("found"))
    bp = ((label or {}).get("by_pt") or {}).get(pt) or {}
    tag = f"{label.get('brand') or label.get('drug') or ''}, setid {label.get('setid')}" if found else ""
    if label_listed(label, pt):
        secs = [x for x in bp.get("sections") or [] if x != "contraindications"]
        ev = [h["id"] for h in label.get("hits", []) if h.get("pt") == pt and h.get("section") != "contraindications"]
        return {**base, "choice": "label", "source": SRC_LABEL, "evidence": ev or [f"label:{label.get('setid')}"],
                "lookup_failed": False, "scope": f"미국 FDA 허가사항({tag})의 {', '.join(secs)} 절에 '{pt}' 기재"}
    # 라벨 조회 범위는 +2 와 0 에 같이 씁니다(라벨을 못 찾았거나 조회에 실패했는데 '기재 없음'으로 적지 않습니다)
    if label_error:
        lab_scope = f"미국 FDA 허가사항 조회 실패({label_error})"
    elif found:
        only_ci = bool(bp.get("contraindication")) or "contraindications" in (bp.get("sections") or [])
        lab_scope = f"미국 FDA 허가사항({tag})에 '{pt}' 기재 없음" + (" (금기 절에만 언급)" if only_ci else "")
    else:
        lab_scope = "미국 FDA 허가사항(openFDA drug/label)에서 이 성분의 라벨을 찾지 못했습니다"
    pmids = case_report_pmids(lit)
    # 평가 반응이 이 약의 적응증이면 증례보고는 그 질환 자체를 다룬 글일 수 있습니다(예: 시타라빈과 급성골수성백혈병).
    # 규칙만으로는 가려낼 수 없으므로 +2 를 주지 않고 평가자에게 넘깁니다
    ind = (indication or "").lower().strip()
    if pmids and (bp.get("indication_term") or (ind and (pt.lower() in ind or ind in pt.lower()))):
        return {**base, "choice": "unknown", "source": SRC_NONE, "evidence": [f"pubmed:{x}" for x in pmids],
                "lookup_failed": bool(label_error),
                "scope": f"{lab_scope} · PubMed 증례보고 {len(pmids)}건이 있으나 평가 반응이 이 약의 적응증과 겹쳐 "
                         "그 질환 자체를 다룬 글일 수 있습니다. 평가자가 확인해 주십시오"}
    if pmids:
        # 라벨 조회가 실패했다면 +3 여부를 모르므로 조회 실패로도 표시합니다
        return {**base, "choice": "case_reports", "source": f"PubMed 증례보고(PMID {', '.join(pmids[:4])})",
                "evidence": [f"pubmed:{x}" for x in pmids], "lookup_failed": bool(label_error),
                "scope": f"{lab_scope} · PubMed {(lit or {}).get('query')} 에서 증례보고 {len(pmids)}건"}
    lit_scope = (f"PubMed 조회 실패({lit_error})" if lit_error else "PubMed 는 조회하지 않았습니다" if lit is None else
                 f"PubMed {lit.get('query')} 검색 {lit.get('count')}건, 그중 증례보고 0건")
    failed = bool(label_error or lit_error)
    return {**base, "choice": "unknown", "source": SRC_FAIL if failed else SRC_NONE, "evidence": [], "lookup_failed": failed,
            "scope": f"{lab_scope} · {lit_scope}"}


def jev_questions() -> dict:
    """Jev 에 묻는 선택형 질문입니다. 규칙 항목('약물에 대해 알려진 정보')은 묻지 않습니다."""
    qs = {}
    for it in KR_ALGO:
        if it.get("rule"):
            continue
        qs[it["id"]] = {"type": "choice", "instructions": it["q"] + " Answer only from the report; choose no_info when not stated.",
                        "criteria": {k: lab for k, lab, _ in it["options"]}}
    qs["who_umc"] = {"type": "choice", "instructions": "WHO-UMC causality category for the primary suspect drug, based only on this report.",
                     "criteria": {"certain": "확실함 (certain)", "probable": "상당히 확실함 (probable/likely)", "possible": "가능함 (possible)",
                                  "unlikely": "가능성 적음 (unlikely)", "conditional": "평가 곤란 (conditional/unclassified)",
                                  "unassessable": "평가 불가 (unassessable/unclassifiable)"}}
    return qs


async def _known_lookup(ps: dict | None, pts: list[str]) -> tuple[dict | None, dict | None, str | None, str | None]:
    """평가 반응(pts[0])으로 미국 FDA 허가 라벨을 보고, 기재가 없으면 같은 반응으로 PubMed 증례보고를 찾습니다."""
    label = lit = label_err = lit_err = None
    if not (ps and pts):
        return label, lit, label_err, lit_err
    async with httpx.AsyncClient() as c:
        try:
            label = await evidence.label_lookup(ps["drug"], pts[:3], c, ps.get("route"))
            label_err = label.get("error")
        except Exception as e:  # 조회 실패는 0점 + 검토 필요로 남깁니다
            label_err = type(e).__name__
        if not label_listed(label, pts[0]):
            try:
                lit = await literature.read(ps["drug"], pts[0], c, use_jev=False)
                if lit.get("error") or lit.get("count") is None:
                    lit_err = lit.get("error") or "응답 없음"
            except Exception as e:
                lit_err = type(e).__name__
    return label, lit, label_err, lit_err


async def causality_kr(case: dict, case_state: str, narrative: str | None = None) -> dict:
    """한국형 알고리즘 7개 항목과 WHO-UMC 를 한 번의 Jev 호출로 판단하고 점수를 규칙으로 합산합니다.
    '약물에 대해 알려진 정보'는 Jev 에 묻지 않고 known_item 규칙(미국 FDA 허가 라벨 → PubMed 증례보고)으로만 정합니다.
    국내 평가 기준인 식약처 허가사항은 자동 조회하지 않으므로 그 항목은 항상 평가자 검토 대상이고 mfds_label 에 검색 링크를 둡니다."""
    ps = next((d for d in case.get("drugs", []) if d.get("role") == "PS"), None)
    pts = clinical_pts(case.get("reactions") or [])
    state = case_state + (f"\n\nNarrative: {narrative}" if narrative else "")
    res, (label, lit, label_err, lit_err) = await asyncio.gather(clients.jev(state, jev_questions()), _known_lookup(ps, pts))
    known = known_item(label, lit, pts[0] if (ps and pts) else None, label_err, lit_err, (ps or {}).get("indication"))
    items, total = [], 0
    for it in KR_ALGO:
        opt = {k: (lab, sc) for k, lab, sc in it["options"]}
        if it.get("rule"):
            choice, source, ev_ids = known["choice"], known["source"], known["evidence"]
            conf, probs, review = (0.0 if known["lookup_failed"] else 1.0), {}, True
        else:
            a = res["answers"][it["id"]]
            choice, source, ev_ids, conf, probs = a["choice"], "jev", [], a["confidence"], a["probabilities"]
            review = conf < 0.55
        lab, sc = opt.get(choice, ("정보없음", 0))
        total += sc
        row = {"id": it["id"], "name": it["name"], "choice": choice, "label": lab, "score": sc, "confidence": conf,
               "probabilities": probs, "source": source, "method": "rule" if it.get("rule") else "jev", "evidence": ev_ids,
               "options": [{"key": k, "label": l, "score": s} for k, l, s in it["options"]], "needs_review": review}
        if it.get("rule"):
            row.update(scope=known["scope"], reaction=known["reaction"], mfds_checked=False, lookup_failed=known["lookup_failed"])
        items.append(row)
    who = res["answers"]["who_umc"]
    ko = (ps or {}).get("name_ko") or (ps or {}).get("drug") or ""
    return {"items": items, "total": total, "max": KR_MAX, "min": KR_MIN, **kr_grade(total),
            "who_umc": {"choice": who["choice"], "confidence": who["confidence"], "probabilities": who["probabilities"]},
            "assessed_reaction": known["reaction"],
            "mfds_label": {"checked": False, "reason": MFDS_REASON, "search_url": NEDRUG_SEARCH + quote(ko)},
            "literature": ({"query": lit.get("query"), "count": lit.get("count"), "summary": lit.get("summary"),
                            "articles": lit.get("articles", []), "case_reports_rule": case_report_pmids(lit)} if lit else None),
            "label": ({"found": label.get("found"), "setid": label.get("setid"), "brand": label.get("brand"), "listed": label.get("listed"),
                       "by_pt": label.get("by_pt"), "hits": label.get("hits", [])} if label else None),
            "note": "한국형 알고리즘 등급(확실함·가능성 높음·가능성 있음·가능성 낮음)과 WHO-UMC 등급은 체계가 달라 서로 바꿔 쓰지 않습니다.",
            "latency_ms": res["latency_ms"], "usage": res["usage"], "model": res["model"]}


def dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False)
