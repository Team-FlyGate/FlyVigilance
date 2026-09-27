---
name: pv-kr-intake-causality
description: Use when a Korean adverse event report (MFDS professional form, consumer report, or hospital/pharmacist narrative) must be structured into the MFDS form sections and a triage case, scored with the Korean causality algorithm ver 2.0, and routed under Korean expedited-reporting rules.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: sense + encode + reflex
  model: nvidia/nemotron-3-super-120b-a12b (intake), typesafe jev-latest (causality items)
  tags: [pharmacovigilance, korea, mfds, kaers, causality]
---

# 국내 보고 구조화 · 한국형 인과성 평가 · 국내 규정 모드

## 1. 보고 구조화 (`POST /api/kr/intake`)
- 입력: `{text, form}`이며, `form`은 `professional`(의약전문가용 서식), `consumer`(일반인), `narrative`(병원·약사 사례 서술) 중 하나입니다.
- Nemotron이 식약처 공고 제2023-057호 의약전문가용 서식의 가~바 섹션(`kr_form`)을 채웁니다. 원문에 없는 값은 비워 두고 `missing`에 적습니다.
- 트리아지용 케이스(`case`)의 약물 역할(PS/SS/C), 보고자 코드, 결과 코드, 재투여 여부는 서식 값에서 **규칙으로** 만듭니다.

## 2. 한국형 인과성 평가 알고리즘 ver 2.0 (`POST /api/kr/causality`)
- 8개 항목(시간적 선후관계, 감량·중단, 과거력, 병용약물, 비약물요인, 알려진 정보, 재투약, 특이적 검사)을 Jev 선택형 질문 한 번으로 판단합니다.
- 점수 합산(최고 19점, 최저 −13점)과 등급 구간(12점 이상 확실함, 6~11점 가능성 높음, 2~5점 가능성 있음, 1점 이하 가능성 낮음)은 규칙으로 계산합니다.
- "알려진 정보" 항목은 openFDA 라벨에서 반응명이 확인되면 규칙으로 +3을 줍니다. 국내 허가사항은 평가자가 의약품안전나라에서 확인합니다.
- 신뢰도 0.55 미만 항목은 `needs_review`로 표시합니다.
- WHO-UMC 등급은 따로 내며, 두 체계의 등급을 섞지 않습니다.

## 3. 국내 규정 모드 (`POST /api/triage?regime=KR`)
- KR: 중대한 약물이상반응이면 15일 신속보고 후보입니다(의약품 등의 안전에 관한 규칙 별표 4의3 제7호, "예상하지 못한" 요건 없음).
- US: 중대하고 예상하지 못한 사례만 15일 신속보고 후보입니다(21 CFR 314.80).
- 우선순위 규칙으로 올라온 사례에는 신속보고 기한 대신 "즉시 사람 검토"를 붙입니다.

## 근거 자료
- 팀 문서 「국내 PV 흐름 설명」, 「약물부작용 인과성평가 기준 및 도구」(WHO-UMC, 한국형 알고리즘 ver 2.0, Naranjo)
