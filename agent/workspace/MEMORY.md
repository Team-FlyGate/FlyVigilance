# MEMORY.md · 오래 남길 사실

사람이 검토한 내용만 여기에 둡니다. 새 내용은 memory/YYYY-MM-DD.md 에 먼저 적습니다. 숫자마다 출처 파일을 붙였습니다.

## 데이터 기준

- FAERS 웨어하우스와 신호 추출본의 기준 분기는 2026Q2 입니다(`api/_data/signals.json.gz` 의 asof, `data/derived/faers.duckdb`).
- 벤치마크와 검증 수치는 파일에서 읽습니다: `web/public/data/bench.json`(ablation, ablation_blind), `web/public/data/validation.json`(refsets).

## 데모 약물의 흐름: 니라파립 (PARP1 억제제)

- STEP 1 FlyDiscovery (`fly_discovery/measurements/measurements.json`, `fly_discovery/README.md`)
  - MSA-Search: PARP1 상동 서열 101개, 63.6초. OpenFold3: pLDDT 95.95, 4R6E 결정 구조 대비 CA RMSD 1.0 Å.
  - DiffDock 재도킹 니라파립@PARP1 0.71 Å. Boltz-2 PARP1 친화도 벤치마크 39종 Spearman 0.767.
  - 크리틱은 'PARP1 -10.178 vs Factor Xa -7.967 이므로 PARP1 선택적'을 반려합니다. 다른 단백질의 도킹 점수는 비교 대상이 아닙니다.
- STEP 2 FlyVigilance (`flygate grade NIRAPARIB thrombocytopenia`)
  - 근거 ID `faers:2x2:NIRAPARIB:thrombocytopenia@2026Q2`: a=1061, PRR 9.86, 3중 기준 SDR, 라벨 경고·주의사항 기재 → PV 분류 '규명된 위해성 후보'.

## 전문가(약사) 검토로 정한 규칙

- 불균형 보고 신호는 SDR 이라고 부릅니다(신호로 확정하지 않습니다).
- PV 분류는 라벨 상태 × SDR 두 축으로 정합니다. 금기 절은 이상반응 기재로 세지 않습니다.
- EMA DME 62개 PT 는 모델 판단과 상관없이 사람 확인으로 올립니다(안전망).
- 보고자 구성에 편향 표시를 붙입니다. 예: 이소트레티노인-염증성 장질환은 보고의 95%가 변호사 보고입니다.
- 국내 15일 신속보고 후보는 '중대함'과 '인과관계를 배제할 수 없음'이 함께 있을 때입니다.
- 평가는 결과 코드(사망, 입원 등)를 가린 상태로 합니다.

## 검증에서 확인된 사실

- 반사 트리아지는 타입 있는 질문 7개를 한 번의 판단 호출로 받습니다: p50 296 ms. 같은 질문을 자기회귀로 생성하면 2,286 ms 입니다.
- 문헌 설계 분류는 MEDLINE 색인과 92.0% 일치합니다(598편).
- 크리틱 주입 시험: 틀린 주장 31/31 적발, 정상 대조 6/6 통과.
- Harpaz 전향 검증(2013년 이전 보고만 사용): 3중 기준 SDR 이 2013년 라벨 변경 57건 중 21건을 먼저 표시했고, 오경보는 70건 중 1건입니다(PPV 0.95).

## 운영 메모

- 제출과 발송은 사람이 합니다. 대기열의 `submitted` 는 늘 비어 있어야 합니다.
- 페르소나 파일의 배포본 해시는 `flygate watch --workspace` 가 매번 대조합니다.
