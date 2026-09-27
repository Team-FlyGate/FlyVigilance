#!/usr/bin/env bash
# MaleCNS v1.0 (Janelia FlyEM, CC-BY 4.0) 원본을 data/malecns 에 받는다.
#  1) flat-connectome 핵심 feather 4개 (약 1.8GB)
#  2) 뇌 neuropil ROI 메시 (scripts/download_malecns_rois.py)
#  3) 선택 뉴런 SWC 스켈레톤 (약 3.9GB, 49,244개) — data/derived/connectome/swc_ids.txt 가 필요
#     (pipeline/connectome/select_subgraph.py 를 먼저 돌리거나 scripts/fetch_data.sh 로 받는다)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome"
FC="$ROOT/data/malecns/flat-connectome"
mkdir -p "$FC" "$ROOT/data/malecns/swc"

for f in body-annotations-male-cns-v1.0-minconf-0.5.feather body-neurotransmitters-male-cns-v1.0.feather \
         body-stats-male-cns-v1.0-minconf-0.5.feather connectome-weights-male-cns-v1.0-minconf-0.5.feather; do
  echo "fetch $f"
  curl -sSL --retry 3 -C - -o "$FC/$f" "$BASE/$f"
done

python3 "$ROOT/scripts/download_malecns_rois.py"

IDS="$ROOT/data/derived/connectome/swc_ids.txt"
if [ -f "$IDS" ]; then
  echo "fetch $(wc -l < "$IDS" | tr -d ' ') SWC skeletons"
  xargs -P 48 -I{} sh -c 'f="'"$ROOT"'/data/malecns/swc/{}.swc"; [ -s "$f" ] || curl -sf --retry 3 -o "$f" "https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/{}.swc"' < "$IDS"
else
  echo "skip SWC: $IDS 없음"
fi
echo "done: $(du -sh "$ROOT/data/malecns" | cut -f1)"
