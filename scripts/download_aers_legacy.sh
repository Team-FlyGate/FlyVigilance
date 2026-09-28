#!/usr/bin/env bash
# FDA 구형 AERS 분기 파일(2004Q1~2012Q3)을 받습니다. 참조 세트의 전향적 검증(2013년 라벨 변경 이전 데이터)에만 씁니다.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/data/aers_legacy"
mkdir -p "$DEST"
for y in $(seq 2004 2012); do
  for q in 1 2 3 4; do
    [ "$y" = 2012 ] && [ "$q" = 4 ] && break
    f="aers_ascii_${y}q${q}.zip"
    if [ -s "$DEST/$f" ] && unzip -tq "$DEST/$f" >/dev/null 2>&1; then echo "skip $f"; continue; fi
    echo "fetch $f"
    curl -sSL --http1.1 --retry 5 -o "$DEST/$f.part" "https://fis.fda.gov/content/Exports/$f" && mv "$DEST/$f.part" "$DEST/$f"
  done
done
echo "done: $(ls "$DEST"/*.zip | wc -l | tr -d ' ') files, $(du -sh "$DEST" | cut -f1)"
