# FlyDiscoverer

**시판 전 탐색: 후보 하나를 구조 예측, 도킹, 친화도로 따라가며 근거를 넘는 주장을 반려하는 워크벤치**

FlyVigilance가 시판 후 감시라면 FlyDiscoverer는 그 앞 단계다. 한 후보(니라파립)를 PARP1 결정 구조부터
친화도 벤치마크까지 따라가고, 단계마다 그 분야의 전통 기준으로 채점한다.
이 후보의 시판 후 이상사례는 FlyVigilance [라이브 트리아지](https://flyvigilance.vercel.app/#/triage)가 이어받는다.

## 왜 만들었나

결과를 더 많이 내는 것보다 **결과가 말해도 되는 범위를 정하는 것**이 중요하다. 크리틱 3단이 그 일을 한다.

| 단 | 검사 | 모델 |
| --- | --- | --- |
| 1 | 주장에 근거 ID가 붙었나 | 미개입 |
| 2 | 숫자가 원본 로그(`measurements/`)와 맞나 | 미개입 |
| 3 | 추론이 근거를 넘지 않았나 | LLM |

숫자가 다 맞아도 3단에서 반려될 수 있다. "PARP1 -10.178, Factor Xa -7.967이므로 PARP1 선택적이다"는
두 숫자 모두 실측이지만, 다른 단백질의 도킹 점수는 교차 비교할 수 없으므로 반려한다.

## 구조

| 경로 | 내용 |
| --- | --- |
| `web/index.html` | 화면. 후보 비교, 결합 포즈, 주장 검증, 친화도 벤치마크 |
| `web/dc-shim.js` | Design 아트보드 템플릿(`{{ 경로 }}`, `sc-for`, `sc-if`, `onClick`)을 브라우저에서 돌리는 최소 런타임 |
| `web/fgscene.json` | 결합 포즈 3D 장면 데이터 |
| `measurements/measurements.json` | 화면 수치의 원본 요약 |
| `measurements/nim/` | NVIDIA NIM 원본 응답 (MSA, OpenFold3, DiffDock, Boltz-2, 크리틱 평가) |
| `measurements/pub/` | ChEMBL ID·친화도, PARP1 벤치마크 세트 |

빌드 단계와 번들러가 없다. 화면의 수치는 전부 하드코딩된 상수이고 런타임에 API를 부르지 않는다.
원본은 `measurements/`에 있다.

## 실측 결과

### NVIDIA NIM (health.api.nvidia.com, 계정 키로 실제 호출)

| NIM | 결과 |
| --- | --- |
| MSA-Search | PARP1 상동 서열 101개 (Uniref30_2302), 63.6초 |
| OpenFold3 | pLDDT 95.95, pTM 0.828, ipTM 0.658 · 4R6E 결정 구조 대비 CA RMSD **1.0 Å**, 리간드 1.16 Å |
| DiffDock | 8조합. 재도킹 RMSD 니라파립@PARP1 **0.71 Å**, 아픽사반@Xa 0.56 Å, 셀레콕시브@COX-2 0.55 Å |
| Boltz-2 | 8조합 + PARP1 벤치마크 39종 친화도 예측 |
| OpenFold2 | **실패.** HTTP 500 CUDA 오류, 6회 시도. 서버측 장애라 OpenFold3로 갔다 |

MSA-Search → OpenFold3 조합은 NVIDIA 공식 스킬 `bionemo-msa-structure-prediction-pipeline`의 규격을 따랐다.

### 친화도 예측 벤치마크

ChEMBL에서 PARP1 IC50 활성 4,180건 → 고유 화합물 3,370종 → 활성 범위가 고루 퍼지도록 39종을 골랐다.
Boltz-2 예측을 ChEMBL pChEMBL 중앙값과 대조했다.

| 지표 | 값 |
| --- | --- |
| Spearman | 0.767 |
| Pearson | 0.746 |
| MAE | 0.71 log 단위 |
| Enrichment (상위 25%) | 2.41 (9개 중 5개) |
| 민감도 / 특이도 (pIC50 ≥ 7) | 0.80 / 0.86 |
| 포즈 RMSD ≤ 2 Å 성공률 | 3 / 3 (재도킹 대조) |

### 크리틱

평가 8건(과잉해석 4, 정상 4)으로 쟀다.

| 모델 | 과잉해석 적발 | 정상 통과 | 소요 |
| --- | --- | --- | --- |
| `nemotron-3-super-120b-a12b` | 4 / 4 | 3 / 4 | 41.8초 |
| `nemotron-3.5-lightning-30b-a3b` | 0 / 4 | 1 / 4 | 294.5초 |

Lightning의 0점은 성능이 아니라 출력 토큰 문제다. 추론에 토큰을 다 쓰고 `VERDICT:` 줄 전에 잘렸다.

정직하게 밝혀 둘 한계가 있다.

- 재도킹 RMSD 0.71 Å는 공결정 구조에 원래 리간드를 다시 넣은 대조 실험이다. 도킹 설정이 작동한다는 것 이상은 말하지 않는다.
- 4R6E는 공개 구조라 OpenFold3 학습 데이터에 있었을 수 있다.
- 친화도 벤치마크는 n=39, PARP1 한 타깃이다.
- 크리틱 평가 8건은 표본이 너무 작다.

## 실행

```bash
cd fly_discoverer/web && python3 -m http.server 8777   # http://localhost:8777 (fetch 때문에 정적 서버 필요)
```

## 고칠 때

- 색·간격 토큰은 `web/index.html`의 `:root`에 있다.
- 수치를 바꿀 때는 `measurements/`의 원본과 대조한다. 근거가 없으면 `미조회` 또는 `—`로 남기고 추정값을 채우지 않는다.
- 푸터의 크레딧 줄은 라이선스 요구사항이라 지우면 안 된다. 색·컴포넌트 토큰은 [FDDD](https://github.com/AwesomeZun/FDDD)(fly-connectome-template)에서 가져왔다.

원본은 [Geongyu/flygate](https://github.com/Geongyu/flygate)의 STEP 1 화면이다.
