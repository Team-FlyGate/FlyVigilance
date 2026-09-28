---
name: "pv-evidence-grade"
title: "PV Evidence Grade"
version: "1.0.0"
description: "Use when a drug–event pair needs a population-level evidence classification: a PV class candidate (label status × SDR) and a one-letter grade (A/B/C/L/D/U) built by fixed rules from the openFDA label section, the FAERS triple-criterion SDR and PubMed literature, returned with its basis (evidence IDs), gaps and flags. Do not use as individual-case causality or as a regulatory classification."
license: "Apache-2.0"
compatibility: "Deterministic rules (no model decides the class or grade); openFDA drug/label (api.fda.gov), PubMed E-utilities (eutils.ncbi.nlm.nih.gov) and the FAERS warehouse extract. The literature axis comes from pv-literature-reading."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "memory (mushroom body)"
  endpoint: "GET /api/grade?drug=<DRUG>&pt=<pt>"
  origin: "team prototype evidence-grade note (korea-agentic-hackathon-2026, 2026-09-28), revised after pharmacist review"
  domain: "pharmacovigilance"
  tags:
    - pharmacovigilance
    - evidence-grade
    - signal-assessment
    - openfda
    - sdr
---

# 근거 등급 (FlyVigilance Evidence Grade v2)

## When to Use

- 약물–이상반응 쌍 하나에 대해 "라벨에 있는가, SDR 이 섰는가, 문헌은 어떤가"를 한 번에 정리해야 할 때 씁니다.
- System-2 메모가 인용할 `grade:` 근거 ID 가 필요할 때 씁니다(`pv-signal-memory` 가 묶음에 넣습니다).

## Do Not Use

- 이 한 사례의 인과 판단에는 쓰지 않습니다. 집단 수준 근거이며, 근거와 공백 없이 등급만 인용하지 않습니다(크리틱 R13).
- 실제 위해성 분류로 쓰지 않습니다. 실제 분류는 허가권자와 규제기관이 평가해서 정하므로 결과에는 항상 '후보'를 붙입니다.

## Requirements

분류와 등급에는 자격 증명이 필요 없습니다. FAERS·openFDA·PubMed 는 공개 자료입니다. 판단 모델 API 키(`TYPESAFE_API_KEY`)가 있으면 문헌 축과 지식 기반 참고값을 채우고, 없으면 등급은 그대로 내고 문헌 축을 `not_judged` 로 표시합니다.

## 규칙 (모델 미사용)

PV 분류 후보는 라벨 상태 × SDR 로 정합니다. 검토 우선순위는 라벨에 없는데 SDR 이 선 쌍을 가장 먼저 봅니다.

| PV 분류 후보 | 조건 | 우선순위 |
| --- | --- | --- |
| 검토가 필요한 SDR · 새 신호 후보 | 라벨 미기재(또는 확인 불가) + SDR | 1 |
| 잠재적 위해성 후보 | 라벨 기재 + 그 반응에 인과 미확립 단서 | 2 |
| 판정 불가 | 라벨 또는 FAERS 통계를 확인하지 못함 | 2 |
| 규명된 위해성 후보 | 라벨 기재 + SDR | 3 |
| 알려진 위험 · SDR 없음 | 라벨 기재, SDR 없음 | 4 |
| 해당 없음 | 라벨 미기재, SDR 없음 (안전하다는 뜻이 아닙니다, R4) | 5 |

팀 시제품과 비교하려고 한 글자 등급도 함께 냅니다.

| 등급 | 조건 |
| --- | --- |
| A | 박스 경고 + SDR |
| B | 경고·주의 또는 이상반응 절 기재 + SDR |
| C | SDR 이 있으나 라벨 미기재, 또는 라벨이 그 반응의 인과 미확립을 명시 (A·B 의 상한) |
| L | 라벨 기재, SDR 없음 (신호 부재 ≠ 근거 부재, R4) |
| D | 라벨 미기재, SDR 없음 |
| U | 라벨을 확인하지 못했거나 통계를 계산하지 못함 |

- SDR = Evans(PRR≥2, χ²≥4, a≥3) ∧ ROR025>1 ∧ IC025>0 입니다. SDR 은 검증된 신호가 아닙니다(EU GVP Module IX).
- 라벨 상태는 박스 경고 / 경고·주의 / 이상반응(임상시험·구분 없음·시판 후)으로 나눕니다. 금기 절과 효능·효과 절은 기재로 세지 않습니다.
- 인과 미확립 단서는 그 반응이 언급된 문장과 뒤의 두 문장 안에서만 찾습니다. 이상반응 절 첫머리의 상투 문구("reported voluntarily from a population of uncertain size")는 세지 않습니다.
- 문헌은 등급을 바꾸지 않는 참고 축입니다(분석 연구의 지지·혼재·반론 상태).
- 따로 붙이는 표시: 박스 경고(심각성), EMA DME(우선순위를 2 이상으로 올림), 변호사·소비자 보고 편중(보고 편향 의심), 금기 절 언급, 적응증 용어.

## 팀 시제품과 달라진 점

팀 시제품은 이소트레티노인–염증성장질환을 C 로 매겼습니다. 인용한 단서("Mechanism(s) and causality for this reaction have not been established")는 같은 경고 절의 5.9 청력 손상 항목에 붙은 문장이었습니다. 반응 범위로 단서를 찾으면 라벨 기재 + SDR 이 되고, 대신 문헌 축에 "분석 연구 결과 혼재"가 표시됩니다. 이 쌍은 보고의 90% 이상이 변호사 보고라 보고 편향 표시도 함께 붙습니다.

## 호출

`GET /api/grade?drug=CLOZAPINE&pt=neutropenia` · `flygate grade` · 근거 ID `grade:<DRUG>:<pt>@<asof>` · 구현 `api/_fv/grade.py::grade_pair` · 테스트 `tests/test_grade.py`
