# 해커톤 제출 문구

NVIDIA Korea Agentic AI Hackathon 2026 · Section 02 · 서비스 명: **Project-FlyGate**

- 서비스 URL: https://flygate.kr
- GitHub: https://github.com/Team-FlyGate/Project-FlyGate

## (1) 해결하고자 했던 문제 (Problem Definition, 300자 내외)

약물 안전성 검토자는 흩어진 근거를 모아 판단을 씁니다. 시판 전에는 표적 결합 예측(도킹) 점수와 친화도, 시판 후에는 허가 라벨·이상사례 보고·문헌입니다. 미국 FDA 이상사례 보고(FAERS)에만 한 분기 42만 건이 넘는 보고가 들어옵니다. 생성형 언어 모델(LLM)로 전량을 읽으면 느리고 비싸며, 질문 하나로 거르면 중대 사례를 놓치거나 사람에게 과하게 넘깁니다. 숫자와 출처는 맞는데 결론만 근거를 넘는 주장도 형식 검사로는 걸러지지 않습니다. 다른 단백질의 도킹 점수로 선택성을 말하거나 보고 비율을 인과로 읽는 식입니다.

<sub>공백 포함 300자 · 제한 300자 이내</sub>

## (2) 서비스 소개 및 주요 기능 (Solution, 500자 내외)

Project-FlyGate는 시판 전 표적 결합과 시판 후 이상사례를 함께 보는 약물 안전성 에이전트입니다. STEP 1 FlyDiscovery는 NVIDIA BioNeMo NIM(MSA-Search→OpenFold3→DiffDock→Boltz-2)으로 표적 결합을 예측하고 근거를 넘는 주장을 반려합니다. STEP 2 FlyVigilance는 FAERS 사례를 규칙 게이트→FDA 라벨 조회→7문항 판단→결정 정책으로 분류하고, 필요한 사례만 Nemotron이 근거 ID를 붙여 평가하며 3단 검증과 Safety Guard가 과잉해석을 막습니다. 비자기회귀 판단 모델을 병용해 판단이 296 ms에 끝나고, 결과 표시를 가린 440건에서 중대 사례 247/250이 검토에 닿았으며(질문 하나 234, p=0.004) 사람 업무량은 302건→138건으로 줄었습니다. 모든 기능은 한 줄 설치 flygate CLI로 부르고, OpenShell 샌드박스의 OpenClaw도 같은 명령을 씁니다.

<sub>공백 포함 499자 · 제한 500자 이내</sub>

## (3) 활용한 핵심 기술 및 AI 모델 (Tech Stack)

**NVIDIA 모델 (build.nvidia.com NIM: NVIDIA 추론 마이크로서비스, OpenAI 호환 API)**
- NVIDIA Nemotron 3 Super 120B (`nvidia/nemotron-3-super-120b-a12b`): System-2(숙고 단계) 평가 메모, 국내 보고 서식 구조화, FlyDiscovery 크리틱(근거를 넘는 주장을 반려하는 검사 단계) 판정. JSON 모드 사용
- NVIDIA Nemotron 3 Ultra 550B (`nvidia/nemotron-3-ultra-550b-a55b`), Nemotron 3.5 Lightning 30B (`nvidia/nemotron-3.5-lightning-30b-a3b`): 폴백 사슬(주 모델이 응답하지 않을 때의 대체 경로)
- NVIDIA Nemotron Safety Guard 8B v3 + NVIDIA Nemotron 3.5 Content Safety: 메모의 주장마다 두 가드를 동시에 검사합니다. Content Safety에는 공식 스킬 nemotron-policy-generator로 만든 PV(약물감시) 정책(치료 조언, PRR(비례 보고 비) 인과 단정, 자발 보고 발생률, 재식별, 허용 외 도구 사용)을 custom_policy로 넣어, PRR 인과 단정 7/7 · 없는 발생률 8/8을 가드 층에서 잡습니다(평가 50건 정확도 0.58 → 0.84)
- NVIDIA Nemotron 리랭커(검색 결과를 관련도 순으로 다시 줄 세우는 모델, llama-nemotron-rerank-vl-1b-v2): PubMed 후보 20편을 재정렬해 읽는 6편의 관련 문헌 비율 0.65 → 0.85
- NVIDIA BioNeMo NIM (health.api.nvidia.com): MSA-Search(상동 서열 정렬, 상동 서열 101개), OpenFold3(PARP1 CA RMSD 1.0 Å, RMSD는 결정 구조와의 거리), DiffDock(재도킹 0.71 Å), Boltz-2(ChEMBL 39종 Spearman 0.767, Spearman은 순위 상관)

**NVIDIA 에이전트 스택**
- NemoClaw v0.0.124 · OpenShell 0.0.116 · OpenClaw: OpenClaw 작업 공간(SOUL · AGENTS · IDENTITY · USER · TOOLS · HEARTBEAT · MEMORY), 하트비트(정기 자가 점검) 감시 작업. OpenShell 정책은 deny-by-default(기본 차단, 허용 목록만 개방) 네트워크(호스트·메서드·경로·실행 파일 단위), Landlock(리눅스 파일 경로 접근 제한) 파일 시스템, 비루트 실행이며, 보고서를 밖으로 보내는 경로는 열지 않습니다. 실제 샌드박스 스모크(기본 동작 점검) 20/20 통과
- FlyGate Agent CLI(`flygate`, 명령줄 인터페이스): 저장소를 받은 뒤 `./scripts/install_flygate.sh` 한 줄로 설치합니다. 명령 9개(login, chat, triage, grade, signals, kr-causality, critic, discover, watch)가 모두 근거 ID가 붙은 JSON을 출력합니다. `flygate`만 입력하면 대화형 모드가 열려 "PARP1 후보 근거를 보여줘" 같은 요청에 실행할 명령을 제안하고 확인을 받은 뒤 실행합니다. NVIDIA 키는 `flygate login`으로 OS 보안 저장소에 저장합니다. `flygate discover --live`는 DiffDock NIM을 실시간으로 부르며, 사람과 OpenShell 샌드박스의 OpenClaw 에이전트가 같은 명령을 씁니다
- NVIDIA Agent Skills(github.com/NVIDIA/skills): 우리 역량 11개를 공식 규격 SKILL.md와 스킬 카드(skill-card-generator)로 패키징하고, 공식 스킬 bionemo-msa-structure-prediction-pipeline · nemotron-policy-generator · nemotron-retrieval-recipes를 실제 파이프라인에 적용

**비자기회귀 판단 모델** (글을 생성하지 않고 정해진 질문의 확률을 한 번에 돌려주는 모델)
- TypeSafe AI Jev: 반사 트리아지(사례 분류) 7문항(296 ms, 같은 문항 자기회귀 생성 2,286 ms), 지식 기반 판별(OMOP AUC 0.960, AUC는 판별 정확도), 문헌 관련성·설계 판정(MEDLINE 색인 일치 92.0%), 크리틱 과잉해석 판정

**데이터와 소프트웨어**
- FDA FAERS(미국 FDA 이상사례 보고 시스템) 55개 분기(2012Q4–2026Q2, 고유 사례 약 1,760만 건) + 구형 AERS 35개 분기, openFDA 라벨, DailyMed, PubMed E-utilities, RCSB PDB(단백질 구조 데이터베이스), ChEMBL(화합물 활성값 데이터베이스), EMA DME 목록(EMA가 지정한 특별 주의 이상사례), OMOP · EU-ADR · Harpaz 참조 세트(정답을 미리 정해 둔 평가용 목록)
- [MaleCNS v1.0](https://male-cns.janelia.org/) 초파리 커넥텀(뉴런 간 연결 지도): Janelia FlyEM 등이 공개한 수컷 초파리 중추신경계 데이터(CC-BY 4.0). 이 중 중앙뇌 부분그래프(뉴런 49,244개, 뉴런 간 연결 1,051,255개)를 에이전트의 9개 기능 층에 대응시켜 작업 분기와 검토 경로를 시각화합니다.
- Python 3.12, DuckDB(5계층 웨어하우스, 불균형 지표는 SQL 계산), FastAPI, React + Vite + TypeScript, Vercel
