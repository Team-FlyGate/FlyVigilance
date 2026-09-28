"""Reflex 층: 비자기회귀 판단 모델(System-1)로 ICSR 한 건에 타입 있는 판단 7개를 한 번에 받고 라우팅한다.

판단은 확률로 받는다. 확률은 집단 보정값이지 이 한 건의 보장이 아니므로,
라우팅은 확률과 신뢰도 둘 다를 보고 애매하면 위(System-2, 사람)로 올린다.
"""
import functools
import json
import time

import httpx

from . import clients, config, evidence, labeltext

OUTCOME = {"DE": "death", "LT": "life-threatening", "HO": "hospitalization", "DS": "disability",
           "CA": "congenital anomaly", "RI": "required intervention", "OT": "other serious"}
OCCP = {"MD": "physician", "PH": "pharmacist", "OT": "other health professional", "LW": "lawyer", "CN": "consumer",
        "HP": "health professional"}
ROLE = {"PS": "primary suspect", "SS": "secondary suspect", "C": "concomitant", "I": "interacting"}

PRIORITY_LEVELS = ["routine (periodic report)", "standard review (30 days)", "priority review (7 days)",
                   "expedited (15-day report, immediate)"]
ROUTES = {
    "close": "no safety concern beyond known profile; archive",
    "monitor": "keep in routine aggregate surveillance",
    "signal_review": "potential new signal; needs signal assessment",
    "expedite": "serious and unexpected; prepare expedited report and human review now",
}


def case_state(case: dict, include_outcome: bool = True, grounding: dict | None = None) -> str:
    """ICSR 를 판단 모델 상태 문자열로. include_outcome=False 는 중대성 맹검 벤치마크용.
    grounding 이 있으면 라벨 조회 결과를 상태에 넣어, 판단 모델이 라벨 원문으로 확인된 사실을 보고 판단하게 합니다."""
    lines = [f"FAERS ICSR primaryid {case['primaryid']} (case {case['caseid']}, {case.get('quarter')})"]
    demo = []
    if case.get("age") is not None:
        demo.append(f"age {case['age']:.0f}y")
    if case.get("sex"):
        demo.append({"F": "female", "M": "male"}.get(case["sex"], case["sex"]))
    if case.get("weight"):
        demo.append(f"{case['weight']:.0f} kg")
    lines.append("Patient: " + (", ".join(demo) or "not reported"))
    lines.append(f"Reporter: {OCCP.get(case.get('occp_cod'), 'not reported')}, country {case.get('country') or 'unknown'}")
    for d in case.get("drugs", [])[:8]:
        extra = []
        if d.get("route"):
            extra.append(d["route"].lower())
        if d.get("indication"):
            extra.append(f"for {d['indication']}")
        if d.get("dechal") in ("Y", "N"):
            extra.append("dechallenge " + ("positive" if d["dechal"] == "Y" else "negative"))
        if d.get("rechal") in ("Y", "N"):
            extra.append("rechallenge " + ("positive" if d["rechal"] == "Y" else "negative"))
        lines.append(f"Drug [{ROLE.get(d.get('role'), d.get('role'))}]: {d['drug']}" + (f" ({'; '.join(extra)})" if extra else ""))
    lines.append("Reactions (MedDRA PT): " + "; ".join(case.get("reactions", [])[:15]))
    if include_outcome:
        oc = [OUTCOME.get(o, o) for o in case.get("outcomes", [])]
        lines.append("Outcomes: " + (", ".join(oc) if oc else "none reported"))
    if grounding and grounding.get("label", {}).get("found"):
        lab = grounding["label"]
        facts = []
        for pt, info in lab.get("by_pt", {}).items():
            fact = f"{pt}: " + (f"listed in {', '.join(info['sections'])}" if info["sections"] else "not found in label text")
            if info.get("contraindication") and not info["sections"]:
                fact += " (named only in contraindications as a patient condition, not an adverse-reaction listing)"
            if info.get("indication_term"):
                fact += " (also appears in the indications section)"
            facts.append(fact)
        lines.append(f"Label check (US label {lab.get('brand')}, effective {lab.get('effective')}): " + "; ".join(facts))
    elif grounding is not None and not grounding.get("clinical_reactions"):
        lines.append("Label check: not applicable (only product-use or non-clinical terms reported)")
    elif grounding is not None:
        lines.append("Label check: no US label found for the primary suspect; expectedness unknown")
    return "\n".join(lines)


async def ground(case: dict, client: httpx.AsyncClient | None = None) -> dict:
    """주 의심약의 라벨에서 주요 임상 반응(비임상 PT 제외, 최대 5개)의 기재 여부를 확인합니다.
    라벨이 있으면 예측성은 규칙으로 정합니다: 주요 반응 3개가 모두 기재되어 있으면 예상된 반응입니다."""
    suspect = principal_suspect(case)
    clinical = [p for p in case.get("reactions", []) if not labeltext.is_nonclinical(p)]
    route = next((d.get("route") for d in case.get("drugs", []) if d.get("drug") == suspect), None)
    own = client is None
    client = client or httpx.AsyncClient()
    t0 = time.perf_counter()
    try:
        lab = await evidence.label_lookup(suspect, clinical[:5], client, route) if clinical else {"found": False}
    finally:
        if own:
            await client.aclose()
    expected = None
    if lab.get("found") and clinical:
        expected = 1.0 if all(lab["listed"].get(p) for p in clinical[:3]) else 0.0
    return {"label": lab, "clinical_reactions": clinical[:5], "expected": expected,
            "expected_source": "openFDA label" if expected is not None else "jev",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def questions(suspect: str) -> dict:
    return {
        "serious": {"type": "noul", "instructions":
                    "Does this case meet ICH E2A seriousness criteria (death, life-threatening, hospitalization, "
                    "disability, congenital anomaly, or other medically important event)?"},
        "expected": {"type": "noul", "instructions":
                     f"Are the principal reactions already described in the approved product labeling of {suspect}?"},
        "causality": {"type": "choice", "instructions":
                      f"WHO-UMC causality category for {suspect} and the principal reaction, based only on this report.",
                      "criteria": {"certain": "certain", "probable": "probable / likely", "possible": "possible",
                                   "unlikely": "unlikely", "unassessable": "unassessable / unclassifiable"}},
        "special": {"type": "choice", "instructions": "Is there a special situation in this report?",
                    "criteria": {"none": "no special situation", "pregnancy": "pregnancy or lactation exposure",
                                 "pediatric": "pediatric patient", "elderly": "elderly patient",
                                 "misuse": "overdose, abuse, misuse or medication error",
                                 "offlabel": "off-label use", "interaction": "drug interaction"}},
        "priority": {"type": "score", "instructions": "How urgently should a pharmacovigilance professional review this case?",
                     "criteria": PRIORITY_LEVELS},
        "route": {"type": "choice", "instructions": "What should the safety system do next with this case?",
                  "criteria": ROUTES},
        "deep": {"type": "noul", "instructions":
                 "Would a careful expert medical narrative assessment change the handling of this case?"},
    }


def validity(case: dict) -> dict:
    """ICH 최소 4요소는 구조화 필드로 판정한다. 규칙으로 되는 일은 모델에 맡기지 않는다."""
    checks = {
        "reporter": bool(case.get("occp_cod") or case.get("country")),
        "patient": any(case.get(k) not in (None, "") for k in ("age", "sex", "weight")),
        "suspect_drug": any(d.get("role") in ("PS", "SS") for d in case.get("drugs", [])),
        "adverse_event": bool(case.get("reactions")),
    }
    return {"valid": all(checks.values()), "checks": checks}


# 규정 모드: 신속보고 요건이 나라마다 다릅니다
REGIMES = {
    "US": {"name": "미국 FDA", "expedite_rule": "serious_unexpected",
           "deadline": "15 calendar days (21 CFR 314.80: serious and unexpected)"},
    "KR": {"name": "한국 식약처", "expedite_rule": "serious_adr",
           "deadline": "15일 이내 (의약품 등의 안전에 관한 규칙 별표 4의3 제7호 나목: 중대한 약물이상반응, '예상하지 못한' 요건 없음)"},
}


KR_CAUSALITY_EXCLUDABLE = {"unlikely"}   # WHO-UMC 중 배제 후보는 가능성 적음뿐입니다(평가 곤란·평가 불가는 배제 불가)


@functools.lru_cache(maxsize=1)
def dme_terms() -> frozenset:
    """EMA 지정 의학적 사건(DME) PT 목록입니다. 한 건만으로도 의심해야 하는 사건이라 점수와 무관하게 사람에게 보냅니다."""
    p = config.DATA / "dme_pts.json"
    if not p.exists():
        return frozenset()
    return frozenset(t.lower() for t in json.loads(p.read_text())["pts"])


def dme_hits(case: dict) -> list[str]:
    terms = dme_terms()
    return [r for r in case.get("reactions", []) if r.lower() in terms]


def route_policy(ans: dict, valid: dict | None = None, regime: str = "US", expected: float | None = None,
                 expected_source: str = "jev", dme: list[str] | None = None) -> dict:
    """결정론적 라우팅 정책입니다. 모델 확률을 행동으로 바꾸고, 모든 규칙을 사유 문자열로 남깁니다.
    expected 가 주어지면(라벨 조회 결과) 모델 추정 대신 그 값을 씁니다.
    dme 는 보고된 PT 중 EMA 지정 의학적 사건(DME)입니다. 있으면 점수와 무관하게 사람 검토로 올립니다(EMA 방식의 안전망)."""
    d = _route(ans, valid, regime, expected, expected_source)
    if dme and d["action"] in ("monitor", "close", "signal_review"):
        d = {"action": "expedite", "tier": "human", "system2": True, "dme": True,
             "reasons": [f"[DME] {', '.join(dme)}: EMA designated medical event -> human review regardless of scores"] + d["reasons"]}
    elif dme:
        d["reasons"].append(f"[DME] {', '.join(dme)}: EMA designated medical event")
        d["dme"] = True
    d["regime"] = regime
    d["report15"] = bool(d.get("report15", False))
    if d["report15"]:
        d["deadline"] = REGIMES[regime]["deadline"]
    elif d.pop("kr_causality_check", False):
        d["deadline"] = ("즉시 사람 검토: 인과관계 배제 여부 확인 (보고자와 품목허가를 받은 자가 모두 관련 없다고 판단한 경우에만 "
                         "신속보고 제외, 별표 4의3 제1호 차목 단서)")
    elif d["action"] == "expedite":
        d["deadline"] = ("즉시 사람 검토 (규정상 15일 신속보고 요건에는 해당하지 않음)" if regime == "KR"
                         else "Urgent human review (does not meet the 15-day expedited criteria)")
    return d


def _route(ans: dict, valid: dict | None, regime: str, expected_override: float | None = None,
           expected_source: str = "jev") -> dict:
    p = lambda k: ans[k]["noul"]
    serious, deep = p("serious"), p("deep")
    expected = expected_override if expected_override is not None else p("expected")
    pr = ans["priority"]
    route = ans["route"]["choice"]
    cau = ans["causality"]
    reasons = []
    if valid is not None and not valid["valid"]:
        missing = [k for k, v in valid["checks"].items() if not v]
        reasons = [f"ICH minimum elements missing: {', '.join(missing)} -> request follow-up"]
        if serious >= 0.5:  # 요소가 빠졌어도 중대해 보이면 사람이 먼저 추가정보를 요청합니다
            reasons.append(f"serious={serious:.2f}: priority follow-up handled by a human reviewer")
            return {"action": "follow_up", "tier": "human", "system2": False, "priority_follow_up": True, "reasons": reasons}
        return {"action": "follow_up", "tier": "rule", "system2": False, "reasons": reasons}
    if regime == "KR" and serious >= 0.5:
        # 별표 4의3 제1호 차목: 약물이상반응은 인과관계를 배제할 수 없는 반응입니다. 자발보고에서 인과관계를 알 수 없으면(unassessable)
        # 약물이상반응으로 보고, 보고자와 품목허가권자가 모두 관련 없다고 판단해야만 제외합니다. 모델은 그 둘이 아니므로 스스로 제외하지 않습니다
        excl = cau["choice"] in KR_CAUSALITY_EXCLUDABLE and cau["confidence"] >= 0.55
        if not excl:
            reasons.append(f"[KR] serious={serious:.2f}, WHO-UMC {cau['choice']} (conf {cau['confidence']:.2f}, 인과관계 배제 불가): "
                           f"중대한 약물이상반응 -> 15일 신속보고 후보 (expected={expected:.2f}와 무관)")
            return {"action": "expedite", "tier": "human", "system2": True, "reasons": reasons, "report15": True}
        reasons.append(f"[KR] serious={serious:.2f}, WHO-UMC unlikely (conf {cau['confidence']:.2f}): 인과관계 배제 후보 -> "
                       f"보고자·품목허가권자 판단 확인 전까지 15일 기한은 그대로 둡니다")
        return {"action": "expedite", "tier": "human", "system2": True, "reasons": reasons, "report15": False,
                "kr_causality_check": True}
    if serious >= 0.5 and expected < 0.5:
        reasons.append(f"[US] serious={serious:.2f} and expected={expected:.2f} ({expected_source}): serious unexpected -> expedited candidate")
        return {"action": "expedite", "tier": "human", "system2": True, "reasons": reasons, "report15": True}
    if pr["score"] >= 2.5:
        reasons.append(f"priority score {pr['score']:.2f} >= 2.5")
        return {"action": "expedite", "tier": "human", "system2": True, "reasons": reasons}
    uncertain = cau["confidence"] < 0.55 or ans["route"]["confidence"] < 0.55
    if route == "signal_review" or deep >= 0.5 or uncertain:
        if route == "signal_review":
            reasons.append("model route = signal_review")
        if deep >= 0.5:
            reasons.append(f"deep={deep:.2f} >= 0.50")
        if uncertain:
            reasons.append(f"low confidence (causality {cau['confidence']:.2f}, route {ans['route']['confidence']:.2f}) -> escalate")
        return {"action": "signal_review", "tier": "system2", "system2": True, "reasons": reasons}
    reasons.append(f"route={route} (conf {ans['route']['confidence']:.2f}), serious={serious:.2f}, expected={expected:.2f}")
    return {"action": route if route in ("close", "monitor") else "monitor", "tier": "reflex", "system2": False,
            "reasons": reasons}


def principal_suspect(case: dict) -> str:
    for d in case.get("drugs", []):
        if d.get("role") == "PS":
            return d["drug"]
    return case["drugs"][0]["drug"] if case.get("drugs") else "the suspect drug"


async def triage(case: dict, client=None, regime: str = "US", grounded: bool = True, include_outcome: bool = True,
                 use_dme: bool = True) -> dict:
    """FlyVigilance 반사 판단입니다. 규칙 게이트 → 라벨 근거 주입 → 판단 모델 7문항 → 결정 정책(+ DME 안전망).
    include_outcome=False 는 결과 코드를 가린 비교 실험용입니다(정답이 결과 코드이므로)."""
    suspect = principal_suspect(case)
    g = await ground(case) if grounded else None
    state = case_state(case, include_outcome=include_outcome, grounding=g)
    valid = validity(case)
    res = await clients.jev(state, questions(suspect), client=client)
    exp = g["expected"] if g else None
    decision = route_policy(res["answers"], valid, regime if regime in REGIMES else "US", exp,
                            g["expected_source"] if g else "jev", dme_hits(case) if use_dme else None)
    return {"state": state, "suspect": suspect, "validity": valid, "grounding": g, "jev": res, "decision": decision}


RAW_QUESTION = {"review_first": {"type": "noul", "instructions": "Should a pharmacovigilance professional review this case first?"}}


async def raw_triage(case: dict, client=None, include_outcome: bool = True) -> dict:
    """비교용 기준 조건 '모델 단독 · 질문 하나'입니다. 근거 주입·타입 질문 설계·규칙·정책 없이 질문 하나만 던집니다."""
    state = case_state(case, include_outcome=include_outcome)
    res = await clients.jev(state, RAW_QUESTION, client=client)
    p = res["answers"]["review_first"]["noul"]
    return {"state": state, "jev": res, "escalate": p >= 0.5, "p": p}
