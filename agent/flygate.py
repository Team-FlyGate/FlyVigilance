#!/usr/bin/env python3
"""flygate: FlyGate 에이전트가 쓰는 도구 모음(현대 CLI 패턴, NemoClaw 강좌 04b)입니다.

OpenClaw 에이전트는 exec 도구로 이 명령을 부릅니다. 하위 명령은 모두 JSON 한 덩어리를 stdout 에 쓰고,
결과마다 근거 ID(evidence_ids)를 붙입니다. 모델을 부르는 일은 기존 코드(api/_fv)에 맡기고 여기서는 감싸기만 합니다.

  triage        ICSR 한 건 반사 판단 (규칙 게이트 -> 라벨 근거 -> 판단 모델 7문항 -> 결정 정책 + DME 안전망)
  grade         약물-반응 쌍의 근거 등급과 PV 분류 후보 (FAERS SQL 통계 + 라벨 절 + 문헌 읽기)
  signals       한 약물의 불균형 지표 상위 반응 (웨어하우스 추출본, 모델 미개입)
  kr-causality  국내 보고 구조화(Nemotron) + 한국형 인과성 평가 ver 2.0 (판단 모델 + 규칙 합산)
  critic        주장 목록을 크리틱 3단(+ 안전 가드)에 통과
  discover      FlyDiscovery 실측(MSA-Search, OpenFold3, DiffDock, Boltz-2, ChEMBL)과 크리틱 판정
  watch         하트비트/cron 작업: 최신 분기 감지, 감시 목록 재계산, 날짜별 메모, 사람 검토 대기열

키가 없거나 네트워크가 막히면 실패를 숨기지 않고 표시합니다. 판단 모델이나 가드를 쓰지 못한 결과는
'안전'이 아니라 '사람 확인'으로 돌립니다(fail closed). 이 도구는 보고서나 메시지를 밖으로 보내지 않습니다.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import gzip
import hashlib
import json
import os
import pathlib
import sys

AGENT = pathlib.Path(__file__).resolve().parent
ROOT = AGENT.parent
sys.path.insert(0, str(ROOT / "api"))
MEASUREMENTS = ROOT / "fly_discovery" / "measurements"
WORKSPACE = AGENT / "workspace"
PERSONA_FILES = ["SOUL.md", "AGENTS.md", "IDENTITY.md", "TOOLS.md", "HEARTBEAT.md"]

# 감시 목록 기본값입니다. 니라파립(FlyGate 가 시판 전부터 따라온 분자)과 같은 계열 약, 보고 편향 사례 하나를 둡니다.
DEFAULT_WATCHLIST = [
    ["NIRAPARIB", "thrombocytopenia"], ["NIRAPARIB", "platelet count decreased"], ["NIRAPARIB", "anaemia"],
    ["NIRAPARIB", "neutropenia"], ["NIRAPARIB", "myelodysplastic syndrome"], ["NIRAPARIB", "acute myeloid leukaemia"],
    ["NIRAPARIB", "hypertension"], ["TALAZOPARIB", "thrombocytopenia"], ["TALAZOPARIB", "myelodysplastic syndrome"],
    ["ISOTRETINOIN", "inflammatory bowel disease"],
]


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def _ids(*groups) -> list[str]:
    """근거 ID 를 순서대로 모으고 중복을 뺍니다."""
    out: list[str] = []
    for g in groups:
        for x in g or []:
            if x and x not in out:
                out.append(x)
    return out


# ---------------------------------------------------------------- triage
def _load_case(arg: str | None, demo: int | None) -> dict:
    if demo is not None:
        from _fv import config
        cases = json.load(gzip.open(config.DATA / "cases.json.gz", "rt"))
        return cases[demo % len(cases)]
    d = json.loads(pathlib.Path(arg).read_text())
    return d.get("case", d) if isinstance(d, dict) else d[0]


def _compact_answers(ans: dict) -> dict:
    out = {}
    for k, v in ans.items():
        if v.get("type") == "noul":
            out[k] = round(v["noul"], 3)
        elif v.get("type") == "score":
            out[k] = {"score": round(v["score"], 2), "confidence": round(v.get("confidence", 0), 2)}
        else:
            out[k] = {"choice": v.get("choice"), "confidence": round(v.get("confidence", 0), 2)}
    return out


async def _triage(case: dict, regime: str, include_outcome: bool, grounded: bool) -> dict:
    from _fv import clients, triage as tri
    try:
        res = await tri.triage(case, regime=regime, grounded=grounded, include_outcome=include_outcome)
        mode = "reflex"
    except clients.NotConfigured as e:
        # 판단 모델을 쓰지 못하면 규칙 층(ICH 최소 요소, 라벨 근거, DME)만 돌리고 사람에게 보냅니다
        g = await tri.ground(case) if grounded else None
        dme = tri.dme_hits(case)
        res = {"suspect": tri.principal_suspect(case), "validity": tri.validity(case), "grounding": g, "jev": None,
               "decision": {"action": "human_review", "tier": "human", "system2": False, "regime": regime,
                            "reasons": [f"{e} not configured: reflex judgment unavailable -> fail closed to the human queue"]
                            + ([f"[DME] {', '.join(dme)}: EMA designated medical event"] if dme else [])}}
        mode = "rules_only"
    g = res.get("grounding") or {}
    lab = g.get("label") or {}
    label_ids = ([f"label:{lab['setid']}"] if lab.get("found") else []) + [h["id"] for h in lab.get("hits", [])]
    return {
        "cmd": "triage", "mode": mode, "case": case["primaryid"], "quarter": case.get("quarter"),
        "suspect": res["suspect"], "reactions": case.get("reactions", [])[:8], "outcome_codes_hidden": not include_outcome,
        "decision": res["decision"], "validity": res["validity"],
        "grounding": {"label_found": lab.get("found", False), "brand": lab.get("brand"), "listed": lab.get("listed"),
                      "expected": g.get("expected"), "expected_source": g.get("expected_source")} if grounded else None,
        "judgments": _compact_answers(res["jev"]["answers"]) if res.get("jev") else None,
        "latency_ms": (res.get("jev") or {}).get("latency_ms"),
        "evidence_ids": _ids([f"faers:case:{case['primaryid']}"], label_ids),
        "note": "판단은 집단 보정 확률이고 이 한 건의 보장이 아닙니다(R10). 신속보고 여부는 사람이 확인하고 사람이 제출합니다.",
    }


def cmd_triage(a) -> dict:
    case = _load_case(a.case, a.demo)
    return asyncio.run(_triage(case, a.regime.upper(), not a.no_outcome, not a.no_ground))


# ---------------------------------------------------------------- grade
async def _grade(drug: str, pt: str, route: str | None, judge: bool) -> dict:
    import httpx
    from _fv import evidence, grade, literature
    async with httpx.AsyncClient() as c:
        lab = await evidence.label_lookup(drug, [pt], c, route)
        lit = await literature.read(drug, pt, c, use_jev=judge)
    g = grade.grade_pair(drug, pt, evidence.faers_2x2(drug, pt), lab, lit)
    keep = ("id", "drug", "pt", "pv_class", "pv_class_name", "pv_hint", "review_priority", "grade", "grade_name",
            "axes", "flags", "label_sections", "stats", "basis", "gaps", "summary", "caution")
    out = {"cmd": "grade", **{k: g[k] for k in keep}}
    out["literature"] = {"query": lit.get("query"), "count": lit.get("count"), "summary": lit.get("summary"),
                         "judge_error": lit.get("judge_error"),
                         "articles": [{k: x.get(k) for k in ("id", "year", "design", "design_source", "addresses", "supports")}
                                      for x in lit.get("articles", [])]}
    out["evidence_ids"] = _ids([g["id"]], g["basis"], [h["id"] for h in lab.get("hits", [])], lit.get("ids"))
    return out


def cmd_grade(a) -> dict:
    return asyncio.run(_grade(a.drug, a.pt, a.route, not a.no_judge))


# ---------------------------------------------------------------- signals
def cmd_signals(a) -> dict:
    from _fv import evidence
    s = evidence._signals()
    rows = evidence.drug_profile(a.drug, 10 ** 6 if a.pt else a.limit)
    if a.pt:
        rows = [r for r in rows if a.pt.lower() in r["pt"]][: a.limit]
    out = []
    for r in rows:
        out.append({"pt": r["pt"], "a": r["a"], "prr": r["prr"], "ror025": r["ror_lo"], "ic025": r["ic025"],
                    "sdr": evidence.signal_tier(r), "id": f"faers:2x2:{evidence.id_drug(a.drug)}:{r['pt']}@{s['asof']}"})
    return {"cmd": "signals", "drug": a.drug.upper(), "asof": s.get("asof"), "n_reports_with_drug": s.get("n_drug", {}).get(a.drug.upper()),
            "rows": out, "evidence_ids": [r["id"] for r in out],
            "note": "SDR(불균형 보고 신호)은 보고 연관이지 인과가 아닙니다(R1). FAERS 에는 노출 분모가 없습니다(R2). "
                    "sdr=strong 은 Evans ∧ ROR025>1 ∧ IC025>0 세 기준을 모두 넘었다는 뜻입니다."}


# ---------------------------------------------------------------- kr-causality
async def _kr(text: str, form: str, route: bool) -> dict:
    from _fv import kr, triage as tri
    intake = await kr.intake(text, form)
    case = intake["case"]
    res = await kr.causality_kr(case, tri.case_state(case), text)
    items = [{k: it.get(k) for k in ("id", "name", "choice", "label", "score", "confidence", "method", "evidence", "needs_review")}
             for it in res["items"]]
    routed = await _triage(case, "KR", True, True) if route else None
    return {"cmd": "kr-causality", "form": form, "intake_model": intake.get("model"), "kr_form": intake.get("kr_form"),
            "missing": intake.get("missing"), "narrative_en": intake.get("narrative_en"), "case": case,
            "total": res["total"], "range": [res["min"], res["max"]], "grade": res["grade"], "band": res["band"],
            "items": items, "who_umc": res["who_umc"], "assessed_reaction": res["assessed_reaction"],
            "mfds_label": res["mfds_label"], "kr_routing": routed and routed["decision"], "note": res["note"],
            "evidence_ids": _ids([e for it in res["items"] for e in (it.get("evidence") or [])],
                                 [h["id"] for h in ((res.get("label") or {}).get("hits") or [])],
                                 routed and routed["evidence_ids"])}


def cmd_kr(a) -> dict:
    return asyncio.run(_kr(pathlib.Path(a.report).read_text(), a.form, a.route))


# ---------------------------------------------------------------- critic
async def _critic(spec: dict, offline: bool) -> dict:
    from _fv import assess, clients, config
    claims, state, bundle = spec["claims"], spec.get("state", ""), spec.get("bundle")
    if bundle is None and spec.get("case"):  # 근거 묶음이 없으면 케이스로 새로 만듭니다(라벨·문헌 조회)
        from _fv import evidence, triage as tri
        case = spec["case"]
        state = state or tri.case_state(case)
        bundle = await evidence.bundle(case, tri.principal_suspect(case))
    bundle = bundle or {"ids": []}
    assess.clean_evidence(claims)
    have_keys = bool(config.TYPESAFE_API_KEY and config.NVIDIA_API_KEY)
    if not offline and have_keys:
        try:
            res = await assess.critic_only(claims, state, bundle)
            issues = res["issues"]
            guard_unknown = res["guard"].get("unchecked") or []
            verdict = "returned" if issues else ("human_check" if guard_unknown else "pass")
            return {"cmd": "critic", "tiers": ["T1 rules", "T2 numeric oracle", "T3 overclaim (judgment model)", "safety guard"],
                    "verdict": verdict, "issues": issues, "guard": res["guard"],
                    "overclaim_p": {c.get("id"): c.get("overclaim_p") for c in claims},
                    "evidence_ids": _ids([e for c in claims for e in (c.get("evidence") or [])])}
        except (clients.NotConfigured, RuntimeError) as e:
            offline_reason = f"{type(e).__name__}: {e}"[:160]
    else:
        offline_reason = "--offline" if offline else "API keys not configured"
    t1 = assess.tier1_rules(claims, set(bundle.get("ids", [])))
    t2 = assess.tier2_oracle(claims, assess._bundle_numbers(state, bundle))
    issues = t1 + t2
    return {"cmd": "critic", "tiers": ["T1 rules", "T2 numeric oracle"], "skipped": ["T3 overclaim", "safety guard"],
            "skip_reason": offline_reason, "verdict": "returned" if issues else "human_check", "issues": issues,
            "evidence_ids": _ids([e for c in claims for e in (c.get("evidence") or [])]),
            "note": "T3(과잉해석 판단)와 안전 가드를 돌리지 못했습니다. 규칙 2단을 통과해도 '통과'가 아니라 '사람 확인'입니다."}


def cmd_critic(a) -> dict:
    spec = json.loads(pathlib.Path(a.claims).read_text())
    if isinstance(spec, list):
        spec = {"claims": spec}
    return asyncio.run(_critic(spec, a.offline))


# ---------------------------------------------------------------- discover
TARGETS = {
    "parp1": {"label": "PARP1", "pdb": "4R6E-A", "protein": "Human PARP1, 4R6E chain A", "file": "parp1-4r6e-chain-a"},
    "xa": {"label": "Factor Xa", "pdb": "2P16", "protein": "Human factor Xa, 2P16", "file": "factor-xa-2p16"},
    "cox2": {"label": "COX-2", "pdb": "3LN1", "protein": "Mouse COX-2, 3LN1 (non-human protein)", "file": "cox2-3ln1"},
}
ALIASES = {"parp1": "parp1", "parp-1": "parp1", "xa": "xa", "fxa": "xa", "factorxa": "xa", "factor-xa": "xa",
           "f10": "xa", "cox2": "cox2", "cox-2": "cox2", "ptgs2": "cox2"}
# 후보의 역할은 FlyDiscovery 화면(fly_discovery/web/index.html 의 후보 표)과 같습니다
ROLES = {
    "15r@parp1": ("in", "PARP1 co-crystal ligand"), "pamiparib@parp1": ("in", "PARP inhibitor"),
    "niraparib@parp1": ("in", "PARP inhibitor (FlyGate molecule)"), "rucaparib@parp1": ("in", "PARP inhibitor"),
    "celecoxib@cox2": ("redock_control", "co-crystal ligand redocked (setup check)"),
    "niraparib@cox2": ("cross_dock", "exploratory cross-docking"),
    "apixaban@xa": ("redock_control", "co-crystal ligand redocked (setup check)"),
    "niraparib@xa": ("cross_dock", "exploratory cross-docking"),
}
# 3단 크리틱이 반려한 이유입니다(팀 스킬 flygate-evidence-critic 의 규칙 이름). 측정 기록 8건의 순서와 같습니다.
CLAIM_RULES = [None, None, None, None, "cross-target", "confidence≠affinity", "predicted≠measured", "n<8"]
# MSA-Search 실행 기록입니다(fly_discovery/README.md 의 실측 표, 원본 정렬은 measurements/nim/parp1.a3m).
MSA_SEARCH = {"endpoint": "/v1/biology/colabfold/msa-search/predict", "database": "Uniref30_2302", "seconds": 63.6,
              "source": "fly_discovery/README.md, fly_discovery/measurements/nim/parp1.a3m"}
DISCOVERY_LIMITS = [
    "재도킹 RMSD 는 공결정 구조에 원래 리간드를 다시 넣은 대조 실험입니다. 도킹 설정이 작동한다는 것 이상은 말하지 않습니다.",
    "4R6E 는 공개 구조라 OpenFold3 학습 데이터에 있었을 수 있습니다.",
    "다른 단백질의 도킹 점수는 교차 비교하지 않습니다(선택성은 실험 친화도로만 판단합니다).",
    "Boltz-2 pIC50 은 예측값이지 측정값이 아닙니다. 친화도 벤치마크는 PARP1 한 타깃, n=39 입니다.",
    "COX-2 구조(3LN1)는 쥐 단백질이라 사람 결과로 옮기지 않습니다.",
]


def _discovery_data() -> dict:
    return json.loads((MEASUREMENTS / "measurements.json").read_text())


def cmd_discover(a) -> dict:
    norm = a.target.lower().replace(" ", "").replace("_", "-")
    key = ALIASES.get(norm) or ALIASES.get(norm.replace("-", ""))
    if not key:
        raise SystemExit(json.dumps({"cmd": "discover", "error": f"unknown target {a.target!r}; use parp1 | xa | cox2"}))
    t, m = TARGETS[key], _discovery_data()
    dd = json.loads((MEASUREMENTS / "nim" / "dd_eval_all.json").read_text())
    cands, ids = [], []
    for k, vina, dd_conf, pic50, p_bind, chembl, n in m["diffdock_boltz2_chembl"]:
        lig, tgt = k.split("@")
        if tgt != key:
            continue
        kind, role = ROLES.get(k, ("?", "?"))
        pose = dd.get(f"{t['file']}--{lig}", {})
        ev = [f"vina:{key}/{lig}", f"diffdock:{t['pdb']}/{lig}", f"boltz2:{key}/{lig}"] + ([f"chembl:{lig}/{key}"] if n else [])
        ids += ev
        cands.append({"ligand": lig, "kind": kind, "role": role, "vina_kcal_mol": vina, "diffdock_confidence": dd_conf,
                      "diffdock_rmsd_to_xtal_A": pose.get("rmsd_xtal"), "diffdock_pocket_dist_A": pose.get("pocket_dist"),
                      "boltz2_pic50_predicted": pic50, "boltz2_p_binder": p_bind,
                      "chembl_median_pchembl": chembl, "chembl_n": n, "evidence_ids": ev})
    cands.sort(key=lambda c: c["vina_kcal_mol"])
    out = {"cmd": "discover", "target": t["label"], "structure_input": t["protein"], "candidates": cands,
           "ranking_rule": "순위는 같은 수용체·같은 프로토콜 안에서만 매깁니다(PARP1 후보 4개). 교차 도킹 행은 결합 근거가 아닙니다."}
    if key == "parp1":
        of3, bench = m["openfold3_msa"], m["parp1_affinity_benchmark"]
        out["structure"] = {"pipeline": "MSA-Search -> OpenFold3 (NVIDIA BioNeMo NIM)",
                            "msa_search": {**MSA_SEARCH, "homologs": of3["msa_homologs"], "evidence_id": "msa:parp1/4R6E-A"},
                            "endpoint": of3["endpoint"],
                            "msa_homologs": of3["msa_homologs"], "plddt": of3["plddt"], "ptm": of3["ptm"], "iptm": of3["iptm"],
                            "ca_rmsd_vs_4R6E_A": of3["ca_rmsd_vs_4R6E"], "ligand_rmsd_A": of3["ligand_rmsd"],
                            "evidence_id": "openfold3:parp1/4R6E-A"}
        ids.insert(0, "msa:parp1/4R6E-A")
        out["affinity_benchmark"] = {k: bench[k] for k in ("n", "spearman", "pearson", "mae", "ef_top25", "sens", "spec")} | {
            "evidence_id": "boltz2:parp1/chembl-benchmark-39", "source": "ChEMBL PARP1 IC50 (pChEMBL median) vs Boltz-2"}
        ids += ["openfold3:parp1/4R6E-A", "boltz2:parp1/chembl-benchmark-39"]
        out["failed_runs"] = {"openfold2": m["openfold2"], "nemoguard_topic_control": m["nemoguard_topic_control"]}
    label_kw = {"parp1": ("PARP1", "4R6E", "pamiparib", "rucaparib", "15R", "ChEMBL"), "xa": ("Xa",), "cox2": ("COX",)}[key]
    critic = []
    models = m["critic_eval"]
    first = next(iter(models.values()))["rows"]
    for i, (claim, expected, _) in enumerate(first):
        if not any(kw.lower() in claim.lower() for kw in label_kw):
            continue
        critic.append({"claim": claim, "expected": expected, "rule": CLAIM_RULES[i] if i < len(CLAIM_RULES) else None,
                       "verdicts": {mod.split("/")[-1]: v["rows"][i][2] for mod, v in models.items()}})
    out["critic"] = {"measured": critic, "summary": {mod.split("/")[-1]: {k: v[k] for k in ("caught", "n_over", "passed", "n_valid", "sec")}
                                                     for mod, v in models.items()},
                     "note": "측정 8건(과잉해석 4, 정상 4)의 기록입니다. Lightning 행은 출력 토큰 한도 안에서 판정 줄(VERDICT)을 "
                             "내지 못한 실행이라 NONE 으로 남았습니다. 수치는 이 8건 범위의 측정입니다."}
    if not critic:
        out["critic"]["note"] = "이 타깃에 대해 기록된 크리틱 실행이 없습니다. " + out["critic"]["note"]
    handoff = {"molecule": "NIRAPARIB", "reaction": "thrombocytopenia", "next": "flygate grade NIRAPARIB thrombocytopenia",
               "why": "같은 분자(니라파립)를 시판 후 감시(STEP 2 FlyVigilance)로 넘깁니다."}
    try:
        from _fv import evidence
        f = evidence.faers_2x2("NIRAPARIB", "thrombocytopenia")
        if f and f.get("a") is not None:
            handoff["faers"] = {"id": f["id"], "a": f["a"], "prr": f["prr"], "ror025": f["ror_lo"], "ic025": f["ic025"],
                                "sdr": evidence.signal_tier(f)}
            ids.append(f["id"])
    except ImportError:
        handoff["faers"] = None
    out["handoff_to_vigilance"] = handoff
    out["limits"] = DISCOVERY_LIMITS
    out["source"] = "fly_discovery/measurements/measurements.json (+ nim/*.json raw NIM responses)"
    out["evidence_ids"] = _ids(ids)
    return out


# ---------------------------------------------------------------- watch
def _latest_quarter(warehouse: pathlib.Path | None) -> dict:
    """웨어하우스(DuckDB)가 있으면 그 최신 분기를, 없으면 신호 추출본(api/_data/signals.json.gz)의 기준 분기를 씁니다."""
    from _fv import evidence
    info = {"extract_asof": evidence._signals().get("asof"), "warehouse": None, "warehouse_quarter": None}
    if warehouse and warehouse.exists():
        try:
            import duckdb
            con = duckdb.connect(str(warehouse), read_only=True)
            info["warehouse_quarter"] = con.execute("SELECT max(quarter) FROM ops_quarter").fetchone()[0]
            info["warehouse"] = str(warehouse)
            con.close()
        except Exception as e:  # 잠금·모듈 없음은 추출본으로 물러섭니다
            info["warehouse_error"] = f"{type(e).__name__}: {e}"[:160]
    raw = ROOT / "data" / "faers" / "raw"
    if raw.exists():
        zips = sorted(p.stem.replace("faers_ascii_", "").upper() for p in raw.glob("faers_ascii_*.zip"))
        info["downloaded_latest"] = zips[-1] if zips else None
    info["quarter"] = info["warehouse_quarter"] or info["extract_asof"]
    info["source"] = "warehouse" if info["warehouse_quarter"] else "signals extract"
    return info


def _pair_stats(con, drug: str, pt: str) -> dict | None:
    from _fv import evidence
    if con is not None:
        r = con.execute("""SELECT a, prr, ror_lo, ic025, chi2_yates, evans_signal, ror_signal, ic_signal
                           FROM sig_signal WHERE drug = ? AND pt = ?""", [drug.upper(), pt.lower()]).fetchone()
        if not r:
            return {"a": None, "source": "warehouse"}
        a, prr, ror_lo, ic025, chi2, ev, rs, ics = r
        return {"a": a, "prr": round(prr, 3), "ror_lo": round(ror_lo, 3), "ic025": round(ic025, 3), "chi2": round(chi2, 1),
                "evans": ev, "ror_sig": rs, "ic_sig": ics, "source": "warehouse"}
    f = evidence.faers_2x2(drug, pt)
    return {**f, "source": "signals extract"} if f else None


async def _label_facts(drugs: list[str], pts_by_drug: dict, online: bool) -> dict:
    """라벨 절 조회는 캐시(FV_CACHE_DIR)가 있을 때나 --online 일 때만 합니다. 오프라인에서 새로 부르지 않습니다."""
    import httpx
    from _fv import evidence
    out = {}
    cdir = evidence._cache_dir()
    async with httpx.AsyncClient() as c:
        for d in drugs:
            cached = bool(cdir and (cdir / f"openfda_label_{d.upper()}.json").exists())
            if not (cached or online):
                out[d] = None
                continue
            out[d] = await evidence.label_lookup(d, pts_by_drug[d], c)
    return out


async def _openfda_freshness() -> dict:
    """openFDA 이상사례 API 의 갱신일(meta.last_updated)만 봅니다. 허용 목록의 GET /drug/event.json 한 번입니다."""
    import httpx
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get("https://api.fda.gov/drug/event.json", params={"limit": 1}, timeout=20)
        return {"status": r.status_code, "last_updated": (r.json().get("meta") or {}).get("last_updated")}
    except Exception as e:
        return {"status": 0, "error": f"{type(e).__name__}"}


def _quarter_end(q: str) -> dt.date:
    y, n = int(q[:4]), int(q[-1])
    return dt.date(y, 3 * n, 30 if n in (2, 3) else 31)


def _workspace_check(live: pathlib.Path) -> dict:
    """배포한 페르소나 파일(저장소의 agent/workspace)과 살아 있는 작업 공간을 SHA-256 으로 대조합니다."""
    res = {}
    for f in PERSONA_FILES:
        ref, cur = WORKSPACE / f, live / f
        h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None
        res[f] = {"deployed": h(ref), "live": h(cur), "same": h(ref) is not None and h(ref) == h(cur)}
    return res


async def _watch(a) -> dict:
    from _fv import grade, triage as tri
    today = a.date or dt.date.today().isoformat()
    mem = pathlib.Path(a.memory_dir)
    mem.mkdir(parents=True, exist_ok=True)
    state_p = mem / "watch_state.json"
    prev = json.loads(state_p.read_text()) if state_p.exists() else {}
    wl = json.loads(pathlib.Path(a.watchlist).read_text()) if a.watchlist else DEFAULT_WATCHLIST
    wl = [[d.upper(), p.lower()] for d, p in (x.values() if isinstance(x, dict) else x for x in wl)]
    q = _latest_quarter(pathlib.Path(a.warehouse) if a.warehouse else None)
    queue = []
    new_quarter = bool(prev.get("quarter")) and prev.get("quarter") != q["quarter"]
    if new_quarter:
        queue.append({"kind": "new_quarter", "what": f"새 분기 {q['quarter']} 가 적재되었습니다(지난 실행 {prev['quarter']}). "
                      "감시 목록 전체를 다시 검토합니다.", "evidence_ids": []})
    if q.get("downloaded_latest") and q["downloaded_latest"] > (q["quarter"] or ""):
        queue.append({"kind": "operator", "what": f"{q['downloaded_latest']} 원천 파일을 받았지만 아직 적재하지 않았습니다. "
                      "운영자가 pipeline/faers 적재를 돌려야 합니다.", "evidence_ids": []})
    fresh = await _openfda_freshness() if a.online else None
    if fresh and fresh.get("last_updated") and q["quarter"]:
        lag = (dt.date.fromisoformat(fresh["last_updated"]) - _quarter_end(q["quarter"])).days
        fresh["days_after_our_quarter_end"] = lag
        if lag > 120:
            queue.append({"kind": "operator", "what": f"openFDA 갱신일 {fresh['last_updated']} 이 우리 기준 분기 끝보다 {lag}일 뒤입니다. "
                          "새 분기 공개 여부를 운영자가 확인합니다(scripts/download_faers.sh).", "evidence_ids": []})
    con = None
    if q["source"] == "warehouse":
        import duckdb
        con = duckdb.connect(q["warehouse"], read_only=True)
    pts_by_drug: dict = {}
    for d, p in wl:
        pts_by_drug.setdefault(d, []).append(p)
    labels = await _label_facts(list(pts_by_drug), pts_by_drug, a.online)
    rows, prev_tiers = [], prev.get("pairs", {})
    from _fv import evidence
    for d, p in wl:
        f = _pair_stats(con, d, p)
        tier = evidence.signal_tier(f)
        lab = labels.get(d)
        if lab is None:            # 라벨을 보지 않았습니다(오프라인, 캐시 없음)
            by, reg, label_name = {}, -1, "미확인"
        elif not lab.get("found"):  # 조회했지만 미국 라벨이 없습니다
            by, reg, label_name = {}, -1, grade.LABEL_STATUS_NAMES["no_label"]
        else:
            by = lab.get("by_pt", {}).get(p, {})
            reg = int(by.get("rank", 0))
            label_name = grade.LABEL_STATUS_NAMES.get(by.get("label_status") or ("unlisted" if reg == 0 else ""), "?")
        pc = grade.pv_class(reg, tier, bool(by.get("disclaimer")))
        fid = f"faers:2x2:{evidence.id_drug(d)}:{p}@{q['quarter']}"
        lab_ids = [h["id"] for h in (lab or {}).get("hits", []) if h["pt"] == p]
        before = prev_tiers.get(f"{d}|{p}")
        change = None if before in (None, tier) else f"{before} -> {tier}"
        f = f or {}
        bias = grade.reporting_bias(d, p)   # 변호사·소비자 보고 편중(약사 검토 반영)
        flags = (["EMA DME"] if p in grade._dme() else []) + (
            [f"변호사 보고 {bias['lawyer_share']:.0%}"] if bias and bias["flag_lawyer"] else []) + (
            [f"소비자 보고 {bias['consumer_share']:.0%}"] if bias and bias["flag_consumer"] else [])
        row = {"drug": d, "pt": p, "a": f.get("a"), "prr": f.get("prr"), "ror025": f.get("ror_lo"), "ic025": f.get("ic025"),
               "sdr": tier, "label": label_name, "pv_class": pc, "pv_class_name": grade.PV_CLASSES[pc][0], "flags": flags,
               "change": change, "source": f.get("source"), "evidence_ids": _ids([fid], lab_ids)}
        rows.append(row)
        if before is None and bias and (bias["flag_lawyer"] or bias["flag_consumer"]) and tier == "strong":
            nl = bias["no_lawyer"]
            queue.append({"kind": "reporting_bias", "what": f"{d} · {p}: 보고의 {', '.join(flags)} 입니다. PRR {_fmt(f.get('prr'))} 은 "
                          f"소송 등으로 자극된 보고에 부풀었을 수 있습니다. 변호사 보고를 빼면 a={nl['a']}, PRR {nl['prr']:.1f}, "
                          f"SDR {'유지' if nl['sdr'] else '사라짐'}입니다.", "evidence_ids": row["evidence_ids"]})
        if change and tier == "strong":
            queue.append({"kind": "new_sdr", "what": f"{d} · {p}: SDR 이 새로 섰습니다({change}). 신호 검토 대상입니다.",
                          "evidence_ids": row["evidence_ids"]})
        elif change and before == "strong":
            queue.append({"kind": "sdr_lost", "what": f"{d} · {p}: SDR 이 사라졌습니다({change}). 안전하다는 뜻은 아닙니다(R4).",
                          "evidence_ids": row["evidence_ids"]})
        if pc == "review_sdr":
            queue.append({"kind": "review_sdr", "what": f"{d} · {p}: 라벨에 없는데 SDR 이 섰습니다(검토가 필요한 SDR 후보).",
                          "evidence_ids": row["evidence_ids"]})
    if con is not None:
        con.close()
    triaged = []
    if a.triage:
        from _fv import config
        cases = json.load(gzip.open(config.DATA / "cases.json.gz", "rt"))
        done = set(prev.get("triaged", []))
        todo = [c for c in cases if c["primaryid"] not in done and c.get("quarter") == q["quarter"]][: a.triage]
        for c in todo:
            r = await _triage(c, "US", True, True)
            triaged.append({"case": c["primaryid"], "mode": r["mode"], "action": r["decision"]["action"],
                            "tier": r["decision"]["tier"], "reasons": r["decision"]["reasons"][:2]})
            if r["decision"]["tier"] == "human":
                queue.append({"kind": "case", "what": f"FAERS {c['primaryid']}: {r['decision']['action']} "
                              f"({r['decision']['reasons'][0][:120]})", "evidence_ids": r["evidence_ids"]})
            done.add(c["primaryid"])
        prev["triaged"] = sorted(done)
    ws = _workspace_check(pathlib.Path(a.workspace)) if a.workspace else None
    if ws and not all(v["same"] for v in ws.values()):
        changed = [k for k, v in ws.items() if not v["same"]]
        queue.append({"kind": "persona_changed", "what": f"작업 공간 페르소나 파일이 배포본과 다릅니다: {', '.join(changed)}. "
                      "사람이 변경 이력을 확인하고, 모르는 변경이면 배포본으로 되돌립니다.", "evidence_ids": []})
    now = dt.datetime.now().strftime("%H:%M")
    note = mem / f"{today}.md"
    note_existed = note.exists()
    with note.open("a") as fh:
        if not note_existed:
            fh.write(f"# {today} FlyGate 하트비트 메모\n\n이 파일은 `flygate watch` 가 실행마다 덧붙이는 날짜별 원본 메모입니다. "
                     "오래 남길 내용은 사람이 검토한 뒤 MEMORY.md 로 옮깁니다.\n")
        fh.write(_note_md(now, q, prev.get("quarter"), fresh, rows, queue, triaged, ws))
    prev.update({"last_run": dt.datetime.now().isoformat(timespec="seconds"), "quarter": q["quarter"],
                 "pairs": {f"{r['drug']}|{r['pt']}": r["sdr"] for r in rows}})
    state_p.write_text(json.dumps(prev, ensure_ascii=False, indent=1))
    return {"cmd": "watch", "date": today, "quarter": q, "new_quarter": new_quarter, "openfda": fresh, "watchlist": rows,
            "review_queue": queue, "triaged": triaged, "workspace": ws, "memory_note": str(note), "state": str(state_p),
            "submitted": [], "evidence_ids": _ids([e for r in rows for e in r["evidence_ids"]]),
            "note": "이 작업은 아무것도 제출하거나 보내지 않습니다. 대기열은 사람이 검토하고, 보고는 사람이 제출합니다."}


def _fmt(x, nd=2):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def _note_md(now, q, prev_q, fresh, rows, queue, triaged, ws) -> str:
    L = [f"\n## {now} 실행 (flygate watch)\n",
         f"- 기준 분기: **{q['quarter']}** ({'웨어하우스' if q['source'] == 'warehouse' else '신호 추출본'} 기준, 추출본 asof {q['extract_asof']})",
         f"- 지난 실행 기준 분기: {prev_q or '첫 실행'}" + (" → **새 분기**" if prev_q and prev_q != q['quarter'] else ""),
         f"- openFDA 갱신일: " + (f"{fresh.get('last_updated')} (HTTP {fresh.get('status')})" if fresh else "확인하지 않았습니다(오프라인 실행)"),
         "", "### 감시 목록 재계산 (SQL 통계, 모델 미개입)", "",
         "| 약물 | 반응 | a | PRR | ROR025 | IC025 | SDR | 라벨 | PV 분류(후보) | 표시 | 변화 | 근거 ID |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        L.append(f"| {r['drug']} | {r['pt']} | {_fmt(r['a'])} | {_fmt(r['prr'])} | {_fmt(r['ror025'])} | {_fmt(r['ic025'])} | "
                 f"{r['sdr']} | {r['label']} | {r['pv_class_name']} | {', '.join(r['flags']) or '-'} | {r['change'] or '-'} | "
                 f"`{r['evidence_ids'][0]}` |")
    L += ["", "### 사람 검토 대기열", ""]
    L += [f"- [ ] ({x['kind']}) {x['what']}" + (f" 근거: {', '.join('`' + e + '`' for e in x['evidence_ids'][:3])}" if x["evidence_ids"] else "")
          for x in queue] or ["- 새로 올릴 항목이 없습니다."]
    if triaged:
        L += ["", "### 새 사례 반사 판단", ""] + [f"- FAERS {t['case']}: {t['action']} ({t['tier']}, {t['mode']})" for t in triaged]
    if ws:
        L += ["", "### 페르소나 파일 대조 (SHA-256 앞 16자리)", ""] + [
            f"- {k}: {'같음' if v['same'] else '**다름**'} (배포본 {v['deployed'] or '없음'}, 현재 {v['live'] or '없음'})"
            for k, v in ws.items()]
    L += ["", "### 하지 않은 일", "", "- 보고서·메시지를 밖으로 보내지 않았습니다. 제출은 사람이 합니다.",
          "- SDR 은 보고 연관이지 인과가 아닙니다(R1). 라벨 기재 여부는 캐시나 조회로 확인한 경우만 적었습니다.", ""]
    return "\n".join(L)


def cmd_watch(a) -> dict:
    return asyncio.run(_watch(a))


# ---------------------------------------------------------------- entry
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="flygate", description="FlyGate agent tools: every command prints JSON with evidence IDs.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("triage", help="reflex triage of one ICSR")
    s.add_argument("case", nargs="?", help="case JSON file (FAERS case format)")
    s.add_argument("--demo", type=int, help="use the N-th real case from api/_data/cases.json.gz")
    s.add_argument("--regime", default="US", choices=["US", "KR", "us", "kr"])
    s.add_argument("--no-outcome", action="store_true", help="hide outcome codes (outcome-blind evaluation)")
    s.add_argument("--no-ground", action="store_true", help="skip the openFDA label grounding")
    s.set_defaults(fn=cmd_triage)
    s = sub.add_parser("grade", help="evidence grade and PV class candidate for a drug-event pair")
    s.add_argument("drug")
    s.add_argument("pt", help="MedDRA preferred term")
    s.add_argument("--route")
    s.add_argument("--no-judge", action="store_true", help="read literature without the judgment model")
    s.set_defaults(fn=cmd_grade)
    s = sub.add_parser("signals", help="top disproportionality rows for one drug (SQL extract)")
    s.add_argument("drug")
    s.add_argument("--pt", help="substring filter on the reaction")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_signals)
    s = sub.add_parser("kr-causality", help="structure a Korean report and score the Korean causality algorithm v2.0")
    s.add_argument("report", help="text file with the Korean report")
    s.add_argument("--form", default="narrative", choices=["narrative", "professional", "consumer"])
    s.add_argument("--route", action="store_true", help="also route the structured case under the Korean regime (15-day rule)")
    s.set_defaults(fn=cmd_kr)
    s = sub.add_parser("critic", help="run claims through the 3-tier critic (+ safety guard)")
    s.add_argument("claims", help='JSON: {"claims":[...], "state":"...", "bundle":{"ids":[...]}} or {"claims":[...], "case":{...}}')
    s.add_argument("--offline", action="store_true", help="rules only (T1, T2); result is human_check, never pass")
    s.set_defaults(fn=cmd_critic)
    s = sub.add_parser("discover", help="FlyDiscovery evidence and critic verdicts for a target")
    s.add_argument("target", help="parp1 | xa | cox2")
    s.set_defaults(fn=cmd_discover)
    s = sub.add_parser("watch", help="heartbeat/cron job: detect quarter, recompute watchlist, write memory note")
    s.add_argument("--memory-dir", default=str(WORKSPACE / "memory"))
    s.add_argument("--watchlist", help="JSON list of [drug, pt]")
    s.add_argument("--warehouse", default=str(ROOT / "data" / "derived" / "faers.duckdb"))
    s.add_argument("--date", help="YYYY-MM-DD (default: today)")
    s.add_argument("--online", action="store_true", help="allow label lookups and the openFDA freshness check")
    s.add_argument("--triage", type=int, default=0, help="triage the next N untriaged cases of the latest quarter")
    s.add_argument("--workspace", help="live OpenClaw workspace dir to compare persona files with the deployed copy")
    s.set_defaults(fn=cmd_watch)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "triage" and not a.case and a.demo is None:
        build_parser().error("triage needs a case file or --demo N")
    emit(a.fn(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
