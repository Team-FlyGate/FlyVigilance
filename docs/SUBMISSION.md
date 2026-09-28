# 해커톤 제출 문구

NVIDIA Korea Agentic AI Hackathon 2026 · Section 02 · 서비스 명: **Project-FlyGate**

- 서비스 URL: https://project-flygate.vercel.app
- GitHub: https://github.com/Team-FlyGate/Project-FlyGate

## (1) 해결하고자 했던 문제 (Problem Definition, 300자 내외)

약물 안전성 검토자는 흩어진 근거를 모아 판단을 씁니다. 신약 개발 단계의 도킹 점수와 친화도, 시판 후의 허가 라벨·이상사례 보고·문헌입니다. FDA FAERS에만 한 분기 42만 건이 넘는 보고가 들어옵니다. 생성형 LLM에 전량을 읽히면 느리고 비싸고, 질문 하나로 거르면 중대 사례를 놓치거나 사람에게 과하게 넘깁니다. 숫자와 출처는 맞는데 결론만 근거를 넘는 주장도 있습니다. 서로 다른 단백질의 도킹 점수로 선택성을 말하거나, 불균형 지표를 인과로 읽는 식입니다. 빠르면서도 근거를 지키는 에이전트가 필요합니다.

<sub>공백 포함 292자</sub>

## (2) 서비스 소개 및 주요 기능 (Solution, 500자 내외)

Project-FlyGate는 시판 전 후보 물질의 표적 결합과 시판 후 허가 약물의 이상사례를 함께 다루는 약물 안전성 에이전트입니다. STEP 1 FlyDiscovery는 NVIDIA BioNeMo NIM(MSA-Search→OpenFold3→DiffDock→Boltz-2)으로 PARP1 결합을 예측하고 근거를 넘는 주장을 반려합니다. STEP 2 FlyVigilance는 FAERS 사례마다 규칙 게이트→FDA 라벨 원문 조회→7문항 판단→결정 정책→EMA DME 안전망을 거쳐 사람 우선, System-2 검토 등 경로를 정합니다. System-2에서는 Nemotron이 근거 ID를 붙여 평가하고 3단 크리틱과 Safety Guard가 과잉해석을 막습니다. 비자기회귀 판단 모델을 병용해 7문항 판단이 296 ms에 끝나고, 결과 코드를 가린 440건에서 중대 사례 247/250이 검토에 닿았습니다(질문 하나 234, p=0.004). 사람 업무량은 302건에서 138건으로 줄었습니다. 에이전트는 OpenShell 샌드박스 안의 OpenClaw로 돕니다.

<sub>공백 포함 542자</sub>

## (3) 활용한 핵심 기술 및 AI 모델 (Tech Stack)

**NVIDIA 모델 (build.nvidia.com NIM, OpenAI 호환 API)**
- NVIDIA Nemotron 3 Super 120B (`nvidia/nemotron-3-super-120b-a12b`): System-2 평가 메모, 국내 보고 서식 구조화, FlyDiscovery 크리틱 판정. JSON 모드 사용
- NVIDIA Nemotron 3 Ultra 550B (`nvidia/nemotron-3-ultra-550b-a55b`), Nemotron 3.5 Lightning 30B (`nvidia/nemotron-3.5-lightning-30b-a3b`): 폴백 사슬
- NVIDIA Nemotron Safety Guard 8B v3 + NVIDIA Nemotron 3.5 Content Safety: 메모의 주장마다 두 가드를 동시에 검사합니다. Content Safety에는 공식 스킬 nemotron-policy-generator로 만든 PV 정책(치료 조언, PRR 인과 단정, 자발 보고 발생률, 재식별, 허용 외 도구 사용)을 custom_policy로 넣어, PRR 인과 단정 7/7 · 없는 발생률 8/8을 가드 층에서 잡습니다(평가 50건 정확도 0.58 → 0.84)
- NVIDIA Nemotron 리랭커(llama-nemotron-rerank-vl-1b-v2): PubMed 후보 20편을 재정렬해 읽는 6편의 관련 문헌 비율 0.65 → 0.85
- NVIDIA BioNeMo NIM (health.api.nvidia.com): MSA-Search(상동 서열 101개), OpenFold3(PARP1 CA RMSD 1.0 Å), DiffDock(재도킹 0.71 Å), Boltz-2(ChEMBL 39종 Spearman 0.767)

**NVIDIA 에이전트 스택**
- NemoClaw v0.0.124 · OpenShell 0.0.116 · OpenClaw: OpenClaw 작업 공간(SOUL · AGENTS · IDENTITY · USER · TOOLS · HEARTBEAT · MEMORY), `flygate` CLI 도구 7종(triage, grade, signals, kr-causality, critic, discover, watch), 하트비트 감시 작업. OpenShell 정책은 deny-by-default 네트워크(호스트·메서드·경로·실행 파일 단위), Landlock 파일 시스템, 비루트 실행이며, 보고서를 밖으로 보내는 경로는 열지 않습니다. 실제 샌드박스 스모크 20/20 통과
- NVIDIA Agent Skills(github.com/NVIDIA/skills): 우리 역량 11개를 공식 규격 SKILL.md와 스킬 카드(skill-card-generator)로 패키징하고, 공식 스킬 bionemo-msa-structure-prediction-pipeline · nemotron-policy-generator · nemotron-retrieval-recipes를 실제 파이프라인에 적용

**비자기회귀 판단 모델**
- TypeSafe AI Jev: 반사 트리아지 7문항(296 ms, 같은 문항 자기회귀 생성 2,286 ms), 지식 기반 판별(OMOP AUC 0.960), 문헌 관련성·설계 판정(MEDLINE 일치 92.0%), 크리틱 과잉해석 판정

**데이터와 소프트웨어**
- FDA FAERS 55개 분기(2012Q4–2026Q2, 고유 사례 약 1,760만 건) + 구형 AERS 35개 분기, openFDA 라벨, DailyMed, PubMed E-utilities, RCSB PDB, ChEMBL, EMA DME 목록, OMOP · EU-ADR · Harpaz 참조 세트
- Python 3.12, DuckDB(5계층 웨어하우스, 불균형 지표는 SQL 계산), FastAPI, React + Vite + TypeScript, Vercel
