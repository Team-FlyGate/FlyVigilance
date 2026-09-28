<p align="center">
  <a href="https://project-flygate.vercel.app"><img src="docs/images/flygate-hero_v2.0.0.png" width="100%" alt="FlyGate — 분자에서 환자까지, 추론보다 근거가 먼저. Evidence before inference."></a>
</p>

<p align="center"><strong>분자에서 환자까지, 추론보다 근거가 먼저. FlyGate.</strong></p>
<p align="center">NVIDIA Korea Agentic AI Hackathon 2026 · Team FlyGate</p>
<p align="center">
  <a href="https://project-flygate.vercel.app"><strong>라이브 대시보드 ↗</strong></a> &nbsp; · &nbsp;
  <a href="https://project-flygate.vercel.app/showreel/FlyGate_showreel_v4.2.0.html">쇼릴 ↗</a> &nbsp; · &nbsp;
  <a href="docs/EVALUATION.md">평가 보고서</a> &nbsp; · &nbsp;
  <a href="https://project-flygate.vercel.app/#/glossary">용어 풀이 ↗</a> &nbsp; · &nbsp;
  <a href="#06--meet-the-team">Team</a> &nbsp; · &nbsp;
  <a href="#07--build--run">Quickstart</a>
</p>

---

## 01 / Two perspectives. One evidence trail.

**FlyGate = FlyDiscovery + FlyVigilance.** 시판 전에는 후보 물질의 표적 결합을, 시판 후에는 허가 약물의 이상사례(약을 쓴 뒤 생긴 좋지 않은 일)를 살핍니다.

데모에서는 이미 허가된 PARP1(DNA 손상을 고치는 단백질) 억제제 니라파립으로 시판 전 단계를 되짚어 재현하고, 같은 약의 실제 시판 후 보고로 이어서 보여 드립니다. 두 단계 모두 다른 표적과 약물에 그대로 씁니다.

| | |
| --- | --- |
| 라이브 대시보드 | https://project-flygate.vercel.app |
| 쇼릴 v4.2 (전체판, 4분 4초 · 21장면 · FlyGate Agent CLI 강조) | [웹](https://project-flygate.vercel.app/showreel/FlyGate_showreel_v4.2.0.html) · [MP4](https://github.com/Team-FlyGate/Project-FlyGate/releases/download/v4.2/FlyGate_showreel_v4.2.0.mp4) · [내레이션 대본](docs/SHOWREEL_SCRIPT_v4.2.0.md) |
| 쇼릴 v3 (이전 판, 2분 9초) | [웹](https://project-flygate.vercel.app/showreel/FlyGate_showreel_v3.0.0.html) · [MP4](https://github.com/Team-FlyGate/Project-FlyGate/releases/download/v3.0/FlyGate_showreel_v3.0.0.mp4) |
| 티저 (15초) | [웹](https://project-flygate.vercel.app/showreel/FlyGate_teaser_15s_v1.1.0.html) · [MP4 가로 · 세로](https://github.com/Team-FlyGate/Project-FlyGate/releases/tag/teaser-v1.1) |
| 에이전트 구성 (NemoClaw · OpenShell · OpenClaw: NVIDIA의 에이전트 배포 구성 · 정책 샌드박스 · 에이전트 실행 틀) | [docs/AGENT.md](docs/AGENT.md) · [agent/](agent/) |
| 평가 보고서 | [docs/EVALUATION.md](docs/EVALUATION.md) |
| 약사 검토 반영 내역 | [docs/PHARMACIST_REVIEW.md](docs/PHARMACIST_REVIEW.md) |

Project-FlyGate는 **NVIDIA 스킬 위에 구성한 에이전트 워크플로**입니다. build.nvidia.com NIM(NVIDIA 추론 마이크로서비스: AI 모델을 바로 호출해 쓸 수 있게 포장한 서비스), NVIDIA Agent Skills(에이전트 능력 패키지 규격), NemoClaw · OpenShell · OpenClaw를 씁니다.
글을 써야 하는 일은 NVIDIA Nemotron(NVIDIA 언어 모델 계열)이 맡고, 확률만 필요한 판단에는 **비자기회귀(non-autoregressive) 판단 모델을 병용**합니다. 비자기회귀 판단 모델은 글을 한 글자씩 생성하지 않고 정해진 질문에 대한 확률을 한 번에 돌려주는 모델입니다. 이 조합으로 높은 속도와 통계적으로 유의한 개선을 얻었습니다.

<p align="center"><img src="docs/images/flygate-modules_v2.0.0.png" width="100%" alt="FlyDiscovery: 구조·결합·근거. FlyVigilance: 보고·신호·검토."></p>
<p align="center"><sub>히어로와 모듈 아트는 AI 생성 개념 이미지이며, 실제 분자 구조나 임상 데이터를 나타내지 않습니다.</sub></p>

| 단계 | 이름 | 하는 일 |
| --- | --- | --- |
| STEP 1 · 시판 전 | **FlyDiscovery** | 후보 물질을 NVIDIA BioNeMo NIM(구조생물학·신약 탐색 모델 모음)으로 표적(약이 붙어 작용하는 단백질) 구조 예측 → 도킹(약물 분자가 결합 자리에 붙는 모양을 계산으로 맞춰 보는 일) → 친화도(약물이 표적에 붙는 세기)까지 평가하고, 근거를 넘는 주장을 반려합니다(데모: 니라파립 · PARP1, 대조 약물 2종, 친화도 벤치마크 39종) |
| STEP 2 · 시판 후 | **FlyVigilance** | FAERS(미국 식품의약국 FDA의 이상사례 보고 시스템) 이상사례(약물 2,563종의 SDR 표. SDR은 불균형 보고 신호로, 특정 약·이상반응 조합이 다른 약보다 유난히 많이 보고되는 통계 신호입니다)를 한 건씩 분류(트리아지: 급한 정도를 가려 처리 경로를 정하는 첫 단계)하고, SDR·라벨(허가사항: 규제기관이 허가한 약의 공식 설명서)·문헌으로 PV(약물감시) 분류(라벨 상태 × SDR로 매긴 검토 우선순위)를 매기고, 사람 검토 대기열과 신속보고(중요한 사례를 정해진 기한 안에 규제기관에 보고하는 의무) 기한을 만듭니다 |

## 02 / Measured, not assumed.

평가 질문, 측정값, 데이터 범위를 함께 제시합니다. 상세 조건과 재현 절차는 [평가 보고서](docs/EVALUATION.md)를 참고하세요.

| 질문 | 결과 | 데이터 |
| --- | --- | --- |
| 중대 사례를 놓치지 않으면서 사람 일을 줄이는가 | 결과 코드(보고에 붙은 사망·입원 등 결과 표시)를 가린 채로 중대 사례(사망·생명 위협·입원·장애처럼 결과가 심각한 사례) **247/250**이 검토에 닿았습니다(모델 단독 질문 하나 234/250, McNemar(짝지은 비교 검정) p(우연히 이만한 차이가 나올 확률) = 0.0044). 사람 우선 업무량은 **138건**으로 질문 하나(302건)의 절반 아래입니다(p = 3.6×10⁻⁴⁸) | 실제 FAERS 440건 |
| 빠른가 | 규제 용어로 나눈 7문항 판단이 한 번 호출에 **296 ms**입니다. 같은 문항을 자기회귀 생성(앞 글자를 보고 한 글자씩 이어 쓰는 방식)으로 풀면 2,286 ms입니다 | 같은 사례 27건 |
| 공인된 약물–이상반응 연관을 알아보는가 | FlyVigilance 지식 기반 판별(약·반응 이름을 보고 공인된 연관인지 판단) AUC(판별 정확도: 0.5는 무작위, 1은 완벽) **0.960**(OMOP), **0.983**(EU-ADR)으로 최고 통계 지표(0.815, 0.919)보다 유의하게 높습니다 | 공개 참조 세트(OMOP · EU-ADR: 정답을 미리 정해 둔 평가용 목록) 480쌍 |
| 라벨에 적힌 반응을 불균형 지표가 잡는가 (파일럿) | 라벨 기재 참조 세트 64,796쌍에서 Evans 규칙(고전적 불균형 판정 기준) 민감도(실제 양성 중 잡아낸 비율) **0.30**, 하한 지표(ROR₀₂₅ 보고 오즈비 하한 · IC₀₂₅ 정보 성분 하한) AUC **0.62~0.63**입니다. 라벨 기재 쌍의 절반 넘게에 SDR이 서지 않습니다([평가 1-6](docs/EVALUATION.md#1-6-sider-라벨-기재-참조-세트-파일럿-하네스-저장소)) | SIDER 4.1(약 라벨 부작용 공개 데이터베이스) 약 31종 · 팀 선행 저장소 |
| 기전 근거가 라벨 기재를 가르는가 (파일럿) | Open Targets(표적-질환 연관 공개 데이터베이스) 표적-질환 연관 점수 AUC **0.559**(귀무 0.532: 정답을 무작위로 섞었을 때의 기준값)로, 같은 행의 불균형 지표(0.570~0.679)보다 낮습니다. 평가 행의 68.4%가 0점입니다([평가 7](docs/EVALUATION.md#7-기전-타당성-축-파일럿-open-targets)) | Open Targets 26.09 · 17,472쌍 |
| 라벨이 바뀌기 전에 알 수 있었는가 | 2013년 이전 보고만으로 그해 라벨 변경 57건 중 **21건**에 SDR이 섰고, 오경보는 음성 70건 중 **1건**입니다(PPV(양성 예측도: 양성 판정 중 실제 양성의 비율) **0.95**) | 구형 AERS(2012년까지 쓰던 FAERS 이전 시스템) 2004–2012 |
| 과잉해석(근거가 허락하는 범위를 넘는 결론)을 막는가 | 일부러 넣은 틀린 주장 **31/31**을 반려했고, 정상 주장 6/6은 통과했습니다. 공식 스킬 `nemotron-policy-generator`로 만든 PV 정책을 Nemotron 3.5 Content Safety(NVIDIA 안전 판정 모델)에 넣자 가드 층만으로 PRR(비례 보고 비) 인과 단정 **7/7**, 없는 발생률 **8/8**을 잡습니다(기본 가드 0/7, 0/8) | 실제 중대 사례 8건 · 평가 문장 50건 |
| 문헌을 제대로 읽는가 | 연구 설계 판정이 MEDLINE(의학 논문 색인 데이터베이스) 색인과 **92.0%** 일치합니다. NVIDIA Nemotron 리랭커(검색 결과를 관련도 순으로 다시 줄 세우는 모델)로 후보를 재정렬하자 읽는 6편 중 관련 문헌 비율이 **0.65 → 0.85**로 올랐습니다(21쌍 개선, 0쌍 악화) | PubMed(의학 논문 검색 서비스) 598편 · 30쌍 575편 |
| 시판 전 예측이 믿을 만한가 | OpenFold3(단백질–약물 복합체 구조 예측 모델) PARP1 구조 CA RMSD(실험으로 푼 결정 구조와의 거리, 작을수록 정확하며 1 Å은 0.1 나노미터) **1.0 Å**, DiffDock(약물 결합 자세 예측 모델) 재도킹(결정 구조에서 원래 약물을 빼고 다시 도킹해 제자리를 찾는지 보는 대조 실험) **0.71 Å**, Boltz-2(결합 세기 예측 모델) 친화도 Spearman(순위 상관, 1이면 순위가 완전히 같음) **0.767** | 4R6E(PARP1–니라파립 결정 구조의 PDB 번호), ChEMBL(화합물 실험 활성값 공개 데이터베이스) 39종 |

### 심사 기준별 요약

| 심사 기준 | Project-FlyGate의 근거 |
| --- | --- |
| **NVIDIA Agent 기술 활용 심도** | Nemotron 3 Super · Ultra · Lightning(System-2 평가, 서식 구조화. System-2는 필요한 사례만 올려 근거를 모아 천천히 따져 보는 숙고 단계입니다), Safety Guard 8B v3(NVIDIA 안전 판정 모델) + Nemotron 3.5 Content Safety(PV 정책), Nemotron 리랭커, BioNeMo NIM 4종. 공식 NVIDIA Agent Skills 4개를 실제 파이프라인에 적용했습니다. OpenClaw 에이전트를 OpenShell 샌드박스(외부와 격리된 실행 공간)에 올려 스모크(기본 동작 점검) 20/20, 하트비트(정기 자가 점검)와 cron(예약 실행)까지 확인했습니다(NemoClaw 과정 01a–04c 대응표: [docs/AGENT.md](docs/AGENT.md)) |
| **실용성 · 산업 가치 · 혁신성** | 분기 42만 건 FAERS 보고를 사람 우선 · System-2 · 추가정보 요청 · 모니터링으로 나눕니다. 결과 코드를 가린 채로 중대 사례 247/250이 검토에 닿고, 사람 업무량은 302건에서 138건으로 줄었습니다. 미국·한국 15일 규정 모드와 한국형 인과성(약이 반응을 일으켰을 가능성) 평가를 갖췄고, 현업 약사 검토 15개 항목을 반영했습니다 |
| **완성도** | 라이브 대시보드와 API(프로그램끼리 요청과 응답을 주고받는 창구), 실제 FAERS 55개 분기 웨어하우스(분석용으로 정리한 데이터베이스), 공개 참조 세트 3종 검증, 오프라인 테스트 147개, 재현 스크립트, 쇼릴 v3를 갖췄습니다 |
| **커스터마이징 · 독창성** | 판단은 비자기회귀 모델(7문항 296 ms), 글쓰기는 Nemotron으로 나눴습니다. 과잉해석 13규칙 크리틱(근거를 넘는 주장을 반려하는 검사 단계)과 약물감시 전용 가드 정책을 두고, 시판 전 결합 예측과 시판 후 감시를 한 에이전트로 이었습니다 |

## 03 / Why FlyGate

약물 안전성 검토자는 흩어진 근거를 모아 판단을 씁니다. 도킹 점수, 참조 친화도, 허가 라벨, 이상사례 보고, 문헌입니다.
- **양**: FAERS에는 한 분기에 42만 건이 넘는 보고가 들어옵니다(2026Q2 422,459건).
- **배분**: 질문 하나로 선별하면 중대 사례를 놓치지 않으려고 사람에게 과하게 넘기거나, 중대 사례가 아무도 보지 않는 자동 큐에 남습니다.
- **과잉해석**: 숫자와 출처가 다 맞는데 결론만 근거를 넘는 주장이 있습니다. 서로 다른 단백질의 도킹 점수로 선택성(원하는 표적에만 붙는 정도)을 말하거나, 불균형 지표(PRR)를 인과로 읽는 식입니다. 형식 검사로는 걸러지지 않습니다.

### 두 단계, 하나의 에이전트

단계는 둘, 에이전트는 하나입니다. **NVIDIA NemoClaw** 기반 배포 구성에서 **OpenClaw**가 에이전트로 실행되고, **NVIDIA OpenShell**이 파일·네트워크 접근 정책과 샌드박스 격리를 담당합니다. 에이전트는 `flygate` CLI(명령줄 인터페이스)를 통해 두 모듈을 실행합니다.

<a href="docs/images/flygate-architecture_v2.1.0.png"><img src="docs/images/flygate-architecture_v2.1.0.png" width="100%" alt="NVIDIA NemoClaw 기반 구성에서 OpenShell 안의 OpenClaw 에이전트가 flygate CLI를 통해 FlyDiscovery와 FlyVigilance를 실행합니다. 근거 ID, 수치, 해석·안전성 검증을 거쳐 사람이 검토합니다."></a>

<sub>핵심 처리 경로를 요약한 구조도입니다. 모든 사례에 모델을 호출하지 않으며, 규칙과 결정 정책이 사람 우선·System-2·추가정보 요청·모니터링으로 경로를 나눕니다.</sub>

- **FlyDiscovery:** PARP1 서열 → MSA-Search(상동 서열 정렬: 진화적으로 닮은 단백질 서열을 모아 줄 맞추는 단계) → OpenFold3 구조 → DiffDock 포즈(약물 분자의 위치와 자세) → Boltz-2 친화도 → 전통 기준 채점 → 크리틱 3단.
- **FlyVigilance:** FAERS 사례 → ICH(의약품 국제조화위원회) 최소 4요소(보고자 · 환자 · 의심 약 · 이상사례) 확인 → FDA 라벨 원문 조회 → 7문항 판단 → 결정 정책(확률을 행동과 기한으로 바꾸는 규칙표)과 EMA(유럽의약품청) DME(EMA가 지정한 특별 주의 이상사례) 안전망. 필요한 사례만 Nemotron 평가와 크리틱·Safety Guard로 보냅니다.
- **공통 사례:** 니라파립의 시판 전 예측을 시판 후 근거와 연결합니다. 보고서의 판정과 제출은 사람이 담당합니다.

| 부품 | 하는 일 | 모델 |
| --- | --- | --- |
| 규칙 게이트 | ICH 최소 4요소, 결과 코드, 약물 역할처럼 규칙으로 되는 일은 모델에 묻지 않습니다 | 없음 |
| 라벨 원문 조회 | 반응이 FDA 허가 라벨 어느 절에 있는지(박스 경고: 라벨 맨 위의 가장 강한 경고 · 경고 · 임상시험 · 시판 후)를 원문으로 정합니다. 금기(쓰면 안 되는 조건)·적응증(약을 쓰도록 허가된 질환) 문맥은 기재로 세지 않습니다 | 없음 |
| 반사 판단 | 중대성 · 예측성(라벨에 이미 적힌 반응인지 여부) · 인과 가능성 등 7문항을 한 번에 확률로 받습니다 | 비자기회귀 판단 모델 |
| 결정 정책 | 확률을 행동과 기한으로 바꿉니다. 미국(중대 + 예상하지 못함)과 한국(중대한 약물이상반응) 15일 규정 모드를 둡니다 | 없음 |
| SDR 통계 | PRR · ROR(보고 오즈비) · IC₀₂₅와 3중 기준(Evans 기준 · ROR₀₂₅ > 1 · IC₀₂₅ > 0을 모두 넘는 경우)을 SQL(데이터베이스 질의 언어)로 계산합니다. 모델은 숫자를 바꾸지 못합니다 | 없음 |
| PV 분류 | 라벨 상태 × SDR로 검토 우선순위를 매기고, 박스 경고 · DME · 보고 편향(소송·언론 등으로 특정 보고가 몰려 통계가 부풀려지는 현상) 표시를 붙입니다 | 없음 |
| 지식 기반 판별 | 약·반응 이름으로 공인된 연관인지 확률을 줍니다(참고 축) | 비자기회귀 판단 모델 |
| 문헌 읽기 | PubMed 초록이 그 반응을 실제로 다루는지 먼저 묻고, 설계별 항목을 읽습니다 | 비자기회귀 판단 모델 |
| System-2 평가 | 승격된 사례만 근거 ID(주장이 기댄 자료의 고유 식별자)를 붙여 평가 메모를 씁니다 | NVIDIA Nemotron 3 Super |
| 크리틱 3단 | ① 근거 ID 실재 ② 숫자 오라클(문장 속 숫자를 원래 수치와 대조하는 검사) ③ 과잉해석 13규칙 + 안전 가드 | 판단 모델, NVIDIA Nemotron Safety Guard |
| 사람 승인 | 보고서를 밖으로 보내는 경로는 없습니다. 판정과 제출은 사람이 합니다 | – |

상세 구조는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), 에이전트 배치는 [docs/AGENT.md](docs/AGENT.md)에 있습니다.

## 04 / Built with NVIDIA

| 기술 | 어디에 | 비고 |
| --- | --- | --- |
| **NVIDIA Nemotron 3 Super 120B** (`nvidia/nemotron-3-super-120b-a12b`) | System-2 평가 메모, 국내 보고 서식 구조화, FlyDiscovery 크리틱 판정 | Ultra 550B → 3.5 Lightning 30B 폴백(주 모델이 응답하지 않을 때의 대체 경로) 사슬, NIM JSON(구조화된 텍스트 데이터 형식) 모드 |
| **NVIDIA Nemotron Safety Guard 8B v3** + **Nemotron 3.5 Content Safety (PV 정책)** | 메모의 주장마다 두 가드를 동시에 돌려 치료 조언, PRR 인과 단정, 자발 보고로 낸 발생률, 재식별 시도를 반려 | PV 정책은 공식 스킬 `nemotron-policy-generator`로 생성해 `custom_policy`로 전달, 평가 50건 정확도 0.58 → 0.84 |
| **NVIDIA Nemotron 리랭커** (`llama-nemotron-rerank-vl-1b-v2`) | 문헌 읽기 전 PubMed 후보 20편 재정렬 | 공식 스킬 `nemotron-retrieval-recipes` 기준, 추가 지연 중앙값 0.57초 |
| **NVIDIA BioNeMo NIM** | MSA-Search → OpenFold3 → DiffDock → Boltz-2 | 공식 스킬 `bionemo-msa-structure-prediction-pipeline` 규격 |
| **NVIDIA Agent Skills** ([NVIDIA/skills](https://github.com/NVIDIA/skills)) | 우리 역량 11개를 공식 규격의 [skills/*/SKILL.md](skills/)와 스킬 카드로 패키징하고, 공식 스킬 `bionemo-msa-structure-prediction-pipeline` · `nemotron-policy-generator` · `nemotron-retrieval-recipes` · `skill-card-generator`를 실제로 적용 | 목록: [skills/README.md](skills/README.md) |
| **NemoClaw · OpenShell · OpenClaw** | OpenClaw 작업 공간(SOUL · AGENTS · TOOLS · HEARTBEAT), deny-by-default(밖으로 나가는 연결을 기본으로 모두 막고 목록에 적은 곳만 여는 방식) 네트워크 정책, Landlock(리눅스의 파일 경로 접근 제한 기능) 파일 시스템, 비루트(관리자 권한 없는) 실행 | [agent/policy/flygate.yaml](agent/policy/flygate.yaml), 실제 OpenShell 샌드박스 스모크 **20/20** 통과 [agent/evidence/](agent/evidence/) |

비자기회귀 판단 모델로는 TypeSafe AI의 Jev를 FlyVigilance 안에서 씁니다.

### 전문가 검토 반영

현업 약사의 검토 의견 15개를 반영했습니다. 주요 항목은 다음과 같습니다([전체 내역](docs/PHARMACIST_REVIEW.md)).
- 통계 기준을 넘은 상태를 **SDR**(불균형 보고 신호)로 부르고, 한 글자 등급 대신 **PV 분류**(라벨 상태 × SDR)와 검토 우선순위를 앞에 둡니다.
- **EMA DME 62개 PT**(MedDRA PT: 이상반응 표준 용어)가 보고되면 점수와 관계없이 사람 검토로 보냅니다.
- **보고 편향 표시**: 이소트레티노인–염증성장질환은 보고의 94.9%가 변호사 보고라, 변호사 보고를 뺀 민감도 분석(조건을 바꿔도 결과가 유지되는지 보는 분석)을 함께 냅니다.
- 라벨의 **금기 절은 기재로 세지 않고**, 이상반응은 임상시험과 시판 후를 나눕니다.
- **국내 15일 규칙**은 중대한 약물이상반응(인과관계 배제 불가)을 기준으로 적용합니다.
- 주 측정은 **결과 코드를 가린 조건**으로 합니다.

## 05 / Inside the workbench

<table>
<tr><td width="50%"><strong>01 / FlyDiscovery</strong><br><sub>구조·결합·친화도와 주장 검증</sub></td><td width="50%"><strong>02 / FlyVigilance</strong><br><sub>이상사례·검토 경로와 안전성 근거</sub></td></tr>
<tr><td><a href="docs/images/flydiscovery-workbench_v2.0.0.png"><img src="docs/images/flydiscovery-workbench_v2.0.0.png" width="100%" alt="실제 FlyDiscovery 탐색 워크벤치"></a></td><td><a href="docs/images/flyvigilance-workbench_v2.0.0.png"><img src="docs/images/flyvigilance-workbench_v2.0.0.png" width="100%" alt="실제 FlyVigilance 관제 화면"></a></td></tr>
</table>

<sub>라이브 데모의 실제 화면입니다. 이미지를 클릭하면 원본 크기로 볼 수 있습니다.</sub>

| 화면 | 내용 |
| --- | --- |
| 개요 | 두 관문(STEP 1 시판 전 · STEP 2 시판 후)과 데모 약물 니라파립의 흐름 |
| 후보 탐색 | FlyDiscovery: 후보 비교, 결합 포즈 3D, 주장 검증, 친화도 벤치마크 |
| 관제 센터 · 사례 분류(트리아지) | 실제 FAERS 사례 440건의 분류 결과를 정답(결과 코드)과 나란히 재생하고, 한 건을 골라 반사 판단 → 경로 → Nemotron 숙고 → 크리틱까지 실제 API로 돌립니다 |
| 국내 보고 · 인과성 | 국내 서식 구조화(Nemotron)와 한국형 인과성 평가 알고리즘 ver 2.0 |
| 신호 연구실 · 신호 타임머신 | SDR 순위, PV 분류 카드, FDA 조치 8건의 분기별 재계산 |
| 검증 · 벤치마크 | 공개 참조 세트 ROC(민감도–오경보율 곡선), 결과 코드를 가린 비교 실험 |
| 에이전트 구성 | OpenShell 정책, OpenClaw 작업 공간, 스킬 |

MaleCNS 초파리 커넥텀(뇌 뉴런 연결 배선도, 뉴런 49,244개) 화면은 에이전트의 라우팅 위상을 시각화한 것입니다.

## 06 / Meet the team

면역학, 바이오 데이터, 의료영상 AI, 약학, 에이전트 개발의 관점을 하나의 검토 흐름으로 연결합니다.

<table>
<tr>
<td align="center" width="20%"><a href="https://github.com/kakyungkim"><img src="https://avatars.githubusercontent.com/u/84395053?v=4" width="88" alt="Ka-Kyung Kim"><br><strong>김가경</strong><br>Ka-Kyung Kim</a><br><sub>TEAM COORDINATION<br>PV EVIDENCE</sub></td>
<td align="center" width="20%"><a href="https://github.com/AwesomeZun"><img src="https://avatars.githubusercontent.com/u/55944204?v=4" width="88" alt="Seong-Jun Kang"><br><strong>강성준</strong><br>Seong-Jun Kang</a><br><sub>INTEGRATION<br>FLYVIGILANCE</sub></td>
<td align="center" width="20%"><a href="https://github.com/Geongyu"><img src="https://avatars.githubusercontent.com/u/37532168?v=4" width="88" alt="Geon-Gyu LEE"><br><strong>이건규</strong><br>Geon-Gyu LEE</a><br><sub>FLYDISCOVERY<br>AI & INTERFACE</sub></td>
<td align="center" width="20%"><a href="https://github.com/ybaeus"><img src="https://avatars.githubusercontent.com/u/47170687?v=4" width="88" alt="Yeji Bae"><br><strong>배예지</strong><br>Yeji Bae</a><br><sub>AGENT WORKFLOWS<br>PV EXTENSION</sub></td>
<td align="center" width="20%"><a href="https://github.com/YMYDGenie"><img src="https://avatars.githubusercontent.com/u/133306595?v=4" width="88" alt="Eunjin Jeon"><br><strong>전은진</strong><br>Eunjin Jeon</a><br><sub>PHARMACY<br>DOMAIN REVIEW</sub></td>
</tr>
</table>

| Member | Background | Contribution to FlyGate |
| :--- | :--- | :--- |
| **김가경** · [@kakyungkim](https://github.com/kakyungkim) | 바이오 데이터 분석 · 혈중 암세포 및 신약개발 바이오마커 분석 경험 | FlyVigilance 개발 · 팀 조율과 제출 기획 · 약물감시 근거 설계 · 보고서 양식 매핑과 근거 등급 규칙 |
| **강성준** <sup><a href="https://kangseongjun.com" title="강성준 개인 웹사이트">↗</a></sup> · [@AwesomeZun](https://github.com/AwesomeZun) | 단일세포·공간오믹스 · 신약 후보 평가 · 『AI 신약개발 실전가이드』 출간 | FlyVigilance, FlyDiscovery 개발 · 데이터·평가 파이프라인 · 두 모듈 통합과 시각화 · FDDD(초파리 커넥텀 시각화 템플릿) 개발 ([https://github.com/AwesomeZun/FDDD](https://github.com/AwesomeZun/FDDD)) |
| **이건규** · [@Geongyu](https://github.com/Geongyu) | AI researcher · 병리·영상의학 및 오믹스를 결합한 예후·약물 반응 예측 | FlyDiscovery 개발 · 탐색 워크벤치와 사용자 인터페이스 개선 |
| **배예지** · [@ybaeus](https://github.com/ybaeus) | 병원 데이터 사이언티스트 · 멀티오믹스·공간·이미지 데이터 | FlyVigilance 개발 · Jev 기반 약물감시 확장 · 문헌 검토 흐름 설계 · 약사 피드백 반영 |
| **전은진** · [@YMYDGenie](https://github.com/YMYDGenie) | 약사 · 약사를 위한 AI 제품 개발 | FlyVigilance 개발 · 약학 관점의 요구사항 검토 · 이상사례·국내 보고 사례 조사 · 워크플로 자문 |

## 07 / Build & run

### flygate CLI

에이전트가 쓰는 도구와 사람이 쓰는 명령이 같습니다. 모든 명령은 근거 ID(`evidence_ids`)가 붙은 JSON을 출력합니다.

```bash
git clone https://github.com/Team-FlyGate/Project-FlyGate && cd Project-FlyGate
./scripts/install_flygate.sh              # .venv 생성, 의존성 설치, ~/.local/bin/flygate 연결
# 키: 저장소 루트 .env 에 TYPESAFE_API_KEY, NVIDIA_API_KEY (없으면 판단이 필요한 명령은 '사람 확인'으로 돌립니다)

flygate discover parp1                    # STEP 1: BioNeMo NIM 실측과 크리틱 판정
flygate signals NIRAPARIB                 # 불균형 지표 상위 반응 (SQL 추출본)
flygate grade NIRAPARIB thrombocytopenia  # PV 분류 후보: 라벨 절 + SDR + 문헌(리랭커)
flygate triage agent/examples/case_niraparib.json      # 반사 트리아지 7문항 + 결정 정책
flygate critic agent/examples/claims_niraparib.json    # 크리틱 3단 + PV 정책 가드
flygate kr-causality agent/examples/kr_report.txt --route   # 국내 보고 구조화 + 한국형 인과성
flygate watch                             # 하트비트 · cron 점검 (제출하지 않습니다)
```

OpenShell 샌드박스 배포는 `agent/deploy_nemoclaw.sh worker|assistant`, 점검은 `agent/openshell_smoke.sh`로 합니다([docs/AGENT.md](docs/AGENT.md)).

### 로컬 실행과 검증

```bash
# 데이터: 빌드된 FAERS 웨어하우스(DuckDB)를 릴리스에서 받습니다 (zstd 필요)
./scripts/fetch_data.sh

# 키 (.env, 커밋하지 않습니다)
TYPESAFE_API_KEY=...
NVIDIA_API_KEY=nvapi-...

# 대시보드와 API
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt duckdb pandas pyarrow numpy scipy uvicorn pytest
.venv/bin/python -m uvicorn api.index:app --port 8000
cd web && npm install && npm run dev          # http://localhost:5173

# OpenShell 샌드박스 스모크
./agent/openshell_smoke.sh

# 테스트와 평가
.venv/bin/python -m pytest -q tests          # 오프라인 147개
.venv/bin/python pipeline/refsets/evaluate.py
FV_CACHE_DIR=data/cache/api .venv/bin/python pipeline/bench/ablation.py
```

처음부터 재현하는 절차(FAERS 55개 분기 적재, 참조 세트, 구형 AERS)는 [docs/EVALUATION.md](docs/EVALUATION.md)의 각 절 끝에 있습니다.

### 저장소 구조

| 경로 | 내용 |
| --- | --- |
| `agent/` | OpenClaw 작업 공간, `flygate` CLI, OpenShell 정책, 스모크 기록 |
| `fly_discovery/` | STEP 1 FlyDiscovery 화면과 NIM 실측 원본 |
| `api/_fv/` | STEP 2 FlyVigilance 핵심 모듈(트리아지, 라벨, 통계, 문헌, 평가, 크리틱, 국내 모드) |
| `pipeline/` | FAERS 웨어하우스, 참조 세트 검증, 벤치마크 |
| `skills/` | NVIDIA Agent Skills 형식의 역량 11개 |
| `web/` | 라이브 대시보드(React + Vite) |
| `docs/` | 평가 보고서, 아키텍처, 에이전트 구성, 약사 검토 반영 |

## 08 / Sources & license

- **FDA FAERS / AERS** 공개 분기 데이터. 자발 보고는 인과관계를 증명하지 않습니다.
- **openFDA**(FDA 공개 데이터 조회 API), **DailyMed**(미국 약 라벨 원문 사이트), **PubMed E-utilities**(PubMed 조회 API), **RCSB PDB**(단백질 3차원 구조 공개 데이터베이스), **ChEMBL**
- **참조 세트**: OMOP(Ryan et al. 2013), EU-ADR(Coloma et al. 2013) — OHDSI MethodEvaluation, Apache-2.0 · Time-indexed reference standard(Harpaz et al. 2014) — CC0
- **EMA Designated Medical Events** 목록(EMA/326038/2020)
- **MaleCNS v1.0 커넥텀**: Janelia FlyEM · Cambridge Drosophila Connectomics Group, CC-BY 4.0 (https://male-cns.janelia.org)
- **팀 선행 저장소**: [Team-FlyGate/korea-agentic-hackathon-2026](https://github.com/Team-FlyGate/korea-agentic-hackathon-2026) (과잉해석 규칙 원본, 측정 스크립트, NAT(NVIDIA NeMo Agent Toolkit) 워크플로, OpenShell 정책, 1-6과 7절의 참조 세트 검증 코드)

코드는 Apache-2.0입니다.

## 09 / Glossary · 용어 풀이

이 문서에 나오는 주요 약어와 전문 용어를 풉니다. 대시보드의 [용어 풀이 페이지](https://project-flygate.vercel.app/#/glossary)에서는 모든 용어를 검색할 수 있고, 본문 용어에 마우스를 올리면 풀이가 뜹니다.

| 용어 | 풀이 |
| --- | --- |
| PV (약물감시) | 허가된 약을 쓰는 동안 생기는 이상사례를 모으고 평가해 위험을 찾아내는 일입니다 |
| 이상사례 · ICSR | 이상사례는 약을 쓴 뒤 생긴 모든 좋지 않은 일입니다. ICSR(개별 이상사례 보고)은 환자 한 명의 이상사례 한 건을 적은 보고서입니다 |
| FAERS | 미국 FDA 이상사례 보고 시스템입니다. 의료인·환자·제약사가 낸 보고를 분기마다 공개합니다. 구형 AERS는 2012년까지 쓰던 이전 시스템입니다 |
| 트리아지 (사례 분류) | 들어온 보고가 얼마나 급한지 가려 처리 경로를 정하는 첫 단계입니다. 응급실의 환자 분류와 같은 일입니다 |
| 중대성 | 사망, 생명 위협, 입원, 장애, 선천 기형처럼 결과가 심각한 사례인지 여부입니다. 증상의 세기(심각도)와는 다른 개념입니다 |
| 라벨 · 예측성 | 라벨(허가사항)은 규제기관이 허가한 약의 공식 설명서입니다. 예측성은 그 반응이 라벨에 이미 적혀 있는지 여부이며, 적혀 있지 않으면 "예상하지 못한" 반응입니다 |
| 신속보고 | 중요한 사례를 정해진 기한(보통 15일) 안에 규제기관에 보고하는 의무입니다 |
| SDR (불균형 보고 신호) | 특정 약·이상반응 조합이 다른 약보다 유난히 많이 보고되는 통계 신호입니다. 검토를 시작할 이유이지 검증된 신호나 인과의 증거가 아닙니다 |
| PRR · ROR | PRR(비례 보고 비)과 ROR(보고 오즈비)은 이 약에서 그 반응이 보고된 비율을 다른 약과 비교한 값입니다. 보고 비율이지 발생률이 아닙니다 |
| ROR₀₂₅ · IC₀₂₅ | 각각 보고 오즈비와 정보 성분(관측 보고 수가 기대치보다 얼마나 많은지 나타낸 베이지안 지표)의 95% 신뢰구간 하한입니다 |
| 3중 기준 | Evans 기준(PRR ≥ 2, χ² ≥ 4, 함께 보고된 사례 3건 이상), ROR₀₂₅ > 1, IC₀₂₅ > 0을 모두 넘는 경우입니다. 이 프로젝트의 SDR 판정 기준입니다 |
| PV 분류 | 라벨 기재 여부와 SDR 여부를 조합해 검토 우선순위를 매긴 분류입니다. 모두 "후보"이며 최종 분류는 허가권자와 규제기관이 정합니다 |
| ICH · 최소 4요소 | ICH(의약품 국제조화위원회)가 정한 유효한 보고의 최소 조건입니다. 확인 가능한 보고자, 환자, 의심 약, 이상사례가 있어야 합니다 |
| EMA DME | EMA(유럽의약품청)가 드물지만 심각해서 한 건만 보고돼도 살펴봐야 한다고 지정한 이상반응 목록입니다 |
| MedDRA PT | 이상반응 이름을 통일한 국제 의학 용어집(MedDRA)의 대표 용어(PT)입니다 |
| AUC · ROC | AUC(판별 정확도)는 양성과 음성을 얼마나 잘 가르는지 나타내는 0~1 점수로, 0.5는 무작위, 1은 완벽입니다. ROC는 민감도와 오경보율을 그린 곡선입니다 |
| 민감도 · PPV | 민감도는 실제 양성 중 잡아낸 비율, PPV(양성 예측도)는 양성으로 판정한 것 가운데 실제 양성의 비율입니다 |
| McNemar 검정 · p값 | McNemar는 같은 사례에 두 방법을 적용해 비교하는 짝지은 비교 검정입니다. p값은 실제로 차이가 없다고 가정할 때 이만한 차이가 우연히 나올 확률입니다 |
| 비자기회귀 판단 모델 | 글을 한 글자씩 생성하지 않고 정해진 질문에 대한 확률을 한 번에 돌려주는 모델입니다. 그래서 빠르고 쌉니다. 이 프로젝트는 TypeSafe AI의 Jev를 씁니다 |
| System-2 (숙고 단계) | 빠른 반사 판단으로 부족한 사례만 올려, NVIDIA Nemotron이 근거를 모아 평가 메모를 쓰는 단계입니다 |
| 근거 ID · 크리틱 | 근거 ID는 주장이 기댄 자료(통계 행, 라벨 절, 논문)의 고유 식별자입니다. 크리틱은 근거 ID 실재, 숫자 일치, 과잉해석을 검사해 근거를 넘는 주장을 반려합니다 |
| 과잉해석 | 숫자와 출처는 맞는데 결론이 근거가 허락하는 범위를 넘는 주장입니다. 예: "PRR이 높으니 이 환자에게 인과가 있다" |
| NIM · Nemotron | NIM(NVIDIA 추론 마이크로서비스)은 AI 모델을 표준 API로 바로 부를 수 있게 포장한 서비스이고, Nemotron은 NVIDIA의 언어 모델 계열입니다 |
| NemoClaw · OpenShell · OpenClaw | OpenClaw는 에이전트 실행 틀(하네스), OpenShell은 정책이 허용한 네트워크·파일·시스템 호출만 통과시키는 샌드박스, NemoClaw는 둘을 한 벌로 배포하는 NVIDIA 구성입니다 |
| deny-by-default · Landlock | deny-by-default는 밖으로 나가는 연결을 기본으로 모두 막고 목록에 적은 호스트만 여는 방식입니다. Landlock은 읽고 쓸 수 있는 파일 경로를 제한하는 리눅스 보안 기능입니다 |
| 하트비트 · cron | 하트비트는 에이전트가 정해진 간격으로 점검 목록을 스스로 확인하는 작업이고, cron은 정해진 시각에 명령을 자동 실행하는 예약 도구입니다 |
| 도킹 · 재도킹 · 포즈 | 도킹은 약물 분자가 단백질 결합 자리에 붙는 모양을 계산으로 맞춰 보는 일이고, 포즈는 그 위치와 자세 하나입니다. 재도킹은 결정 구조의 원래 약물을 빼고 다시 도킹해 제자리를 찾는지 보는 대조 실험입니다 |
| MSA · pLDDT | MSA(상동 서열 정렬)는 진화적으로 닮은 단백질 서열을 모아 줄 맞춘 것입니다. pLDDT(구조 예측 신뢰도)는 구조 예측 모델이 아미노산마다 매기는 0~100 신뢰도입니다 |
| RMSD · Å | RMSD는 예측한 원자 위치가 실험으로 푼 결정 구조와 평균 몇 Å 떨어졌는지입니다. 1 Å은 0.1 나노미터이며, 2 Å 이하면 보통 맞았다고 봅니다 |
| Spearman ρ · ChEMBL · PDB | Spearman ρ(순위 상관)는 예측 순위와 실측 순위가 얼마나 같이 움직이는지 나타냅니다. ChEMBL은 화합물 실험 활성값을, PDB는 단백질 3차원 구조를 모은 공개 데이터베이스입니다 |

---

<p align="center"><strong>FlyDiscovery + FlyVigilance = FlyGate</strong><br>분자에서 환자까지, 추론보다 근거가 먼저.<br><sub>From molecule to patient — evidence before inference.</sub></p>
