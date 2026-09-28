---
name: "pv-kr-intake-causality"
title: "PV Korean Intake and Causality"
version: "1.0.0"
description: "Use when a Korean adverse event report (MFDS professional form, consumer report, or hospital/pharmacist narrative) must be structured into the MFDS form sections and a triage case, scored with the Korean causality algorithm ver 2.0 (seven items judged by the non-autoregressive judgment model, the known-information item by label/literature rules, score summed by rule), and routed under Korean expedited-reporting rules. Do not use as the final causality decision or as an MFDS submission."
license: "Apache-2.0"
compatibility: "nvidia/nemotron-3-super-120b-a12b (fallback ultra-550b, 3.5-lightning-30b) via NVIDIA NIM integrate.api.nvidia.com for intake; non-autoregressive judgment model (TypeSafe AI Jev, api.typesafe.ai/v1/systemone) for the causality items; openFDA drug/label and PubMed E-utilities for the rule item."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "sense + encode + reflex"
  model: "nvidia/nemotron-3-super-120b-a12b (intake) + non-autoregressive judgment model (causality items)"
  endpoint: "POST /api/kr/intake · POST /api/kr/causality · POST /api/triage?regime=KR"
  domain: "pharmacovigilance"
  tags:
    - pharmacovigilance
    - korea
    - mfds
    - kaers
    - causality
---

# 국내 보고 구조화 · 한국형 인과성 평가 · 국내 규정 모드

## When to Use

- 한국어 이상사례 보고서(의약전문가용 서식, 일반인 보고, 병원·약사 사례 서술)를 구조화하고 한국형 알고리즘 점수와 국내 신속보고 기한을 함께 봐야 할 때 씁니다.

## Do Not Use

- 인과성 최종 판정이나 식약처 제출 문서로 쓰지 않습니다. 결과는 평가자 검토용 초안입니다.
- 식약처 허가사항 확인을 대신하지 않습니다. "알려진 정보" 항목은 미국 FDA 라벨과 PubMed 로만 채우므로 항상 평가자 검토 대상입니다.

## Requirements

구조화에는 NVIDIA API 키(`NVIDIA_API_KEY`, build.nvidia.com), 인과성 항목에는 판단 모델 API 키(`TYPESAFE_API_KEY`)가 필요합니다. 키가 없으면 API 가 503 "not configured"로 답합니다. 키는 환경 변수나 OpenShell provider 에 두고 프롬프트나 로그에 남기지 않습니다.

## 1. 보고 구조화 (`POST /api/kr/intake`)
- 입력: `{text, form}`이며, `form`은 `professional`(의약전문가용 서식), `consumer`(일반인), `narrative`(병원·약사 사례 서술) 중 하나입니다.
- Nemotron이 식약처 공고 제2023-057호 의약전문가용 서식의 가~바 섹션(`kr_form`)을 채웁니다. 원문에 없는 값은 비워 두고 `missing`에 적습니다.
- 트리아지용 케이스(`case`)의 약물 역할(PS/SS/C), 보고자 코드, 결과 코드, 재투여 여부는 서식 값에서 **규칙으로** 만듭니다(`api/_fv/kr.py::_norm_case`).

## 2. 한국형 인과성 평가 알고리즘 ver 2.0 (`POST /api/kr/causality`)
- 8개 항목 중 7개(시간적 선후관계, 감량·중단, 과거력, 병용약물, 비약물요인, 재투약, 특이적 검사)와 WHO-UMC 등급을 판단 모델의 선택형 질문 한 번으로 판단합니다.
- "약물에 대해 알려진 정보" 항목은 모델에 묻지 않고 규칙으로만 정합니다. 미국 FDA 라벨에 기재(금기 절만은 제외)되면 +3, 라벨에는 없고 PubMed 증례보고(출판 유형 기준)가 있으면 +2, 둘 다 없으면 0 입니다. 평가 반응이 적응증과 겹치면 +2 를 주지 않고 평가자에게 넘깁니다.
- 점수 합산(최고 19점, 최저 −13점)과 등급 구간(12점 이상 확실함, 6~11점 가능성 높음, 2~5점 가능성 있음, 1점 이하 가능성 낮음)은 규칙으로 계산합니다.
- 신뢰도 0.55 미만 항목은 `needs_review`로 표시합니다. 국내 허가사항은 평가자가 의약품안전나라에서 확인하도록 검색 링크(`mfds_label.search_url`)를 둡니다.
- WHO-UMC 등급은 따로 내며, 두 체계의 등급을 섞지 않습니다.

## 3. 국내 규정 모드 (`POST /api/triage?regime=KR`)
- KR: 중대한 약물이상반응이면 15일 신속보고 후보입니다(의약품 등의 안전에 관한 규칙 별표 4의3 제7호, "예상하지 못한" 요건 없음). WHO-UMC 가 신뢰도 0.55 이상으로 "가능성 적음"이면 15일 기한을 붙이지 않고 즉시 사람 검토로 보냅니다(별표 4의3 제1호 차목 단서).
- US: 중대하고 예상하지 못한 사례만 15일 신속보고 후보입니다(21 CFR 314.80).
- 우선순위 규칙으로 올라온 사례에는 신속보고 기한 대신 "즉시 사람 검토"를 붙입니다.

## 근거 자료
- 팀 문서 「국내 PV 흐름 설명」, 「약물부작용 인과성평가 기준 및 도구」(WHO-UMC, 한국형 알고리즘 ver 2.0, Naranjo)
- 구현 `api/_fv/kr.py`, `api/_fv/triage.py::route_policy` · 테스트 `tests/test_kr.py`, `tests/test_routing.py`
