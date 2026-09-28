#!/usr/bin/env bash
# FlyGate 를 NemoClaw 스택(OpenShell 샌드박스 + OpenClaw 하네스)에 올립니다.
#
#   agent/deploy_nemoclaw.sh worker      OpenShell 샌드박스를 새로 만들고 flygate 도구·작업 공간·스킬을 올립니다(스모크 검사와 같은 방식).
#   agent/deploy_nemoclaw.sh assistant   이미 `nemoclaw onboard` 로 만든 OpenClaw 비서에 FlyGate 정책 프리셋, 도구, 작업 공간, 스킬, cron 을 더합니다.
#
# 환경변수
#   SANDBOX=flygate            대상 샌드박스 이름입니다. my-assistant 는 거부합니다(다른 용도의 비서입니다).
#   IMAGE=...                  worker 모드의 이미지입니다. 기본값은 NemoClaw OpenClaw 샌드박스 이미지입니다.
#   PROVIDERS="--provider nvidia-prod --provider typesafe"   worker 모드에서 붙일 자격 증명 provider 입니다(키는 프록시가 넣습니다).
#   DRY_RUN=1                  명령만 출력하고 실행하지 않습니다.
# 이 스크립트는 보고서를 보내는 경로를 만들지 않습니다. cron 작업은 --no-deliver 로 등록합니다.
set -euo pipefail

MODE="${1:-worker}"
SANDBOX="${SANDBOX:-flygate}"
IMAGE="${IMAGE:-ghcr.io/nvidia/nemoclaw/openclaw-sandbox@sha256:7dcb6046542110dc21d128377be5d49c53204b5ed9b54b70fb8370c8e695f5c1}"
PROVIDERS="${PROVIDERS:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-$ROOT/.venv/bin/python}"
case "$SANDBOX" in my-assistant) echo "my-assistant 에는 배포하지 않습니다. SANDBOX 를 다른 이름으로 주세요." >&2; exit 2;; esac

run() { echo "+ $*"; [ -n "${DRY_RUN:-}" ] || "$@"; }

# 샌드박스에 올릴 묶음입니다: agent/, api/_fv/, api/_data/, fly_discovery/measurements/, 순수 파이썬 의존성(vendor/). .env 는 넣지 않습니다.
stage() {
  STAGE="$(mktemp -d "${TMPDIR:-/tmp}/flygate_stage.XXXXXX")"
  mkdir -p "$STAGE/flygate/api" "$STAGE/flygate/fly_discovery" "$STAGE/flygate/vendor"
  cp -R "$ROOT/agent" "$STAGE/flygate/agent"
  rm -rf "$STAGE/flygate/agent/evidence"
  cp -R "$ROOT/api/_fv" "$ROOT/api/_data" "$STAGE/flygate/api/"
  cp -R "$ROOT/fly_discovery/measurements" "$STAGE/flygate/fly_discovery/"
  local site; site="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
  for pkg in httpx httpcore h11 anyio idna certifi typing_extensions.py; do cp -R "$site/$pkg" "$STAGE/flygate/vendor/"; done
  # OpenClaw 작업 공간: 페르소나 파일과 스킬(저장소 skills/*/SKILL.md)
  mkdir -p "$STAGE/workspace/skills"
  cp "$ROOT"/agent/workspace/*.md "$STAGE/workspace/"
  cp -R "$ROOT"/skills/* "$ROOT"/agent/skills/* "$STAGE/workspace/skills/"
  find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
  echo "stage: $STAGE"
}

# network_policies 만 NemoClaw 프리셋 형식으로 옮깁니다(NemoClaw 하네스 내부 경로는 청사진 기본 정책에 이미 있습니다).
preset() {
  "$PY" - "$ROOT/agent/policy/flygate.yaml" "$1" <<'PYEOF'
import sys, yaml
src, dst = sys.argv[1], sys.argv[2]
p = yaml.safe_load(open(src))
internal = {"managed_inference", "openclaw_gateway_dialback"}
nets = {k: v for k, v in p["network_policies"].items() if k not in internal}
yaml.safe_dump({"preset": {"name": "flygate", "description": "FlyGate: openFDA, PubMed, TypeSafe judgment, NVIDIA NIM, BioNeMo NIM (python only)"},
                "network_policies": nets}, open(dst, "w"), sort_keys=False, allow_unicode=True)
print("preset:", dst, sorted(nets))
PYEOF
}

CRON_MSG="HEARTBEAT.md 의 정기 점검 목록을 따르세요. flygate watch 를 실행하고 review_queue 를 근거 ID 와 함께 요약합니다. 아무것도 제출하거나 보내지 않습니다."

case "$MODE" in
  worker)
    stage
    # shellcheck disable=SC2086
    run openshell sandbox create --name "$SANDBOX" --from "$IMAGE" --policy "$ROOT/agent/policy/flygate.yaml" \
        --no-auto-providers $PROVIDERS --label app=flygate --detach --no-tty -- sleep infinity </dev/null
    run openshell sandbox upload "$SANDBOX" "$STAGE/flygate" /sandbox </dev/null
    run openshell sandbox upload "$SANDBOX" "$STAGE/workspace" /sandbox/.openclaw </dev/null
    run openshell sandbox exec -n "$SANDBOX" --no-tty --timeout 120 -- /sandbox/flygate/agent/bin/flygate discover parp1 </dev/null
    echo "검사: SANDBOX=$SANDBOX agent/openshell_smoke.sh"
    ;;
  assistant)
    stage
    preset "$STAGE/flygate-preset.yaml"
    run nemoclaw "$SANDBOX" policy add --from-file "$STAGE/flygate-preset.yaml" --yes
    run nemoclaw "$SANDBOX" upload "$STAGE/flygate" /sandbox
    run nemoclaw "$SANDBOX" upload "$STAGE/workspace" /sandbox/.openclaw
    for d in "$ROOT"/skills/*/ "$ROOT"/agent/skills/*/; do run nemoclaw "$SANDBOX" skill install "$d"; done
    # 하트비트와 별도로 매일 07:00(서울) 격리 세션에서 같은 점검을 돌립니다. 결과는 채팅으로 내보내지 않습니다(--no-deliver).
    run nemoclaw "$SANDBOX" exec --no-tty -- openclaw cron add --name flygate-daily-watch --cron "0 7 * * *" --tz Asia/Seoul \
        --session isolated --tools exec,read,write --no-deliver --message "$CRON_MSG"
    run nemoclaw "$SANDBOX" exec --no-tty -- /sandbox/flygate/agent/bin/flygate discover parp1
    run nemoclaw "$SANDBOX" policy explain
    ;;
  *)
    echo "사용법: $0 worker|assistant" >&2; exit 2;;
esac
