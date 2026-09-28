"""Project-FlyGate 쇼릴 v3 를 파일 하나로 완결된 HTML 로 만듭니다.

데모 약물 니라파립으로 두 단계를 잇습니다. STEP 1 FlyDiscovery(시판 전: PARP1 → MSA-Search → OpenFold3 → DiffDock → Boltz-2 → 크리틱)에서
STEP 2 FlyVigilance(시판 후: FAERS → 규칙 → 라벨 근거 → 비자기회귀 판단 + Nemotron → 크리틱 → 사람)로 이어지고,
NemoClaw · OpenShell 에이전트 구성으로 끝납니다.

템플릿(scripts/reel/flygate_v3.template.html)의 `/*__DATA__*/null` 자리에 실측 수치를 JSON 으로 넣습니다.
수치는 모두 빌드할 때 저장소의 JSON 에서 읽으므로, 측정을 다시 하면 이 스크립트만 다시 돌리면 됩니다.
키가 없으면 해당 항목은 대체값을 쓰거나 화면에서 빠지고, 어떤 대체값을 썼는지 마지막 줄에 출력합니다.
외부 폰트, CDN, fetch 를 쓰지 않으므로 파일만 따로 전달해도 어디서나 그대로 재생됩니다.
render_reel.py 가 file:// 주소로 프레임을 뽑을 수 있게 window.__reel.renderAt(t) / DUR 를 그대로 둡니다.

사용:
  .venv/bin/python scripts/build_reel_v3.py [출력 경로]
  .venv/bin/python scripts/build_reel_v3.py --refresh-grade   # 로컬 API(:8000)에서 니라파립 근거 등급 스냅숏을 다시 받습니다

입력(모두 저장소 안의 파일입니다):
  fly_discovery/measurements/measurements.json, nim/{of3_parp1_niraparib.pdb, niraparib_diffdock_pose1-5.sdf, parp1.a3m, dd_eval_all.json}
  web/public/data/bench.json (jev_triage, nemotron, ablation, ablation_blind)
  web/public/data/validation.json (refsets.*.methods 를 key 로 찾습니다), literature_eval.json, critic_probe.json, skills.json
  web/public/data/faers/overview.json, web/public/data/agent.json (있을 때만), web/public/showreel/brain_pts.json
  api/_data/{signals,reporter_mix}.json.gz
  scripts/reel/niraparib_grade.json (GET /api/grade?drug=NIRAPARIB&pt=thrombocytopenia 응답을 줄인 스냅숏)
"""
import gzip
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUB = ROOT / "web/public"
DISC = ROOT / "fly_discovery/measurements"
REEL = ROOT / "scripts/reel"
TEMPLATE = REEL / "flygate_v3.template.html"
GRADE_SNAPSHOT = REEL / "niraparib_grade.json"
DEFAULT_OUT = PUB / "showreel/FlyGate_showreel_v3.0.0.html"

REPO = "https://github.com/Team-FlyGate/Project-FlyGate"
LIVE = "https://flygate.kr"

FALLBACKS: list[str] = []  # 대체값을 쓴 항목(빌드 끝에 출력합니다)

# bench.json 에 ablation_blind(결과 코드를 가린 비교)가 없을 때만 쓰는 대체값입니다.
# 2026-09-27 시험 실행(data/bench_blind_run1.json)과 같은 값이며, pipeline/bench/ablation.py 를 돌리면 bench.json 값을 그대로 읽습니다.
BLIND_FALLBACK = {
    "n": 440, "serious": 250,
    "flyvigilance": {"serious_without_review": 4, "over_escalated": 2, "escalated": 139,
                     "routes_serious": {"expedite": 137, "signal_review": 94, "follow_up": 15, "monitor": 4, "close": 0}},
    "raw_jev": {"serious_without_review": 19, "over_escalated": 71, "escalated": 302},
    "tests": {"serious_unreviewed_fv_vs_raw": {"p": 0.0015}, "over_escalation_fv_vs_raw": {"p": 3e-21},
              "workload_fv_vs_raw": {"p": 7e-48}},
}

# 에이전트 구성의 대체값입니다(agent.json 도, agent/ 아래 실제 파일도 없을 때).
# 허용 호스트는 api/_fv 와 fly_discovery 가 실제로 부르는 곳이고, 워크스페이스 파일은 NVIDIA DLI
# 'Securing Agents with NemoClaw and OpenShell' 3b 의 OpenClaw 구성입니다.
WS_ROLE = {"SOUL.md": "역할 · 경계 · 어조", "AGENTS.md": "작업 규칙 · 근거 ID 인용", "IDENTITY.md": "이름 · 성격",
           "USER.md": "주 사용자 · PV 평가자", "TOOLS.md": "flygate CLI 사용법", "HEARTBEAT.md": "주기 점검 목록",
           "MEMORY.md": "오래 남길 기억"}
WS_ORDER = ["SOUL.md", "AGENTS.md", "IDENTITY.md", "USER.md", "TOOLS.md", "HEARTBEAT.md", "MEMORY.md"]
AGENT_FALLBACK = {
    "workspace": [[f, WS_ROLE[f]] for f in ("SOUL.md", "AGENTS.md", "TOOLS.md", "HEARTBEAT.md", "MEMORY.md")],
    "hosts": [["integrate.api.nvidia.com", "POST"], ["health.api.nvidia.com", "POST"], ["api.typesafe.ai", "POST"],
              ["api.fda.gov", "GET"], ["eutils.ncbi.nlm.nih.gov", "GET"]],
}
STAT_NAME = {"a": "보고 건수", "prr": "PRR", "ror_lo": "ROR₀₂₅", "chi2s": "χ²", "ic025": "IC₀₂₅"}
KB_KEYS = ("raw_named", "knowledge", "fv_knowledge", "kb", "named")  # 지식 기반 판별(약·반응 이름 사용) 조건의 key 후보


def jload(path: pathlib.Path):
    return json.loads(path.read_text())


def jload_opt(path: pathlib.Path):
    try:
        return jload(path)
    except (OSError, ValueError):
        FALLBACKS.append(f"{path.relative_to(ROOT)} 없음")
        return {}


def dig(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def r2(v: float) -> float:
    return round(float(v), 2)


# ---------------------------------------------------------------- FlyDiscovery
def parse_pdb(path: pathlib.Path):
    """OpenFold3 예측 복합체에서 사슬 A 의 Cα(좌표, pLDDT)와 리간드 원자를 뽑습니다."""
    ca, plddt, lig, lig_el = [], [], [], []
    for line in path.read_text().splitlines():
        if line.startswith("ENDMDL"):
            break
        rec = line[:6].strip()
        if rec not in ("ATOM", "HETATM"):
            continue
        name = line[12:16].strip()
        xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
        b = float(line[60:66])
        if rec == "ATOM" and name == "CA":
            ca += xyz
            plddt.append(round(b, 1))
        elif rec == "HETATM":
            el = line[76:78].strip() or name[0]
            if el != "H":
                lig += xyz
                lig_el.append(el)
    return ca, plddt, lig, lig_el


def parse_sdf(path: pathlib.Path):
    lines = path.read_text().splitlines()
    na, nb = int(lines[3][:3]), int(lines[3][3:6])
    xyz, el = [], []
    for ln in lines[4:4 + na]:
        p = ln.split()
        xyz += [float(p[0]), float(p[1]), float(p[2])]
        el.append(p[3])
    bonds = []
    for ln in lines[4 + na:4 + na + nb]:
        bonds.append([int(ln[:3]) - 1, int(ln[3:6]) - 1, int(ln[6:9])])
    return xyz, el, bonds


def msa_rows(path: pathlib.Path):
    """a3m 을 쿼리 열에 맞춘 행으로 바꿉니다. 2=쿼리와 같은 잔기, 1=치환, 0=간격(소문자 삽입은 버립니다)."""
    recs, cur = [], None
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            if cur is not None:
                recs.append(cur)
            cur = ""
        elif cur is not None:
            cur += line.strip()
    if cur is not None:
        recs.append(cur)
    aligned = [re.sub(r"[a-z]", "", s) for s in recs]
    q = aligned[0]
    rows = []
    for s in aligned:
        s = s[:len(q)].ljust(len(q), "-")
        rows.append("".join("0" if c == "-" else "2" if c == q[i] else "1" for i, c in enumerate(s)))
    return rows, len(q)


def disc_part() -> dict:
    m = jload(DISC / "measurements.json")
    of3 = m["openfold3_msa"]
    ca, plddt, lig, lig_el = parse_pdb(DISC / "nim/of3_parp1_niraparib.pdb")
    poses, el0, bonds0 = [], None, None
    for i in range(1, 6):
        xyz, el, bonds = parse_sdf(DISC / f"nim/niraparib_diffdock_pose{i}.sdf")
        if el0 is None:
            el0, bonds0 = el, bonds
        poses.append([r2(v) for v in xyz])
    # OpenFold3 리간드와 DiffDock 포즈는 원자 순서(원소 배열)가 같아 SDF 결합표를 함께 씁니다. 다르면 결합표를 빼고 거리로 잇습니다.
    lig_bonds = bonds0 if lig_el == el0 else None
    dd = jload(DISC / "nim/dd_eval_all.json")
    rows, qlen = msa_rows(DISC / "nim/parp1.a3m")
    vina = {r[0]: r[1] for r in m["diffdock_boltz2_chembl"]}
    boltz = {r[0]: {"pic50": r[3], "p": r[4], "chembl": r[5], "n": r[6]} for r in m["diffdock_boltz2_chembl"]}
    crit = m["critic_eval"]["nvidia/nemotron-3-super-120b-a12b"]
    b = m["parp1_affinity_benchmark"]
    return {
        "msa": {"n": of3["msa_homologs"], "len": qlen, "rows": rows,
                "sec": 63.6, "db": "Uniref30_2302"},  # 초와 DB 이름은 fly_discovery/README.md 의 실측 표 값입니다
        "of3": {k: of3[k] for k in ("plddt", "ptm", "iptm", "ca_rmsd_vs_4R6E", "n_ca", "ligand_rmsd", "seconds")}
               | {"ca": [r2(v) for v in ca], "b": plddt, "lig": [r2(v) for v in lig], "lig_el": "".join(e[0] for e in lig_el),
                  "lig_bonds": lig_bonds},
        "dd": {"poses": poses, "el": "".join(e[0] for e in el0), "bonds": bonds0,
               "redock": [["니라파립 @ PARP1", dd["parp1-4r6e-chain-a--niraparib"]["rmsd_xtal"]],
                          ["아픽사반 @ Factor Xa", dd["factor-xa-2p16--apixaban"]["rmsd_xtal"]],
                          ["셀레콕시브 @ COX-2", dd["cox2-3ln1--celecoxib"]["rmsd_xtal"]]]},
        "vina": [["15R", vina["15r@parp1"]], ["파미파립", vina["pamiparib@parp1"]],
                 ["니라파립", vina["niraparib@parp1"]], ["루카파립", vina["rucaparib@parp1"]]],
        "vina_xa": vina["niraparib@xa"],
        "boltz_nir": boltz["niraparib@parp1"],
        "bench": {k: b[k] for k in ("n", "spearman", "pearson", "mae", "ef_top25", "hit", "k", "sens", "spec")} | {"pairs": b["pairs"]},
        "critic": {"model": "Nemotron 3 Super 120B", "sec": crit["sec"], "caught": crit["caught"], "n_over": crit["n_over"],
                   "passed": crit["passed"], "n_valid": crit["n_valid"],
                   "rows": [[r[0], r[1], r[2]] for r in crit["rows"]]},
    }


# ---------------------------------------------------------------- 니라파립 시판 후
def trim_grade(g: dict) -> dict:
    lit, lab = g.get("literature") or {}, g.get("label") or {}
    s = lit.get("summary") or {}
    return {
        "drug": g["drug"], "pt": g["pt"], "pv_class": g["pv_class"], "pv_class_name": g["pv_class_name"],
        "pv_hint": g.get("pv_hint"), "review_priority": g.get("review_priority"), "grade": g.get("grade"),
        "label_status_name": dig(g, "axes", "label_status_name"),
        "signal_name": dig(g, "axes", "signal_name"),
        "knowledge_p": dig(g, "axes", "knowledge", "p"),
        "stats": g.get("stats"), "caution": g.get("caution"),
        "label": {"brand": lab.get("brand"), "effective": lab.get("effective"), "setid": lab.get("setid"),
                  "sections": (lab.get("by_pt") or {}).get(g["pt"], {}).get("sections", [])},
        "literature": {"count": lit.get("count"), "read": s.get("read"), "relevant": s.get("relevant"),
                       "supportive": s.get("supportive"), "designs": s.get("designs"),
                       "judge_questions": lit.get("judge_questions"), "judge_latency_ms": lit.get("judge_latency_ms")},
        "recorded": time.strftime("%Y-%m-%d %H:%M"),
    }


def refresh_grade():
    url = "http://127.0.0.1:8000/api/grade?drug=NIRAPARIB&pt=thrombocytopenia"
    with urllib.request.urlopen(url, timeout=120) as r:
        g = json.loads(r.read())
    GRADE_SNAPSHOT.write_text(json.dumps(trim_grade(g), ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {GRADE_SNAPSHOT}")


def nir_part() -> dict:
    sig = json.loads(gzip.open(ROOT / "api/_data/signals.json.gz", "rt").read())
    cols = sig["columns"]
    row = next(dict(zip(cols, r)) for r in sig["drugs"]["NIRAPARIB"] if r[0] == "thrombocytopenia")
    g = jload(GRADE_SNAPSHOT)
    keep = ("pv_class_name", "pv_hint", "review_priority", "grade", "label_status_name", "signal_name", "knowledge_p", "label", "literature")
    return {"asof": sig["asof"], "cases": sig["n_drug"]["NIRAPARIB"],
            "a": row["a"], "prr": row["prr"], "prr_lo": row["prr_lo"], "prr_hi": row["prr_hi"],
            "ror_lo": row["ror_lo"], "ic025": row["ic025"], "sdr": bool(row["evans"] and row["ror_sig"] and row["ic_sig"]),
            "grade": {k: g.get(k) for k in keep}}


# ---------------------------------------------------------------- FlyVigilance
def blind_part(bench: dict) -> dict:
    """결과 코드를 가린 비교. FlyVigilance 와 기준선(모델 단독 · 질문 하나)을 같은 사례 짝으로 비교합니다."""
    ab = bench.get("ablation_blind")
    fallback = not (isinstance(ab, dict) and "flyvigilance" in ab and "raw_jev" in ab and "tests" in ab)
    if fallback:
        FALLBACKS.append("bench.json ablation_blind 없음 → 2026-09-27 시험 실행 값")
        ab = BLIND_FALLBACK
    fv, base, tests = ab["flyvigilance"], ab["raw_jev"], ab["tests"]
    serious = ab["serious"]
    routes = fv.get("routes_serious") or {}
    auto = fv["serious_without_review"]
    if not routes:  # 경로별 중대 사례 수가 없으면 사람 우선과 나머지 검토만 나눕니다
        human = fv["escalated"] - fv["over_escalated"]
        routes = {"expedite": human, "signal_review": serious - human - auto, "follow_up": 0, "monitor": auto, "close": 0}
    return {
        "fallback": fallback, "n": ab["n"], "serious": serious,
        "fv": {"auto": auto, "over": fv["over_escalated"], "human": fv["escalated"],
               "routes": {k: routes.get(k, 0) for k in ("expedite", "signal_review", "follow_up", "monitor", "close")}},
        "base": {"auto": base["serious_without_review"], "over": base["over_escalated"], "human": base["escalated"]},
        "p": {"unreviewed": tests["serious_unreviewed_fv_vs_raw"]["p"], "over": tests["over_escalation_fv_vs_raw"]["p"],
              "workload": tests["workload_fv_vs_raw"]["p"]},
    }


def val_part(val: dict) -> dict:
    """공개 참조 세트: FlyVigilance 지식 기반 판별(약·반응 이름 사용)과 최고 통계 지표의 AUC, Harpaz 전향 결과."""
    sets = []
    for name in ("OMOP", "EU-ADR", "Harpaz"):
        r = dig(val, "refsets", name)
        if not r:
            FALLBACKS.append(f"validation.json refsets.{name} 없음 → 화면에서 뺌")
            continue
        ms = r.get("methods", [])
        kb = next((m for k in KB_KEYS for m in ms if m.get("key") == k), None) \
            or next((m for m in ms if m.get("family") in ("memory", "knowledge")), None)
        stats = [m for m in ms if m.get("family") == "metric"]
        if not kb or not stats:
            FALLBACKS.append(f"validation.json {name}: 지식 기반 판별 또는 통계 지표 없음 → 화면에서 뺌")
            continue
        best = max(stats, key=lambda m: m["auc"])
        sets.append({"name": name, "n": r.get("n"), "kb": round(kb["auc"], 3),
                     "best": {"name": STAT_NAME.get(best["key"], best.get("label", best["key"])), "auc": round(best["auc"], 3)}})
    pro = dig(val, "refsets", "Harpaz-prospective")
    tri = dig(pro, "points", "triple") if pro else None
    out = {"sets": sets, "pro": None}
    if tri:
        out["pro"] = {"tp": tri["tp"], "pos": tri["tp"] + tri["fn"], "fp": tri["fp"], "neg": tri["fp"] + tri["tn"],
                      "ppv": tri["ppv"], "window": pro.get("window", "")}
    else:
        FALLBACKS.append("validation.json Harpaz-prospective 없음 → 화면에서 뺌")
    return out


def bias_part() -> dict:
    mix = json.loads(gzip.open(ROOT / "api/_data/reporter_mix.json.gz", "rt").read())
    sig = json.loads(gzip.open(ROOT / "api/_data/signals.json.gz", "rt").read())
    cols = sig["columns"]
    full = {r[0]: dict(zip(cols, r)) for r in sig["drugs"]["ISOTRETINOIN"]}
    pairs = mix["pairs"]["ISOTRETINOIN"]
    ibd = pairs["inflammatory bowel disease"]
    return {"drug": "ISOTRETINOIN", "a": ibd["a"], "lw": ibd["n_lw"], "bg": mix["background"]["lw"],
            "rows": [[pt, full[pt]["prr"], pairs[pt]["no_lawyer"]["prr"], bool(pairs[pt]["no_lawyer"]["sdr"])]
                     for pt in ("inflammatory bowel disease", "colitis ulcerative", "crohn's disease")]}


def fv_part() -> dict:
    bench = jload(PUB / "data/bench.json")
    ov = jload(PUB / "data/faers/overview.json")
    val = jload_opt(PUB / "data/validation.json")
    lit = jload_opt(PUB / "data/literature_eval.json")
    probe = jload_opt(PUB / "data/critic_probe.json")
    skills = jload_opt(PUB / "data/skills.json")
    ps = probe.get("summary") or {}
    wrong = [k for k in ps if k != "ctrl"]
    return {
        "ov": {"asof": ov["asof"], "q_reports": ov["per_quarter"][-1]["reports"], "first": ov["first"],
               "raw_reports": ov["raw_reports"], "cases": ov["cases"]},
        "jev_p50": dig(bench, "jev_triage", "latency_ms", "p50"), "questions": dig(bench, "jev_triage", "questions_per_call", default=7),
        "gen_p50": dig(bench, "nemotron", "triage", "latency_ms", "p50"), "gen_n": dig(bench, "nemotron", "triage", "n"),
        "label_p50": dig(bench, "ablation", "grounding", "label_latency_ms", "p50"),
        "blind": blind_part(bench),
        "val": val_part(val),
        "lit": {"n": lit.get("n"), "acc": lit.get("accuracy")} if lit else None,
        "probe": {"caught": sum(ps[k]["correct"] for k in wrong), "n": sum(ps[k]["n"] for k in wrong),
                  "ctrl": dig(ps, "ctrl", "correct"), "ctrl_n": dig(ps, "ctrl", "n")} if ps else None,
        "bias": bias_part(),
        "skills": len(skills) if isinstance(skills, list) else 0,
    }


# ---------------------------------------------------------------- 에이전트 (NemoClaw / OpenShell)
def _as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [v]
    return []


HOST_ORDER = ["integrate.api.nvidia.com", "health.api.nvidia.com", "api.typesafe.ai", "api.fda.gov", "eutils.ncbi.nlm.nih.gov"]


def _internal(host: str) -> bool:
    """NemoClaw 하네스 내부 경로(inference.local, 게이트웨이 IP)는 인터넷 이그레스가 아니므로 목록에서 뺍니다."""
    return host.endswith(".local") or bool(re.fullmatch(r"[\d.]+", host))


def _policy_yaml() -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    for y in sorted((ROOT / "agent/policy").glob("*.y*ml")):
        try:
            d = yaml.safe_load(y.read_text())
        except yaml.YAMLError:
            continue
        if isinstance(d, dict) and d.get("network_policies"):
            return d
    return {}


def _smoke_group(name: str) -> str:
    """스모크 검사 이름(영어·한국어 모두)을 화면에 쓸 묶음으로 나눕니다."""
    n = name.lower()
    has = lambda *ks: any(k in n for k in ks)
    if has("root", "비루트", "seccomp", "privs", "capabilit"):
        return "비루트 · seccomp · 권한 상승 차단"
    if has("workspace", "작업 공간", "skills in place"):
        return "OpenClaw 워크스페이스 · 스킬 배치"
    if has("flygate", "in sandbox", "샌드박스 안"):
        return "샌드박스 안에서 flygate 실행"
    if has("write", "쓰기"):
        return "파일 쓰기 경계 (Landlock)"
    if has("binary", "curl", "not in rules", "method", "path", "실행 파일", "규칙에 없는", "(l7)"):
        return "묶이지 않은 실행 파일 · 경로 · 메서드 차단"
    if n.startswith(("denied", "차단")):
        return "목록 밖 호스트 차단"
    if n.startswith(("allowed", "허용")):
        return "허용 호스트 연결"
    return "기타 점검"


def smoke_part(sm_json) -> dict | None:
    """라이브 OpenShell 스모크: agent.json 의 smoke(ran=true) 또는 agent/evidence/openshell_smoke_*.txt 의 RESULT 줄."""
    rows, when, source = [], None, None
    if isinstance(sm_json, dict) and sm_json.get("ran"):
        rows = [(bool(r.get("pass", r.get("ok"))), str(r.get("check") or r.get("name") or ""))
                for r in _as_list(sm_json.get("results")) if isinstance(r, dict)]
        when, source = sm_json.get("when"), "agent.json"
    if not rows:
        logs = sorted((ROOT / "agent/evidence").glob("openshell_smoke_*.txt"))
        if logs:
            txt = logs[-1].read_text()
            rows = [(p[1] == "PASS", p[2]) for p in (ln.split("\t") for ln in txt.splitlines() if ln.startswith("RESULT\t")) if len(p) >= 3]
            m = re.search(r"date_utc:\s*(\S+)", txt)
            when, source = (m.group(1) if m else None), str(logs[-1].relative_to(ROOT))
    if not rows:
        return None
    groups = {}
    for ok, name in rows:
        g = groups.setdefault(_smoke_group(name), [0, 0])
        g[0] += ok
        g[1] += 1
    order = ["허용 호스트 연결", "목록 밖 호스트 차단", "묶이지 않은 실행 파일 · 경로 · 메서드 차단", "파일 쓰기 경계 (Landlock)",
             "비루트 · seccomp · 권한 상승 차단", "OpenClaw 워크스페이스 · 스킬 배치", "샌드박스 안에서 flygate 실행", "기타 점검"]
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})", str(when or ""))
    when = f"{m.group(1)} {m.group(2)} UTC" if m else str(when or "")[:20]
    return {"when": when, "source": source, "passed": sum(ok for ok, _ in rows), "total": len(rows),
            "groups": [[k, *groups[k]] for k in order if k in groups]}


def agent_part(n_skills: int) -> dict:
    """agent.json(web/src/lib/types.ts 의 AgentInfo)이 있으면 그 값을, 없으면 agent/ 아래 실제 파일을, 그것도 없으면 대체값을 씁니다."""
    a = jload(PUB / "data/agent.json") if (PUB / "data/agent.json").exists() else {}
    out = {"source": "agent.json" if a else "repo", "workspace": None, "skills": n_skills, "hosts": None,
           "rw": None, "user": None, "seccomp": None, "triggers": [], "smoke": None}
    py = {} if a.get("policy") else _policy_yaml()
    # 워크스페이스
    ws = [w for w in _as_list(a.get("workspace")) if w]
    if ws:
        def role(f, r):  # 화면에는 짧은 이름표를 씁니다. 모르는 파일이면 agent.json 설명의 첫 마디를 씁니다
            return WS_ROLE.get(f) or re.split(r"입니다|[.,(]", str(r or ""))[0].strip()[:24]
        out["workspace"] = [[w, role(w, "")] if isinstance(w, str) else
                            [w.get("file") or w.get("name") or w.get("path") or "", role(w.get("file") or w.get("name"), w.get("role"))]
                            for w in ws][:8]
    else:
        wdir = ROOT / "agent/workspace"
        files = sorted((p.name for p in wdir.glob("*.md")), key=lambda f: WS_ORDER.index(f) if f in WS_ORDER else 99) if wdir.is_dir() else []
        if files:
            out["workspace"] = [[f, WS_ROLE.get(f, "")] for f in files][:8]
        else:
            FALLBACKS.append("에이전트 워크스페이스 파일 없음 → DLI 3b 구성")
            out["workspace"] = AGENT_FALLBACK["workspace"]
    # 스킬 수: agent.json → 저장소의 SKILL.md 개수
    sk = a.get("skills")
    if isinstance(sk, list) and sk:
        out["skills"] = len(sk)
    else:
        n = len(list((ROOT / "skills").glob("*/SKILL.md"))) + len(list((ROOT / "agent/skills").glob("*/SKILL.md")))
        out["skills"] = n or n_skills
    # 이그레스 허용 목록: agent.json policy.egress → agent/policy/*.yaml 의 network_policies → 대체값
    pol = a.get("policy") or {}
    eg = pol.get("egress")
    if isinstance(eg, list) and eg:
        hosts = []
        for e in eg:
            if isinstance(e, str):
                hosts.append([e, ""])
            elif isinstance(e, dict) and e.get("host"):
                ms = re.findall(r"[A-Z]+", " ".join(str(m).upper() for m in _as_list(e.get("methods"))))
                hosts.append([e["host"], " ".join(sorted(set(ms)))])
        out["hosts"] = hosts
    elif py:
        hosts = []
        for blk in (py.get("network_policies") or {}).values():
            for e in (blk or {}).get("endpoints", []) or []:
                ms = {str(r["allow"].get("method", "")).upper() for r in e.get("rules", []) or [] if isinstance(r, dict) and isinstance(r.get("allow"), dict)}
                if e.get("host"):
                    hosts.append([e["host"], " ".join(sorted(m for m in ms if m))])
        out["hosts"] = hosts
    else:
        FALLBACKS.append("이그레스 정책 파일 없음 → 코드가 부르는 호스트 목록")
        out["hosts"] = AGENT_FALLBACK["hosts"]
    # 같은 호스트가 여러 규칙으로 나뉘어 있으면 메서드를 모으고, 내부 경로는 빼고, NVIDIA 부터 정렬합니다
    merged = {}
    for h, m in out["hosts"]:
        if not _internal(h):
            merged.setdefault(h, set()).update(x for x in m.split() if x)
    rank = lambda h: HOST_ORDER.index(h) if h in HOST_ORDER else len(HOST_ORDER)
    out["hosts"] = [[h, " ".join(sorted(merged[h]))] for h in sorted(merged, key=rank)]
    fs = pol.get("filesystem") or py.get("filesystem_policy") or {}
    # 쓰기 가능 경로를 최상위 디렉터리로 줄입니다(/sandbox/.openclaw → /sandbox). /dev 아래 런타임 경로는 뺍니다
    tops = []
    for q in _as_list(fs.get("read_write")) + (["/sandbox"] if fs.get("include_workdir") else []):
        q = str(q).split()[0] if str(q).strip() else ""
        top = "/" + q.strip("/").split("/")[0]
        if q.startswith("/") and not q.startswith("/dev") and top not in tops:
            tops.append(top)
    out["rw"] = tops[:3] or None
    proc = pol.get("process") or py.get("process") or {}
    user = str(proc.get("user") or proc.get("run_as_user") or "")
    out["user"] = re.split(r"[:\s(]", user)[0] or None
    sc = str(proc.get("seccomp") or "")
    out["seccomp"] = "seccomp 필터 · no_new_privs · capability 0" if "NoNewPrivs" in sc else None
    trig = []
    for t in _as_list(a.get("triggers")):
        if not isinstance(t, dict):
            continue
        name = str(t.get("name", "")).lower()
        if name not in ("heartbeat", "cron"):
            continue
        sess = str(t.get("session", ""))
        where = "메인 세션" if sess.startswith("main") else "격리 세션" if "isolated" in sess else sess[:12]
        when = re.sub(r"\s*\(openclaw[^)]*\)", "", str(t.get("trigger", ""))).strip()
        trig.append(["하트비트" if name == "heartbeat" else "cron", f"{where} · {when}"[:48]])
    out["triggers"] = trig
    out["smoke"] = smoke_part(a.get("smoke"))
    return out


def brain_part() -> dict:
    """MaleCNS 점구름에서 뇌 부분만(복측 신경삭 제외) 1/3 로 줄여 씁니다(마무리 장면 배경)."""
    p = jload(PUB / "showreel/brain_pts.json")
    idx = [i for i in range(0, len(p["x"]), 3) if p["z"][i] >= 420]
    return {"layers": p["layers"], "x": [p["x"][i] for i in idx], "y": [p["y"][i] for i in idx],
            "z": [p["z"][i] for i in idx], "l": [p["l"][i] for i in idx]}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--refresh-grade" in sys.argv:
        refresh_grade()
    out = pathlib.Path(args[0]) if args else DEFAULT_OUT
    fv = fv_part()
    data = {
        "meta": {"built": time.strftime("%Y-%m-%d %H:%M"), "repo": REPO, "live": LIVE},
        "disc": disc_part(),
        "nir": nir_part(),
        "fv": fv,
        "agent": agent_part(fv["skills"]),
        "brain": brain_part(),
    }
    html = TEMPLATE.read_text()
    marker = "/*__DATA__*/null"
    assert html.count(marker) == 1, "template data marker missing"
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html.replace(marker, blob))
    b = fv["blind"]
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  blind: n={b['n']} serious={b['serious']} reached={b['serious'] - b['fv']['auto']} vs {b['serious'] - b['base']['auto']}"
          f" · p={b['p']['unreviewed']:.2g} / {b['p']['over']:.2g} / {b['p']['workload']:.2g}"
          f" · source={'fallback' if b['fallback'] else 'bench.json'}")
    print(f"  refsets: " + ", ".join(f"{s['name']} {s['kb']} vs {s['best']['name']} {s['best']['auc']}" for s in fv["val"]["sets"]))
    ag = data["agent"]
    print(f"  agent: source={ag['source']} workspace={len(ag['workspace'])} skills={ag['skills']} hosts={len(ag['hosts'])}"
          f" smoke={'ran' if ag['smoke'] else 'none'}")
    print("  fallbacks: " + ("; ".join(FALLBACKS) if FALLBACKS else "none"))


if __name__ == "__main__":
    main()
