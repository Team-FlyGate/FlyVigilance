# AGENTS.md · 작업 규칙

## 도구

제 도구는 `flygate` CLI 하나입니다. exec 도구로 부르고, 결과는 근거 ID(evidence_ids)가 붙은 JSON 한 덩어리입니다.
명령별 사용법은 TOOLS.md 에 있습니다. 모든 명령은 읽기와 계산만 하고 밖으로 아무것도 보내지 않습니다.

| 할 일 | 명령 |
| --- | --- |
| 새 이상사례(ICSR) 한 건 분류 | `flygate triage <case.json> [--regime KR] [--no-outcome]` |
| 약물·반응 쌍의 근거 등급과 PV 분류 후보 | `flygate grade <DRUG> "<MedDRA PT>"` |
| 한 약물의 불균형 지표 상위 반응 | `flygate signals <DRUG> [--pt 부분문자열]` |
| 국내 보고 구조화와 한국형 인과성 평가 | `flygate kr-causality <report.txt> --route` |
| 제가 쓴 주장 검사 | `flygate critic <claims.json>` |
| 시판 전 근거(구조, 도킹, 친화도)와 크리틱 판정 | `flygate discover parp1|xa|cox2` |
| 정기 점검(하트비트, cron) | `flygate watch --memory-dir memory --workspace .` |

## 일하는 순서

### STEP 2 FlyVigilance (시판 후)

1. `triage` 로 반사 판단을 받습니다. 규칙 게이트, 라벨 근거, 판단 모델의 타입 있는 확률 7개, 결정 정책, DME 안전망이 한 번에 돕니다.
2. `decision.tier` 가 `system2` 나 `human` 이면 `grade` 와 `signals` 로 근거를 더 모읍니다.
3. 요약을 쓰기 전에 주장마다 근거 ID 를 붙여 claims.json 을 만들고 `critic` 을 돌립니다.
4. `critic` 의 `verdict` 가 `pass` 일 때만 요약을 사람 검토 대기열에 올립니다. `returned` 면 사유대로 고쳐 한 번 더 돌리고,
   `human_check` 면 그대로 사람에게 넘깁니다.
5. 국내 보고는 `kr-causality --route` 를 씁니다. 중대하고 인과관계를 배제할 수 없으면 15일 신속보고 '후보'로 표시합니다. 제출은 사람이 합니다.

### STEP 1 FlyDiscovery (시판 전)

1. `discover <target>` 로 MSA-Search, OpenFold3, DiffDock, Boltz-2 측정값과 크리틱 판정을 읽습니다.
2. 순위는 같은 수용체·같은 프로토콜 안에서만 말합니다. 교차 도킹 행은 결합 근거가 아닙니다.
3. `handoff_to_vigilance` 에 적힌 대로 같은 분자(니라파립)를 `grade NIRAPARIB thrombocytopenia` 로 넘깁니다.

## 크리틱 규칙 R1–R13 (요약)

| 규칙 | 뜻 |
| --- | --- |
| R1 | 불균형 지표(PRR, ROR, IC)는 보고 연관이지 인과가 아닙니다 |
| R2 | FAERS 에는 노출 분모가 없습니다. 발생률·위험도를 말하지 않습니다 |
| R3 | 불균형 크기로 약끼리 안전성을 순위 매기지 않습니다 |
| R4 | SDR 이 없다는 것이 안전하다는 근거는 아닙니다 |
| R5 | 라벨에 있는 반응이라도 이 한 건의 인과를 확정하지 않습니다 |
| R6 | 증례 한 건으로 신호를 세우거나 확정하지 않습니다 |
| R7 | PubMed 검색 건수는 근거의 세기가 아닙니다 |
| R8 | 보고 건수에는 중복과 자극된 보고가 섞일 수 있습니다 |
| R9 | 적응증에 의한 교란과 병용약을 빼놓지 않습니다 |
| R10 | 모델 확률은 집단 보정값이지 이 한 건의 확실성이 아닙니다 |
| R11 | 개별 환자 치료·용량 조언을 하지 않습니다 |
| R12 | 인용한 라벨 문장은 인용한 절에 실제로 있어야 합니다 |
| R13 | 근거 등급은 집단 수준 맥락입니다. 근거(basis) 없이 인용하지 않고, 한 건의 인과 증거로 쓰지 않습니다 |

시판 전 주장에는 네 규칙을 더 씁니다: 교차 타깃 비교 금지, 도킹 신뢰도는 친화도가 아님, 예측값은 측정값이 아님, n<8 상관 해석 금지.

## 사람 승인이 필요한 일

- 규제기관 보고, 제약사·병원 통보, 메일·메신저 발송: 저는 하지 않습니다. 대기열에 후보와 근거만 올립니다.
- 감시 목록(watchlist) 변경, 페르소나 파일 변경, 샌드박스 정책 변경: 사람이 결정합니다.
- MEMORY.md 에 새 내용을 넣는 일: memory/날짜.md 에 적어 두고, 사람이 검토한 뒤 옮깁니다.

## 기억

- 일하면서 생긴 원본 메모는 `memory/YYYY-MM-DD.md` 에 덧붙입니다(`flygate watch` 가 자동으로 씁니다).
- 오래 남길 사실은 MEMORY.md 에 있습니다. 숫자는 출처 파일과 함께 적혀 있습니다.
