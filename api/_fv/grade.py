"""근거 등급 FlyVigilance Evidence Grade v2 입니다 (약사 검토 반영).

약물감시 실무의 공식 분류를 빌려 '라벨 상태 × SDR' 두 축으로 나눕니다(약사 검토 의견).
- 라벨 상태: 박스 경고 / 경고·주의사항 / 이상반응(임상시험) / 이상반응(구분 없음) / 이상반응(시판 후) / 미기재 / 확인 불가.
  금기 절은 환자 조건을 적는 절이라 이상반응 기재로 세지 않습니다.
- SDR(불균형 보고 신호): Evans(PRR>=2, chi2>=4, a>=3) ∧ ROR025>1 ∧ IC025>0 을 모두 넘은 상태입니다.
  SDR 은 검증된 신호가 아닙니다(EU GVP Module IX).

PV 분류(공식 용어 + '후보'): 검토가 필요한 SDR / 잠재적 위해성 후보 / 규명된 위해성 후보 / 알려진 위험·SDR 없음 /
해당 없음 / 판정 불가. 실제 분류는 허가권자와 규제기관이 평가해서 정하므로 도구 결과에는 반드시 '후보'를 붙입니다.
검토 우선순위는 PV 실무 순서를 따릅니다. 라벨에 없는데 SDR 이 선 쌍을 가장 먼저 봅니다.

따로 붙이는 표시: 심각성(박스 경고, 근거의 확실성과는 다른 축), EMA DME, 보고 편향 의심(변호사·소비자 보고 편중),
문헌 근거 수준, 금기 절 언급, 적응증 용어.

팀 시제품과 비교하려고 한 글자 등급(A/B/C/L/D/U)도 함께 냅니다. 모델은 분류하지 않습니다. 모두 고정 규칙이며,
근거(basis)와 공백(gaps)을 항상 함께 냅니다. 집단 수준 근거이며 개별 사례의 인과가 아닙니다(크리틱 R13).
"""
import functools
import gzip
import json

from . import config, evidence, literature

GRADE_NAMES = {
    "A": "박스 경고 기재 + SDR",
    "B": "라벨 기재 + SDR",
    "C": "SDR, 라벨 미기재 또는 라벨이 그 반응의 인과 미확립을 명시",
    "L": "라벨 기재, SDR 없음",
    "D": "라벨 미기재, SDR 없음",
    "U": "판정 불가 · 라벨 또는 FAERS 통계를 확인하지 못함",
}
REG_NAMES = {3: "박스 경고", 2: "경고·주의사항", 1: "이상반응 절", 0: "라벨 미기재", -1: "라벨 확인 불가"}
LABEL_STATUS_NAMES = {
    "boxed": "박스 경고", "warnings_precautions": "경고·주의사항", "ar_clinical_trials": "이상반응 (임상시험)",
    "ar_unspecified": "이상반응 (구분 없음)", "ar_postmarketing": "이상반응 (시판 후 자발보고)", "unlisted": "라벨 미기재",
    "no_label": "라벨 확인 불가",
}
SIG_NAMES = {"strong": "3중 기준 SDR", "weak": "기준 일부 충족 (SDR 아님)", "none": "SDR 없음",
             "insufficient": "보고 부족 (a<3)", "unavailable": "통계 없음"}
PV_CLASSES = {
    "review_sdr": ("검토가 필요한 SDR", "새 신호 후보입니다. 라벨에 없는데 SDR 이 섰으므로 먼저 검토합니다", 1),
    "potential_candidate": ("잠재적 위해성 후보", "라벨에 있으나 그 반응에 인과 미확립 단서가 붙어 있습니다", 2),
    "undetermined": ("판정 불가", "라벨이나 FAERS 통계를 확인하지 못했습니다. 사람이 확인해야 합니다", 2),
    "identified_candidate": ("규명된 위해성 후보", "라벨에 있고 SDR 도 섰습니다. 알려진 위험이 보고와 일치합니다", 3),
    "known_no_sdr": ("알려진 위험 · SDR 없음", "허가사항(임상 근거)에 있는 반응입니다. 흔한 반응은 SDR 이 서지 않는 것이 보통입니다", 4),
    "none": ("해당 없음", "라벨에 없고 SDR 도 서지 않았습니다. 현재 근거가 없다는 뜻이지 안전하다는 뜻은 아닙니다(R4)", 5),
}


def decide(reg: int, sig: str, disclaimer: bool) -> str:
    """규제 강도(reg: -1 확인 불가, 0 미기재, 1 이상반응, 2 경고·주의, 3 박스 경고), SDR 단계, 인과 미확립 단서로
    한 글자 등급을 정합니다(팀 시제품 호환). 순수 함수입니다."""
    if sig == "strong":
        if disclaimer:
            return "C"   # 라벨이 그 반응의 인과 미확립을 명시하면 숫자가 아무리 커도 C 가 상한입니다
        return {3: "A", 2: "B", 1: "B"}.get(reg, "C")
    if reg >= 1:
        return "L"
    if reg == 0 and sig in ("none", "weak", "insufficient"):
        return "D"
    return "U"


def pv_class(reg: int, sig: str, disclaimer: bool) -> str:
    """라벨 상태 × SDR 로 PV 분류를 정합니다. 순수 함수입니다."""
    if reg >= 1:
        if disclaimer:
            return "potential_candidate"
        return "identified_candidate" if sig == "strong" else "known_no_sdr"
    if sig == "strong":
        return "review_sdr"          # 미기재이거나 라벨을 찾지 못했는데 SDR 이 섰습니다
    if reg < 0 or sig == "unavailable":
        return "undetermined"
    return "none"


@functools.lru_cache(maxsize=1)
def _reporter_mix() -> dict:
    p = config.DATA / "reporter_mix.json.gz"
    return json.load(gzip.open(p, "rt")) if p.exists() else {"pairs": {}}


@functools.lru_cache(maxsize=1)
def _dme() -> frozenset:
    p = config.DATA / "dme_pts.json"
    return frozenset(t.lower() for t in json.loads(p.read_text())["pts"]) if p.exists() else frozenset()


def reporting_bias(drug: str, pt: str) -> dict | None:
    """변호사·소비자 보고 편중 표시입니다(pipeline/faers/export_reporter_mix.py). 표시가 없으면 None 입니다."""
    rm = _reporter_mix()
    r = rm["pairs"].get(drug.upper(), {}).get(pt.lower())
    if not r:
        return None
    a = r["a"] or 1
    return {"lawyer_share": round(r["n_lw"] / a, 3), "consumer_share": round(r["n_cn"] / a, 3),
            "hcp_share": round(r["n_hcp"] / a, 3), "background": rm.get("background"),
            "flag_lawyer": r["flag_lw"], "flag_consumer": r["flag_cn"],
            "no_lawyer": r["no_lawyer"], "hcp_only": r["hcp_only"]}


def grade_pair(drug: str, pt: str, f: dict | None, label: dict, lit: dict | None = None) -> dict:
    asof = evidence._signals().get("asof")
    sig = evidence.signal_tier(f)
    found = bool(label and label.get("found"))
    by = (label or {}).get("by_pt", {}).get(pt, {})
    reg = int(by.get("rank", 0)) if found else -1
    status = (by.get("label_status") or ("unlisted" if reg == 0 else None)) if found else "no_label"
    if status is None:  # 라벨 담당 모듈이 상태를 주지 않을 때의 예비값입니다
        status = {3: "boxed", 2: "warnings_precautions", 1: "ar_unspecified"}.get(reg, "unlisted")
    disc = by.get("disclaimer")
    g = decide(reg, sig, bool(disc))
    pc = pv_class(reg, sig, bool(disc))
    pc_name, pc_hint, priority = PV_CLASSES[pc]
    lit_s = (lit or {}).get("summary") or {}
    bias = reporting_bias(drug, pt)
    dme = pt.lower() in _dme()
    if dme:
        priority = min(priority, 2)
    basis, gaps = [], []
    if f and f.get("id"):
        basis.append(f["id"])
    if found:
        basis += [h["id"] for h in label.get("hits", []) if h["pt"] == pt]
    basis += [a["id"] for a in (lit or {}).get("articles", []) if (a.get("supports") or 0) >= 0.5
              and a.get("addresses") not in ("passing", "unrelated")][:4]
    if sig in ("unavailable", "insufficient"):
        gaps.append("FAERS 통계 부족: 동시 보고 3건 미만이거나 웨어하우스 상위 반응 목록 밖입니다")
    if reg < 0:
        gaps.append("미국 FDA 허가 라벨(openFDA drug/label)을 찾지 못했습니다. 국내 허가사항은 의약품안전나라에서 확인해야 합니다")
    elif reg == 0:
        gaps.append("라벨 검색은 PT 문자열과 동의어 목록 기준입니다. 라벨이 다른 표현으로 적었을 수 있습니다")
    if status == "ar_postmarketing":
        gaps.append("라벨 기재가 시판 후 자발보고 절에만 있습니다(분모가 없고 빈도·인과를 확립하지 못한다는 정형 문구가 붙는 절)")
    if by.get("contraindication") and reg == 0:
        gaps.append("금기 절에 환자 조건으로만 언급되어 있습니다. 금기 절은 이상반응 기재가 아닙니다")
    if by.get("indication_term"):
        gaps.append("이 반응명이 효능·효과(적응증)에도 나옵니다. 적응증 교란이나 효과 부족일 수 있습니다")
    if bias and (bias["flag_lawyer"] or bias["flag_consumer"]):
        who = "변호사" if bias["flag_lawyer"] else "소비자"
        share = bias["lawyer_share"] if bias["flag_lawyer"] else bias["consumer_share"]
        gaps.append(f"보고 편향 의심: 이 조합 보고의 {share:.0%}가 {who} 보고입니다(FAERS 전체 변호사 "
                    f"{(bias['background'] or {}).get('lw', 0):.1%}). PRR 이 크다고 근거가 단단한 것은 아닙니다")
        if sig == "strong" and bias["flag_lawyer"] and not bias["no_lawyer"]["sdr"]:
            gaps.append("변호사 보고를 빼면 SDR 이 사라집니다(소송으로 자극된 보고일 가능성)")
    if not lit_s.get("read"):
        gaps.append("문헌을 읽지 못했습니다")
    elif lit_s.get("analytic_status") == "not_judged":
        gaps.append("문헌은 찾았지만 판단 모델 호출에 실패해 연관 보고 여부를 판단하지 못했습니다")
    elif lit_s.get("analytic_status") == "no_analytic":
        gaps.append("상위 문헌에 이 약과 이 반응을 실제로 다룬 분석 연구(RCT·코호트·환자대조군·메타분석)가 없습니다")
    elif lit_s.get("analytic_status") in ("mixed", "not_supported"):
        gaps.append(f"분석 연구 {lit_s.get('analytic_read')}편 중 {lit_s.get('analytic_supportive')}편만 연관을 지지합니다 "
                    "(문헌 결과 혼재 또는 반론)")
    if lit_s.get("anecdotal_supportive") and sig == "strong":
        gaps.append(literature.DOUBLE_COUNT_NOTE)
    if sig in ("none", "weak") and reg == 0:
        gaps.append("SDR 부재는 안전성의 증거가 아닙니다 (R4)")
    summary = (f"label={LABEL_STATUS_NAMES.get(status, status)}, FAERS={SIG_NAMES[sig]}"
               + (f", literature supportive {lit_s.get('supportive', 0)}/{lit_s.get('read', 0)} "
                  f"(analytic {lit_s.get('analytic_supportive', 0)}/{lit_s.get('analytic_read', 0)} {lit_s.get('analytic_status')}, "
                  f"case reports {lit_s.get('anecdotal_supportive', 0)})" if lit_s.get("read") else "")
               + (", label states causality not established for this reaction" if disc else "")
               + (", reporting-bias flag" if bias and (bias["flag_lawyer"] or bias["flag_consumer"]) else ""))
    return {
        "id": f"grade:{evidence.id_drug(drug)}:{pt.lower()}@{asof}", "drug": drug.upper(), "pt": pt.lower(),
        "pv_class": pc, "pv_class_name": f"{pc_name} (후보)" if pc not in ("none", "undetermined") else pc_name,
        "pv_hint": pc_hint, "review_priority": priority,
        "grade": g, "grade_name": GRADE_NAMES[g],
        "axes": {"regulatory": reg, "regulatory_name": REG_NAMES[reg], "label_status": status,
                 "label_status_name": LABEL_STATUS_NAMES.get(status, status), "signal": sig, "signal_name": SIG_NAMES[sig],
                 "literature": {**{k: lit_s.get(k, 0) for k in ("read", "supportive", "analytic_read", "analytic_supportive",
                                                                "anecdotal_supportive")},
                                "analytic_status": lit_s.get("analytic_status", "not_read")}},
        "flags": {"severity_boxed": reg == 3, "dme": dme, "reporting_bias": bias,
                  "contraindication": by.get("contraindication"), "indication_term": bool(by.get("indication_term"))},
        "label_sections": by.get("sections", []), "disclaimer": disc,
        "stats": ({k: f.get(k) for k in ("a", "prr", "prr_lo", "prr_hi", "ror_lo", "ic025", "chi2")} if f and f.get("a") is not None else None),
        "basis": basis, "gaps": gaps, "summary": summary,
        "caution": ("집단 수준의 근거 분류이며 '후보'입니다. 이 한 사례의 인과를 뜻하지 않고, 실제 분류는 허가권자와 규제기관이 평가해서 "
                    "정합니다. 근거와 공백 없이 분류만 인용하지 않습니다."),
    }
