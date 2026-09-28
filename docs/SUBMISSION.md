# 해커톤 제출 문구 (최종 제출본)

NVIDIA Korea Agentic AI Hackathon 2026 · Section 02 · 서비스 명: **Project-FlyGate** · 팀 FlyGate · 2026-09-28 제출

- 서비스 URL: https://flygate.kr
- GitHub: https://github.com/Team-FlyGate/Project-FlyGate
- 쇼릴 (4분 10초): https://flygate.kr/showreel/FlyGate_showreel_v4.3.0.html
- 제출한 PDF(7쪽): [docs/submission/NVIDIA_해커톤_FlyGate_Final_제출버전.pdf](submission/NVIDIA_해커톤_FlyGate_Final_제출버전.pdf)

이 문서는 실제로 제출한 PDF의 문구를 그대로 옮긴 최종본입니다. 제출 전 초안은 `SUBMISSION_v1.0.0.md` ~ `SUBMISSION_v1.0.2.md`, 영어판은 [`SUBMISSION_en_v1.1.0.md`](SUBMISSION_en_v1.1.0.md)(최종본 번역), 이전 초안 번역은 `SUBMISSION_en_v1.0.0.md` 에 있습니다.

## (1) 해결하고자 했던 문제 (Problem Definition)

환자의 생명을 지키는 신약 안전성은 개발 단계의 결합 예측부터 출시 후 환자 부작용 보고까지 전주기 근거를 살펴야 합니다. 그러나 개발 단계에서는 단순 결합 점수만 보고 특정 표적에만 잘 붙는다고 과신하는 오류가 잦습니다. 출시 후에는 FDA에만 분기당 42만 건씩 쏟아지는 부작용 보고를 기존 LLM이나 사람이 전수 검토하기에 시간과 비용이 너무 큽니다. 그렇다고 질문 하나로 기계적으로 거르면 위험 신호를 놓치며, 단순 보고 건수를 약물의 인과관계로 비약해 환자의 안전을 위협하는 치명적인 왜곡도 걸러내지 못합니다.

<sub>공백 포함 290자</sub>

## (2) 서비스 소개 및 주요 기능 (Solution)

Project-FlyGate는 감각 신호를 초고속으로 걸러내는 초파리 뇌 커넥톰의 게이팅(Gating) 원리를 적용해, 출시 전 개발 예측부터 출시 후 부작용까지 전 과정을 검증하는 AI 신약 안전성 에이전트입니다. 1단계 FlyDiscovery는 BioNeMo NIM(MSA-Search→OpenFold3→DiffDock→Boltz-2)으로 표적 결합을 시뮬레이션하고 근거 없는 과장 결론을 자동 반려합니다. 2단계 FlyVigilance는 대량의 부작용 보고를 규칙 게이트와 공식 허가 라벨로 먼저 걸러낸 뒤, 비자기회귀(Non-Autoregressive) 판단 모델 Jev가 7개 핵심 문항을 0.3초(296ms) 만에 초고속 판별합니다. 이어 정밀 검토가 필요한 사례만 Nemotron 3 Super 120b가 근거 번호를 매겨 심층 평가하며 Safety Guard로 인과 왜곡을 차단합니다. 440건 검증에서 위험 사례 247/250건을 탐지하며 사람의 검토 부담을 302건에서 138건으로 54% 절감했습니다. 모든 기능은 flygate CLI와 OpenShell 기반 NemoClaw로 호출됩니다.

<sub>공백 포함 565자</sub>

## (3) 활용한 핵심 기술 및 AI 모델 (Tech Stack)

### NVIDIA 모델 (build.nvidia.com NIM: NVIDIA 추론 마이크로서비스, OpenAI 호환 API)

- **NVIDIA Nemotron 3 Super 120B** (`nvidia/nemotron-3-super-120b-a12b`): System-2(숙고 단계) 평가 메모, 국내 보고 서식 구조화, FlyDiscovery 크리틱(근거를 넘는 주장을 반려하는 검사 단계) 판정. JSON 모드 사용
- **NVIDIA Nemotron 3 Ultra 550B** (`nvidia/nemotron-3-ultra-550b-a55b`), **Nemotron 3.5 Lightning 30B** (`nvidia/nemotron-3.5-lightning-30b-a3b`): 폴백 사슬(주 모델이 응답하지 않을 때의 대체 경로)
- **NVIDIA Nemotron Safety Guard 8B v3 + NVIDIA Nemotron 3.5 Content Safety**: 메모의 주장마다 두 가드를 동시에 검사합니다. Content Safety에는 공식 스킬 nemotron-policy-generator로 만든 PV(약물감시) 정책(치료 조언, PRR(비례 보고 비) 인과 단정, 자발 보고 발생률, 재식별, 허용 외 도구 사용)을 custom_policy로 넣어, PRR 인과 단정 7/7 · 없는 발생률 8/8을 가드 층에서 잡습니다(평가 50건 정확도 0.58 → 0.84)
- **NVIDIA Nemotron 리랭커**(검색 결과를 관련도 순으로 다시 줄 세우는 모델, `llama-nemotron-rerank-vl-1b-v2`): PubMed 후보 20편을 재정렬해 읽는 6편의 관련 문헌 비율 0.65 → 0.85
- **NVIDIA BioNeMo NIM** (health.api.nvidia.com): MSA-Search(상동 서열 정렬, 상동 서열 101개), OpenFold3(PARP1 CA RMSD 1.0 Å, RMSD는 결정 구조와의 거리), DiffDock(재도킹 0.71 Å), Boltz-2(ChEMBL 39종 Spearman 0.767, Spearman은 순위 상관)

### NVIDIA 에이전트 스택

- **NemoClaw v0.0.124 · OpenShell 0.0.116 · OpenClaw**: OpenClaw 작업 공간(SOUL · AGENTS · IDENTITY · USER · TOOLS · HEARTBEAT · MEMORY), 하트비트(정기 자가 점검) 감시 작업. OpenShell 정책은 deny-by-default(기본 차단, 허용 목록만 개방) 네트워크(호스트·메서드·경로·실행 파일 단위), Landlock(리눅스 파일 경로 접근 제한) 파일 시스템, 비루트 실행이며, 보고서를 밖으로 보내는 경로는 열지 않습니다. 실제 샌드박스 스모크(기본 동작 점검) 20/20 통과
- **FlyGate Agent CLI** (`flygate`, 명령줄 인터페이스): 저장소를 받은 뒤 `./scripts/install_flygate.sh` 한 줄로 설치합니다. 명령 9개(login, chat, triage, grade, signals, kr-causality, critic, discover, watch)가 모두 근거 ID가 붙은 JSON을 출력합니다. `flygate`만 입력하면 대화형 모드가 열려 "PARP1 후보 근거를 보여줘" 같은 요청에 실행할 명령을 제안하고 확인을 받은 뒤 실행합니다. NVIDIA 키는 `flygate login`으로 OS 보안 저장소에 저장합니다. `flygate discover --live`는 DiffDock NIM을 실시간으로 부르며, 사람과 OpenShell 샌드박스의 OpenClaw 에이전트가 같은 명령을 씁니다
- **NVIDIA Agent Skills** (github.com/NVIDIA/skills): 우리 역량 11개를 공식 규격 SKILL.md와 스킬 카드(skill-card-generator)로 패키징하고, 공식 스킬 bionemo-msa-structure-prediction-pipeline · nemotron-policy-generator · nemotron-retrieval-recipes를 실제 파이프라인에 적용

### 비자기회귀 판단 모델 (글을 생성하지 않고 정해진 질문의 확률을 한 번에 돌려주는 모델)

- **TypeSafe AI Jev**: 반사 트리아지(사례 분류) 7문항(296 ms, 같은 문항 자기회귀 생성 2,286 ms), 지식 기반 판별(OMOP AUC 0.960, AUC는 판별 정확도), 문헌 관련성·설계 판정(MEDLINE 색인 일치 92.0%), 크리틱 과잉해석 판정

### 데이터와 소프트웨어

- FDA FAERS(미국 FDA 이상사례 보고 시스템) 55개 분기(2012Q4–2026Q2, 고유 사례 약 1,760만 건) + 구형 AERS 35개 분기, openFDA 라벨, DailyMed, PubMed E-utilities, RCSB PDB(단백질 구조 데이터베이스), ChEMBL(화합물 활성값 데이터베이스), EMA DME 목록(EMA가 지정한 특별 주의 이상사례), OMOP · EU-ADR · Harpaz 참조 세트(정답을 미리 정해 둔 평가용 목록)
- MaleCNS v1.0 초파리 커넥텀(뉴런 간 연결 지도): Janelia FlyEM 등이 공개한 수컷 초파리 중추신경계 데이터(CC-BY 4.0). 이 중 중앙뇌 부분그래프(뉴런 49,244개, 뉴런 간 연결 1,051,255개)를 에이전트의 9개 기능 층에 대응시켜 작업 분기와 검토 경로를 시각화합니다.
- Python 3.12, DuckDB(5계층 웨어하우스, 불균형 지표는 SQL 계산), FastAPI, React + Vite + TypeScript, Vercel

## PDF에 함께 넣은 내용

PDF에는 위 세 항목과 함께 다음 쪽이 들어 있습니다. 내용은 저장소의 해당 문서와 같습니다.

- 표지: 핵심 수치 247/250 · 302 → 138 · 296 ms · Boltz-2 0.767 · 샌드박스 스모크 20/20 · MEDLINE 색인 일치 92.0%
- 구조: NemoClaw · OpenShell · OpenClaw 에이전트가 flygate CLI로 FlyDiscovery와 FlyVigilance를 실행하는 구성도
- NVIDIA 기술 활용 내역: 기술마다 코드 위치 · 실행 화면 · 아키텍처 그림 · 실제 호출 기록([NVIDIA_CALL_LOG_v1.0.0.md](NVIDIA_CALL_LOG_v1.0.0.md))
- FlyGate Agent CLI 설치와 사용(flygate.kr/#/cli)
- NVIDIA 호출 기록(flygate.kr/#/calls)
