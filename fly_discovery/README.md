**한국어** · [English](README.en.md)

# FlyDiscovery

**시판 전 탐색: 후보를 구조 예측, 도킹, 친화도로 따라가며 근거를 넘는 주장을 반려하는 워크벤치**

FlyDiscovery는 Project-FlyGate의 STEP 1(시판 전 탐색)이고, FlyVigilance는 STEP 2(시판 후 감시)입니다.
후보를 PARP1 결정 구조부터 친화도 벤치마크까지 따라가며, 단계마다 그 분야의 전통 기준으로 채점합니다.
이 후보의 시판 후 이상사례는 FlyVigilance [라이브 트리아지](https://flygate.kr/#/triage)가 이어받습니다.

## 왜 만들었나

결과를 더 많이 내는 것보다 **결과가 말해도 되는 범위를 정하는 것**이 중요합니다. 크리틱 3단이 그 역할을 맡습니다.

| 단 | 검사 | 모델 |
| --- | --- | --- |
| 1 | 주장에 근거 ID가 붙었습니까 | 미개입 |
| 2 | 숫자가 원본 로그(`measurements/`)와 맞습니까 | 미개입 |
| 3 | 추론이 근거를 넘지 않았습니까 | LLM |

숫자가 다 맞아도 3단에서 반려될 수 있습니다. "PARP1 -10.178, Factor Xa -7.967이므로 PARP1 선택적이다"는
두 숫자 모두 실측이지만, 다른 단백질의 도킹 점수는 교차 비교할 수 없으므로 반려합니다.
3단이 적용하는 해석 한계는 `api/_fv/discovery.py`의 `DISCOVERY_RULES`(D1–D9)에 있습니다.

## 화면

대시보드([flygate.kr](https://flygate.kr))의 STEP 1 메뉴 7개입니다. 화면 코드는 `web/src/pages/Discovery*.tsx`에 있습니다.

| 메뉴 | 내용 |
| --- | --- |
| 전체 프로세스 | 다섯 단계 3D 자동 재생, 지표 4장, 약물 패널(FAERS 케이스 ↔ 재도킹 ↔ STEP 2 링크) |
| 1 MSA-Search | 상동 서열 100개가 결합 포켓 구간에 정렬되는 모습, 잔기별 보존도 |
| 2 OpenFold3 | 예측 구조를 그려 나가고 결정 구조를 겹쳐 비교(약물 없이 단백질만) |
| 3 DiffDock | 결합 포켓으로 줌인하는 도킹, 직접 도킹해 보기, 재도킹 스트림 |
| 4 Boltz-2 | 예측 pIC50과 ChEMBL 실측 대조, 39종 벤치마크 산점도 |
| 5 크리틱 | PARP1 ↔ Factor Xa 분할 화면, 3단 판정, 모델 2종 비교 |
| 6 근거 검증 | 도킹 검증 관문 → 선택성 근거 표 → 후보 근거 카드 → STEP 2 |

각 단계 페이지에는 **흐름 띠**(앞 단계에서 무엇을 받아 다음으로 무엇을 넘겼는지)와
**라이브 실행 카드**(그 단계의 NIM을 지금 다시 부르기)가 있습니다.

### 라이브로 되는 것

화면에서 NVIDIA NIM을 실제로 부를 수 있습니다. 서버는 `api/_fv/discovery.py`이고 키는 서버에만 둡니다.

- 다섯 단계 각각(`POST /api/discovery/{msa,openfold3,diffdock,boltz2}`)과 크리틱
- **다섯 단계 이어 실행** — MSA 정렬(a3m)을 OpenFold3·Boltz-2로, OpenFold3 예측 구조를 DiffDock 수용체로 넘기며 차례로 호출
- 직접 도킹(`POST /api/dock`) — 미리 계산해 둔 조합에 없는 새 조합만 호출
- **임의 표적·리간드** — UniProt·RCSB·PubChem에서 찾아 그대로 파이프라인에 넣습니다(SMILES 붙여 넣기 포함)
- 실행 기록을 JSON으로 내려받기(근거 ID·요청 ID·수치)

실패하면 조용히 대체하지 않고 **"지난 측정으로 대체" 라벨과 사유를 함께** 보여 줍니다.
키가 없는 배포에서도 화면이 동작하도록, 아래 측정값은 모두 미리 계산해 두었습니다.

## 구조

| 경로 | 내용 |
| --- | --- |
| `measurements/measurements.json` | 화면 수치의 원본 요약 |
| `measurements/nim/` | NVIDIA NIM 원본 응답 58개 (MSA, OpenFold3, DiffDock, Boltz-2, 크리틱 평가) |
| `measurements/pub/` | ChEMBL ID·친화도, PARP1 벤치마크 세트 |
| `measurements/redock.json` | 재도킹 요약 |
| `measurements/redock_scenes.json` | 재도킹 3D 장면 좌표 |
| `measurements/hero_scene.json` | 대표 3D 장면(다섯 단계 · 약물 3종) |
| `measurements/dock_library.json` · `dock_matrix.json` | 직접 도킹 목록과 미리 계산 결과 |
| `measurements/validation.json` | 도킹 검증 관문(반복 5회) |
| `measurements/selectivity_evidence.json` | 도킹 격자 칸별 ChEMBL 실측 결합 기록 |
| `measurements/evidence_cards.json` | 후보 근거 카드 |
| `measurements/structure_candidates.json` | 재도킹 후보 구조 탐색 결과(선정은 사람이 했습니다) |
| `web/` | 이전 독립 화면. 빌드 없이 하드코딩 상수로 도는 정적 페이지이며, 대시보드에 iframe으로 남아 있습니다 |

측정값을 만드는 스크립트는 `pipeline/discovery/`에 10개 있습니다.
`web/scripts/sync-discovery.mjs`가 `measurements/`를 `web/public/discovery/data/`로 복사합니다(predev·prebuild 자동).

NVIDIA 공식 스킬 규격을 따른 스킬 5개가 `skills/discovery-*/`에 있습니다
(msa-search, openfold3, diffdock, boltz2-affinity, critic). 각 `SKILL.md`에 `Do Not Use`와 `Limits`를 적었습니다.

## 실측 결과

### NVIDIA NIM (health.api.nvidia.com, 계정 키로 실제 호출)

| NIM | 결과 |
| --- | --- |
| MSA-Search | PARP1 상동 서열 101개 (Uniref30_2302), 63.6초 |
| OpenFold3 | pLDDT 95.95, pTM 0.828, ipTM 0.658 · 4R6E 결정 구조 대비 CA RMSD **1.0 Å**, 리간드 1.16 Å |
| DiffDock | 재도킹 14건 + 직접 도킹 미리 계산 266건 + 검증 관문 반복 75건 |
| Boltz-2 | 8조합 + PARP1 벤치마크 39종 친화도 예측 |
| OpenFold2 | HTTP 500(CUDA 오류) 6회 시도 후 서버측 오류로 응답을 받지 못해 OpenFold3로 진행했습니다 |

MSA-Search → OpenFold3 조합은 NVIDIA 공식 스킬 `bionemo-msa-structure-prediction-pipeline`의 규격을 따랐습니다.

### 재도킹 (공결정 리간드를 다시 넣는 대조 실험)

기준은 대칭을 고려한 중원자 top-1 RMSD ≤ 2 Å(정렬 없음)입니다. **8 / 14 통과**.

| 구분 | 통과 |
| --- | --- |
| 가용성 단백질 | 8 / 9 |
| 세포막 단백질(GPCR·수송체) | **0 / 5** |

세포막 단백질 5건은 모두 실패했습니다. 실패군은 cryo-EM 3.3–3.4 Å 또는 X-ray 2.9 Å 이상에 몰려 있습니다.

### 도킹 검증 관문 (같은 입력으로 5번씩, 총 75회)

구조 품질 · 반복 수렴 · 결정 포즈 대조를 합쳐 등급을 냅니다. **HIGH 8 · MEDIUM 3 · LOW 4**(표적 15개).

"같은 자리로 모였다(수렴)"와 "그 자리가 정답이다(결정 대조)"는 다른 질문입니다.
아리피프라졸은 5번 모두 거의 같은 자리로 모였지만 결정 구조의 정답과 10 Å 넘게 떨어져 있어 LOW입니다.
결정 구조가 없는 새 표적이라면 수렴만 보고 믿었을 사례라, 등급은 결정 대조를 우선합니다.

### 포즈 순위 신뢰도

DiffDock 포즈 5개를 1순위만 보지 않고 **모두** 결정 구조와 대조했습니다.

- 재도킹 **13건 중 10건**에서 하위 순위 포즈가 1순위보다 정답에 더 가까웠습니다.
- 그중 **3건**(리스페리돈 · 피마반세린 · 실데나필)은 1순위만 보면 2 Å 기준 실패인데 하위 포즈는 기준 안에 들어옵니다.
  실데나필은 1순위 2.87 Å → **3순위 1.02 Å** 입니다.
- 자리를 못 찾은 것과 자리는 찾았는데 순위를 잘못 매긴 것은 다른 실패입니다.
  신뢰도는 포즈 순위 점수이지 결합 세기가 아닙니다(D2).

### 선택성 근거 (도킹 격자 + ChEMBL 실측)

약물 20 × 표적 14 격자에 ChEMBL pChEMBL 기록을 겹쳤습니다.

- 원래 표적이 도킹 신뢰도 **단독 1위인 약물은 14개 중 6개**입니다.
- 실측 결합 기록이 있는 22칸(유전자·약물 21쌍) 가운데 도킹 신뢰도도 그 약물 1위였던 칸은 **9칸**입니다.
- 근거 등급은 기록 유무와 중앙값만 봅니다. **도킹 신뢰도는 등급에 넣지 않습니다.**

### 친화도 예측 벤치마크

ChEMBL에서 PARP1 IC50 활성 4,180건 → 고유 화합물 3,370종 → 활성 범위가 고루 퍼지도록 39종을 골랐습니다.
Boltz-2 예측을 ChEMBL pChEMBL 중앙값과 대조했습니다.

| 지표 | 값 |
| --- | --- |
| Spearman | 0.767 |
| Pearson | 0.746 |
| MAE | 0.71 log 단위 |
| Enrichment (상위 25%) | 2.41 (9개 중 5개) |
| 민감도 / 특이도 (pIC50 ≥ 7) | 0.80 / 0.86 |

### 크리틱

평가는 8건(과잉해석 4, 정상 4)으로 쟀습니다.

| 모델 | 과잉해석 적발 | 정상 통과 | 소요 |
| --- | --- | --- | --- |
| `nemotron-3-super-120b-a12b` | 4 / 4 | 3 / 4 | 41.8초 |
| `nemotron-3.5-lightning-30b-a3b` | 0 / 4 | 1 / 4 | 294.5초 |

주어진 출력 토큰 예산에서 Lightning 모델은 `VERDICT:` 줄 이전 추론 과정에 토큰을 모두 사용했습니다.
이에 따라 크리틱 판정에는 Super 모델을 사용합니다.

## 정직하게 밝혀 둘 한계

- 재도킹 RMSD 0.71 Å는 공결정 구조에 원래 리간드를 다시 넣은 **대조 실험**입니다. 도킹 설정이 작동한다는 것을
  확인하는 지표이며, 새 후보의 결합을 예측했다는 뜻이 아닙니다(D5).
- 4R6E는 공개 구조로, OpenFold3 학습 데이터에 포함되었을 수 있습니다(D9).
- **친화도 벤치마크는 n=39, PARP1 단일 타깃 기준입니다.** 나머지 표적에서의 정확도는 아직 재지 못했습니다.
  표적 14개로 넓혀 보려 했지만(`pipeline/discovery/benchmark_boltz2_targets.py`, 결과는 `measurements/boltz2_targets.json`)
  MSA 없이 단일 서열로 돌린 값이라 MSA를 쓴 39종 벤치마크와 **직접 비교할 수 없습니다.** 그 수치는 참고로만 두었습니다.
- **Boltz-2 예측값은 조건과 실행에 크게 흔들립니다.** 탈라조파립@PARP1을 대조로 재 보니 이렇습니다.

  | 조건 | 예측 pIC50 | 실측(ChEMBL 중앙값) |
  | --- | --- | --- |
  | MSA 없이(단일 서열), 3회 | 6.23 · 6.12 · 6.48 (평균 **6.28**) | 9.15 |
  | MSA 넣고, 3회 | 7.46 · 9.06 · 7.47 (평균 **8.00**) | 9.15 |
  | 39종 벤치마크(MSA) | 8.90 | 9.22 |

  MSA를 넣으면 실측에 가까워지지만, **같은 입력 3회가 1.6 log 벌어집니다.** 4R6E와 7KK3 서열 모두 MSA 없이는 6.2 부근이라
  구조 차이가 아니라 MSA 유무가 원인입니다. 예측값 한 번을 뽑아 인용하면 안 됩니다(D3).
- 크리틱 수치는 평가 8건 기준입니다.
- COX-2 3LN1은 **쥐** 단백질이라 사람으로 옮길 수 없습니다(D7).
- 니르마트렐비르는 공유결합 억제제인데 DiffDock은 비공유 결합만 모사하므로 참고용입니다.
- 메토트렉세이트/DHFR은 보조인자 NADPH를 수용체에 넣지 않았습니다(ATOM만 사용).
- 선택성 근거는 ChEMBL 한 출처만 씁니다. BindingDB는 따로 부르지 않았습니다.
- 3D 장면에서 리본을 그려 나가는 순서, 포즈가 날아오는 경로, 카메라는 연출입니다.
  **도착한 좌표와 수치는 NIM 응답·RCSB·ChEMBL 그대로입니다.**

## 실행

대시보드에서 보는 것이 기본입니다.

```bash
npm --prefix web install && npm --prefix web run dev     # http://localhost:5173/#/discovery
```

라이브 실행을 쓰려면 API 서버에 NVIDIA 키가 필요합니다(키는 환경 변수로만 넘깁니다).

```bash
NVIDIA_API_KEY=... .venv/bin/uvicorn api.index:app --port 8000
```

측정값을 다시 만들 때는 `pipeline/discovery/`의 스크립트를 순서대로 돌립니다.

```bash
.venv/bin/python pipeline/discovery/redock.py            # 재도킹 → redock.json
.venv/bin/python pipeline/discovery/validate_docking.py  # 검증 관문 → validation.json
.venv/bin/python pipeline/discovery/build_hero_scene.py  # 대표 장면 → hero_scene.json
```

이전 독립 화면만 따로 보려면 정적 서버가 필요합니다(fetch 때문입니다).

```bash
cd fly_discovery/web && python3 -m http.server 8777      # http://localhost:8777
```

## 고칠 때

- 수치를 바꿀 때는 `measurements/`의 원본과 대조합니다. 근거가 없으면 `미조회` 또는 `—`로 남기고 추정값을 채우지 않습니다.
- 측정값을 다시 만들면 `web/scripts/sync-discovery.mjs`의 복사 목록에도 파일이 있는지 확인합니다.
- `web/index.html`의 색·폰트·패널 토큰은 대시보드 `web/src/index.css`와 같은 값입니다. 한쪽을 바꾸면 다른 쪽도 같이 바꿉니다.
- 푸터의 크레딧 줄은 라이선스 요구사항이므로 지우지 않습니다. 색·컴포넌트 토큰은 [FDDD](https://github.com/AwesomeZun/FDDD)(fly-connectome-template)에서 가져왔습니다.

원본은 [Geongyu/flygate](https://github.com/Geongyu/flygate)의 STEP 1 화면입니다.
