#!/usr/bin/env bash
# 핵심 파생 데이터(FAERS DuckDB 웨어하우스, 커넥텀 파생물)를 GitHub Release data-v1 에서 받아 data/ 에 복원한다.
# 원천 데이터(FAERS 분기 zip, MaleCNS 원본)는 공개 출처에서 다시 받는다:
#   ./scripts/download_faers.sh            # FAERS 분기 zip (약 2.8GB)
#   python3 scripts/download_malecns_rois.py # MaleCNS ROI 메시 (flat-connectome, SWC 는 docs/MaleCNS_데이터.md 참고)
# 필요: gh(로그인) 또는 curl, zstd
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="AwesomeZun/Project-FlyGate"   # 데이터 릴리스(5.3GB)는 이 저장소에 둡니다
TAG="data-v1"
TMP="$ROOT/data/.download"
mkdir -p "$TMP"
cd "$TMP"

if command -v gh >/dev/null; then
  gh release download "$TAG" --repo "$REPO" --pattern "flyvigilance-data-v1.*" --pattern "SHA256SUMS" --skip-existing
else
  for f in $(curl -s "https://api.github.com/repos/$REPO/releases/tags/$TAG" | grep -o '"browser_download_url": "[^"]*"' | cut -d'"' -f4); do
    [ -s "$(basename "$f")" ] || curl -L --retry 5 -o "$(basename "$f")" "$f"
  done
fi

shasum -a 256 -c SHA256SUMS
cat flyvigilance-data-v1.tar.zst.part-* | zstd -d -T0 | tar -xf - -C "$ROOT"
echo "restored: $(du -sh "$ROOT/data/derived" | cut -f1) in data/derived"
echo "원한다면 조각 파일 삭제: rm -rf \"$TMP\""
