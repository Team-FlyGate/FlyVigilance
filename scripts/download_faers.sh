#!/usr/bin/env bash
# FDA FAERS 분기별 ASCII 공개 데이터(2012Q4~최신)를 data/faers/raw 에 내려받는다.
# 이미 받은 파일은 건너뛰므로 재실행하면 신규 분기만 추가된다.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/data/faers/raw"
INDEX_URL="https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html"
mkdir -p "$DEST"

urls=$(curl -sL "$INDEX_URL" | grep -oE 'https?://[^"]+faers_ascii_[0-9]{4}[qQ][1-4]\.zip' | sort -u)

for url in $urls; do
  name=$(basename "$url" | tr 'Q' 'q')
  out="$DEST/$name"
  if [[ -s "$out" ]] && unzip -tq "$out" >/dev/null 2>&1; then
    echo "skip  $name"
    continue
  fi
  echo "fetch $name"
  curl -sSL --retry 3 --retry-delay 5 -o "$out.part" "$url"
  mv "$out.part" "$out"
done

echo "done: $(ls "$DEST"/*.zip | wc -l | tr -d ' ') files, $(du -sh "$DEST" | cut -f1)"
