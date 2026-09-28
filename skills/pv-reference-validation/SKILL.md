---
name: pv-reference-validation
description: Use to measure how signal-detection methods perform on public reference sets (OMOP, EU-ADR, Harpaz time-indexed incl. a pre-2013 prospective window from legacy AERS) — ROC/AUC with bootstrap CIs for PRR/ROR/chi2/IC025, raw Jev (named and blinded) and the FlyVigilance case-series judgment.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: control plane
  tags: [pharmacovigilance, validation, reference-set, roc]
---

# 참조 세트 검증

```bash
.venv/bin/python pipeline/refsets/build_refsets.py   # 세트 통합, 반응 정의, 약물명 매칭
./scripts/download_aers_legacy.sh && .venv/bin/python pipeline/refsets/legacy_aers.py   # 2013년 이전 보고
.venv/bin/python pipeline/refsets/evaluate.py         # ROC, AUC, 부트스트랩, Jev 호출(캐시)
```

- 반응 정의는 Harpaz 정의를 먼저 쓰고, 없는 결과는 공개 정규식으로 PT 를 묶습니다(목록 공개).
- 이름 공개 조건은 모델 기억이 새므로 참고용입니다. 공정한 비교는 이름을 가린 조건입니다.
- 이 측정은 "공인된 조합을 가려내는가"를 재며 개별 사례의 인과를 재지 않습니다.

## 결과 요약 (2026-09-28)
- 모델 재순위가 최고 통계 지표를 유의하게 넘은 조건은 없었습니다 → 신호 계산은 SQL 에 둡니다.
- 2013년 이전 보고만으로 3중 기준은 그해 라벨 변경 57건 중 21건을 신호로 세웠고 음성 70건 중 오경보는 1건이었습니다(PPV 95%).
