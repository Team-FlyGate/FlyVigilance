"""국내 약물감시 모듈입니다.

1. intake: 의약전문가용·일반인 보고서식이나 자유 서술(병원·약사 사례 기사)을 Nemotron 으로 구조화합니다.
   결과는 두 가지입니다. 식약처 공고 제2023-057호 의약전문가용 서식의 가~바 섹션(kr_form)과,
   기존 트리아지가 그대로 받을 수 있는 영문 정규화 케이스(case)입니다.
2. causality_kr: 한국형 인과성 평가 알고리즘 ver 2.0 의 8개 항목을 Jev 선택형 질문으로 판단하고,
   점수는 아래 배점표로 규칙 합산합니다. 모델은 점수를 만들지 않습니다.
   WHO-UMC 등급과 한국형 등급은 이름과 체계가 달라 섞지 않습니다.
"""
import json

import httpx

from . import clients, config, evidence

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
    {"id": "known", "name": "약물에 대해 알려진 정보", "q": "Is this adverse reaction known for the suspect drug?",
     "options": [("label", "허가사항(label, insert 등)에 반영되어 있음", 3), ("case_reports", "허가사항에 반영되어 있지 않으나 증례보고가 있었음", 2),
                 ("unknown", "알려진 바 없음", 0)]},
    {"id": "rechallenge", "name": "재투약", "q": "What happened on re-administration of the suspect drug?",
     "options": [("recurred", "재투약으로 동일한 유해사례가 발생함", 3), ("not_recurred", "재투약으로 동일한 유해사례가 발생하지 않음", -2),
                 ("not_done", "재투약하지 않음", 0), ("no_info", "정보없음", 0)]},
    {"id": "specific_test", "name": "특이적인 검사", "q": "Was a specific test done (provocation test, drug concentration, skin test)?",
     "options": [("positive", "양성", 3), ("negative", "음성", -1), ("unknown_result", "결과를 알 수 없음", 0), ("no_info", "정보없음", 0)]},
]
KR_MAX, KR_MIN = 19, -13


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
                      "dechal": m.get("dechal"), "rechal": rechal, "indication": m.get("indication")})
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
        config.MODEL_DELIBERATE, max_tokens=2000, temperature=0.0)
    data = clients.parse_json_block(out["content"])
    case = _norm_case(data.get("kr_form", {}), data.get("case", {}))
    case["primaryid"] = "KR-DEMO"
    case["caseid"] = "KR-DEMO"
    case["quarter"] = "KR"
    data["case"] = case
    return {**data, "model": out["model"], "latency_ms": out["latency_ms"], "usage": out["usage"], "form": form}


async def causality_kr(case: dict, case_state: str, narrative: str | None = None) -> dict:
    """한국형 알고리즘 8개 항목을 한 번의 Jev 호출로 판단하고 점수를 규칙으로 합산합니다.
    '약물에 대해 알려진 정보'는 openFDA 라벨에서 반응명이 확인되면 규칙으로 +3 을 줍니다(국내 허가사항은 별도 확인 필요)."""
    ps = next((d for d in case.get("drugs", []) if d.get("role") == "PS"), None)
    label = None
    if ps and case.get("reactions"):
        async with httpx.AsyncClient(headers={"User-Agent": "FlyVigilance/1.0"}) as c:
            label = await evidence.label_lookup(ps["drug"], case["reactions"][:3], c, ps.get("route"))
    state = case_state + (f"\n\nNarrative: {narrative}" if narrative else "")
    qs = {}
    for it in KR_ALGO:
        qs[it["id"]] = {"type": "choice", "instructions": it["q"] + " Answer only from the report; choose no_info when not stated.",
                        "criteria": {k: label for k, label, _ in it["options"]}}
    qs["who_umc"] = {"type": "choice", "instructions": "WHO-UMC causality category for the primary suspect drug, based only on this report.",
                     "criteria": {"certain": "확실함 (certain)", "probable": "상당히 확실함 (probable/likely)", "possible": "가능함 (possible)",
                                  "unlikely": "가능성 적음 (unlikely)", "conditional": "평가 곤란 (conditional/unclassified)",
                                  "unassessable": "평가 불가 (unassessable/unclassifiable)"}}
    res = await clients.jev(state, qs)
    items, total = [], 0
    for it in KR_ALGO:
        a = res["answers"][it["id"]]
        opt = {k: (label, sc) for k, label, sc in it["options"]}
        choice, source, conf = a["choice"], "jev", a["confidence"]
        if it["id"] == "known" and label and label.get("found") and any(label.get("listed", {}).values()):
            choice, source, conf = "label", "openFDA label", 1.0
        lab, sc = opt.get(choice, ("정보없음", 0))
        total += sc
        items.append({"id": it["id"], "name": it["name"], "choice": choice, "label": lab, "score": sc,
                      "confidence": conf, "probabilities": a["probabilities"], "source": source,
                      "evidence": ([h["id"] for h in label.get("hits", [])] if source == "openFDA label" else []),
                      "options": [{"key": k, "label": l, "score": s} for k, l, s in it["options"]],
                      "needs_review": source == "jev" and conf < 0.55})
    who = res["answers"]["who_umc"]
    return {"items": items, "total": total, "max": KR_MAX, "min": KR_MIN, **kr_grade(total),
            "who_umc": {"choice": who["choice"], "confidence": who["confidence"], "probabilities": who["probabilities"]},
            "label": ({"found": label.get("found"), "setid": label.get("setid"), "brand": label.get("brand"), "listed": label.get("listed"),
                       "hits": label.get("hits", [])} if label else None),
            "note": "한국형 알고리즘 등급(확실함·가능성 높음·가능성 있음·가능성 낮음)과 WHO-UMC 등급은 체계가 달라 서로 바꿔 쓰지 않습니다.",
            "latency_ms": res["latency_ms"], "usage": res["usage"], "model": res["model"]}


def dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False)
