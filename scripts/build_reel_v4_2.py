"""Project-FlyGate 쇼릴 v4.2.0 을 만듭니다. v4.1.0 의 CLI 장면(18번, 9.5초)을 'FlyGate Agent CLI' 세 장면으로 늘린 판입니다.

v4.1.0 의 속도 규칙은 그대로입니다(내레이션 초당 6.3음절 · 꼬리 0.8초 이하 · 늘 움직이는 층 · 강조 틀 · 멈춘 구간 0% 목표).
바뀐 점:
  1) CLI 장면 하나를 세 장면으로 나눕니다. 모두 실제로 돌린 명령의 출력(scripts/reel/cli_runs.json)을 보여 줍니다.
       cli_install  설치 한 줄(git clone → install_flygate.sh) → flygate --help(명령 7개) · 대시보드 #/cli 가이드
       cli_loop     OpenClaw exec 가 부르는 같은 CLI: triage · grade · critic · discover --live(DiffDock NIM) · kr-causality
       cli_safe     OpenShell 샌드박스 · 게이트웨이 · 하트비트 · cron · flygate watch(submitted=[]) · 제출은 사람
     새 장면은 v4.0.0 에 대응하는 장면이 없으므로 warp 가 항등(옛 시각 = 새 시각)이고, 효과음 큐도 새 시각으로 바로 적습니다.
  2) 마무리 구호는 SLOGAN_PARTS 한 줄로 바꿉니다(화면 색 조각 · 내레이션이 모두 이 값을 씁니다).
  3) 나머지 장면 · 수치 · 틀은 v4.1.0 과 같습니다.

v4.1.0 의 파일(build_reel_v4_1.py, flygate_v4_1.template.html, 타임라인 · 대본 · 음원)은 고치지 않습니다.

사용:
  .venv/bin/python scripts/build_reel_v4_2.py [출력 경로]
  .venv/bin/python scripts/build_reel_v4_2.py --refresh-cli   # 명령을 실제로 다시 돌려 scripts/reel/cli_runs.json 을 새로 씁니다
      (새 복제본 설치 · triage · grade · critic · 새 DiffDock NIM 도킹 · kr-causality · watch. 키는 저장소 .env 에서 읽고 출력하지 않습니다)
출력:
  web/public/showreel/FlyGate_showreel_v4.2.0.html · scripts/reel/flygate_v4_2.timeline.json · docs/SHOWREEL_SCRIPT_v4.2.0.md
음원:
  .venv/bin/python scripts/reel/audio_v4_2.py
"""
import asyncio
import datetime as dt
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_reel_v3 as v3  # noqa: E402
import build_reel_v4 as v4  # noqa: E402
import build_reel_v4_1 as v41  # noqa: E402  v4.1 의 내레이션 · 박자 규칙을 그대로 씁니다

VERSION = "4.2.0"
ROOT, PUB, REEL = v4.ROOT, v4.PUB, v4.REEL
TEMPLATE = REEL / "flygate_v4_2.template.html"
DEFAULT_OUT = PUB / f"showreel/FlyGate_showreel_v{VERSION}.html"
TIMELINE_OUT = REEL / "flygate_v4_2.timeline.json"
SCRIPT_OUT = ROOT / f"docs/SHOWREEL_SCRIPT_v{VERSION}.md"
AUDIO_REL = f"scripts/reel/FlyGate_showreel_v{VERSION}_audio.m4a"
CLI_RUNS = REEL / "cli_runs.json"
FALLBACKS = v4.FALLBACKS
syllables, mmss = v4.syllables, v4.mmss
RATE, GAP, CLOSE_MAX = v41.RATE, v41.GAP, v41.CLOSE_MAX
LEAD, TAIL = v41.LEAD, v41.TAIL
ceil1 = v41.ceil1

# ---------------------------------------------------------------- 마무리 구호 (한 줄만 바꾸면 됩니다)
# [글자, 색] 조각. 색은 'white' · 'muted' · 'accent' · 'brand'(브랜드 그라디언트) 또는 '#rrggbb' 입니다. "\n" 조각은 줄바꿈입니다.
# 내레이션: 'brand' 가 아닌 조각을 이어 읽고(마무리 첫 문장), 브랜드 이름은 끝인사("플라이게이트였습니다. 감사합니다.")에서 읽습니다.
SLOGAN_PARTS = [["분자에서 환자까지,", "white"], ["\n", None], ["추론보다 ", "muted"], ["근거가 먼저. ", "accent"], ["FlyGate.", "brand"]]
SIGN_OFF = "플라이게이트였습니다. 감사합니다."

# 새 낱말의 읽기 음절(v4.LATIN 에 더합니다. 앞에 있는 키가 먼저 맞습니다)
v4.LATIN.update({"CLI,": 3, "CLI": 3, "triage는": 5, "grade는": 4, "critic의": 4, "discover는": 5, "kr-causality는": 8,
                 "DiffDock에": 5, "DiffDock": 4, "NIM으로": 4, "watch로": 3, "OpenClaw": 4})


def slogan_read() -> str:
    return " ".join(p[0].strip() for p in SLOGAN_PARTS if p[1] != "brand" and p[0] != "\n").strip()


# =====================================================================
#  --refresh-cli : 명령을 실제로 돌려 줄인 출력을 cli_runs.json 에 씁니다
# =====================================================================
def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(argv, cwd, env, shown):
    t0, p0 = _utc(), time.perf_counter()
    p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)
    wall = round(time.perf_counter() - p0, 2)
    if p.returncode != 0:
        raise SystemExit(f"{shown} 실패(exit {p.returncode}): {p.stderr[-400:]}")
    print(f"  ran {shown} · {wall} s")
    return {"cmd": shown, "started_utc": t0, "wall_s": wall, "exit": p.returncode}, p.stdout


def _rerank_probe(drug: str, pt: str) -> dict:
    """grade 가 읽는 문헌 6편을 고르는 Nemotron 리랭커를 캐시 없이 한 번 더 불러 순서 · 지연을 기록합니다(판단 모델은 부르지 않습니다)."""
    code = ("import asyncio, json, sys, httpx; sys.path.insert(0, 'api'); from _fv import literature\n"
            "async def m():\n"
            "    async with httpx.AsyncClient() as c:\n"
            f"        r = await literature.read({drug!r}, {pt!r}, c, use_jev=False)\n"
            "    print(json.dumps({'order': r.get('order'), 'rerank': r.get('rerank'), 'pmids': r.get('pmids')}))\n"
            "asyncio.run(m())")
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, "FV_CACHE_DIR": td}
        meta, out = _run([str(ROOT / ".venv/bin/python"), "-c", code], ROOT, env, f"rerank probe {drug} {pt}")
    r = json.loads(out)
    rm = r.get("rerank") or {}
    return {**meta, "order": r.get("order"), "model": rm.get("model"), "candidates": rm.get("candidates"),
            "rerank_ms": rm.get("rerank_ms"), "cached": rm.get("cached"), "pmids": r.get("pmids"), "pubmed_ranks": rm.get("pubmed_ranks")}


def refresh_cli():
    env = {**os.environ, "FV_CACHE_DIR": str(ROOT / "data/cache/api")}
    fg = str(ROOT / "agent/bin/flygate")
    runs = {"about": "flygate 명령을 실제로 돌린 출력을 줄인 기록입니다(scripts/build_reel_v4_2.py --refresh-cli). "
                     "경로는 짧게 바꿨습니다(임시 설치 폴더 → ~/.local/bin · ~/Project-FlyGate, 저장소 절대 경로 → 상대 경로). 키는 기록하지 않습니다.",
            "recorded_utc": _utc()}
    # 1) 새 복제본에 설치: README · 대시보드 가이드와 같은 한 줄
    with tempfile.TemporaryDirectory() as td:
        td = os.path.realpath(td)   # macOS: /var → /private/var 로 풀린 경로가 출력에 찍힙니다
        tdp = pathlib.Path(td)
        bin_ = tdp / "bin"
        line = f"git clone {v3.REPO} && cd Project-FlyGate && ./scripts/install_flygate.sh"
        meta, out = _run(["bash", "-c", f"git -c http.version=HTTP/1.1 clone -q {v3.REPO} && cd Project-FlyGate && ./scripts/install_flygate.sh {bin_}"],
                         tdp, os.environ, line)
        head = subprocess.run(["git", "-C", str(tdp / "Project-FlyGate"), "log", "-1", "--format=%h %cI"], capture_output=True, text=True).stdout.split()
        norm = lambda s: s.replace(str(bin_), "~/.local/bin").replace(str(tdp / "Project-FlyGate"), "~/Project-FlyGate").replace(td, "~")
        lines = [norm(x) for x in out.splitlines() if x.strip()]
        runs["install"] = {**meta, "commit": head[0] if head else None, "commit_date": head[1] if len(head) > 1 else None,
                           "stdout": [x for x in lines if not x.startswith("PATH 에")][:3]}
        hm, hout = _run([str(bin_ / "flygate"), "--help"], tdp / "Project-FlyGate", os.environ, "flygate --help")
        runs["help"] = {**hm, "stdout": hout.rstrip().splitlines()}
    # 2) 에이전트 루프: 사람과 OpenClaw exec 가 부르는 같은 명령
    def fj(args, shown):
        m, out = _run([fg, *args], ROOT, env, shown)
        return m, json.loads(out)
    m, o = fj(["triage", "agent/examples/case_niraparib.json"], "flygate triage agent/examples/case_niraparib.json")
    runs["triage"] = {**m, "out": {k: o.get(k) for k in ("cmd", "mode", "case", "quarter", "suspect", "reactions", "decision", "judgments", "latency_ms", "evidence_ids", "note")}}
    m, o = fj(["grade", "NIRAPARIB", "thrombocytopenia"], "flygate grade NIRAPARIB thrombocytopenia")
    lit = o.get("literature") or {}
    runs["grade"] = {**m, "out": {**{k: o.get(k) for k in ("cmd", "id", "pv_class", "pv_class_name", "grade", "grade_name", "axes", "label_sections", "stats", "summary", "evidence_ids")},
                                  "literature": {"query": lit.get("query"), "count": lit.get("count"), "summary": {k: (lit.get("summary") or {}).get(k) for k in ("read", "relevant", "supportive", "designs")}}}}
    runs["grade"]["rerank_probe"] = _rerank_probe("NIRAPARIB", "thrombocytopenia")
    m, o = fj(["critic", "agent/examples/claims_niraparib.json"], "flygate critic agent/examples/claims_niraparib.json")
    g = o.get("guard") or {}
    runs["critic"] = {**m, "out": {"cmd": o.get("cmd"), "tiers": o.get("tiers"), "verdict": o.get("verdict"), "issues": o.get("issues"),
                                   "guard": {k: g.get(k) for k in ("safe", "flagged", "policy", "fired", "by_guard")},
                                   "overclaim_p": o.get("overclaim_p"), "evidence_ids": o.get("evidence_ids")}}
    # 새 DiffDock NIM 도킹. pending 이면 같은 run_dir 을 --resume 으로만 이어 봅니다(새 작업을 다시 보내지 않습니다)
    pdb = "fly_discovery/measurements/nim/of3_parp1_niraparib.pdb"
    smi = (ROOT / "agent/examples/niraparib.smi").read_text().strip()
    m, o = fj(["discover", "--live", "--protein", pdb, "--smiles", smi, "--num-poses", "5", "--timeout", "300"],
              f"flygate discover --live --protein {pdb} --smiles {smi} --num-poses 5")
    tries = 0
    while o.get("status") == "pending" and o.get("run_dir") and tries < 6:
        tries += 1
        time.sleep(20)
        m2, o = fj(["discover", "--resume", o["run_dir"]], f"flygate discover --resume {o['run_dir']}")
        m["resumed"] = tries
    if o.get("run_dir"):
        o["run_dir"] = str(pathlib.Path(o["run_dir"]).resolve().relative_to(ROOT))
    runs["discover"] = {**m, "out": o}
    m, o = fj(["kr-causality", "agent/examples/kr_report.txt", "--route"], "flygate kr-causality agent/examples/kr_report.txt --route")
    runs["kr"] = {**m, "out": {k: o.get(k) for k in ("cmd", "form", "intake_model", "kr_form", "missing", "total", "range", "grade", "band", "who_umc", "assessed_reaction", "kr_routing", "note", "evidence_ids")}}
    # 3) 상시 실행: 하트비트 · cron 이 부르는 watch (메모는 임시 폴더에 씁니다. 저장소의 워크스페이스 메모는 건드리지 않습니다)
    with tempfile.TemporaryDirectory() as td:
        td = os.path.realpath(td)
        m, o = fj(["watch", "--memory-dir", td], "flygate watch --memory-dir memory")
        for k in ("memory_note", "state"):
            if isinstance(o.get(k), str):
                o[k] = o[k].replace(td, "memory")
        if isinstance(o.get("quarter"), dict) and o["quarter"].get("warehouse"):
            o["quarter"]["warehouse"] = str(pathlib.Path(o["quarter"]["warehouse"]).resolve().relative_to(ROOT))
    runs["watch"] = {**m, "out": o}
    CLI_RUNS.write_text(json.dumps(runs, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {CLI_RUNS.relative_to(ROOT)}")


# =====================================================================
#  cli_runs.json → 터미널 줄 · 오른쪽 카드
# =====================================================================
def _short(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def pj(o, ind: int = 0, width: int = 92) -> list[str]:
    """JSON 을 사람이 읽는 모양으로 줄입니다. 한 줄에 들어가는 묶음은 한 줄로 씁니다."""
    pad = "  " * ind
    flat = json.dumps(o, ensure_ascii=False, separators=(", ", ": "))
    if len(pad) + len(flat) <= width or not isinstance(o, (dict, list)):
        return [pad + flat]
    out = [pad + ("{" if isinstance(o, dict) else "[")]
    items = list(o.items()) if isinstance(o, dict) else [(None, v) for v in o]
    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        key = (json.dumps(k, ensure_ascii=False) + ": ") if k is not None else ""
        sub = pj(v, ind + 1, width)
        first = sub[0].lstrip()
        if len(sub) == 1:
            out.append("  " * (ind + 1) + key + first + comma)
        else:
            out.append("  " * (ind + 1) + key + first)
            out += sub[1:-1]
            out.append(sub[-1] + comma)
    out.append(pad + ("}" if isinstance(o, dict) else "]"))
    return out


def mark(lines: list[str], hl=()) -> list[list[str]]:
    """줄마다 종류를 붙입니다: ev(근거 ID) · hl(핵심 값) · j(나머지 JSON)."""
    out, in_ev = [], False
    for s in lines:
        kind = "j"
        if '"evidence_ids"' in s:
            kind, in_ev = "ev", "]" not in s
        elif in_ev:
            kind = "ev"
            if s.strip().startswith("]"):
                in_ev = False
        elif any(h in s for h in hl):
            kind = "hl"
        out.append([kind, s])
    return out


def cli2_part() -> dict | None:
    R = v3.jload_opt(CLI_RUNS)
    if not R:
        FALLBACKS.append("cli_runs.json 없음 → --refresh-cli 로 만드세요(CLI 장면이 비어 보입니다)")
        return None
    ins, hp = R["install"], R["help"]
    # --help: argparse 가 줄을 접은 도움말을 명령 · 설명 한 줄씩으로 다시 폅니다(내용은 그대로입니다)
    txt = "\n".join(hp["stdout"])
    body = txt.split("positional arguments:")[1].split("options:")[0]
    cmds = []
    for ln in body.splitlines()[2:]:
        m = re.match(r"^\s{4}(\S+)\s+(.*)$", ln)
        if m:
            cmds.append([m.group(1), m.group(2).strip()])
        elif ln.strip() and cmds:
            cmds[-1][1] += " " + ln.strip()
    desc = next((ln for ln in hp["stdout"] if ln.startswith("FlyGate agent tools")), "")
    tsx = (ROOT / "web/src/pages/CliTutorial.tsx").read_text()
    steps = re.findall(r"'([^']+)'", re.search(r"const steps = \[(.*?)\]", tsx).group(1))
    # 1) 에이전트 루프 다섯 명령
    tr, gr, cr, dd, kr = (R[k] for k in ("triage", "grade", "critic", "discover", "kr"))
    to, go, co, do, ko = tr["out"], gr["out"], cr["out"], dd["out"], kr["out"]
    J = to["judgments"]
    tri = {"cmd": "triage", "case": to["case"], "suspect": to["suspect"],
           "decision": {k: to["decision"][k] for k in ("action", "tier", "regime")} | {"deadline": _short(to["decision"]["deadline"], 58)},
           "judgments": J, "latency_ms": to["latency_ms"], "evidence_ids": to["evidence_ids"]}
    gs = go["stats"]
    rp = gr.get("rerank_probe") or {}
    grd = {"cmd": "grade", "id": go["id"], "pv_class_name": go["pv_class_name"], "grade": go["grade"], "grade_name": go["grade_name"],
           "axes": {"label_status_name": go["axes"]["label_status_name"], "signal_name": go["axes"]["signal_name"]},
           "stats": {k: gs[k] for k in ("a", "prr", "ror_lo", "ic025")},
           "literature": {"count": go["literature"]["count"], "read": go["literature"]["summary"]["read"], "supportive": go["literature"]["summary"]["supportive"]},
           "evidence_ids": go["evidence_ids"][:6]}
    crt = {"cmd": "critic", "verdict": co["verdict"],
           "issues": [{k: i[k] for k in ("claim", "tier", "rule", "p") if k in i} for i in co["issues"] if not i.get("guards")],
           "guard": {"policy": co["guard"]["policy"], "flagged": co["guard"]["flagged"],
                     "fired": [{"claim": f["claim"], "pv": f["pv"][0], "rule": f["rule"]} for f in co["guard"]["fired"]],
                     "model": (co["guard"]["fired"] or [{}])[0].get("model")},
           "evidence_ids": co["evidence_ids"]}
    wall_dd = None
    try:
        wall_dd = round((dt.datetime.fromisoformat(do["finished_at"]) - dt.datetime.fromisoformat(do["created_at"])).total_seconds(), 1)
    except (KeyError, TypeError, ValueError):
        pass
    dsc = {"cmd": "discover", "mode": do.get("mode"), "run_id": do.get("run_id"), "status": do.get("status"), "endpoint": do.get("endpoint"),
           "num_poses": do.get("num_poses"), "poses": [{"rank": p["rank"], "confidence": round(p["confidence"], 4), "file": p["file"]} for p in do.get("poses", [])],
           "run_dir": do.get("run_dir"), "evidence_ids": do.get("evidence_ids", [])}
    kf = ko["kr_form"]
    ga, na = kf.get("가_환자정보") or {}, kf.get("나_이상사례정보") or {}
    krr = ko["kr_routing"]
    krd = {"cmd": "kr-causality", "intake_model": ko["intake_model"],
           "kr_form": {"가_환자정보": {"나이": ga.get("나이"), "성별": ga.get("성별")}, "나_이상사례정보": {"이상사례명": na.get("이상사례명")}},
           "total": ko["total"], "range": ko["range"], "grade": ko["grade"], "who_umc": {k: ko["who_umc"][k] for k in ("choice", "confidence")},
           "kr_routing": {"action": krr["action"], "report15": krr["report15"], "deadline": _short(krr["deadline"], 40)},
           "evidence_ids": ko["evidence_ids"]}
    sev = {"R1": "인과 단정", "R2": "발생률", "R11": "치료 조언"}
    t1 = [i for i in co["issues"] if i.get("tier") == 1]
    loop = [
        {"id": "triage", "cmd": tr["cmd"], "wall": tr["wall_s"], "when": tr["started_utc"],
         "lines": mark(pj(tri), ('"action"', '"latency_ms"', '"causality"', '"serious"')),
         "card": {"main": f"{to['decision']['action']} · 사람 우선 검토", "sub": f"타입 있는 확률 {len(J)}개 · 판단 {to['latency_ms'] / 1000:.1f}초 · 중대 {J['serious']:.2f}",
                  "model": "비자기회귀 판단 모델"}},
        {"id": "grade", "cmd": gr["cmd"], "wall": gr["wall_s"], "when": gr["started_utc"],
         "lines": mark(pj(grd), ('"pv_class_name"', '"prr"', '"literature"')) + ([["dim", f"# 문헌 {go['literature']['summary']['read']}편 = PubMed 후보 {rp.get('candidates')}편 중 Nemotron 리랭커 선택 · {rp.get('rerank_ms')} ms"]] if rp.get("order") == "nemotron_rerank" else []),
         "card": {"main": f"{go['pv_class_name']} · 등급 {go['grade']}", "sub": f"{go['axes']['label_status_name']} · PRR {gs['prr']:.2f} · 문헌 {go['literature']['summary']['supportive']}/{go['literature']['summary']['read']} 지지",
                  "model": "Nemotron Reranker" if rp.get("order") == "nemotron_rerank" else "PubMed 순서"}},
        {"id": "critic", "cmd": cr["cmd"], "wall": cr["wall_s"], "when": cr["started_utc"],
         "lines": mark(pj(crt), ('"verdict"', '"fired"', '"pv"', '"model"')),
         "card": {"main": f"{co['verdict']} · 가드가 {len(co['guard']['flagged'])}건 반려",
                  "sub": " · ".join(f"{f['claim']} {f['rule']} {sev.get(f['rule'], '')}".strip() for f in co["guard"]["fired"]) + (f" · {t1[0]['claim']} 1단 규칙" if t1 else ""),
                  "model": "Nemotron 3.5 Content Safety · 약물감시 정책"}},
        {"id": "discover", "cmd": "flygate discover --live --protein …/of3_parp1_niraparib.pdb --smiles <niraparib> --num-poses 5", "wall": dd["wall_s"], "when": dd["started_utc"],
         "lines": mark(pj(dsc), ('"status"', '"run_id"', '"endpoint"')),
         "card": {"main": f"{do.get('status')} · 포즈 {len(do.get('poses', []))}개 저장", "sub": f"새 요청 {do.get('run_id')} · NIM 응답 {wall_dd if wall_dd is not None else dd['wall_s']}초",
                  "model": "NVIDIA DiffDock NIM"}},
        {"id": "kr-causality", "cmd": kr["cmd"], "wall": kr["wall_s"], "when": kr["started_utc"],
         "lines": mark(pj(krd), ('"total"', '"grade"', '"report15"', '"deadline"')),
         "card": {"main": f"{ko['total']}점 · {ko['grade']} · {'15일 보고 후보' if krr['report15'] else krr['action']}",
                  "sub": f"식약처 서식 구조화 · 한국형 알고리즘 ver 2.0 · 범위 {ko['range'][0]}~{ko['range'][1]}", "model": "Nemotron 3 Super"}},
    ]
    for x, o in zip(loop, (tri, grd, crt, dsc, krd)):
        x["n_ev"] = len(o["evidence_ids"])
    # 2) 상시 실행: watch 출력
    wo = R["watch"]["out"]
    rq = [{"kind": q["kind"], "what": _short(q["what"], 46), "evidence_ids": q["evidence_ids"][:1]} for q in wo.get("review_queue", [])]
    wat = {"cmd": "watch", "quarter": wo["quarter"]["quarter"], "new_quarter": wo["new_quarter"],
           "watchlist": [{k: w0.get(k) for k in ("drug", "pt", "prr", "sdr")} for w0 in wo["watchlist"][:1]], "review_queue": rq,
           "submitted": wo.get("submitted", []), "note": _short(wo.get("note", ""), 44)}
    wl = mark(pj(wat, width=88), ('"submitted"', '"review_queue"', '"note"'))
    # 감시 목록은 첫 쌍만 보이고, 나머지 개수는 주석 줄로 적습니다(줄인 출력임을 숨기지 않습니다)
    iw = next((i for i, (_, x) in enumerate(wl) if '"watchlist"' in x), None)
    if iw is not None and len(wo["watchlist"]) > 1:
        wl.insert(iw + 1, ["dim", f"    # … 외 {len(wo['watchlist']) - 1}쌍 · 감시 목록 {len(wo['watchlist'])}쌍의 SDR 을 다시 계산했습니다"])
    return {"recorded": R.get("recorded_utc"),
            "install": {"cmd": ins["cmd"], "wall": ins["wall_s"], "when": ins["started_utc"], "commit": ins.get("commit"), "stdout": ins["stdout"][:1]},
            "help": {"desc": desc, "cmds": cmds, "when": hp["started_utc"]},
            "tutorial": {"steps": steps, "url": v3.LIVE.replace("https://", "") + "/#/cli"},
            "loop": loop,
            "watch": {"cmd": R["watch"]["cmd"], "when": R["watch"]["started_utc"], "wall": R["watch"]["wall_s"], "lines": wl,
                      "queue": len(wo.get("review_queue", [])), "pairs": len(wo["watchlist"]), "submitted": len(wo.get("submitted", []))},
            "slogan": SLOGAN_PARTS}


# =====================================================================
#  시간표: v4.1 과 같고, CLI 장면만 새 세 장면으로 바꿉니다
# =====================================================================
def gloss_narration(vo: dict, d: dict) -> dict:
    """v4.2: 약어는 처음 나올 때 우리말 뜻을 먼저 읽고('불균형 보고 신호, 즉 SDR'), 그다음부터는 뜻으로만 읽습니다."""
    def rep(sid, i, old, new):
        assert old in vo[sid][i], f"{sid}[{i}]: '{old}' 없음 → {vo[sid][i]}"
        vo[sid][i] = vo[sid][i].replace(old, new)
    wh, fv = d["wh"], d["fv"]
    sets = {s["name"]: s for s in fv["val"]["sets"]}
    vo["warehouse"][1] = f"미국 FDA 이상사례 보고, 즉 FAERS {wh['quarters']}개 분기 {v4.man(wh['cases'])} 건을 집계합니다."
    rep("flow", 1, "FAERS 통계, 문헌을 모아 PV 분류를", "보고 통계, 문헌을 모아 약물감시, 즉 PV 분류를")
    rep("signals", 0, "SDR은 인과가", "불균형 보고 신호, 즉 SDR은 인과가")
    rep("signals", 1, "중대 의학 사건", "특별 주의 이상사례")
    rep("timemachine", 0, "SDR을 다시", "신호를 다시")
    rep("timemachine", 1, "먼저 SDR이 섰습니다", "먼저 신호가 섰습니다")
    if "OMOP" in sets and "EU-ADR" in sets:
        vo["validated"][0] = f"지식 기반 방식은 판별 정확도, 즉 AUC {sets['OMOP']['kb']:.2f}, {sets['EU-ADR']['kb']:.2f}로 통계 지표를 앞섰습니다."
    rep("nvskills", 1, "PV 가드는", "약물감시 가드는")
    rep("reviewed", 1, "SDR 용어, PV 분류,", "신호 용어, 약물감시 분류,")
    return vo


def narration(d: dict) -> dict:
    vo = gloss_narration(v41.new_narration(d), d)
    vo["close"] = [slogan_read(), SIGN_OFF]
    c2 = d["cli2"] or {}
    n_cmd = len((c2.get("help") or {}).get("cmds") or []) or len(d["cli"]["cmds"])
    L = {x["id"]: x for x in c2.get("loop", [])}
    runs = v3.jload_opt(CLI_RUNS) or {}
    to = (runs.get("triage") or {}).get("out") or {}
    co = (runs.get("critic") or {}).get("out") or {}
    do = (runs.get("discover") or {}).get("out") or {}
    ko = (runs.get("kr") or {}).get("out") or {}
    lat = (to.get("latency_ms") or 400) / 1000
    nflag = len(((co.get("guard") or {}).get("flagged")) or []) or 3
    npose = len(do.get("poses") or []) or 5
    kr15 = ((ko.get("kr_routing") or {}).get("report15"))
    vo["cli_install"] = ["플라이게이트 에이전트 CLI, 명령줄 도구입니다.",
                         f"한 줄로 설치하면 명령 {n_cmd}개가 생깁니다.",
                         "사람도 에이전트도 같은 명령을 씁니다."]
    vo["cli_loop"] = [f"triage는 실제 사례를 {lat:.1f}초에 판단합니다.",
                      "grade는 라벨, 신호, 문헌으로 약물감시 분류를 매깁니다.",
                      f"critic의 Nemotron 가드가 과잉 주장 {nflag}개를 잡습니다.",
                      "discover는 NVIDIA DiffDock에 실제로 도킹을 맡깁니다.",
                      "kr-causality는 국내 보고를 15일 보고 후보로 보냅니다." if kr15 else "kr-causality는 국내 보고를 서식과 점수로 정리합니다.",
                      "출력마다 근거 ID가 붙습니다."]
    vo["cli_safe"] = ["모두 OpenShell 샌드박스 안에서 돕니다.",
                      "매일 아침 예약 작업이 watch로 검토 대기열을 만듭니다.",
                      "보고와 제출은 사람이 합니다."]
    return vo


def vis_new(d: dict) -> dict:
    c2 = d["cli2"] or {}
    L = {x["id"]: x for x in c2.get("loop", [])}
    ins = c2.get("install") or {}
    cr = d["cli"].get("cron") or {}
    sm = (d["agent"].get("smoke") or {})
    card = lambda k: (L.get(k) or {}).get("card", {})
    v = {
        ("cli_install", 0): f"터미널에 git clone … && ./scripts/install_flygate.sh 가 한 글자씩 입력되고 설치 출력이 나옵니다(새 복제본 {ins.get('commit')} · {ins.get('wall')}초 · {ins.get('when')} 실행)",
        ("cli_install", 1): f"flygate --help: 명령 {len(c2.get('help', {}).get('cmds', []))}개 목록 · 오른쪽 대시보드 #/cli 가이드 {len(c2.get('tutorial', {}).get('steps', []))}단계",
        ("cli_install", 2): "사람(터미널) · 에이전트(OpenClaw exec) → 같은 flygate → 근거 ID가 붙은 JSON",
        ("cli_loop", 0): f"OpenClaw exec 터미널에 flygate triage 입력 → 실제 JSON 출력 · 카드 '{card('triage').get('main')}' · {card('triage').get('sub')}",
        ("cli_loop", 1): f"flygate grade → '{card('grade').get('main')}' · {card('grade').get('sub')} · 리랭커 주석",
        ("cli_loop", 2): f"flygate critic → '{card('critic').get('main')}' · {card('critic').get('sub')}",
        ("cli_loop", 3): f"flygate discover --live → '{card('discover').get('main')}' · {card('discover').get('sub')}",
        ("cli_loop", 4): f"flygate kr-causality → '{card('kr-causality').get('main')}' · {card('kr-causality').get('sub')}",
        ("cli_loop", 5): "터미널의 evidence_ids 줄이 차례로 빛나고 다섯 카드에 근거 ID 표시",
        ("cli_safe", 0): f"OpenShell 샌드박스 카드: 기본 거부 · 파이썬만 허용 호스트 · 비루트 sandbox · 스모크 {sm.get('passed', '')}/{sm.get('total', '')}",
        ("cli_safe", 1): f"[gateway] ready · [heartbeat] started · cron {cr.get('name', '')} {cr.get('expr', '')} @ {cr.get('tz', '')} → flygate watch 출력(대기열 {(c2.get('watch') or {}).get('queue')}건)",
        ("cli_safe", 2): "submitted: [] 강조 · '보고와 제출은 사람이 합니다'",
        ("close", 0): "초파리 뇌 점구름 위로 구호가 솟아오릅니다: " + "".join(p[0] for p in SLOGAN_PARTS).replace("\n", " / "),
    }
    return v


NEW = [("cli_install", "CLI 설치", "FlyGate Agent CLI · 설치 한 줄", 3),
       ("cli_loop", "CLI 루프", "FlyGate Agent CLI · 에이전트 루프", 3),
       ("cli_safe", "CLI 상시", "FlyGate Agent CLI · 상시 실행 · 안전", 3)]


def timeline(d: dict) -> list[dict]:
    old = v4.timeline(d)
    vo, vis = narration(d), {**v41.new_vis(d), **vis_new(d)}
    labels = {"validated": "공개 참조 세트 검증", "close": "분자에서 환자까지 · 근거가 먼저"}
    seq = []
    for s in old:
        if s["id"] == "cli":
            seq += [{"id": i, "name": n, "label": lab, "step": st, "fresh": True} for i, n, lab, st in NEW]
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


def write_script(tl: list[dict], dur: float, built: str, c2: dict | None):
    total_syl = sum(syllables(bt["vo"]) for s in tl for bt in s["beats"])
    cli_s = sum(s["t1"] - s["t0"] for s in tl if s["id"].startswith("cli_"))
    lines = [
        f"# Project-FlyGate 쇼릴 v{VERSION} 내레이션 대본", "",
        f"- 영상: `web/public/showreel/FlyGate_showreel_v{VERSION}.html` (1920×1080, 30fps) · 음원 `{AUDIO_REL}`",
        f"- **총 길이 {int(dur // 60)}분 {dur % 60:.0f}초 ({dur:.1f}초)** · 장면 {len(tl)}개 · 내레이션 {total_syl}음절(추정) · v4.1.0 의 CLI 장면(9.5초)을 'FlyGate Agent CLI' 세 장면({cli_s:.1f}초)으로 늘린 판입니다",
        f"- 이 대본은 `scripts/build_reel_v4_2.py` 가 영상과 같은 장면 시간표(`scripts/reel/flygate_v4_2.timeline.json`)로 생성합니다. 손으로 고치지 말고 빌더의 `narration()` 을 고친 뒤 다시 빌드합니다.",
        f"- 수치는 빌드 시점({built})의 저장소 JSON · 측정 파일 값입니다. CLI 장면의 터미널 출력은 `scripts/reel/cli_runs.json`(기록 {str(c2.get('recorded')).replace('T', ' ').replace('Z', ' UTC') if c2 else '없음'})에 있는 실제 실행 결과를 줄인 것입니다. `--refresh-cli` 로 다시 돌립니다.",
        "- 마무리 구호는 빌더의 `SLOGAN_PARTS` 한 줄에서 옵니다. 화면 색 조각과 마무리 내레이션이 모두 이 값을 씁니다.",
        "- 약물감시 전문가가 아닌 시청자를 위해 약어는 처음 나올 때 우리말 뜻을 함께 씁니다. 화면에는 'SDR(불균형 보고 신호)'처럼 괄호나 작은 풀이 줄을 붙이고, 내레이션은 '불균형 보고 신호, 즉 SDR'로 처음 읽은 뒤에는 '신호'처럼 뜻으로만 읽습니다(빌더의 `gloss_narration()`).",
        f"- 장면 길이는 내레이션 시간(초당 {RATE}음절, 문장 사이 {GAP}초 숨)에 꼬리 0.8초 이하를 더한 값입니다(마무리 장면은 {CLOSE_MAX:.0f}초 이하). 음절 수는 숫자와 영문을 소리 나는 대로 센 추정값입니다. 영문 고유명사는 괄호 안 읽기대로 읽습니다: FlyGate(플라이게이트), FlyDiscovery(플라이디스커버리), FlyVigilance(플라이비질런스), Nemotron(네모트론), NemoClaw(네모클로), OpenShell(오픈셸), OpenClaw(오픈클로), FAERS(페어스), SDR(에스디알), CLI(시엘아이), triage(트리아지), grade(그레이드), critic(크리틱), discover(디스커버), kr-causality(케이알 코절리티), DiffDock(디프독), NIM(님), cron(크론), watch(워치).",
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
    if c2:
        lines += ["", "## CLI 장면의 실제 실행 기록", "", "| 명령 | 실행(UTC) | 걸린 시간 |", "| --- | --- | --- |",
                  f"| `{c2['install']['cmd']}` (새 복제본 {c2['install']['commit']}) | {c2['install']['when']} | {c2['install']['wall']}초 |",
                  f"| `flygate --help` | {c2['help']['when']} | – |"]
        lines += [f"| `{x['cmd']}` | {x['when']} | {x['wall']}초 |" for x in c2["loop"]]
        lines += [f"| `{c2['watch']['cmd']}` | {c2['watch']['when']} | {c2['watch']['wall']}초 |",
                  "", "- 게이트웨이 · 하트비트 · cron 줄은 샌드박스 기록 `agent/evidence/openclaw_cron_2026-09-28.txt`, 스모크 점검은 `web/public/data/agent.json`(`agent/evidence/openshell_smoke_2026-09-28.txt`)에서 읽습니다."]
    lines += ["", "## 읽을 때", "",
              "- 장면이 바뀌는 순간(각 표의 첫 줄 시작 시각)에 첫 문장을 시작하면 화면의 숫자가 나타나는 때와 맞습니다.",
              "- 문장 사이 숨은 짧게 둡니다. 화면의 강조 틀이 지금 읽는 숫자 · 카드로 옮겨 가므로 틀을 따라 읽으면 박자가 맞습니다.",
              "- CLI 장면에서는 명령이 입력되기 시작할 때 그 명령 이름을 읽습니다.",
              "- Jev(TypeSafe AI)는 기술 구성 크레딧에서만 이름을 읽고, 본문에서는 '비자기회귀 판단 모델'로 부릅니다. 비교 기준선은 '모델 단독 · 질문 하나'입니다.", ""]
    SCRIPT_OUT.write_text("\n".join(lines))


def main():
    if "--refresh-cli" in sys.argv:
        refresh_cli()
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
        "bt": v4.backtest_part(), "nvs": v4.nvskills_part(disc), "arch": v4.arch_part(), "cli": v4.cli_part(), "cli2": cli2_part(),
        "slogan": SLOGAN_PARTS,
    }
    # v4.2: 약어 풀이. 실제 사례 장면(08)에서 WHO-UMC 가 처음 나오므로 그 자리에서 뜻을 붙입니다
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
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html.replace(marker, blob))
    TIMELINE_OUT.write_text(json.dumps({"version": VERSION, "built": data["meta"]["built"], "dur": dur, "rate": RATE,
                                        "scenes": [{k: v for k, v in s.items()} for s in tl]}, ensure_ascii=False, indent=1) + "\n")
    write_script(tl, dur, data["meta"]["built"], data["cli2"])
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB) · {len(tl)} scenes · {dur:.1f} s")
    print(f"wrote {TIMELINE_OUT.relative_to(ROOT)} · {SCRIPT_OUT.relative_to(ROOT)}")
    for s in tl:
        for bt in s["beats"]:
            r = syllables(bt["vo"]) / (bt["b"] - bt["a"])
            if r > RATE + 1e-6:
                print(f"  ! narration fast ({r:.2f} syl/s) {s['id']}: {bt['vo']}")
        tail = (s["t1"] - s["t0"]) - s["beats"][-1]["b"]
        if tail > (1.0 if s["id"] == "close" else 0.8) + 1e-6:
            print(f"  ! scene tail {tail:.1f} s {s['id']}")
        if s["id"] == "close" and s["t1"] - s["t0"] > CLOSE_MAX + 1e-6:
            print(f"  ! close scene longer than {CLOSE_MAX} s")
    for s in tl:
        syl = sum(syllables(bt["vo"]) for bt in s["beats"])
        print(f"  {s['id']:<12} {s['t1'] - s['t0']:5.1f} s  {syl:3d} syl  {syl / (s['beats'][-1]['b'] - s['beats'][0]['a']):.2f} syl/s")
    print("  fallbacks: " + ("; ".join(FALLBACKS) if FALLBACKS else "none"))


if __name__ == "__main__":
    main()
