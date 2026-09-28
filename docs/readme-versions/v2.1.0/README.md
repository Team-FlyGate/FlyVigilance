<p align="center">
  <a href="https://project-flygate.vercel.app"><img src="docs/images/flygate-hero_v2.0.0.png" width="100%" alt="FlyGate — Evidence before inference. Discovery / Vigilance."></a>
</p>

<p align="center"><strong>신약 후보 탐색부터 시판 후 약물감시까지, 판단이 근거를 넘지 않도록.</strong></p>
<p align="center">NVIDIA Korea Agentic AI Hackathon 2026 · Team FlyGate</p>
<p align="center">
  <a href="https://project-flygate.vercel.app"><strong>라이브 대시보드 ↗</strong></a> &nbsp; · &nbsp;
  <a href="https://project-flygate.vercel.app/showreel/FlyGate_showreel_v4.0.0.html">쇼릴 ↗</a> &nbsp; · &nbsp;
  <a href="docs/EVALUATION.md">평가 보고서</a> &nbsp; · &nbsp;
  <a href="#06--meet-the-team">Team</a> &nbsp; · &nbsp;
  <a href="#07--build--run">Quickstart</a>
</p>

---

## 01 / Two perspectives. One evidence trail.

**FlyGate = FlyDiscovery + FlyVigilance.** 시판 전에는 후보 물질의 표적 결합을, 시판 후에는 허가 약물의 이상사례를 살핍니다.

데모에서는 이미 허가된 PARP1 억제제 니라파립으로 시판 전 단계를 되짚어 재현하고, 같은 약의 실제 시판 후 보고로 이어서 보여 드립니다. 두 단계 모두 다른 표적과 약물에 그대로 씁니다.

| | |
| --- | --- |
| 라이브 대시보드 | https://project-flygate.vercel.app |
| 쇼릴 v4 (전체판, 4분 15초 · 19장면) | [웹](https://project-flygate.vercel.app/showreel/FlyGate_showreel_v4.0.0.html) · [MP4](https://github.com/Team-FlyGate/Project-FlyGate/releases/download/v4.0/FlyGate_showreel_v4.0.0.mp4) · [내레이션 대본](docs/SHOWREEL_SCRIPT_v4.0.0.md) |
| 쇼릴 v3 (요약판, 2분 9초) | [웹](https://project-flygate.vercel.app/showreel/FlyGate_showreel_v3.0.0.html) · [MP4](https://github.com/Team-FlyGate/Project-FlyGate/releases/download/v3.0/FlyGate_showreel_v3.0.0.mp4) |
| 티저 (15초) | [웹](https://project-flygate.vercel.app/showreel/FlyGate_teaser_15s_v1.0.0.html) · [MP4 가로 · 세로](https://github.com/Team-FlyGate/Project-FlyGate/releases/tag/teaser-v1.0) |
| 에이전트 구성 (NemoClaw · OpenShell · OpenClaw) | [docs/AGENT.md](docs/AGENT.md) · [agent/](agent/) |
| 평가 보고서 | [docs/EVALUATION.md](docs/EVALUATION.md) |
| 약사 검토 반영 내역 | [docs/PHARMACIST_REVIEW.md](docs/PHARMACIST_REVIEW.md) |

Project-FlyGate는 **NVIDIA 스킬 위에 구성한 에이전트 워크플로**입니다. build.nvidia.com NIM, NVIDIA Agent Skills, NemoClaw · OpenShell · OpenClaw를 씁니다.
글을 써야 하는 일은 NVIDIA Nemotron이 맡고, 확률만 필요한 판단에는 **비자기회귀(non-autoregressive) 판단 모델을 병용**합니다. 이 조합으로 높은 속도와 통계적으로 유의한 개선을 얻었습니다.

<p align="center"><img src="docs/images/flygate-modules_v2.0.0.png" width="100%" alt="FlyDiscovery: 구조·결합·근거. FlyVigilance: 보고·신호·검토."></p>
<p align="center"><sub>히어로와 모듈 아트는 AI 생성 개념 이미지이며, 실제 분자 구조나 임상 데이터를 나타내지 않습니다.</sub></p>

| 단계 | 이름 | 하는 일 |
| --- | --- | --- |
| STEP 1 · 시판 전 | **FlyDiscovery** | 후보 물질을 NVIDIA BioNeMo NIM으로 표적 구조 예측 → 도킹 → 친화도까지 평가하고, 근거를 넘는 주장을 반려합니다(데모: 니라파립 · PARP1, 대조 약물 2종, 친화도 벤치마크 39종) |
| STEP 2 · 시판 후 | **FlyVigilance** | FAERS 이상사례(약물 2,563종의 SDR 표)를 한 건씩 분류(트리아지: 급한 정도를 가려 처리 경로를 정하는 첫 단계)하고, SDR·라벨·문헌으로 PV 분류를 매기고, 사람 검토 대기열과 신속보고 기한을 만듭니다 |

## 02 / Measured, not assumed.

평가 질문, 측정값, 데이터 범위를 함께 제시합니다. 상세 조건과 재현 절차는 [평가 보고서](docs/EVALUATION.md)를 참고하세요.

| 질문 | 결과 | 데이터 |
| --- | --- | --- |
| 중대 사례를 놓치지 않으면서 사람 일을 줄이는가 | 결과 코드를 가린 채로 중대 사례 **247/250**이 검토에 닿았습니다(모델 단독 질문 하나 234/250, McNemar p = 0.0044). 사람 우선 업무량은 **138건**으로 질문 하나(302건)의 절반 아래입니다(p = 3.6×10⁻⁴⁸) | 실제 FAERS 440건 |
| 빠른가 | 규제 용어로 나눈 7문항 판단이 한 번 호출에 **296 ms**입니다. 같은 문항을 자기회귀 생성으로 풀면 2,286 ms입니다 | 같은 사례 27건 |
| 공인된 약물–이상반응 연관을 알아보는가 | FlyVigilance 지식 기반 판별 AUC **0.960**(OMOP), **0.983**(EU-ADR)으로 최고 통계 지표(0.815, 0.919)보다 유의하게 높습니다 | 공개 참조 세트 480쌍 |
| 라벨이 바뀌기 전에 알 수 있었는가 | 2013년 이전 보고만으로 그해 라벨 변경 57건 중 **21건**에 SDR이 섰고, 오경보는 음성 70건 중 **1건**입니다(PPV **0.95**) | 구형 AERS 2004–2012 |
| 과잉해석을 막는가 | 일부러 넣은 틀린 주장 **31/31**을 반려했고, 정상 주장 6/6은 통과했습니다. 공식 스킬 `nemotron-policy-generator`로 만든 PV 정책을 Nemotron 3.5 Content Safety에 넣자 가드 층만으로 PRR 인과 단정 **7/7**, 없는 발생률 **8/8**을 잡습니다(기본 가드 0/7, 0/8) | 실제 중대 사례 8건 · 평가 문장 50건 |
| 문헌을 제대로 읽는가 | 연구 설계 판정이 MEDLINE 색인과 **92.0%** 일치합니다. NVIDIA Nemotron 리랭커로 후보를 재정렬하자 읽는 6편 중 관련 문헌 비율이 **0.65 → 0.85**로 올랐습니다(21쌍 개선, 0쌍 악화) | PubMed 598편 · 30쌍 575편 |
| 시판 전 예측이 믿을 만한가 | OpenFold3 PARP1 구조 CA RMSD **1.0 Å**, DiffDock 재도킹 **0.71 Å**, Boltz-2 친화도 Spearman **0.767** | 4R6E, ChEMBL 39종 |

### 심사 기준별 요약

| 심사 기준 | Project-FlyGate의 근거 |
| --- | --- |
| **NVIDIA Agent 기술 활용 심도** | Nemotron 3 Super · Ultra · Lightning(System-2 평가, 서식 구조화), Safety Guard 8B v3 + Nemotron 3.5 Content Safety(PV 정책), Nemotron 리랭커, BioNeMo NIM 4종. 공식 NVIDIA Agent Skills 4개를 실제 파이프라인에 적용했습니다. OpenClaw 에이전트를 OpenShell 샌드박스에 올려 스모크 20/20, 하트비트와 cron까지 확인했습니다(NemoClaw 과정 01a–04c 대응표: [docs/AGENT.md](docs/AGENT.md)) |
| **실용성 · 산업 가치 · 혁신성** | 분기 42만 건 FAERS 보고를 사람 우선 · System-2 · 추가정보 요청 · 모니터링으로 나눕니다. 결과 코드를 가린 채로 중대 사례 247/250이 검토에 닿고, 사람 업무량은 302건에서 138건으로 줄었습니다. 미국·한국 15일 규정 모드와 한국형 인과성 평가를 갖췄고, 현업 약사 검토 15개 항목을 반영했습니다 |
| **완성도** | 라이브 대시보드와 API, 실제 FAERS 55개 분기 웨어하우스, 공개 참조 세트 3종 검증, 오프라인 테스트 147개, 재현 스크립트, 쇼릴 v3를 갖췄습니다 |
| **커스터마이징 · 독창성** | 판단은 비자기회귀 모델(7문항 296 ms), 글쓰기는 Nemotron으로 나눴습니다. 과잉해석 13규칙 크리틱과 약물감시 전용 가드 정책을 두고, 시판 전 결합 예측과 시판 후 감시를 한 에이전트로 이었습니다 |

## 03 / Why FlyGate

약물 안전성 검토자는 흩어진 근거를 모아 판단을 씁니다. 도킹 점수, 참조 친화도, 허가 라벨, 이상사례 보고, 문헌입니다.
- **양**: FAERS에는 한 분기에 42만 건이 넘는 보고가 들어옵니다(2026Q2 422,459건).
- **배분**: 질문 하나로 선별하면 중대 사례를 놓치지 않으려고 사람에게 과하게 넘기거나, 중대 사례가 아무도 보지 않는 자동 큐에 남습니다.
- **과잉해석**: 숫자와 출처가 다 맞는데 결론만 근거를 넘는 주장이 있습니다. 서로 다른 단백질의 도킹 점수로 선택성을 말하거나, 불균형 지표(PRR)를 인과로 읽는 식입니다. 형식 검사로는 걸러지지 않습니다.

### 두 단계, 하나의 에이전트

단계는 둘, 에이전트는 하나입니다. 에이전트는 OpenShell 샌드박스 안의 OpenClaw이고, 도구는 `flygate` CLI 하나입니다.

<a href="docs/images/flygate-architecture_v2.0.0.png"><img src="docs/images/flygate-architecture_v2.0.0.png" width="100%" alt="OpenShell 안의 OpenClaw 에이전트가 flygate CLI를 통해 FlyDiscovery와 FlyVigilance를 실행합니다. 근거 ID, 수치, 해석·안전성 검증을 거쳐 사람이 검토합니다."></a>

<sub>핵심 처리 경로를 요약한 구조도입니다. 모든 사례에 모델을 호출하지 않으며, 규칙과 결정 정책이 사람 우선·System-2·추가정보 요청·모니터링으로 경로를 나눕니다.</sub>

- **FlyDiscovery:** PARP1 서열 → MSA-Search → OpenFold3 구조 → DiffDock 포즈 → Boltz-2 친화도 → 전통 기준 채점 → 크리틱 3단.
- **FlyVigilance:** FAERS 사례 → ICH 최소 4요소 확인 → FDA 라벨 원문 조회 → 7문항 판단 → 결정 정책과 EMA DME 안전망. 필요한 사례만 Nemotron 평가와 크리틱·Safety Guard로 보냅니다.
- **공통 사례:** 니라파립의 시판 전 예측을 시판 후 근거와 연결합니다. 보고서의 판정과 제출은 사람이 담당합니다.

| 부품 | 하는 일 | 모델 |
| --- | --- | --- |
| 규칙 게이트 | ICH 최소 4요소, 결과 코드, 약물 역할처럼 규칙으로 되는 일은 모델에 묻지 않습니다 | 없음 |
| 라벨 원문 조회 | 반응이 FDA 허가 라벨 어느 절에 있는지(박스 경고 · 경고 · 임상시험 · 시판 후)를 원문으로 정합니다. 금기·적응증 문맥은 기재로 세지 않습니다 | 없음 |
| 반사 판단 | 중대성 · 예측성 · 인과 가능성 등 7문항을 한 번에 확률로 받습니다 | 비자기회귀 판단 모델 |
| 결정 정책 | 확률을 행동과 기한으로 바꿉니다. 미국(중대 + 예상하지 못함)과 한국(중대한 약물이상반응) 15일 규정 모드를 둡니다 | 없음 |
| SDR 통계 | PRR · ROR · IC₀₂₅와 3중 기준을 SQL로 계산합니다. 모델은 숫자를 바꾸지 못합니다 | 없음 |
| PV 분류 | 라벨 상태 × SDR로 검토 우선순위를 매기고, 박스 경고 · DME · 보고 편향 표시를 붙입니다 | 없음 |
| 지식 기반 판별 | 약·반응 이름으로 공인된 연관인지 확률을 줍니다(참고 축) | 비자기회귀 판단 모델 |
| 문헌 읽기 | PubMed 초록이 그 반응을 실제로 다루는지 먼저 묻고, 설계별 항목을 읽습니다 | 비자기회귀 판단 모델 |
| System-2 평가 | 승격된 사례만 근거 ID를 붙여 평가 메모를 씁니다 | NVIDIA Nemotron 3 Super |
| 크리틱 3단 | ① 근거 ID 실재 ② 숫자 오라클 ③ 과잉해석 13규칙 + 안전 가드 | 판단 모델, NVIDIA Nemotron Safety Guard |
| 사람 승인 | 보고서를 밖으로 보내는 경로는 없습니다. 판정과 제출은 사람이 합니다 | – |

상세 구조는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), 에이전트 배치는 [docs/AGENT.md](docs/AGENT.md)에 있습니다.

## 04 / Built with NVIDIA

| 기술 | 어디에 | 비고 |
| --- | --- | --- |
| **NVIDIA Nemotron 3 Super 120B** (`nvidia/nemotron-3-super-120b-a12b`) | System-2 평가 메모, 국내 보고 서식 구조화, FlyDiscovery 크리틱 판정 | Ultra 550B → 3.5 Lightning 30B 폴백 사슬, NIM JSON 모드 |
| **NVIDIA Nemotron Safety Guard 8B v3** + **Nemotron 3.5 Content Safety (PV 정책)** | 메모의 주장마다 두 가드를 동시에 돌려 치료 조언, PRR 인과 단정, 자발 보고로 낸 발생률, 재식별 시도를 반려 | PV 정책은 공식 스킬 `nemotron-policy-generator`로 생성해 `custom_policy`로 전달, 평가 50건 정확도 0.58 → 0.84 |
| **NVIDIA Nemotron 리랭커** (`llama-nemotron-rerank-vl-1b-v2`) | 문헌 읽기 전 PubMed 후보 20편 재정렬 | 공식 스킬 `nemotron-retrieval-recipes` 기준, 추가 지연 중앙값 0.57초 |
| **NVIDIA BioNeMo NIM** | MSA-Search → OpenFold3 → DiffDock → Boltz-2 | 공식 스킬 `bionemo-msa-structure-prediction-pipeline` 규격 |
| **NVIDIA Agent Skills** ([NVIDIA/skills](https://github.com/NVIDIA/skills)) | 우리 역량 11개를 공식 규격의 [skills/*/SKILL.md](skills/)와 스킬 카드로 패키징하고, 공식 스킬 `bionemo-msa-structure-prediction-pipeline` · `nemotron-policy-generator` · `nemotron-retrieval-recipes` · `skill-card-generator`를 실제로 적용 | 목록: [skills/README.md](skills/README.md) |
| **NemoClaw · OpenShell · OpenClaw** | OpenClaw 작업 공간(SOUL · AGENTS · TOOLS · HEARTBEAT), deny-by-default 네트워크 정책, Landlock 파일 시스템, 비루트 실행 | [agent/policy/flygate.yaml](agent/policy/flygate.yaml), 실제 OpenShell 샌드박스 스모크 **20/20** 통과 [agent/evidence/](agent/evidence/) |

비자기회귀 판단 모델로는 TypeSafe AI의 Jev를 FlyVigilance 안에서 씁니다.

### 전문가 검토 반영

현업 약사의 검토 의견 15개를 반영했습니다. 주요 항목은 다음과 같습니다([전체 내역](docs/PHARMACIST_REVIEW.md)).
- 통계 기준을 넘은 상태를 **SDR**(불균형 보고 신호)로 부르고, 한 글자 등급 대신 **PV 분류**(라벨 상태 × SDR)와 검토 우선순위를 앞에 둡니다.
- **EMA DME 62개 PT**가 보고되면 점수와 관계없이 사람 검토로 보냅니다.
- **보고 편향 표시**: 이소트레티노인–염증성장질환은 보고의 94.9%가 변호사 보고라, 변호사 보고를 뺀 민감도 분석을 함께 냅니다.
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
| 검증 · 벤치마크 | 공개 참조 세트 ROC, 결과 코드를 가린 비교 실험 |
| 에이전트 구성 | OpenShell 정책, OpenClaw 작업 공간, 스킬 |

MaleCNS 초파리 커넥텀(뉴런 49,244개) 화면은 에이전트의 라우팅 위상을 시각화한 것입니다.

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
| **강성준** <sup><a href="https://kangseongjun.com" title="강성준 개인 웹사이트">↗</a></sup> · [@AwesomeZun](https://github.com/AwesomeZun) | 단일세포·공간오믹스 · 신약 후보 평가 · 『AI 신약개발 실전가이드』 출간 | FlyVigilance, FlyDiscovery 개발 · 데이터·평가 파이프라인 · 두 모듈 통합과 시각화 · FDDD 개발 ([https://github.com/AwesomeZun/FDDD](https://github.com/AwesomeZun/FDDD)) |
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
- **openFDA**, **DailyMed**, **PubMed E-utilities**, **RCSB PDB**, **ChEMBL**
- **참조 세트**: OMOP(Ryan et al. 2013), EU-ADR(Coloma et al. 2013) — OHDSI MethodEvaluation, Apache-2.0 · Time-indexed reference standard(Harpaz et al. 2014) — CC0
- **EMA Designated Medical Events** 목록(EMA/326038/2020)
- **MaleCNS v1.0 커넥텀**: Janelia FlyEM · Cambridge Drosophila Connectomics Group, CC-BY 4.0 (https://male-cns.janelia.org)
- **팀 선행 저장소**: [kakyungkim/korea-agentic-hackathon-2026](https://github.com/kakyungkim/korea-agentic-hackathon-2026)

코드는 Apache-2.0입니다.

---

<p align="center"><strong>FlyDiscovery + FlyVigilance = FlyGate</strong><br><sub>Evidence before inference.</sub></p>
