# TOOLS.md · flygate CLI 사용 메모

실행 파일은 `/sandbox/flygate/agent/bin/flygate` 입니다(PATH 에 올라 있으면 `flygate`). 모든 하위 명령은 JSON 한 덩어리를 stdout 에 쓰고,
결과마다 `evidence_ids` 를 붙입니다. 요약을 쓸 때는 이 ID 를 그대로 옮깁니다.

공통 사항

- 나가는 연결은 OpenShell 정책이 허용한 곳만 됩니다: api.fda.gov, eutils.ncbi.nlm.nih.gov, api.typesafe.ai, integrate.api.nvidia.com, health.api.nvidia.com.
  그 밖의 주소로 가는 요청은 샌드박스가 막습니다. 막혔다고 우회를 시도하지 않고 사람에게 알립니다.
- API 키는 환경에 자리표시자로만 보입니다. 실제 키는 OpenShell provider 가 프록시에서 넣습니다. 키를 출력하거나 파일에 쓰지 않습니다.
- `FV_CACHE_DIR` 가 있으면 openFDA·PubMed 응답을 그 캐시에서 먼저 찾습니다(오프라인 재현용).
- 판단 모델이나 가드를 부르지 못하면 결과는 '통과'가 아니라 사람 확인으로 돌아갑니다(fail closed).

## triage

`flygate triage <case.json>` 또는 `flygate triage --demo N`

- 옵션: `--regime KR`(국내 15일 규칙), `--no-outcome`(결과 코드를 가린 평가), `--no-ground`(라벨 근거 생략).
- 출력: `decision.action`(expedite · signal_review · monitor · close · human_review), `decision.tier`(reflex · system2 · human),
  `judgments`(판단 모델의 타입 있는 확률 7개), `latency_ms`, `evidence_ids`(faers:case:…, label:…).
- 한 번의 판단 호출에 질문 7개가 함께 들어갑니다. 확률이 애매하면 결정 정책이 위로 올립니다.

## grade

`flygate grade <DRUG> "<MedDRA PT>"`

- 라벨 상태 × SDR 두 축으로 PV 분류 후보(`pv_class_name`)와 근거 등급(`grade`)을 냅니다. 문헌은 PubMed 상위 논문을 읽어 설계별로 셉니다.
- `flags` 에 DME(EMA 지정 의학적 사건), 보고 편향(변호사·소비자 보고 비중), 금기 절 표시가 나옵니다.
- `--no-judge` 는 문헌 설계 분류를 PubMed 출판 유형 규칙만으로 합니다.
- 등급은 집단 수준 맥락입니다. `basis` 없이 인용하지 않습니다(R13).

## signals

`flygate signals <DRUG> [--pt 부분문자열] [--limit N]`

- 웨어하우스 추출본의 2×2 통계(a, PRR, ROR025, IC025)와 SDR 단계(strong · weak · none)입니다. 모델이 개입하지 않습니다.

## kr-causality

`flygate kr-causality <report.txt> [--form narrative|professional|consumer] [--route]`

- NVIDIA Nemotron 이 식약처 서식(가~바 섹션)으로 구조화하고, 한국형 인과성 평가 ver 2.0 을 항목별로 채점합니다.
- '약물에 대해 알려진 정보' 항목은 모델이 아니라 라벨·문헌 조회 결과로 정합니다.
- `--route` 는 국내 규정으로 라우팅합니다. `report15: true` 는 15일 신속보고 '후보'라는 뜻입니다. 제출은 사람이 합니다.

## critic

`flygate critic <claims.json> [--offline]`

- 입력: `{"claims":[{"id","text","evidence":[…]}], "state":"…", "bundle":{"ids":[…]}}` 또는 `{"claims":[…], "case":{…}}`.
- 3단 검사: T1 근거 ID 규칙, T2 숫자 대조, T3 과잉해석 판단(R1–R13) + 주장별 NVIDIA Safety Guard.
- `verdict`: `pass`(요약에 써도 됨) · `returned`(사유대로 고쳐 다시) · `human_check`(사람에게 넘김). `--offline` 은 T1·T2 만 돌립니다. 문제가 없어도 `pass` 가 아니라 `human_check` 입니다.

## discover

`flygate discover parp1|xa|cox2`

- FlyDiscovery 실측을 읽습니다: MSA-Search → OpenFold3 구조, DiffDock 포즈, Boltz-2 친화도 예측, ChEMBL 실측, PARP1 친화도 벤치마크.
- `critic.measured` 는 시판 전 주장에 대한 크리틱 판정 기록입니다. `limits` 는 각 측정이 말하는 범위입니다.
- `handoff_to_vigilance` 가 같은 약물을 STEP 2 로 넘기는 다음 명령을 알려 줍니다.

## watch

`flygate watch --memory-dir memory --workspace . [--online] [--triage N] [--watchlist list.json]`

- 하트비트와 cron 이 부르는 정기 점검입니다. 최신 FAERS 분기를 확인하고, 감시 목록의 SDR 을 다시 계산하고, 새 사례를 N 건 분류하고,
  `memory/YYYY-MM-DD.md` 에 메모를 덧붙입니다.
- `review_queue` 가 사람 검토 대기열입니다. `submitted` 는 늘 빈 목록입니다(아무것도 보내지 않습니다).
- `--workspace` 를 주면 페르소나 파일을 배포본과 SHA-256 으로 대조합니다. 다르면 `persona_changed` 항목이 대기열에 올라갑니다.
