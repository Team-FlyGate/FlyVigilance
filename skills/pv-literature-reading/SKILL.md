---
name: "pv-literature-reading"
title: "PV Literature Reading"
version: "1.0.0"
description: "Use when a drug–event pair needs its top PubMed articles read and typed: the top 20 PubMed candidates are reordered by the NVIDIA Nemotron reranker, then the top 6 are typed for study design (PubMed publication type by rule, otherwise a judgment-model choice), whether the article actually studies the pair, design-specific items (dechallenge, rechallenge, onset, effect, comparator, dose) and support for the association, with citable pubmed:<pmid>#<design> IDs. Do not use as a systematic review or to count articles as evidence strength."
license: "Apache-2.0"
compatibility: "PubMed E-utilities esearch/efetch (eutils.ncbi.nlm.nih.gov); nvidia/llama-nemotron-rerank-vl-1b-v2 via ai.api.nvidia.com/v1/retrieval (falls back to PubMed order); non-autoregressive judgment model (TypeSafe AI Jev, api.typesafe.ai/v1/systemone), one call per pair for up to 6 articles; Python 3.11+ with httpx."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "memory (mushroom body)"
  model: "nvidia/llama-nemotron-rerank-vl-1b-v2 (rerank) + non-autoregressive judgment model (one call per pair, up to 6 abstracts)"
  domain: "pharmacovigilance"
  tags:
    - pharmacovigilance
    - literature
    - pubmed
    - study-design
    - nemotron-rerank
---

# 문헌 읽기

## When to Use

- 근거 등급의 문헌 축, 한국형 알고리즘 "알려진 정보" 항목의 증례보고(+2) 규칙, System-2 근거 카탈로그에 넣을 문헌 판정이 필요할 때 씁니다.

## Do Not Use

- 체계적 문헌고찰을 대신하지 않습니다. PubMed 상위 20편 후보 가운데 재정렬 상위 6편만 읽습니다.
- PubMed 검색 건수나 편수를 근거 강도로 쓰지 않습니다(크리틱 R7).

## Requirements

PubMed 는 자격 증명이 필요 없습니다. 재정렬에는 NVIDIA API 키(`NVIDIA_API_KEY`, build.nvidia.com)를, 판단 모델 판정에는 `TYPESAFE_API_KEY` 를 씁니다. NVIDIA 키가 없으면 PubMed 순서 앞 6편을 읽고, 판단 모델 키가 없으면 오류 대신 규칙 필드(출판 유형 설계, 증례보고 규칙)만 채우고 `not_judged` 로 돌려줍니다.

## Instructions

1. esearch 로 관련도 상위 문헌 PMID 를 받고, efetch 로 초록과 출판 유형을 받습니다. 반응명은 정확한 동의어를 OR 로 묶습니다.
   이어서 PubMed 관련도 상위 20편을 NVIDIA Nemotron 리랭커(`nvidia/llama-nemotron-rerank-vl-1b-v2`, build.nvidia.com `/v1/retrieval/.../reranking`, 제목+초록, `truncate=END`)로 다시 줄 세워 위에서 6편을 고릅니다. 결과의 `order` 는 `nemotron_rerank` 이고, 편마다 `pubmed_rank`·`rerank_score` 를 남깁니다. 리랭커가 실패하거나 2초 안에 답하지 않으면 PubMed 순서 앞 6편으로 돌아가고 `order: "pubmed"` 로 기록합니다(`FV_RERANK=0` 으로 끌 수 있습니다).
2. 연구 설계는 PubMed 출판 유형(Meta-Analysis, Systematic Review, Randomized Controlled Trial, Case Reports, Review)이 있으면 규칙으로 정합니다.
3. 판단 모델은 쌍마다 한 번만 부릅니다(최대 6편, 편당 최대 8문항). 출판 유형이 없을 때의 설계, 관문(이 약과 이 반응을 실제로 다루는가: focus·reported·passing·unrelated), 설계별 항목(증례: 중단 후 경과, 재투여, 발현 시간, 대안 원인 배제, 인과성 척도 / 비교 연구: 효과 방향과 유의성, 환자 수, 비교군, 용량 관계)을 판단합니다. 초록에 없으면 `not_stated` 를 고릅니다.
4. 관문에서 passing·unrelated 로 판정한 문헌은 지지 편수에서 뺍니다. 판단 모델 호출이 실패하면 "지지 안 함"이 아니라 `not_judged` 로 남깁니다.
5. 초록 원문은 판단에만 쓰고 결과에는 PMID·연도·제목·판정만 남깁니다. 근거 ID 는 `pubmed:<pmid>#<design>` 입니다.
6. 문헌 증례와 FAERS 건수는 서로 독립된 근거로 더하지 않습니다(이중 계산 경고).

## 검증

출판 유형을 가린 채 설계를 고르게 했을 때 MEDLINE 색인과의 일치율은 92.0% 였습니다(598편, 210쌍, `pipeline/bench/literature_eval.py`, 결과 `web/public/data/literature_eval.json`). 설계 질문 문구는 운영 코드와 평가 스크립트가 한 글자도 다르지 않도록 `tests/test_literature.py` 가 확인합니다.

후보 재정렬은 30쌍 575편에서 관문 판정(focus·reported)을 기준으로 측정했습니다. 읽는 상위 6편 가운데 관문을 통과하는 비율이 PubMed 순서 0.65 에서 Nemotron 재정렬 0.85 로 올랐고(21쌍 개선, 9쌍 같음, 악화 없음), 쌍별 AUC 는 0.43 에서 0.78 이 되었습니다. 리랭커 한 번(20편)의 지연 중앙값은 0.43초입니다(`pipeline/bench/literature_rerank_eval.py`, 결과 `web/public/data/literature_rerank_eval.json`).

## 쓰이는 곳

근거 등급의 문헌 축, 한국형 알고리즘 "알려진 정보" 항목의 증례보고(+2) 규칙, System-2 근거 카탈로그. 구현 `api/_fv/literature.py::read`.
