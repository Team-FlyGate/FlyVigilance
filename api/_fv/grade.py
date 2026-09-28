"""근거 등급 FlyVigilance Evidence Grade v1 입니다.

팀 시제품(korea-agentic-hackathon-2026 docs/notes/evidence-grade-2026-09-28.md)의 A~D 규칙을 이어받고
세 군데를 보완했습니다.
1. 두 축을 나눕니다. 규제 강도(라벨의 어느 절인가)와 통계 근거(신호가 서는가)는 다른 질문입니다.
2. 빈 칸을 채웁니다. 라벨에 있으나 FAERS 신호가 서지 않는 조합은 D 가 아니라 L 입니다.
   신호가 없다고 근거가 없는 것이 아닙니다(크리틱 R4).
3. 신호 기준을 명시합니다. Evans(PRR>=2, chi2>=4, a>=3) ∧ ROR025>1 ∧ IC025>0 세 가지 모두일 때 신호입니다.

모델은 등급을 매기지 않습니다. 등급은 고정 규칙이고, 근거(basis)와 공백(gaps)을 항상 함께 냅니다.
등급은 집단 수준의 근거이며 개별 사례의 인과가 아닙니다(크리틱 R13).
"""
from . import evidence

GRADE_NAMES = {
    "A": "확립 · 박스 경고 + 신호",
    "B": "개연 · 라벨 기재 + 신호",
    "C": "관찰 · 신호는 있으나 라벨 미기재 또는 라벨이 인과 미확립 명시",
    "L": "라벨 기재 · FAERS 신호 미검출",
    "D": "불충분 · 라벨 미기재, 신호 없음",
    "U": "판정 불가 · 라벨을 확인하지 못했고 신호도 서지 않음",
}
REG_NAMES = {3: "박스 경고", 2: "경고·주의사항", 1: "이상반응 절", 0: "라벨 미기재", -1: "라벨 확인 불가"}


def decide(reg: int, sig: str, disclaimer: bool) -> str:
    """규제 강도(reg: -1 확인 불가, 0 미기재, 1 이상반응, 2 경고·주의, 3 박스 경고), 신호 단계, 인과 미확립 단서로
    등급을 정합니다. 순수 함수입니다."""
    if sig == "strong":
        if disclaimer:
            return "C"   # 라벨이 인과 미확립을 명시하면 숫자가 아무리 커도 C 가 상한입니다
        return {3: "A", 2: "B", 1: "B"}.get(reg, "C")
    if reg >= 1:
        return "L"
    if reg == 0 and sig in ("none", "weak", "insufficient"):
        return "D"
    return "U"


def grade_pair(drug: str, pt: str, f: dict | None, label: dict, lit: dict | None = None) -> dict:
    asof = evidence._signals().get("asof")
    sig = evidence.signal_tier(f)
    by = (label or {}).get("by_pt", {}).get(pt, {})
    reg = by.get("rank", 0) if label and label.get("found") else -1
    disc = by.get("disclaimer")
    g = decide(reg, sig, bool(disc))
    lit_s = (lit or {}).get("summary") or {}
    basis, gaps = [], []
    if f and f.get("id"):
        basis.append(f["id"])
    if label and label.get("found"):
        basis += [h["id"] for h in label.get("hits", []) if h["pt"] == pt]
    basis += [a["id"] for a in (lit or {}).get("articles", []) if a.get("supports", 0) >= 0.5][:4]
    if sig in ("unavailable", "insufficient"):
        gaps.append("FAERS 통계 부족: 동시 보고 3건 미만이거나 웨어하우스 상위 반응 목록 밖입니다")
    if reg < 0:
        gaps.append("미국 라벨(openFDA)을 찾지 못했습니다. 국내 허가사항은 의약품안전나라에서 확인해야 합니다")
    elif reg == 0:
        gaps.append("라벨 검색은 PT 문자열(영국·미국 철자) 일치 기준입니다. 라벨이 다른 표현으로 적었을 수 있습니다")
    if not lit_s.get("read"):
        gaps.append("문헌을 읽지 못했습니다")
    elif lit_s.get("analytic_status") == "no_analytic":
        gaps.append("상위 문헌에 분석 연구(RCT·코호트·환자대조군·메타분석)가 없습니다")
    elif lit_s.get("analytic_status") in ("mixed", "not_supported"):
        gaps.append(f"분석 연구 {lit_s.get('analytic_read')}편 중 {lit_s.get('analytic_supportive')}편만 연관을 지지합니다 "
                    "(문헌 결과 혼재 또는 반론)")
    if g == "D":
        gaps.append("신호 부재는 안전성의 증거가 아닙니다 (R4)")
    summary = (f"regulatory={REG_NAMES[reg]}, FAERS signal={sig}"
               + (f", literature supportive {lit_s.get('supportive', 0)}/{lit_s.get('read', 0)} "
                  f"(analytic {lit_s.get('analytic_supportive', 0)}/{lit_s.get('analytic_read', 0)} {lit_s.get('analytic_status')}, "
                  f"case reports {lit_s.get('anecdotal_supportive', 0)})" if lit_s.get("read") else "")
               + (", label states causality not established" if disc else ""))
    return {
        "id": f"grade:{evidence.id_drug(drug)}:{pt.lower()}@{asof}", "drug": drug.upper(), "pt": pt.lower(),
        "grade": g, "grade_name": GRADE_NAMES[g],
        "axes": {"regulatory": reg, "regulatory_name": REG_NAMES[reg], "signal": sig,
                 "literature": {**{k: lit_s.get(k, 0) for k in ("read", "supportive", "analytic_read", "analytic_supportive",
                                                                "anecdotal_supportive")},
                                "analytic_status": lit_s.get("analytic_status", "not_read")}},
        "label_sections": by.get("sections", []), "disclaimer": disc,
        "stats": ({k: f.get(k) for k in ("a", "prr", "prr_lo", "prr_hi", "ror_lo", "ic025", "chi2")} if f and f.get("a") is not None else None),
        "basis": basis, "gaps": gaps, "summary": summary,
        "caution": "집단 수준의 근거 등급입니다. 이 한 사례의 인과를 뜻하지 않으며, 근거와 공백 없이 등급만 인용하지 않습니다.",
    }
