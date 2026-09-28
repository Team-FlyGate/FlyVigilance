---
name: pv-literature-reading
description: Use when a drug–event pair needs its top PubMed articles read and typed — study design (PubMed publication type by rule, otherwise judgment-model choice), whether the article reports the association, dechallenge/rechallenge mentions and conclusion strength — with citable pubmed:<pmid>#<design> IDs.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: memory (mushroom body)
  model: typesafe jev-latest (one call per pair, 6 abstracts per call)
  tags: [pharmacovigilance, literature, pubmed]
---

# 문헌 읽기

1. esearch 로 관련도 상위 문헌 PMID 를 받고, efetch 로 초록과 출판 유형을 받습니다.
2. 연구 설계는 PubMed 출판 유형(Meta-Analysis, Randomized Controlled Trial, Case Reports, Review)이 있으면 규칙으로 정합니다.
3. 출판 유형이 없을 때의 설계, 연관 보고 여부(noul), 결론 강도(score 0~4), 중단 후 호전·재투여 재발 기술(noul)은 판단 모델이 한 번 호출로 판단합니다.
4. 초록 원문은 판단에만 쓰고 결과에는 PMID·연도·제목·판정만 남깁니다.

## 검증
출판 유형을 가린 채 설계를 고르게 했을 때 MEDLINE 색인과의 일치율은 92.0% 였습니다(598편, `pipeline/bench/literature_eval.py`).

## 쓰이는 곳
근거 등급의 문헌 축, 한국형 알고리즘 "알려진 정보" 항목의 증례보고(+2) 규칙, System-2 근거 카탈로그.
