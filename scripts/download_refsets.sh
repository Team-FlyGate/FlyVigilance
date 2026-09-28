#!/usr/bin/env bash
# 공개 참조 세트 원본을 data/refsets 에 받습니다 (pipeline/refsets/build_refsets.py 입력).
#   OMOP (Ryan et al. 2013), EU-ADR (Coloma et al. 2013): OHDSI MethodEvaluation 패키지 데이터, Apache-2.0
#   Time-indexed reference standard (Harpaz et al. 2014): figshare collection 1133904, CC0
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/refsets
for f in omopReferenceSet euadrReferenceSet; do
  curl -fL --http1.1 -o "data/refsets/$f.rda" "https://raw.githubusercontent.com/OHDSI/MethodEvaluation/main/data/$f.rda"
done
curl -fL --http1.1 -o data/refsets/timeIndexedReferenceStandard.xls "https://ndownloader.figshare.com/files/3210944"
ls -l data/refsets
