# MaleCNS 커넥텀 데이터

작성일: 2026-09-25

MaleCNS는 Janelia FlyEM 팀과 Cambridge Drosophila Connectomics Group이 공개한 **수컷 초파리 중추신경계(뇌 + 복부신경삭 VNC) 전체 커넥텀**이다. 뉴런 약 166,700개, 세포 유형 11,710개를 담고 있고, 라이선스는 CC-BY다.

> 참고: FlyWire(FAFB)는 **암컷 뇌**만 다룬 별도 데이터셋이다(Princeton 주도, https://codex.flywire.ai). MaleCNS는 FlyWire가 아니라 Janelia FlyEM이 배포한다.

- 공식 사이트: https://male-cns.janelia.org/
- 다운로드 안내: https://male-cns.janelia.org/download/
- 원본 버킷: `gs://flyem-male-cns/v1.0/` (HTTPS: `https://storage.googleapis.com/flyem-male-cns/...`)

## 받아둔 파일

### `data/malecns/flat-connectome/` (Feather 형식, 약 1.8GB)

| 파일 | 크기 | 내용 | 시각화 용도 |
| --- | --- | --- | --- |
| body-annotations-male-cns-v1.0-minconf-0.5.feather | 14MB | 뉴런별 class, type, side 등 주석 | 뉴런 분류, 색상 구분 |
| body-neurotransmitters-male-cns-v1.0.feather | 41MB | 뉴런별 신경전달물질 예측 (ACh, GABA, Glu 등) | 흥분성/억제성 신호 부호 결정 |
| body-stats-male-cns-v1.0-minconf-0.5.feather | 742MB | 뉴런별 통계, ROI별 시냅스 수 | 뉴런이 어느 뇌 영역에 속하는지 |
| connectome-weights-male-cns-v1.0-minconf-0.5.feather | 1.0GB | 뉴런 간 연결 그래프 (pre → post, 시냅스 수) | 활성화 전파 시뮬레이션의 핵심 |

`minconf-0.5`는 시냅스 검출 신뢰도 0.5 이상만 포함했다는 뜻이다.

### `data/malecns/rois/` (neuroglancer precomputed 메시, 약 190MB)

| 디렉터리 | 내용 |
| --- | --- |
| fullbrain-roi-v4/ | 뇌 neuropil 영역 메시 (mesh/, segment_properties/, info) |
| malecns-vnc-neuropil-roi-v0/ | VNC neuropil 영역 메시 |

뇌 외곽과 각 영역(버섯체, 중심복합체, 시엽 등)을 3D로 렌더링하는 데 쓴다. `segment_properties/info`에 ROI id와 이름의 매핑이 있다.

재다운로드: `python3 scripts/download_malecns_rois.py`

## 받지 않은 파일 (필요할 때 추가)

| 경로 | 크기 | 쓰임 |
| --- | --- | --- |
| flat-connectome/syn-points-...feather | 12.7GB | 시냅스 개별 좌표. 시냅스 단위로 점을 찍어 시각화할 때 |
| flat-connectome/syn-partners-...feather | 6.8GB | 시냅스별 pre/post 짝 |
| flat-connectome/tbar-neurotransmitters-...feather | 2.7GB | 시냅스별 신경전달물질 확률 |
| v1.0/segmentation/skeletons-malecns/skeletons-swc/ | 뉴런당 수 KB~수백 KB | 뉴런 형태(선). 뉴런 단위 발화 시각화에 필요. `{bodyId}.swc` 로 개별 요청 가능 |
| v1.0/segmentation/skeletons-unisex-template/ | - | JRC2018 unisex 템플릿 좌표계 스켈레톤 (µm 단위) |
| v1.0/segmentation (메시 포함) | 대용량 | 뉴런 표면 메시 |
| v1.0/database/neo4j | 대용량 | neuPrint 전체 DB |

## 활성화 시각화 구상 메모

1. `connectome-weights`로 방향성 가중 그래프를 만든다.
2. `body-neurotransmitters`로 연결의 부호를 정한다 (ACh는 +, GABA·Glu는 대개 −).
3. 입력 뉴런 집합(예: 특정 감각 뉴런)을 자극하고 전파 모델(선형 전파, LIF 등)로 시간 단계별 활성도를 계산한다.
4. 활성도를 ROI 단위(`body-stats`)로 집계하여 ROI 메시 색을 바꾸거나, 주요 뉴런은 SWC 스켈레톤을 불러 개별로 빛나게 한다.
5. 좌표 단위: 원본 공간은 8nm 복셀, precomputed 스켈레톤은 1nm. 좌표를 섞을 때 단위를 맞춰야 한다.

## 읽기 예시 (Python)

```python
import pandas as pd  # pyarrow 필요: pip install pandas pyarrow
base = "data/malecns/flat-connectome/"
ann = pd.read_feather(base + "body-annotations-male-cns-v1.0-minconf-0.5.feather")
w = pd.read_feather(base + "connectome-weights-male-cns-v1.0-minconf-0.5.feather")
```

현재 시스템 Python에는 `pyarrow`가 설치되어 있지 않아 컬럼 구조는 아직 확인하지 않았다. 프로젝트 가상환경을 만든 뒤 확인할 것.
