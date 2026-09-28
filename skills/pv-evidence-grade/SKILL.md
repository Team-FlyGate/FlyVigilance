---
name: pv-evidence-grade
description: Use when a drug–event pair needs a population-level evidence grade (A/B/C/L/D/U) built by fixed rules from label section, FAERS triple-criterion signal and literature, returned together with its basis (evidence IDs) and gaps.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: memory (mushroom body)
  based_on: korea-agentic-hackathon-2026 docs/notes/evidence-grade-2026-09-28.md
  tags: [pharmacovigilance, evidence-grade, signal-assessment]
---

# 근거 등급 (FlyVigilance Evidence Grade v1)

## 규칙 (모델 미사용)
| 등급 | 조건 |
| --- | --- |
| A | 박스 경고 + 3중 신호 |
| B | 경고·주의 또는 이상반응 절 기재 + 3중 신호 |
| C | 3중 신호가 있으나 라벨 미기재, 또는 그 반응에 붙은 "인과 미확립" 단서 (A·B 의 상한) |
| L | 라벨 기재, FAERS 신호 미검출 (신호 부재 ≠ 근거 부재, R4) |
| D | 라벨 미기재, 신호 없음 |
| U | 라벨을 확인하지 못했거나 통계를 계산하지 못함 |

- 3중 신호 = Evans(PRR≥2, χ²≥4, a≥3) ∧ ROR025>1 ∧ IC025>0 입니다.
- 인과 미확립 단서는 그 반응이 언급된 문장과 뒤의 두 문장 안에서만 찾습니다. 이상반응 절 첫머리의 상투 문구("reported voluntarily from a population of uncertain size")는 세지 않습니다.
- 문헌은 등급을 바꾸지 않는 참고 축입니다(분석 연구의 지지·혼재·반론 상태).

## 팀 시제품과 달라진 점
팀 시제품은 이소트레티노인–염증성장질환을 C 로 매겼습니다. 인용한 단서("Mechanism(s) and causality for this reaction have not been established")는 같은 경고 절의 5.9 청력 손상 항목에 붙은 문장이었습니다. 반응 범위로 단서를 찾으면 B(경고 기재 + 신호)가 되고, 대신 문헌 축에 "분석 연구 결과 혼재"가 표시됩니다.

## 호출
`GET /api/grade?drug=CLOZAPINE&pt=neutropenia` · 근거 ID `grade:<DRUG>:<pt>@<asof>` · 크리틱 규칙 R13
