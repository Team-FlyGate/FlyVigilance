#!/usr/bin/env bash
# FlyGate OpenShell 스모크 검사입니다. agent/policy/flygate.yaml 이 실제 샌드박스에서 강제되는지 명령과 출력으로 남깁니다.
#
#   1. 허용 목록의 호스트·경로는 파이썬으로 닿습니다 (openFDA 니라파립 라벨, PubMed, NVIDIA, TypeSafe).
#   2. 목록 밖 호스트(example.com, pastebin.com)는 막힙니다.
#   3. 허용 호스트라도 정책에 없는 실행 파일(curl), 경로, 메서드는 막힙니다.
#   4. /etc, /usr 쓰기는 실패하고 /tmp, /sandbox/.openclaw 쓰기는 됩니다.
#   5. 에이전트는 root 가 아닙니다.
#   6. flygate 코드를 올려 샌드박스 안에서 discover, signals, grade(--no-judge) 를 돌립니다.
#
# 사용법: SANDBOX=flygate-smoke agent/openshell_smoke.sh
# 결과: agent/evidence/openshell_smoke_<UTC 날짜>.txt. 'RESULT<TAB>PASS|FAIL<TAB>검사<TAB>기대<TAB>관찰' 줄을 export_agent_json.py 가 읽습니다.
# 이 스크립트는 지정한 샌드박스 하나에만 명령을 보냅니다. 다른 샌드박스의 정책을 바꾸거나 다시 시작하지 않습니다.
set -uo pipefail

SANDBOX="${SANDBOX:-flygate-smoke}"
case "$SANDBOX" in my-assistant) echo "my-assistant 에는 실행하지 않습니다" >&2; exit 2;; esac
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-$ROOT/.venv/bin/python}"
OUT="${OUT:-$ROOT/agent/evidence/openshell_smoke_$(date -u +%Y-%m-%d).txt}"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/flygate_stage.XXXXXX")"
PASS=0; FAIL=0

redact() { sed -E -e 's/\x1b\[[0-9;]*m//g' -e 's/(nvapi-|gho_|ghp_|sk-)[A-Za-z0-9_-]+/\1<REDACTED>/g' \
                  -e 's/([Bb]earer )[A-Za-z0-9._-]+/\1<REDACTED>/g' -e 's/((token|TOKEN|Token)[\"]?[:=][ \"]*)[A-Za-z0-9._-]{12,}/\1<REDACTED>/g'; }
log() { printf '%s\n' "$@" | redact | tee -a "$OUT"; }
t() { perl -e 'alarm shift; exec @ARGV' "$@"; }

# 샌드박스 안에서 sh 명령을 돌립니다. 따옴표가 여러 셸을 거쳐도 깨지지 않게 base64 로 감쌉니다.
# stdin 은 /dev/null 로 닫습니다(openshell sandbox exec 는 stdin 을 넘기므로 비대화형 실행에서 EOF 를 기다립니다).
sb() {
  local b64; b64="$(printf '%s' "$1" | base64 | tr -d '\n')"
  t 150 openshell sandbox exec -n "$SANDBOX" --no-tty --timeout 120 -- sh -c "echo $b64 | base64 -d | sh" </dev/null 2>&1
}

# 표준 라이브러리만 쓰는 HTTP 탐침입니다. 샌드박스의 HTTPS_PROXY 와 SSL_CERT_FILE(OpenShell CA)을 urllib 가 그대로 씁니다.
PROBE_B64="$(base64 <<'PYEOF' | tr -d '\n'
import json, sys, urllib.request, urllib.error
url, method = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "GET")
data = b"{}" if method == "POST" else None
req = urllib.request.Request(url, method=method, data=data,
                             headers={"User-Agent": "flygate-smoke/1.0", "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=25) as r:
        body = r.read()
        extra = ""
        if "drug/label.json" in url:
            res = json.loads(body)["results"][0]
            extra = " brand=%s set_id=%s" % (res["openfda"].get("brand_name"), res.get("set_id"))
        print("http=%d rc=0%s" % (r.status, extra))
except urllib.error.HTTPError as e:
    print("http=%d rc=0 body=%s" % (e.code, e.read(160).decode("utf-8", "replace").replace("\n", " ")))
except Exception as e:
    print("http=000 rc=7 err=%s %s" % (type(e).__name__, str(e)[:160]))
PYEOF
)"
probe() {  # probe <url> [METHOD]
  sb "echo $PROBE_B64 | base64 -d > /tmp/flygate_probe.py && python3 /tmp/flygate_probe.py '$1' ${2:-GET}; rm -f /tmp/flygate_probe.py"
}

record() {  # record PASS|FAIL <검사> <기대> <관찰>
  local obs; obs="$(printf '%s' "$4" | tr '\n\t' '  ' | redact | cut -c1-220)"
  [ "$1" = PASS ] && PASS=$((PASS + 1)) || FAIL=$((FAIL + 1))
  printf 'RESULT\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$obs" | tee -a "$OUT"
}

check_http() {  # check_http <검사> <url> <METHOD> <기대 정규식> <기대 설명>
  log "" "## $1" "\$ openshell sandbox exec -n $SANDBOX -- python3 probe.py '$2' $3"
  local o; o="$(probe "$2" "$3")"
  log "$o"
  if printf '%s' "$o" | grep -qE "$4"; then record PASS "$1" "$5" "$o"; else record FAIL "$1" "$5" "$o"; fi
}

check_sh() {  # check_sh <검사> <명령> <기대 정규식> <기대 설명>
  log "" "## $1" "\$ openshell sandbox exec -n $SANDBOX -- sh -c '$2'"
  local o; o="$(sb "$2")"
  log "$o"
  if printf '%s' "$o" | grep -qE "$3"; then record PASS "$1" "$4" "$o"; else record FAIL "$1" "$4" "$o"; fi
}

mkdir -p "$(dirname "$OUT")"
: > "$OUT"
log "# FlyGate OpenShell 스모크 검사"
log "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
log "sandbox: $SANDBOX   policy: agent/policy/flygate.yaml   host: macOS + Docker Desktop (openshell compute driver: docker)"
log "openshell: $(openshell --version 2>&1)   nemoclaw: $(t 20 nemoclaw --version 2>&1 | head -1)"
log "gateway: $(t 20 openshell status 2>&1 | redact | grep -E 'Gateway:|Server:|Status:' | tr -s ' ' | tr '\n' ' ')"
log "image: $(t 30 openshell sandbox get "$SANDBOX" -o yaml 2>/dev/null | grep -m1 -E 'image' | tr -s ' ' || echo 'ghcr.io/nvidia/nemoclaw/openclaw-sandbox (my-assistant 와 같은 이미지)')"

log "" "# 1. 프로세스 신원"
check_sh "non-root user" "id; whoami" "uid=[1-9][0-9]*\(sandbox\)" "uid != 0 (sandbox)"
check_sh "seccomp filter, no_new_privs, no capabilities" "grep -E '^(CapEff|NoNewPrivs|Seccomp):' /proc/self/status | tr '\n\t' '  '" "CapEff: *0+ .*NoNewPrivs: *1 .*Seccomp: *2" "CapEff 0, NoNewPrivs 1, Seccomp 2 (filter)"

log "" "# 2. 허용 목록 (파이썬)"
check_http "allowed openFDA niraparib label" "https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22niraparib%22&limit=1" GET "http=200 .*brand=" "HTTP 200 + label JSON"
check_http "allowed PubMed esearch" "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=niraparib+thrombocytopenia&retmax=1&retmode=json" GET "http=200" "HTTP 200"
check_http "allowed NVIDIA NIM models" "https://integrate.api.nvidia.com/v1/models" GET "http=200" "HTTP 200"
check_http "allowed TypeSafe POST /v1/systemone (no key sent)" "https://api.typesafe.ai/v1/systemone" POST "authentication_error|Must supply an API key" "origin auth error (request reached api.typesafe.ai)"

log "" "# 3. 허용 목록 밖 호스트"
check_http "denied example.com" "https://example.com/" GET "Tunnel connection failed: 403|http=000" "CONNECT 403"
check_http "denied pastebin.com" "https://pastebin.com/" GET "Tunnel connection failed: 403|http=000" "CONNECT 403"

log "" "# 4. 허용 호스트, 정책 밖 실행 파일·경로·메서드"
check_sh "denied curl to api.fda.gov (binary not bound)" "curl -sS -o /dev/null -w 'http=%{http_code}' 'https://api.fda.gov/drug/label.json?limit=1'; echo \" rc=\$?\"" "rc=56|CONNECT tunnel failed|403" "CONNECT 403 for /usr/bin/curl"
check_http "denied openFDA path not in rules (/drug/ndc.json)" "https://api.fda.gov/drug/ndc.json?limit=1" GET "http=403" "L7 403"
check_http "denied TypeSafe GET (method not in rules)" "https://api.typesafe.ai/v1/systemone" GET "http=403" "L7 403"

log "" "# 5. 파일시스템"
check_sh "denied write /etc" "echo x > /etc/flygate_probe; echo rc=\$?" "Permission denied|Read-only" "EACCES"
check_sh "denied write /usr" "echo x > /usr/flygate_probe; echo rc=\$?" "Permission denied|Read-only" "EACCES"
check_sh "allowed write /tmp" "echo x > /tmp/flygate_probe && echo write_ok; rm -f /tmp/flygate_probe" "write_ok" "write ok"
check_sh "allowed write /sandbox/.openclaw" "echo x > /sandbox/.openclaw/flygate_probe && echo write_ok; rm -f /sandbox/.openclaw/flygate_probe" "write_ok" "write ok"

log "" "# 6. flygate 를 샌드박스 안에서 실행"
# 올리는 것: agent/, api/_fv/, api/_data/, fly_discovery/measurements/, 순수 파이썬 의존성(httpx 등). .env 는 올리지 않습니다.
mkdir -p "$STAGE/flygate/api" "$STAGE/flygate/fly_discovery" "$STAGE/flygate/vendor"
cp -R "$ROOT/agent" "$STAGE/flygate/agent"; rm -rf "$STAGE/flygate/agent/evidence"
cp -R "$ROOT/api/_fv" "$ROOT/api/_data" "$STAGE/flygate/api/"
cp -R "$ROOT/fly_discovery/measurements" "$STAGE/flygate/fly_discovery/"
SITE="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
for pkg in httpx httpcore h11 anyio idna certifi typing_extensions.py; do cp -R "$SITE/$pkg" "$STAGE/flygate/vendor/"; done
# OpenClaw 작업 공간: 페르소나 파일 7개와 저장소 skills/*/SKILL.md
mkdir -p "$STAGE/workspace/skills"
cp "$ROOT"/agent/workspace/*.md "$STAGE/workspace/"
cp -R "$ROOT"/skills/* "$ROOT"/agent/skills/* "$STAGE/workspace/skills/"
find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
sb "rm -rf /sandbox/flygate /sandbox/.openclaw/workspace/memory" >/dev/null
log "" "\$ openshell sandbox upload $SANDBOX <stage>/flygate /sandbox   (결과: /sandbox/flygate)"
log "$(t 180 openshell sandbox upload "$SANDBOX" "$STAGE/flygate" /sandbox </dev/null 2>&1 | tail -1 | sed "s|$STAGE|<stage>|")"
log "" "\$ openshell sandbox upload $SANDBOX <stage>/workspace /sandbox/.openclaw   (결과: /sandbox/.openclaw/workspace)"
log "$(t 180 openshell sandbox upload "$SANDBOX" "$STAGE/workspace" /sandbox/.openclaw </dev/null 2>&1 | tail -1 | sed "s|$STAGE|<stage>|")"
FG="cd /sandbox/flygate && /sandbox/flygate/agent/bin/flygate"
SUMMARY='import json,sys; d=json.load(sys.stdin); print("cmd=%s keys=%d evidence_ids=%d first=%s" % (d.get("cmd"), len(d), len(d.get("evidence_ids") or []), (d.get("evidence_ids") or ["-"])[0]))'
check_sh "OpenClaw workspace files and skills in place" "cd /sandbox/.openclaw/workspace && echo \"\$(ls *.md | tr '\n' ' ')skills=\$(ls skills | wc -l | tr -d ' ')\"" \
  "SOUL.md.*TOOLS.md.*skills=12" "7 persona files + 12 skills"
check_sh "flygate discover parp1 in sandbox" "$FG discover parp1 | python3 -c '$SUMMARY'" "cmd=discover .*evidence_ids=[1-9]" "JSON with evidence IDs"
check_sh "flygate signals NIRAPARIB in sandbox" "$FG signals NIRAPARIB --pt thrombocytopenia | python3 -c '$SUMMARY'" "cmd=signals .*evidence_ids=[1-9]" "JSON with evidence IDs"
check_sh "flygate grade NIRAPARIB thrombocytopenia --no-judge in sandbox (live openFDA + PubMed through the policy)" \
  "$FG grade NIRAPARIB thrombocytopenia --no-judge | python3 -c '$SUMMARY'" "cmd=grade .*evidence_ids=[1-9]" "JSON with label and PubMed evidence IDs"
WATCH='import json,sys; d=json.load(sys.stdin); print("cmd=%s quarter=%s pairs=%d queue=%d submitted=%s persona_same=%s note=%s" % (d["cmd"], d["quarter"]["quarter"], len(d["watchlist"]), len(d["review_queue"]), d["submitted"], all(v["same"] for v in d["workspace"].values()), d["memory_note"]))'
check_sh "flygate watch (heartbeat) in sandbox: memory note under /sandbox/.openclaw, nothing submitted" \
  "$FG watch --online --memory-dir /sandbox/.openclaw/workspace/memory --workspace /sandbox/.openclaw/workspace | python3 -c '$WATCH'" \
  "submitted=\[\] persona_same=True note=/sandbox/.openclaw/workspace/memory/" "memory note written, submitted=[]"
rm -rf "$STAGE"

log "" "# 7. 감사 로그 원문 (openshell logs $SANDBOX --since 20m, DENIED 만)"
log "$(t 60 openshell logs "$SANDBOX" --since 20m -n 800 </dev/null 2>/dev/null | redact | grep -aE 'DENIED' | tail -12 || true)"
log "" "# 8. 유효 정책 (openshell policy get $SANDBOX --full, 앞부분)"
log "$(t 60 openshell policy get "$SANDBOX" --full </dev/null 2>&1 | redact | head -24)"
log "" "summary: pass=$PASS fail=$FAIL"
echo "결과 파일: $OUT (pass=$PASS fail=$FAIL)"
[ "$FAIL" -eq 0 ]
