"""Project-FlyGate 쇼릴 v4.3.0 을 만듭니다. v4.2.0 의 CLI 세 장면(18–20번)을 실제 터미널 캡처로 다시 짠 판입니다.

v4.1.0 · v4.2.0 의 속도 규칙은 그대로입니다(내레이션 초당 6.3음절 · 꼬리 0.8초 이하 · 늘 움직이는 층 · 멈춘 구간 0% 목표).
바뀐 점:
  1) CLI 구간을 CC-statusline 모션 릴 문법으로 다시 짭니다.
       cli_open     "> flygate" 가 한 글자씩 입력된 뒤 거대한 'FlyGate Agent CLI'
       cli_install … cli_watch
                    명령마다 거대한 낱말 하나(INSTALL · TRIAGE · GRADE · CRITIC · DOCK · KR · WATCH)와
                    그 명령의 실제 터미널 캡처(web/public/cli/captures/*.png)를 3D로 기울인 창에 띄우고, 핵심 줄로 확대합니다.
       cli_same     사람도 에이전트도 같은 명령(OpenShell 샌드박스 안 OpenClaw exec · 스모크 통과 수)
       cli_line     설치 한 줄 + 저장소 주소 마무리 카드
     캡처는 원본 크기(2배율) 그대로 WebP 로 HTML 안에 넣습니다(파일 하나로 완결).
     확대할 줄의 자리는 캡처의 터미널 격자를 재고 원본 터미널 바이트(ansi/*.ans)에서 줄 번호를 세어 정합니다(KEYS).
     화면 설명 · 내레이션의 수치도 그 바이트에 찍힌 JSON 에서 읽습니다. 캡처가 없으면 cli_runs.json 의 줄로 대신 그립니다.
  2) 나머지 장면 · 수치 · 틀 · 구호는 v4.2.0 과 같습니다.

v4.2.0 의 파일(build_reel_v4_2.py, flygate_v4_2.template.html, 타임라인 · 대본 · 음원)은 고치지 않습니다.

사용:
  .venv/bin/python scripts/build_reel_v4_3.py [출력 경로]
출력:
  web/public/showreel/FlyGate_showreel_v4.3.0.html · scripts/reel/flygate_v4_3.timeline.json · docs/SHOWREEL_SCRIPT_v4.3.0.md
음원:
  .venv/bin/python scripts/reel/audio_v4_3.py
"""
import base64
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_reel_v3 as v3  # noqa: E402
import build_reel_v4 as v4  # noqa: E402
import build_reel_v4_1 as v41  # noqa: E402
import build_reel_v4_2 as v42  # noqa: E402  CLI 실행 기록 · 약어 풀이 · 구호를 그대로 씁니다

VERSION = "4.3.0"
ROOT, PUB, REEL = v4.ROOT, v4.PUB, v4.REEL
TEMPLATE = REEL / "flygate_v4_3.template.html"
DEFAULT_OUT = PUB / f"showreel/FlyGate_showreel_v{VERSION}.html"
TIMELINE_OUT = REEL / "flygate_v4_3.timeline.json"
SCRIPT_OUT = ROOT / f"docs/SHOWREEL_SCRIPT_v{VERSION}.md"
AUDIO_REL = f"scripts/reel/FlyGate_showreel_v{VERSION}_audio.m4a"
CAP_DIR = PUB / "cli/captures"
CAP_MANIFEST = PUB / "cli/captures.json"
FALLBACKS = v4.FALLBACKS
syllables, mmss = v4.syllables, v4.mmss
RATE, GAP, CLOSE_MAX = v41.RATE, v41.GAP, v41.CLOSE_MAX
LEAD, TAIL = v41.LEAD, v41.TAIL
ceil1 = v41.ceil1
SLOGAN_PARTS, SIGN_OFF, slogan_read = v42.SLOGAN_PARTS, v42.SIGN_OFF, v42.slogan_read
INSTALL_LINE = "git clone https://github.com/Team-FlyGate/Project-FlyGate && cd Project-FlyGate && ./scripts/install_flygate.sh"

v4.LATIN.update({"kr-causality는": 8, "discover는": 5, "DiffDock": 4, "NIM에": 3, "OpenClaw도": 5, "OpenClaw": 4, "watch는": 3,
                 "critic은": 4, "grade는": 4, "triage는": 5, "CLI,": 3, "CLI를": 4, "CLI": 3})

# 캡처는 원본 크기(2배율, 가로 2452px) 그대로 WebP 로 넣습니다. 확대 장면에서 화면 1px 에 캡처 1px 가까이 쓰므로 줄이지 않습니다
CAP_MAX_W = 2452
CAP_Q = 84
COLS = 110   # 캡처 터미널의 열 수(manifest: 110열)

# 캡처 이름 → 핵심 줄. (정규식, 이름, 묶는 방식, 최대 열)
#   정규식은 캡처의 원본 터미널 바이트(ansi/*.ans)를 글자로 푼 줄(논리 줄)에 맞춥니다. 논리 줄이 110열을 넘어 접히면 접힌 화면 줄까지 덮습니다.
#   'block' 은 그 줄부터 ']' 로 끝나는 줄까지, 'cmds' 는 도움말의 명령 줄(들여쓴 명령 이름)이 이어지는 동안 묶습니다.
#   최대 열을 주면 상자의 오른쪽 끝을 그 열에서 자릅니다(긴 줄의 앞부분만 확대할 때).
KEYS = {
    "install": [(r"^설치했습니다", "installed"), (r"every command prints JSON", "desc"), (r"^    (login|chat|triage|grade|signals|kr-causality|critic|discover|watch)\s", "cmds", "cmds", 34)],
    "triage": [(r'"action"', "action"), (r'"tier"', "tier"), (r'"brand"', "brand"), (r'"thrombocytopenia": true', "listed"), (r'"evidence_ids"', "ev", "block")],
    "grade": [(r'^  "grade"', "grade"), (r'"grade_name"', "grade_name"), (r'"pv_class_name"', "class"), (r'"summary"', "summary"), (r'"prr"', "prr"), (r'"evidence_ids"', "ev", "block")],
    "critic": [(r'"verdict"', "verdict"), (r'"issues"', "issues", "block"), (r'"safe"', "safe"), (r'"flagged"', "flagged", "block"), (r'"model"', "model"), (r'"evidence_ids"', "ev", "block")],
    "discover_live": [(r'"status"', "status"), (r'"run_id"', "run"), (r'"endpoint"', "endpoint"), (r'"confidence"', "conf", "block"), (r'"evidence_ids"', "ev", "block")],
    "kr_causality": [(r'"total"', "total"), (r'"grade"', "grade"), (r'"band"', "band"), (r'"who_umc"', "who"), (r'"action"', "action"), (r'"deadline"', "deadline", None, 34), (r'"evidence_ids"', "ev", "block")],
    "watch": [(r'"quarter"', "quarter"), (r'"watchlist"', "watchlist", "block"), (r'"review_queue"', "queue"), (r'"submitted"', "submitted"), (r'"note"', "note")],
}
KEYS["discover-live"], KEYS["kr-causality"], KEYS["help"] = KEYS["discover_live"], KEYS["kr_causality"], KEYS["install"]


# =====================================================================
#  실제 터미널 캡처 → WebP(data URI) + 핵심 줄 자리 + 화면에 보이는 값
# =====================================================================
def _probe_size(p: pathlib.Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


def _gray(p: pathlib.Path):
    import numpy as np
    w, h = _probe_size(p)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w).astype(float)


def _grid(p: pathlib.Path) -> dict:
    """캡처에서 터미널 격자를 잽니다: 줄 간격(pitch) · 첫 줄 가운데(c0) · 글자 폭(cw) · 왼쪽 끝(left). 좌표는 원본 픽셀입니다.
    제목 막대 아래의 글자 띠(가로 투영)를 찾아, 띠 가운데가 같은 간격의 격자에 가장 잘 맞는 간격을 고릅니다."""
    import numpy as np
    g = _gray(p)
    h, w = g.shape
    bg = np.median(g[h // 2, w // 4: 3 * w // 4])
    med = np.median(g[:, w // 4: 3 * w // 4], axis=1)
    top = next(y for y in range(10, h - 20) if np.all(np.abs(med[y:y + 20] - bg) < 3))
    ink = g[top:h - 10, 20:w - 20] > bg + 45
    on = ink.sum(1) > 0
    bands, y = [], 0
    while y < len(on):
        if on[y]:
            y0 = y
            while y < len(on) and on[y]:
                y += 1
            if y - y0 >= 6:
                bands.append((y0 + top, y - 1 + top))
        y += 1
    c = np.array([(a + b) / 2 for a, b in bands])
    best = min(((((c - c[0] - np.round((c - c[0]) / q) * q) ** 2).sum(), q) for q in np.arange(50, 62, 0.01)))
    b0 = bands[0]
    left = int(np.where(ink[b0[0] - top:b0[1] - top + 1].any(0))[0].min() + 20)
    right = int(np.where(ink.any(0))[0].max() + 20)
    return {"pitch": float(best[1]), "c0": float(c[0]), "left": left, "cw": (right - left) / (COLS - 0.5)}


def _dw(ch: str) -> int:
    import unicodedata
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _screen(ans: pathlib.Path) -> list[dict]:
    """원본 터미널 바이트를 논리 줄로 풉니다(색 코드 제거, \\r 로 덮어쓴 진행 표시는 마지막 모습). 줄마다 화면 줄 시작 번호와 접힌 줄 수를 붙입니다."""
    t = ans.read_bytes().decode("utf-8", errors="replace")   # read_text 는 홀로 쓴 \r 을 줄바꿈으로 바꾸므로 바이트로 읽습니다
    t = re.sub(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)", "", t)
    t = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", t)
    t = re.sub(r"\x1b[()][A-Za-z0-9]", "", t)
    out, row = [], 0
    for ln in t.replace("\r\n", "\n").split("\n"):
        cur = []
        for part in ln.split("\r"):
            part = list(part)
            cur = part + cur[len(part):]
        s = "".join(cur).rstrip()
        width = sum(_dw(ch) for ch in s)
        n = max(1, -(-width // COLS))
        out.append({"text": s, "row": row, "rows": n, "width": width})
        row += n
    while out and not out[-1]["text"]:
        out.pop()
    return out


def _key_boxes(name: str, lines: list[dict], G: dict) -> list[dict]:
    keys, used = [], set()
    for spec in KEYS.get(name, []):
        rx, kid = spec[0], spec[1]
        mode = spec[2] if len(spec) > 2 else None
        maxc = spec[3] if len(spec) > 3 else None
        idx = [i for i, q in enumerate(lines) if i not in used and re.search(rx, q["text"])]
        if not idx:
            FALLBACKS.append(f"{name}: 핵심 줄 '{kid}' 을 찾지 못함")
            continue
        i0 = i1 = idx[0]
        if mode == "block":
            while i1 + 1 < len(lines) and i1 - i0 < 12 and not lines[i1]["text"].rstrip().rstrip(",").endswith("]"):
                i1 += 1
        elif mode == "cmds":
            while i1 + 1 < len(lines) and re.match(spec[0], lines[i1 + 1]["text"]):
                i1 += 1
        used.update(range(i0, i1 + 1))
        seg = lines[i0:i1 + 1]
        c0 = min(len(q["text"]) - len(q["text"].lstrip()) for q in seg)
        c1 = min(COLS, max(q["width"] for q in seg))
        if maxc:
            c1 = min(c1, maxc)
        r0, r1 = seg[0]["row"], seg[-1]["row"] + seg[-1]["rows"]
        y0 = G["c0"] - G["pitch"] / 2 + r0 * G["pitch"]
        keys.append({"id": kid, "rows": [r0, r1], "text": " / ".join(q["text"].strip() for q in seg)[:200],
                     "box": [round(G["left"] + c0 * G["cw"] - 12), round(y0 - 4), round(G["left"] + c1 * G["cw"] + 12), round(y0 + (r1 - r0) * G["pitch"] + 4)]})
    return keys


def _values(name: str, lines: list[dict]) -> dict:
    """화면에 보이는 값: 명령 줄 다음의 JSON 을 그대로 읽습니다(도움말은 명령 목록)."""
    txt = [q["text"] for q in lines]
    if name in ("install", "help"):
        cmds = [m.group(1) for s in txt if (m := re.match(r"^    (\S+)\s{2,}\S", s))]
        return {"cmds": cmds, "installed": next((s for s in txt if s.startswith("설치했습니다")), "")}
    try:
        i0 = txt.index("{")
        i1 = max(i for i, s in enumerate(txt) if s == "}")
        return json.loads("\n".join(txt[i0:i1 + 1]))
    except (ValueError, json.JSONDecodeError):
        FALLBACKS.append(f"{name}: 화면 JSON 을 읽지 못함")
        return {}


def _manifest_entries() -> list[dict]:
    """captures.json 의 captures 목록(또는 {이름: 항목})을 읽습니다."""
    m = v3.jload_opt(CAP_MANIFEST)
    if not m:
        return []
    items = m.get("captures", m) if isinstance(m, dict) else m
    if isinstance(items, dict):
        items = [{"name": k, **(v if isinstance(v, dict) else {"file": v})} for k, v in items.items()]
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        f = it.get("file") or it.get("png") or it.get("path")
        name = it.get("name") or (pathlib.Path(f).stem if f else None)
        if not f or not name:
            continue
        res = lambda rel: next((b / rel for b in (PUB, CAP_MANIFEST.parent, CAP_DIR, ROOT) if (b / rel).exists()), pathlib.Path(rel))
        out.append({**it, "name": name, "path": res(f), "ans_path": res(it["ansi"]) if it.get("ansi") else None})
    return out


def caps_part() -> dict:
    caps = {}
    for it in _manifest_entries():
        p = it["path"]
        if not p.exists():
            FALLBACKS.append(f"캡처 {it['name']} 파일 없음({p}) → 실행 기록 줄로 대신 그림")
            continue
        w0, h0 = _probe_size(p)
        w = min(w0, CAP_MAX_W)
        h = round(h0 * w / w0)
        k = w / w0
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "c.webp"
            subprocess.run(["cwebp", "-quiet", "-q", str(CAP_Q), "-m", "6", "-alpha_q", "100", "-resize", str(w), str(h), str(p), "-o", str(out)], check=True)
            b = out.read_bytes()
        keys, vals, lines = [], {}, []
        if it.get("ans_path") and it["ans_path"].exists():
            G = _grid(p)
            lines = _screen(it["ans_path"])
            keys = _key_boxes(it["name"], lines, G)
            for q in keys:
                q["box"] = [round(v * k) for v in q["box"]]
            vals = _values(it["name"], lines)
        else:
            FALLBACKS.append(f"캡처 {it['name']}: 터미널 원본 바이트 없음 → 확대할 줄 없이 씁니다")
        rel = str(p.resolve().relative_to(ROOT))
        caps[it["name"]] = {"src": "data:image/webp;base64," + base64.b64encode(b).decode(), "w": w, "h": h, "orig": [w0, h0],
                            "file": rel, "kb": round(len(b) / 1024), "cmd": it.get("cmd"), "when": it.get("captured_at_utc"),
                            "seconds": it.get("seconds"), "exit": it.get("exit_code"), "keys": keys, "vals": vals,
                            "text": "\n".join(q["text"] for q in lines)}
    return caps


# 장면 → 캡처 이름 후보(앞에 있는 것부터 씁니다)
SCENE_CAP = {"cli_install": ["install", "help"], "cli_triage": ["triage"], "cli_grade": ["grade"], "cli_critic": ["critic"],
             "cli_dock": ["discover_live", "discover-live"], "cli_kr": ["kr_causality", "kr-causality"], "cli_watch": ["watch"]}


def pick_caps(caps: dict) -> dict:
    out = {}
    for sid, names in SCENE_CAP.items():
        for n in names:
            if n in caps:
                out[sid] = n
                break
        else:
            FALLBACKS.append(f"{sid}: 캡처 없음 → 실행 기록 줄로 대신 그림")
    return out


# =====================================================================
#  CLI 구간 값: 화면에 보이는 값은 캡처(원본 터미널 바이트의 JSON)에서, 캡처가 없으면 실행 기록(cli_runs.json)에서 읽습니다
# =====================================================================
def _sandbox_lines() -> list[list[str]]:
    """OpenShell 샌드박스 안에서 flygate 를 부른 실제 기록(agent/evidence/openshell_smoke_*.txt)의 RESULT 줄."""
    logs = sorted((ROOT / "agent/evidence").glob("openshell_smoke_*.txt"))
    if not logs:
        return []
    out = []
    for ln in logs[-1].read_text().splitlines():
        m = re.match(r"^RESULT\tPASS\t(flygate [^\t]*?) in sandbox[^\t]*\t[^\t]*\t(cmd=.*)$", ln)
        if m:
            out.append([m.group(1), m.group(2)])
    return out


def cli3_part(d: dict, caps: dict, pick: dict) -> dict:
    R = v3.jload_opt(v42.CLI_RUNS) or {}
    run = lambda k: (R.get(k) or {}).get("out") or {}
    cap = lambda sid: caps.get(pick.get(sid, ""), {})
    V = lambda sid: cap(sid).get("vals") or {}
    c2 = d["cli2"] or {}
    sm = d["agent"].get("smoke") or {}
    ins, tri, grd, crt, dck, krc, wat = (V(s) for s in ("cli_install", "cli_triage", "cli_grade", "cli_critic", "cli_dock", "cli_kr", "cli_watch"))
    to, go, co, do, ko, wo = run("triage"), run("grade"), run("critic"), run("discover"), run("kr"), run("watch")
    cmds = ins.get("cmds") or [c[0] for c in (c2.get("help") or {}).get("cmds", [])]
    dec = tri.get("decision") or to.get("decision") or {}
    conf = dck.get("confidence") or [p.get("confidence") for p in do.get("poses") or []]
    guard = crt.get("guard") or co.get("guard") or {}
    krr = krc.get("kr_routing") or ko.get("kr_routing") or {}
    return {
        "n_cmd": len(cmds), "cmds": cmds,
        # triage 캡처는 jq 로 고른 필드만 보이므로 걸린 시간은 캡처 기록(manifest seconds, 실행 전체)을 씁니다
        "tri_s": cap("cli_triage").get("seconds") or round((to.get("latency_ms") or 0) / 1000, 1),
        "action": dec.get("action"), "tier": dec.get("tier"), "brand": (tri.get("grounding") or {}).get("brand"),
        "n_ev_tri": len(tri.get("evidence_ids") or to.get("evidence_ids") or []),
        "pv_class": grd.get("pv_class_name") or go.get("pv_class_name"), "grade": grd.get("grade") or go.get("grade"),
        "grade_name": grd.get("grade_name") or go.get("grade_name"), "prr": (grd.get("stats") or go.get("stats") or {}).get("prr") or 0,
        "n_ev_grade": len(grd.get("evidence_ids") or go.get("evidence_ids") or []),
        "verdict": crt.get("verdict") or co.get("verdict"), "flagged": guard.get("flagged") or [], "guard_model": guard.get("model"),
        "dock_status": dck.get("status") or do.get("status"), "dock_run": dck.get("run_id") or do.get("run_id"),
        "dock_poses": len(conf), "dock_conf": round(max([x for x in conf if x is not None] or [0]), 3), "dock_s": cap("cli_dock").get("seconds"),
        "kr_total": krc.get("total", ko.get("total")), "kr_grade": krc.get("grade") or ko.get("grade"), "kr_band": krc.get("band"), "kr_who": krc.get("who_umc"),
        "kr_action": krr.get("action"), "kr15": "15일" in str(krr.get("deadline", "")) or bool(krr.get("report15")),
        "queue": wat.get("review_queue") if isinstance(wat.get("review_queue"), int) else len(wo.get("review_queue") or []),
        "pairs": len(wat.get("watchlist") or wo.get("watchlist") or []), "submitted": len(wat.get("submitted") or wo.get("submitted") or []),
        "quarter": wat.get("quarter") or (wo.get("quarter") or {}).get("quarter"),
        "cron": d["cli"].get("cron") or {}, "smoke": [sm.get("passed"), sm.get("total")], "smoke_when": sm.get("when"),
        "install": INSTALL_LINE, "repo": v3.REPO.replace("https://", ""), "recorded": R.get("recorded_utc"),
        "captured": max([c.get("when") or "" for c in caps.values()] or [""]),
        "sandbox": _sandbox_lines(),
    }

# =====================================================================
#  시간표: v4.2 와 같고, CLI 세 장면만 새 CLI 구간으로 바꿉니다
# =====================================================================
NEW = [("cli_open", "CLI", "FlyGate Agent CLI"),
       ("cli_install", "INSTALL", "CLI · INSTALL · 한 줄 설치"),
       ("cli_triage", "TRIAGE", "CLI · TRIAGE · 사례 분류"),
       ("cli_grade", "GRADE", "CLI · GRADE · 라벨 · 신호 · 문헌"),
       ("cli_critic", "CRITIC", "CLI · CRITIC · 근거를 넘으면 반려"),
       ("cli_dock", "DOCK", "CLI · DOCK · DiffDock NIM 실시간"),
       ("cli_kr", "KR", "CLI · KR · 국내 15일 규칙"),
       ("cli_watch", "WATCH", "CLI · WATCH · 상시 실행 · 제출 0건"),
       ("cli_same", "같은 명령", "CLI · 사람도 에이전트도 같은 명령"),
       ("cli_line", "한 줄", "CLI · 설치 한 줄")]


def narration(d: dict) -> dict:
    vo = v42.gloss_narration(v41.new_narration(d), d)
    vo["close"] = [slogan_read(), SIGN_OFF]
    c = d["cli3"]
    vo["cli_open"] = ["플라이게이트 에이전트 CLI, 명령줄 도구입니다."]
    vo["cli_install"] = [f"설치는 한 줄이면 되고, 명령 {c['n_cmd']}개가 바로 생깁니다."]
    vo["cli_triage"] = [f"triage는 실제 사례 한 건을 {c['tri_s']:.1f}초 만에 분류합니다."]
    vo["cli_grade"] = ["grade는 라벨, 신호, 문헌을 함께 읽고 등급을 매깁니다."]
    vo["cli_critic"] = [f"critic은 근거를 넘는 주장 {len(c['flagged'])}개를 반려합니다."]
    vo["cli_dock"] = ["discover는 DiffDock NIM에 실시간으로 도킹을 맡깁니다."]
    vo["cli_kr"] = ["kr-causality는 국내 보고를 15일 보고 후보로 보냅니다." if c["kr15"] else "kr-causality는 국내 보고를 서식과 점수로 정리합니다."]
    vo["cli_watch"] = ["watch는 매일 아침 검토 대기열을 만들고, 아무것도 제출하지 않습니다."]
    vo["cli_same"] = ["사람도 에이전트도 같은 명령을 씁니다.", "OpenClaw도 샌드박스 안에서 같은 CLI를 부릅니다."]
    vo["cli_line"] = ["저장소에서 한 줄로 설치해 바로 쓰실 수 있습니다."]
    return vo


def vis_new(d: dict) -> dict:
    c, caps, pick = d["cli3"], d["caps"], d["cap_of"]
    cap = lambda sid: (f"실제 캡처 `{caps[pick[sid]]['file']}`" if sid in pick else "캡처 없음 → 실행 기록 줄")
    return {
        ("cli_open", 0): "빈 화면에 '› flygate' 가 한 글자씩 입력되고 글리치와 함께 거대한 'FlyGate / Agent CLI' 로 바뀝니다 · 명령 이름 띠",
        ("cli_install", 0): f"색 화면 위 거대한 INSTALL → 왼쪽 '한 줄 설치' · 오른쪽 3D 터미널 창({cap('cli_install')}) → flygate --help 의 명령 {c['n_cmd']}개 줄로 확대",
        ("cli_triage", 0): f"TRIAGE · '사례 분류 {c['tri_s']:.1f}초' · {cap('cli_triage')} → \"action\": \"{c['action']}\" · \"tier\": \"{c['tier']}\" 줄로 확대",
        ("cli_grade", 0): f"GRADE · '라벨 · 신호 · 문헌' · {cap('cli_grade')} → 등급 {c['grade']}({c['grade_name']}) · {c['pv_class']} 줄로 확대",
        ("cli_critic", 0): f"CRITIC · '근거를 넘으면 반려' · {cap('cli_critic')} → \"safe\": false · \"flagged\": {', '.join(c['flagged'])} 줄로 확대",
        ("cli_dock", 0): f"DOCK · 'DiffDock NIM 실시간' · {cap('cli_dock')} → \"status\": \"{c['dock_status']}\" · run_id {c['dock_run']} 줄로 확대",
        ("cli_kr", 0): f"KR · '국내 15일 규칙' · {cap('cli_kr')} → \"action\": \"{c['kr_action']}\" · \"deadline\": \"15일 이내 …\" 줄로 확대",
        ("cli_watch", 0): f"WATCH · '상시 실행 · 제출 {c['submitted']}건' · {cap('cli_watch')} → \"review_queue\": {c['queue']} · \"submitted\": [] 줄로 확대",
        ("cli_same", 0): "왼쪽 '사람' 터미널 창(triage 캡처)과 오른쪽 '에이전트' 창(OpenShell 샌드박스 안 OpenClaw exec)이 같은 flygate 명령을 부릅니다",
        ("cli_same", 1): f"샌드박스 실행 기록(RESULT PASS flygate … in sandbox)이 차례로 빛나고 스모크 {c['smoke'][0]}/{c['smoke'][1]} 통과가 찍힙니다",
        ("cli_line", 0): f"'One line.' · 설치 한 줄(`{c['install']}`) · {c['repo']}",
        ("close", 0): "초파리 뇌 점구름 위로 구호가 솟아오릅니다: " + "".join(p[0] for p in SLOGAN_PARTS).replace("\n", " / "),
    }


def timeline(d: dict) -> list[dict]:
    old = v4.timeline(d)
    vo, vis = narration(d), {**v41.new_vis(d), **vis_new(d)}
    labels = {"validated": "공개 참조 세트 검증", "close": "분자에서 환자까지 · 근거가 먼저"}
    seq = []
    for s in old:
        if s["id"] == "cli":
            seq += [{"id": i, "name": n, "label": lab, "step": 3, "fresh": True} for i, n, lab in NEW]
        else:
            seq.append({**s, "fresh": False})
    out, t = [], 0.0
    for s in seq:
        sid = s["id"]
        lines = vo[sid]
        ob = s.get("beats") or [None] * len(lines)
        assert len(lines) == len(ob), f"{sid}: 박자 수가 v4.0.0 과 달라집니다"
        a = LEAD.get(sid, 0.3)
        beats, knots = [], [[0.0, 0.0]]
        for i, (bo, line) in enumerate(zip(ob, lines)):
            w = ceil1(syllables(line) / RATE + (GAP if i < len(lines) - 1 else 0))
            bb = round(a + w, 2)
            beats.append({"a": round(a, 2), "b": bb, "vis": vis.get((sid, i), bo["vis"] if bo else ""), "vo": line})
            if bo:
                knots += [[bo["a"], a], [bo["b"], bb]]
            a = bb
        dur = round(a + TAIL.get(sid, 0.5), 1)
        if sid == "close":
            dur = min(dur, CLOSE_MAX)
        if s["fresh"]:
            kn, ot0, ot1 = [[0.0, 0.0], [dur, dur]], None, None
        else:
            knots.append([s["t1"] - s["t0"], dur])
            kn = []
            for o, n in knots:
                if kn and (o <= kn[-1][0] + 1e-6 or n <= kn[-1][1] + 1e-6):
                    continue
                kn.append([round(o, 3), round(n, 3)])
            ot0, ot1 = s["t0"], s["t1"]
        out.append({"id": sid, "t0": round(t, 3), "t1": round(t + dur, 3), "name": s["name"], "label": labels.get(sid, s["label"]),
                    "step": s["step"], "fresh": s["fresh"], "old_t0": ot0, "old_t1": ot1, "warp": kn, "beats": beats})
        t += dur
    return out


def write_script(tl: list[dict], dur: float, built: str, d: dict):
    total_syl = sum(syllables(bt["vo"]) for s in tl for bt in s["beats"])
    cli = [s for s in tl if s["id"].startswith("cli_")]
    cli_s = sum(s["t1"] - s["t0"] for s in cli)
    caps, pick, c = d["caps"], d["cap_of"], d["cli3"]
    lines = [
        f"# Project-FlyGate 쇼릴 v{VERSION} 내레이션 대본", "",
        f"- 영상: `web/public/showreel/FlyGate_showreel_v{VERSION}.html` (1920×1080, 30fps) · 음원 `{AUDIO_REL}`",
        f"- **총 길이 {int(dur // 60)}분 {dur % 60:.0f}초 ({dur:.1f}초)** · 장면 {len(tl)}개 · 내레이션 {total_syl}음절(추정) · v4.2.0 의 CLI 세 장면을 실제 터미널 캡처로 다시 짠 'FlyGate Agent CLI' 구간 {len(cli)}장면({cli_s:.1f}초)으로 바꾼 판입니다",
        f"- 이 대본은 `scripts/build_reel_v4_3.py` 가 영상과 같은 장면 시간표(`scripts/reel/flygate_v4_3.timeline.json`)로 생성합니다. 손으로 고치지 말고 빌더의 `narration()` 을 고친 뒤 다시 빌드합니다.",
        f"- 수치는 빌드 시점({built})의 저장소 JSON · 측정 파일 값입니다. CLI 구간의 터미널 화면은 `web/public/cli/captures/` 의 실제 캡처(촬영 {str(c.get('captured')).replace('T', ' ').replace('Z', ' UTC')})이고, 화면 설명과 내레이션의 수치도 그 캡처의 원본 터미널 바이트(`web/public/cli/captures/ansi/*.ans`)에 찍힌 JSON 에서 읽습니다. triage 걸린 시간은 캡처 기록(`captures.json` 의 seconds, 명령 실행 전체)입니다.",
        "- CLI 구간은 CC-statusline 모션 릴의 문법을 따릅니다: 명령마다 거대한 낱말 하나, 3D로 기울인 터미널 창의 실제 캡처, 핵심 줄로 확대, 글리치 · 타자 전환.",
        "- 마무리 구호는 빌더의 `SLOGAN_PARTS` 한 줄에서 옵니다. 화면 색 조각과 마무리 내레이션이 모두 이 값을 씁니다.",
        "- 약물감시 전문가가 아닌 시청자를 위해 약어는 처음 나올 때 우리말 뜻을 함께 씁니다(v4.2 빌더의 `gloss_narration()`).",
        f"- 장면 길이는 내레이션 시간(초당 {RATE}음절, 문장 사이 {GAP}초 숨)에 꼬리 0.8초 이하를 더한 값입니다(마무리 장면은 {CLOSE_MAX:.0f}초 이하). 음절 수는 숫자와 영문을 소리 나는 대로 센 추정값입니다. 영문 고유명사는 괄호 안 읽기대로 읽습니다: FlyGate(플라이게이트), FlyDiscovery(플라이디스커버리), FlyVigilance(플라이비질런스), Nemotron(네모트론), NemoClaw(네모클로), OpenShell(오픈셸), OpenClaw(오픈클로), FAERS(페어스), SDR(에스디알), CLI(시엘아이), triage(트리아지), grade(그레이드), critic(크리틱), discover(디스커버), kr-causality(케이알 코절리티), DiffDock(디프독), NIM(님), watch(워치).",
        "", "## 장면 한눈에 보기", "",
        "| # | 장면 | 시작 | 끝 | 길이 |", "| --- | --- | --- | --- | --- |",
    ]
    for i, s in enumerate(tl, 1):
        lines.append(f"| {i:02d} | {s['label']} | {mmss(s['t0'])} | {mmss(s['t1'])} | {s['t1'] - s['t0']:.1f}초 |")
    lines.append(f"| | **합계** | 00:00.0 | {mmss(dur)} | **{dur:.1f}초** |")
    for i, s in enumerate(tl, 1):
        lines += ["", f"## {i:02d} · {s['label']} ({mmss(s['t0'])}–{mmss(s['t1'])})", "",
                  "| 시간 | 화면 | 내레이션 | 속도 |", "| --- | --- | --- | --- |"]
        for bt in s["beats"]:
            a, bb = s["t0"] + bt["a"], s["t0"] + bt["b"]
            syl = syllables(bt["vo"])
            lines.append(f"| {mmss(a)}–{mmss(bb)} | {bt['vis']} | {bt['vo']} | {syl}음절 · {syl / (bb - a):.1f}/초 |")
    lines += ["", "## CLI 구간에 넣은 실제 터미널 캡처", "", "| 장면 | 캡처 | 명령 | 촬영(UTC) · 실행 | 넣은 크기 | 강조 · 확대한 줄 |", "| --- | --- | --- | --- | --- | --- |"]
    for sid, n in pick.items():
        cp = caps[n]
        cmd = str(cp.get("cmd") or "").replace("\n", " ; ").replace("|", "\\|")
        lines.append(f"| {sid} | `{cp['file']}` | `{cmd[:90]}{'…' if len(cmd) > 90 else ''}` | {str(cp.get('when')).replace('T', ' ').replace('Z', '')} · {cp.get('seconds')}초 · exit {cp.get('exit')} | {cp['w']}×{cp['h']} WebP {cp['kb']} KB | {', '.join(k['id'] for k in cp['keys']) or '–'} |")
    if not pick:
        lines.append("| – | 캡처 없음(실행 기록 줄로 대신 그림) | – | – | – |")
    lines += ["", "- 캡처는 원본 크기(2배율) 그대로 WebP 로 HTML 안에 넣습니다. 확대할 줄의 자리는 캡처의 터미널 격자(줄 간격 · 글자 폭)를 재고, 원본 터미널 바이트에서 그 줄이 몇 번째 화면 줄인지 세어 정합니다(빌더의 `KEYS`).",
              "- '사람도 에이전트도 같은 명령' 장면의 샌드박스 줄은 `agent/evidence/openshell_smoke_2026-09-28.txt` 의 RESULT 줄, 스모크 점검 수는 `web/public/data/agent.json` 에서 읽습니다.",
              "", "## 읽을 때", "",
              "- 장면이 바뀌는 순간(각 표의 첫 줄 시작 시각)에 첫 문장을 시작하면 화면의 숫자가 나타나는 때와 맞습니다.",
              "- CLI 구간에서는 거대한 낱말이 뜰 때 그 명령 이름을 읽습니다. 터미널 창이 핵심 줄로 확대되는 순간이 수치를 읽는 자리입니다.",
              "- Jev(TypeSafe AI)는 기술 구성 크레딧에서만 이름을 읽고, 본문에서는 '비자기회귀 판단 모델'로 부릅니다. 비교 기준선은 '모델 단독 · 질문 하나'입니다.", ""]
    SCRIPT_OUT.write_text("\n".join(lines))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = pathlib.Path(args[0]) if args else DEFAULT_OUT
    fv = v3.fv_part()
    disc = v3.disc_part()
    val = v4.jload_opt(PUB / "data/validation.json")
    fv["val"] = v4.val4_part(val)
    data = {
        "meta": {"built": time.strftime("%Y-%m-%d %H:%M"), "repo": v3.REPO, "live": v3.LIVE, "version": VERSION},
        "disc": disc, "nir": v3.nir_part(), "fv": fv, "agent": v3.agent_part(fv["skills"]), "brain": v3.brain_part(),
        "panel": v4.panel_part(disc), "wh": v4.warehouse_part(), "triage": v4.triage_part(), "kr": v4.kr_part(), "pvc": v4.pv_class_part(),
        "bt": v4.backtest_part(), "nvs": v4.nvskills_part(disc), "arch": v4.arch_part(), "cli": v4.cli_part(), "cli2": v42.cli2_part(),
        "slogan": SLOGAN_PARTS,
    }
    data["caps"] = caps_part()
    data["cap_of"] = pick_caps(data["caps"])
    data["cli3"] = cli3_part(data, data["caps"], data["cap_of"])
    for pr in data["triage"]["probs"]:
        pr[0] = pr[0].replace("WHO-UMC", "WHO-UMC(세계보건기구 기준)")
    tl = timeline(data)
    dur = tl[-1]["t1"]
    for s in data["fv"]["val"]["sets"]:
        s.pop("stat", None)
    data["tl"] = {"dur": dur, "scenes": [{k: s[k] for k in ("id", "t0", "t1", "name", "label", "step", "fresh", "old_t0", "old_t1", "warp")} for s in tl],
                  "beats": {s["id"]: [[bt["a"], bt["b"]] for bt in s["beats"]] for s in tl}}
    html = TEMPLATE.read_text()
    marker = "/*__DATA__*/null"
    assert html.count(marker) == 1, "template data marker missing"
    page = dict(data)
    page["caps"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("text", "vals")} for k, v in data["caps"].items()}
    blob = json.dumps(page, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html.replace(marker, blob))
    TIMELINE_OUT.write_text(json.dumps({"version": VERSION, "built": data["meta"]["built"], "dur": dur, "rate": RATE,
                                        "captures": {sid: data["caps"][n]["file"] for sid, n in data["cap_of"].items()},
                                        "scenes": list(tl)}, ensure_ascii=False, indent=1) + "\n")
    write_script(tl, dur, data["meta"]["built"], data)
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB) · {len(tl)} scenes · {dur:.1f} s")
    print(f"wrote {TIMELINE_OUT.relative_to(ROOT)} · {SCRIPT_OUT.relative_to(ROOT)}")
    for n, cp in data["caps"].items():
        print(f"  cap {n:<14} {cp['orig'][0]}x{cp['orig'][1]} → {cp['w']}x{cp['h']} {cp['kb']} KB · keys {[k['id'] for k in cp['keys']]}")
        if re.search(r"\bjev\b", cp["text"], re.I):
            print(f"  ! capture {n} shows 'jev' text")
    for s in tl:
        for bt in s["beats"]:
            r = syllables(bt["vo"]) / (bt["b"] - bt["a"])
            if r > RATE + 1e-6:
                print(f"  ! narration fast ({r:.2f} syl/s) {s['id']}: {bt['vo']}")
        tail = (s["t1"] - s["t0"]) - s["beats"][-1]["b"]
        if tail > (1.0 if s["id"] == "close" else 0.8) + 1e-6:
            print(f"  ! scene tail {tail:.1f} s {s['id']}")
    for s in tl:
        if s["id"].startswith("cli_") or s["id"] in ("agent", "close"):
            syl = sum(syllables(bt["vo"]) for bt in s["beats"])
            print(f"  {s['id']:<12} {s['t0']:6.1f} {s['t1'] - s['t0']:5.1f} s  {syl:3d} syl")
    print("  fallbacks: " + ("; ".join(FALLBACKS) if FALLBACKS else "none"))


if __name__ == "__main__":
    main()
