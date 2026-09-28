# Project-FlyGate Agent Skills

Project-FlyGate 의 능력을 [NVIDIA Agent Skills](https://github.com/NVIDIA/skills) 규격의 스킬 16개로 나눴습니다.
STEP 2 FlyVigilance(시판 후 약물감시)가 11개, STEP 1 FlyDiscovery(시판 전 탐색, 라이브 NIM 실행)가 5개입니다.
각 스킬은 `SKILL.md`(프런트매터 + 언제 쓰는지 + 실행 계약), `skill-card.md`(NVIDIA 거버넌스 카드), 그리고 확인 가능한 사례가 있는 스킬은 `evals/evals.json`(평가 과제)을 갖습니다.
모든 스킬은 저장소의 실제 코드(`api/_fv/`, `pipeline/`, `agent/flygate.py`)를 가리키며, 참조한 파일과 함수가 실제로 있는지 확인했습니다.

이 스킬들은 연구·개발용입니다. 결과는 사람 검토를 전제로 한 초안이며, 규제 보고와 인과성 최종 판정은 사람이 합니다.

## STEP 2 FlyVigilance 스킬 11개

| 스킬 | 층 | 하는 일 | 모델 · 엔드포인트 | 평가 과제 |
| --- | --- | --- | --- | --- |
| [`faers-warehouse`](faers-warehouse/SKILL.md) | 감각 · 부호화 | FAERS 분기 파일을 DuckDB 로 증분 적재하고 중복 제거, 약물명 정규화, 불균형 지표(PRR · ROR · χ² · IC025)를 SQL 로 계산합니다 | 모델 미사용 | – |
| [`pv-reflex-triage`](pv-reflex-triage/SKILL.md) | 반사 | ICSR 한 건을 규칙 게이트 → 라벨 근거 → 7문항 타입 판단 → 결정 정책(+ DME 안전망, 미국·국내 규정)으로 몇 초 안에 분류합니다 | 비자기회귀 판단 모델 | 5 |
| [`pv-signal-memory`](pv-signal-memory/SKILL.md) | 기억 | FAERS 2x2, openFDA 라벨 절, PubMed 문헌, 근거 등급, 참조 세트 지표를 인용 가능한 근거 ID 묶음으로 돌려줍니다 | 모델 미사용(문헌 판정만 판단 모델) | 4 |
| [`pv-literature-reading`](pv-literature-reading/SKILL.md) | 기억 | PubMed 후보 20편을 Nemotron 리랭커로 재정렬하고 상위 6편의 설계와 연관 보고 여부를 판정합니다 | `nvidia/llama-nemotron-rerank-vl-1b-v2` + 비자기회귀 판단 모델 | 5 |
| [`pv-evidence-grade`](pv-evidence-grade/SKILL.md) | 기억 | 라벨 상태 × SDR 로 PV 분류 후보와 한 글자 등급(A/B/C/L/D/U)을 규칙으로 정하고 근거와 공백을 함께 냅니다 | 모델 미사용 | 5 |
| [`pv-deliberate-assess`](pv-deliberate-assess/SKILL.md) | 숙고 | 올라온 사례에 대해 근거 ID 가 붙은 평가 메모를 쓰고 크리틱을 거칩니다 | `nvidia/nemotron-3-super-120b-a12b` (→ ultra-550b → 3.5-lightning-30b) | – |
| [`pv-critic`](pv-critic/SKILL.md) | 억제 | 근거 ID 규칙, 숫자 오라클, 과잉해석 판정, 주장별 안전 가드로 AI 가 쓴 주장을 검사하고 사유와 함께 되돌립니다 | `nvidia/llama-3.1-nemotron-safety-guard-8b-v3`, `nvidia/nemotron-3.5-content-safety` + 비자기회귀 판단 모델 | 5 |
| [`pv-guardrail-policy`](pv-guardrail-policy/SKILL.md) | 억제 | 약물감시 전용 범주(PV-1~PV-5)를 BYO 정책으로 만들어 Nemotron 3.5 Content Safety 에 `custom_policy` 로 넣고, Safety Guard 8B v3 와 함께 주장마다 검사합니다 | `nvidia/nemotron-3.5-content-safety` + `nvidia/llama-3.1-nemotron-safety-guard-8b-v3` | 50 |
| [`pv-kr-intake-causality`](pv-kr-intake-causality/SKILL.md) | 감각 · 반사 | 한국어 보고를 식약처 서식으로 구조화하고, 한국형 인과성 평가 알고리즘 ver 2.0 점수와 국내 신속보고 기한을 냅니다 | `nvidia/nemotron-3-super-120b-a12b` + 비자기회귀 판단 모델 | 5 |
| [`pv-reference-validation`](pv-reference-validation/SKILL.md) | 제어 | OMOP · EU-ADR · Harpaz 참조 세트에서 신호 기준과 판별 모드의 ROC/AUC 를 잽니다 | 비자기회귀 판단 모델(캐시) | 3 |
| [`connectome-router`](connectome-router/SKILL.md) | 전체 | MaleCNS 초파리 중앙뇌 부분그래프(뉴런 49,244개, 연결 1,051,255개)를 에이전트 9개 층에 대응시킨 라우팅 시각화를 만듭니다 | 모델 미사용 | – |

모든 스킬의 프런트매터는 `name`, `title`, `version`(1.0.0), `description`, `license`, `compatibility`, `metadata`(author `Team FlyGate`, `domain`, `tags`, `layer`, `model`)를 갖습니다.
## STEP 1 FlyDiscovery 스킬 5개

시판 전 탐색 다섯 단계입니다. 화면(`/#/msa` → `/#/openfold3` → `/#/diffdock` → `/#/boltz2` → `/#/critic`)의 실행 단추가
이 스킬들의 계약을 그대로 호출하며, 응답은 NVIDIA 호스팅 NIM 에서 실시간으로 받습니다. 지난 측정(`fly_discovery/measurements/`)은
비교용으로만 함께 보여 주고, 라이브 호출이 실패하면 사유와 함께 대체 표시를 답니다.

| 스킬 | 단계 | 하는 일 | 모델 · 엔드포인트 | 따라간 공식 스킬 |
| --- | --- | --- | --- | --- |
| [`discovery-msa-search`](discovery-msa-search/SKILL.md) | 1 | 표적 서열의 상동 서열을 찾아 A3M 정렬과 열별 깊이·보존도를 냅니다 | MSA-Search NIM · `POST /api/discovery/msa` | `bionemo-msa-structure-prediction-pipeline`, `msa-search-nim` |
| [`discovery-openfold3`](discovery-openfold3/SKILL.md) | 2 | 정렬과 리간드를 넣어 복합체를 예측하고 결정 구조 대비 CA RMSD 로 채점합니다 | OpenFold3 NIM · `POST /api/discovery/openfold3` | `bionemo-msa-structure-prediction-pipeline`, `openfold3-nim` |
| [`discovery-diffdock`](discovery-diffdock/SKILL.md) | 3 | 결합 포즈를 계산하고 공결정 재도킹 RMSD(≤ 2 Å)로 설정을 확인합니다 | DiffDock NIM · `POST /api/discovery/diffdock` | `diffdock-nim` |
| [`discovery-boltz2-affinity`](discovery-boltz2-affinity/SKILL.md) | 4 | 복합체와 예측 pIC50 을 받아 ChEMBL 실측값·39종 벤치마크와 대조합니다 | Boltz-2 NIM · `POST /api/discovery/boltz2` | `boltz2-nim` |
| [`discovery-critic`](discovery-critic/SKILL.md) | 5 | 근거 ID·숫자 오라클·Nemotron 과잉해석 판정으로 주장을 되돌립니다 | `nemotron-3-super-120b-a12b` · `POST /api/discovery/critic` | 팀 스킬 `pv-critic` 의 3단 구조 |

대시보드의 스킬 화면은 `pipeline/build_skills.py` 가 만드는 `web/public/data/skills.json` 을 읽습니다.

## 적용한 NVIDIA 공식 스킬

[NVIDIA/skills](https://github.com/NVIDIA/skills) 카탈로그에서 이 저장소에 실제로 적용한 스킬만 적었습니다.

| 공식 스킬 | 적용한 곳 | 적용한 내용 |
| --- | --- | --- |
| `bionemo-msa-structure-prediction-pipeline` | [`discovery-msa-search`](discovery-msa-search/), [`discovery-openfold3`](discovery-openfold3/), `api/_fv/discovery.py` | 1단계 MSA-Search(Uniref30_2302) → 2단계 OpenFold3(`msa.uniref30.a3m`) 규격을 그대로 따라 라이브로 호출합니다. 라이브 실행에서 정렬 101줄(10.8초), pLDDT 95.95, 4R6E 대비 CA RMSD 0.997 Å 를 받았고 지난 측정과 같았습니다. |
| `msa-search-nim` · `openfold3-nim` · `diffdock-nim` · `boltz2-nim` (NVIDIA-BioNeMo/bionemo-agent-toolkit) | [`discovery-*`](.) 5개, `api/_fv/discovery.py` | 엔드포인트 선택, 요청 본문(수용체 ATOM 줄, `ligand_file_type=txt`, `predict_affinity` 한 개, A3M `alignment`/`format`/`rank`), 응답 필드 읽기를 스킬 문서대로 구현했습니다. |
| `nemotron-policy-generator` | [`pv-guardrail-policy`](pv-guardrail-policy/) | 약물감시 범주를 BYO 정책(Markdown 정책, JSON 분류 체계, 시스템 프롬프트)으로 만들어 Nemotron 콘텐츠 안전 가드에 얹습니다. |
| `skill-card-generator` | STEP 2 스킬 11개의 `skill-card.md` | 공식 스크립트(`discover_assets.py` → `render_card.py` → `validate_submission.py`)로 카드를 만들고, 검토 표시가 남지 않았음을 확인했습니다. |
| `nemotron-retrieval-recipes` | [`pv-literature-reading`](pv-literature-reading/) | 1단계 검색(PubMed) 뒤 2단계 리랭커로 상위 순서를 바로잡는 구성과 그 평가 방식(상위 k 정밀도, 쌍별 AUC)을 따랐습니다. 리랭커는 build.nvidia.com 호스팅 모델을 그대로 쓰며, 레시피의 파인튜닝 단계는 쓰지 않았습니다. |

NemoClaw · OpenShell · OpenClaw 는 에이전트 배포에 썼습니다(`agent/`, `docs/AGENT.md`). 이 배포는 NVIDIA DLI 과정 *Securing Agents with NemoClaw and OpenShell* 의 구성을 따랐고, 공식 스킬 `nemoclaw-user-guide` 는 쓰지 않았으므로 위 표에 넣지 않았습니다.

## 검증

| 검사 | 도구 | 결과 |
| --- | --- | --- |
| 스킬 카드 검토 표시 | `skill-card-generator/scripts/validate_submission.py` | 카드 11개 모두 통과 |
| 프런트매터 파싱과 `name`·`description` | NVIDIA 카탈로그 `generate-skill-metadata.py` 의 파서 | 11개 모두 통과, `name` 과 디렉터리 이름 일치 |
| Agent Skills 규격 | [`skills-ref`](https://github.com/agentskills/agentskills/tree/main/skills-ref) 0.1.1 | 이름 형식, 설명 1,024자, compatibility 500자 한도를 모두 지킵니다. `title`·`version` 은 NVIDIA 카탈로그 확장 필드라 skills-ref 가 표시하며, 공식 `nemotron-policy-generator` 도 같은 표시를 받습니다 |
| 참조 경로 | 저장소 자체 점검 | `SKILL.md` 와 카드가 가리키는 파일·함수가 모두 있습니다 |
| 단위 테스트 | `.venv/bin/python -m pytest -q tests` | 평가 과제의 정답은 이 테스트와 `docs/EVALUATION.md` 의 측정값에서 가져왔습니다 |

카탈로그 등록(`components.d`)에 필요한 `skill.oms.sig`(서명)와 `BENCHMARK.md`(SkillEvaluator 결과)는 NVIDIA 서명·평가 파이프라인이 만드는 파일이라 이 저장소에는 두지 않습니다.

## 다시 만들기

```bash
# 스킬 카드 (공식 skill-card-generator)
python3 <NVIDIA/skills>/skills/skill-card-generator/scripts/discover_assets.py skills/<name>
python3 <NVIDIA/skills>/skills/skill-card-generator/scripts/render_card.py \
  --context /tmp/<name>-context.json \
  --template <NVIDIA/skills>/skills/skill-card-generator/references/skill-card.md.j2 \
  --out skills/<name>/skill-card.md
python3 <NVIDIA/skills>/skills/skill-card-generator/scripts/validate_submission.py skills/<name>/skill-card.md

# 대시보드 데이터
.venv/bin/python pipeline/build_skills.py
```
