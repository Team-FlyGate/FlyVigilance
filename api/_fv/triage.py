"""Reflex 층: Jev System-1 로 ICSR 한 건에 타입 있는 판단 7개를 한 번에 받고 라우팅한다.

판단은 확률로 받는다. 확률은 집단 보정값이지 이 한 건의 보장이 아니므로,
라우팅은 확률과 신뢰도 둘 다를 보고 애매하면 위(System-2, 사람)로 올린다.
"""
from . import clients

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


def case_state(case: dict, include_outcome: bool = True) -> str:
    """ICSR 를 Jev 상태 문자열로. include_outcome=False 는 중대성 맹검 벤치마크용."""
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
    return "\n".join(lines)


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
    "KR": {"name": "한국 식약처", "expedite_rule": "serious",
           "deadline": "15일 이내 (의약품 등의 안전에 관한 규칙 별표 4의3 제7호: 중대한 약물이상반응, '예상하지 못한' 요건 없음)"},
}


def route_policy(ans: dict, valid: dict | None = None, regime: str = "US") -> dict:
    """결정론적 라우팅 정책입니다. 모델 확률을 행동으로 바꾸고, 모든 규칙을 사유 문자열로 남깁니다."""
    d = _route(ans, valid, regime)
    d["regime"] = regime
    if d.pop("report15", False):
        d["deadline"] = REGIMES[regime]["deadline"]
    elif d["action"] == "expedite":
        d["deadline"] = ("즉시 사람 검토 (규정상 15일 신속보고 요건에는 해당하지 않음)" if regime == "KR"
                         else "Urgent human review (does not meet the 15-day expedited criteria)")
    return d


def _route(ans: dict, valid: dict | None, regime: str) -> dict:
    p = lambda k: ans[k]["noul"]
    serious, expected, deep = p("serious"), p("expected"), p("deep")
    pr = ans["priority"]
    route = ans["route"]["choice"]
    cau = ans["causality"]
    reasons = []
    if valid is not None and not valid["valid"]:
        missing = [k for k, v in valid["checks"].items() if not v]
        return {"action": "follow_up", "tier": "rule", "system2": False,
                "reasons": [f"ICH minimum elements missing: {', '.join(missing)} -> request follow-up"]}
    if regime == "KR" and serious >= 0.5:
        reasons.append(f"[KR] serious={serious:.2f}: 중대한 약물이상반응 -> 15일 신속보고 후보 (expected={expected:.2f}와 무관)")
        return {"action": "expedite", "tier": "human", "system2": True, "reasons": reasons, "report15": True}
    if serious >= 0.5 and expected < 0.5:
        reasons.append(f"[US] serious={serious:.2f} and expected={expected:.2f}: serious unexpected -> expedited candidate")
        return {"action": "expedite", "tier": "human", "system2": True, "reasons": reasons, "report15": True}
    if pr["score"] >= 2.5:
        reasons.append(f"priority score {pr['score']:.2f} >= 2.5")
        return {"action": "expedite", "tier": "human", "system2": True, "reasons": reasons}
    uncertain = cau["confidence"] < 0.55 or ans["route"]["confidence"] < 0.55
    if route == "signal_review" or deep >= 0.5 or uncertain:
        if route == "signal_review":
            reasons.append("Jev route = signal_review")
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


async def triage(case: dict, client=None, regime: str = "US") -> dict:
    suspect = principal_suspect(case)
    state = case_state(case)
    valid = validity(case)
    res = await clients.jev(state, questions(suspect), client=client)
    decision = route_policy(res["answers"], valid, regime if regime in REGIMES else "US")
    return {"state": state, "suspect": suspect, "validity": valid, "jev": res, "decision": decision}
