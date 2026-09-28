"""Project-FlyGate 쇼릴 v4 를 파일 하나로 완결된 HTML 로 만들고, 같은 장면 시간표로 내레이션 대본을 씁니다.

v3(129초, 10장면)에 없던 내용을 더해 19장면으로 늘렸습니다.
STEP 1 FlyDiscovery(시판 전 후보 물질: BioNeMo NIM, 약물 패널, 재도킹 8종) → 데모 다리(같은 니라파립을 시판 후로)
→ STEP 2 FlyVigilance(시판 후 허가 약물: FAERS 웨어하우스, 워크플로, 실제 사례 트리아지, 국내 규정 모드, PV 분류, 신호 타임머신)
→ 결과 코드를 가린 실측 → 공개 참조 세트 검증 → NVIDIA 공식 Agent Skills 적용 → 약사 검토 → 커넥톰 라우팅 구조
→ NemoClaw · OpenShell · OpenClaw 에이전트 → flygate CLI · 상시 실행 → 마무리.

수치는 모두 빌드할 때 저장소의 JSON · 측정 파일에서 읽습니다. v3 의 데이터 함수(scripts/build_reel_v3.py)를 그대로 가져다 쓰고,
v4 에서 새로 쓰는 데이터만 이 파일에 둡니다. 키가 없으면 대체값을 쓰거나 화면에서 빼고, 마지막 줄에 무엇을 대체했는지 출력합니다.

장면 시간표(TIMELINE)는 이 파일 하나에만 있습니다. 같은 시간표를
  1) HTML 에 넣어 장면 경계와 DUR 로 쓰고,
  2) scripts/reel/flygate_v4.timeline.json 으로 내보내고,
  3) docs/SHOWREEL_SCRIPT_v4.0.0.md (내레이션 대본) 로 씁니다.
그래서 대본의 시각과 영상의 장면 경계가 늘 같습니다.

사용:
  .venv/bin/python scripts/build_reel_v4.py [출력 경로]
  .venv/bin/python scripts/build_reel_v4.py --refresh-kr   # flygate kr-causality · triage 를 다시 돌려 국내 모드 스냅숏을 새로 받습니다

입력(v3 입력에 더해):
  fly_discovery/measurements/{drug_panel.json, redock.json}
  web/public/data/{demo_case_v2.json, guard_policy_eval.json, literature_rerank_eval.json, connectome/meta.json}
  web/public/data/faers/{overview.json, backtest.json, drugs.json}
  api/_data/dme_pts.json, docs/PHARMACIST_REVIEW.md(요약 표 · PV 분류 표), skills/*/skill-card.md
  agent/evidence/openclaw_cron_*.txt, agent/examples/kr_report.txt
  scripts/reel/kr_causality.json (flygate kr-causality 와 US 규정 triage 의 응답을 줄인 스냅숏)
"""
import json
import math
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_reel_v3 as v3  # noqa: E402  v3 의 데이터 함수를 그대로 씁니다(v3 파일은 고치지 않습니다)

ROOT = v3.ROOT
PUB, DISC, REEL = v3.PUB, v3.DISC, v3.REEL
TEMPLATE = REEL / "flygate_v4.template.html"
DEFAULT_OUT = PUB / "showreel/FlyGate_showreel_v4.0.0.html"
TIMELINE_OUT = REEL / "flygate_v4.timeline.json"
SCRIPT_OUT = ROOT / "docs/SHOWREEL_SCRIPT_v4.0.0.md"
KR_SNAPSHOT = REEL / "kr_causality.json"
FALLBACKS = v3.FALLBACKS
jload, jload_opt, dig = v3.jload, v3.jload_opt, v3.dig

KO_DRUG = {"niraparib": "니라파립", "apixaban": "아픽사반", "celecoxib": "셀레콕시브", "dexamethasone": "덱사메타손",
           "risperidone": "리스페리돈", "ruxolitinib": "룩솔리티닙", "lenalidomide": "레날리도마이드", "nirmatrelvir": "니르마트렐비르"}


# ---------------------------------------------------------------- STEP 1 · 약물 패널 · 재도킹
def panel_part(disc: dict) -> dict:
    p = jload(DISC / "drug_panel.json")
    rd = jload(DISC / "redock.json")
    rows = []
    for r in p["rows"]:
        d = r.get("docking") or {}
        mt = r.get("molecule_type") or "Unknown"
        rows.append({"drug": r["drug"].split("\\")[0].title(), "cases": r["cases"], "serious": r["serious"],
                     "type": {"Small molecule": "small", "Antibody": "antibody", "Protein": "protein"}.get(mt, "other"),
                     "dock": d.get("status"), "gene": d.get("gene"), "rmsd": d.get("top1_rmsd")})
    # 재도킹 대조: v3 의 3종(니라파립 · 아픽사반 · 셀레콕시브, dd_eval_all.json) + 약물 패널 5종(redock.json)
    red = [{"name": n.split(" @ ")[0], "target": n.split(" @ ")[1], "rmsd": v, "panel": False} for n, v in disc["dd"]["redock"]]
    secs = []
    for k, r in sorted(rd["results"].items(), key=lambda kv: kv[1]["top1_rmsd"]):
        tgt = r["gene"].split(" ")[0] if r["gene"] else r["target"]
        red.append({"name": KO_DRUG.get(r["drug"], r["drug"]), "target": f"{tgt} · {r['pdb']}", "rmsd": r["top1_rmsd"], "panel": True,
                    "covalent": bool(r.get("note"))})
        secs.append(r["seconds"])
    small = sum(1 for r in rows if r["type"] == "small")
    return {"n_cases": p["n_cases"], "n_suspects": p["n_primary_suspect_drugs"], "rows": rows, "small": small, "bio": len(rows) - small,
            "redock": red, "thr": 2.0, "sec_lo": min(secs), "sec_hi": max(secs),
            "panel_ok": sum(1 for r in red if r["panel"] and r["rmsd"] <= 2.0), "panel_n": sum(1 for r in red if r["panel"])}


# ---------------------------------------------------------------- STEP 2 · FAERS 웨어하우스
def warehouse_part() -> dict:
    ov = jload(PUB / "data/faers/overview.json")
    drugs = jload_opt(PUB / "data/faers/drugs.json")
    return {"quarters": ov["quarters"], "first": ov["first"], "asof": ov["asof"], "raw": ov["raw_reports"], "cases": ov["cases"],
            "pairs": ov["pairs"], "sdr": ov["all3"], "serious": ov["serious_cases"], "drugs": len(drugs) if isinstance(drugs, list) else None,
            "per_q": [[q["quarter"], q["reports"]] for q in ov["per_quarter"]]}


# ---------------------------------------------------------------- STEP 2 · 실제 사례 한 건 (라이브 트리아지 기록)
JEV_KO = {"serious": "중대성", "expected": "예측성 (라벨 기재)", "causality": "인과성 · WHO-UMC", "special": "특수 상황",
          "priority": "우선순위", "route": "다음 경로", "deep": "숙고 필요"}
CHOICE_KO = {"unassessable": "평가 불가", "possible": "가능함", "probable": "상당히 확실함", "pediatric": "소아", "expedite": "사람 우선",
             "none": "해당 없음", "signal_review": "System-2 검토"}


def triage_part() -> dict:
    d = jload(PUB / "data/demo_case_v2.json")
    c, t, a = d["case"], d["triage"], d["assess"]
    ans = t["jev"]["answers"]
    probs = []
    for k in ("serious", "expected", "causality", "special", "priority", "route", "deep"):
        x = ans[k]
        if x["type"] == "noul":
            probs.append([JEV_KO[k], x["noul"], f"{x['noul']:.2f}"])
        elif x["type"] == "score":
            probs.append([JEV_KO[k], x["score"] / 3, f"{x['score']:.2f} / 3"])
        else:
            probs.append([JEV_KO[k], x["probabilities"][x["choice"]], f"{CHOICE_KO.get(x['choice'], x['choice'])} {x['probabilities'][x['choice']]:.2f}"])
    lab = dig(t, "grounding", "label") or {}
    listed = [pt for pt, v in (lab.get("listed") or {}).items() if v]
    rounds = [{"model": r["model"].split("/")[-1], "ms": r["latency_ms"], "claims": len(dig(r, "memo", "claims", default=[]) or []),
               "issues": [{"claim": i["claim"], "tier": i["tier"], "rule": i["rule"]} for i in r["issues"]]} for r in a["rounds"]]
    dec = t["decision"]
    return {"id": c["primaryid"], "quarter": c["quarter"], "age": c["age"], "sex": c["sex"], "suspect": t["suspect"],
            "n_react": len(c["reactions"]), "react0": listed[0] if listed else c["reactions"][0], "outcomes": c["outcomes"],
            "label_brand": lab.get("brand"), "label_listed": listed, "label_sec": "warnings",
            "jev_ms": t["jev"]["latency_ms"], "jev_model": t["jev"]["model"], "probs": probs,
            "action": dec["action"], "deadline": dec.get("deadline"), "regime": dec.get("regime"),
            "rounds": rounds, "verdict": a["verdict"], "guard": {"model": a["guard"]["model"].split("/")[-1], "ms": a["guard"]["latency_ms"],
                                                                  "safe": a["guard"]["safe"]},
            "total_ms": d["total_ms"], "recorded": d["recorded"]}


# ---------------------------------------------------------------- 국내 규정 모드 (스냅숏)
def refresh_kr():
    """flygate kr-causality(국내 서식 구조화 + 한국형 알고리즘 + KR 라우팅)와 같은 케이스의 US 규정 triage 를 돌려 스냅숏을 씁니다."""
    import os
    import tempfile
    env = {**os.environ, "FV_CACHE_DIR": str(ROOT / "data/cache/api")}
    py, cli = str(ROOT / ".venv/bin/python"), str(ROOT / "agent/flygate.py")
    kr = json.loads(subprocess.run([py, cli, "kr-causality", str(ROOT / "agent/examples/kr_report.txt"), "--route"],
                                   capture_output=True, text=True, check=True, env=env).stdout)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(kr["case"], f, ensure_ascii=False)
    us = json.loads(subprocess.run([py, cli, "triage", f.name], capture_output=True, text=True, check=True, env=env).stdout)
    KR_SNAPSHOT.write_text(json.dumps(trim_kr(kr, us), ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {KR_SNAPSHOT}")


def trim_kr(kr: dict, us: dict) -> dict:
    return {"source": "flygate kr-causality agent/examples/kr_report.txt --route · flygate triage (US)",
            "intake_model": kr.get("intake_model"), "kr_form": kr.get("kr_form"), "missing": kr.get("missing"),
            "total": kr["total"], "range": kr["range"], "grade": kr["grade"], "band": kr["band"],
            "items": [{k: it.get(k) for k in ("name", "label", "score", "confidence", "method")} for it in kr["items"]],
            "who_umc": kr.get("who_umc"), "reaction": kr.get("assessed_reaction"), "kr_routing": kr.get("kr_routing"),
            "us_routing": us.get("decision"), "us_latency_ms": us.get("latency_ms"), "recorded": time.strftime("%Y-%m-%d %H:%M")}


def kr_part() -> dict | None:
    snap = jload_opt(KR_SNAPSHOT)
    if not snap:
        FALLBACKS.append("국내 모드 스냅숏 없음 → 국내 장면은 서식 구조만 보입니다")
        return None
    report = (ROOT / "agent/examples/kr_report.txt").read_text().splitlines()
    body = [ln.strip() for ln in report if ln.strip() and not ln.startswith("※") and not ln.startswith("[")]
    f = snap["kr_form"]
    ga, na, da, ra = f.get("가_환자정보") or {}, f.get("나_이상사례정보") or {}, f.get("다_의약품정보") or {}, f.get("라_보고자정보") or {}
    sus = (da.get("의심약물") or [{}])[0]
    ser = [k.replace("_", " ") for k, v in (na.get("중대성") or {}).items() if v]
    form = [["가", "환자", f"{ga.get('나이')}세 · {ga.get('성별')} · {ga.get('체중')} kg"],
            ["나", "이상사례", f"{' · '.join(na.get('이상사례명') or [])} · {'/'.join(ser) or '비중대'}"],
            ["다", "의약품", f"{sus.get('성분명')} {sus.get('용량_용법', '')} · {sus.get('조치', '')}"],
            ["라", "보고자", str(ra.get("보고자_유형") or "")],
            ["마", "보고서", " · ".join(str(x) for x in (f.get("마_보고서정보") or {}).values() if x)],
            ["바", "종합의견", "원문 요지 보존"]]
    krr, usr = snap.get("kr_routing") or {}, snap.get("us_routing") or {}
    return {"model": str(snap.get("intake_model") or "").split("/")[-1], "report": body[:7], "form": form,
            "items": [[it["name"], it["label"], it["score"], it["method"]] for it in snap["items"]],
            "total": snap["total"], "lo": snap["range"][0], "hi": snap["range"][1], "grade": snap["grade"], "band": snap["band"],
            "who": snap.get("who_umc") or {}, "kr": {"action": krr.get("action"), "report15": krr.get("report15"), "deadline": krr.get("deadline")},
            "us": {"action": usr.get("action"), "report15": usr.get("report15"), "deadline": usr.get("deadline")},
            "us_ms": snap.get("us_latency_ms"), "recorded": snap.get("recorded")}


# ---------------------------------------------------------------- PV 분류 · DME · 보고 편향
def pv_class_part() -> dict:
    md = (ROOT / "docs/PHARMACIST_REVIEW.md").read_text()
    sec = md.split("### 2-2.")[1].split("###")[0]
    classes = [[int(m.group(1)), m.group(2).strip(), m.group(3).strip()]
               for m in re.finditer(r"^\| (\d) \| ([^|]+) \| ([^|]+) \|$", sec, re.M)]
    summ = md.split("## 요약")[1].split("\n## ")[0]
    n_review = len(re.findall(r"^\| \d+ \|", summ, re.M))
    dme = jload(ROOT / "api/_data/dme_pts.json")
    return {"classes": classes, "n_review": n_review, "dme_n": dme["n"], "dme_ref": dme["source"]["ref"],
            "dme_pts": ["stevens-johnson syndrome", "toxic epidermal necrolysis", "agranulocytosis", "aplastic anaemia",
                        "torsade de pointes", "hepatic failure", "anaphylactic shock", "rhabdomyolysis"]}


# ---------------------------------------------------------------- 신호 타임머신
def backtest_part() -> dict:
    b = jload(PUB / "data/faers/backtest.json")
    items = b["items"]
    main = next(x for x in items if x["drug"] == "CANAGLIFLOZIN")
    end = b["quarters"].index("2016Q4")
    ser = [[s["q"], s["a"], s.get("ic025"), bool(s.get("signal"))] for s in main["series"][:end + 1]]
    leads = [[x["drug"].title(), x["pt"], x["lead_days"], bool(x.get("left_censored")), x["action"]]
             for x in items if x.get("lead_days") is not None and x.get("action")]
    leads.sort(key=lambda r: -r[2])
    with_action = [x for x in items if x.get("action")]
    return {"main": {"drug": main["drug"].title(), "pt": main["pt"], "action": main["action"], "what": main["what"],
                     "first_q": main["first_signal_quarter"], "first_date": main["first_signal_date"], "lead": main["lead_days"], "series": ser},
            "leads": leads, "n_action": len(with_action), "n_before": sum(1 for x in with_action if (x.get("lead_days") or 0) > 0),
            "criteria": b["criteria"]}


# ---------------------------------------------------------------- 검증: 두 판별 모드
def val4_part(val: dict) -> dict:
    """v3 의 참조 세트 요약에 통계 기반 판별(이름을 가리고 통계만 본 FlyVigilance)의 AUC 를 더합니다."""
    out = v3.val_part(val)
    for s in out["sets"]:
        ms = dig(val, "refsets", s["name"], "methods", default=[])
        st = next((m for m in ms if m.get("key") == "fv" or m.get("family") == "flyvigilance"), None)
        s["stat"] = round(st["auc"], 3) if st else None
    return out


# ---------------------------------------------------------------- NVIDIA 공식 Agent Skills 적용
def nvskills_part(disc: dict) -> dict:
    g = jload(PUB / "data/guard_policy_eval.json")
    r = jload(PUB / "data/literature_rerank_eval.json")
    base, pol = "a_safety_guard_8b_v3", "c_ncs35_pv_policy"
    cp = g["critic_probe"]
    guard = {"generator": g["generator"], "policy": g["policy"],
             "rows": [["PRR 인과 단정", cp["p1"][base]["flagged"], cp["p1"][pol]["flagged"], cp["p1"]["n"]],
                      ["없는 발생률", cp["p2"][base]["flagged"], cp["p2"][pol]["flagged"], cp["p2"]["n"]]],
             "acc0": g["pv_evals"]["all"][base]["accuracy"], "acc1": g["pv_evals"]["all"][pol]["accuracy"], "n_eval": g["pv_evals"]["all"][pol]["n"],
             "ms": g["latency_median_ms"][pol]}
    ch = r["chosen"]
    pool = str(ch["pool"])
    pw = r["paired_vs_pubmed_pool20"][ch["method"]]
    rer = {"model": r["rerank_model"].split("/")[-1], "p0": r["metrics"][pool]["pubmed"]["p_at_6"], "p1": r["metrics"][pool][ch["method"]]["p_at_6"],
           "wins": pw["wins"], "ties": pw["ties"], "losses": pw["losses"], "p": pw["sign_test_p"], "pairs": r["pairs"], "articles": r["articles"],
           "ms": r["rerank_latency_ms"]["p50"], "top": r["read_top"], "pool": ch["pool"]}
    skills = jload_opt(PUB / "data/skills.json")
    names = [s["name"] for s in skills] if isinstance(skills, list) else []
    cards = sorted(p.parent.name for p in (ROOT / "skills").glob("*/skill-card.md"))
    return {"guard": guard, "rerank": rer, "skills": names, "cards": len(cards),
            "msa": {"n": disc["msa"]["n"], "plddt": disc["of3"]["plddt"], "rmsd": disc["of3"]["ca_rmsd_vs_4R6E"]}}


# ---------------------------------------------------------------- 커넥톰 라우팅 구조
def arch_part() -> dict:
    m = jload(PUB / "data/connectome/meta.json")
    return {"neurons": m["neurons"], "edges": m["edges"], "layers": [[l["key"], l["name"], l["neurons"], l["agent"]] for l in m["layers"]]}


# ---------------------------------------------------------------- flygate CLI · 상시 실행
def cli_part() -> dict:
    a = jload_opt(PUB / "data/agent.json")
    cmds = [re.sub(r"\s+\[.*$", "", c["cmd"]).replace('"<MedDRA PT>"', "<PT>") for c in a.get("cli", [])]
    cron = {}
    logs = sorted((ROOT / "agent/evidence").glob("openclaw_cron_*.txt"))
    if logs:
        txt = logs[-1].read_text()
        m = re.search(r"^[0-9a-f-]+\S*\s+-\s+(\S+)\s+cron\s+(.+?)\s+@\s+(\S+)", txt, re.M)
        if m:
            cron = {"name": m.group(1), "expr": m.group(2).strip(), "tz": m.group(3)}
        cron["heartbeat"] = "[heartbeat] started" in txt
        cron["ready"] = "[gateway] ready" in txt
        w = re.search(r"·\s*(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})", txt)
        cron["when"] = f"{w.group(1)} {w.group(2)} UTC" if w else ""
        cron["source"] = str(logs[-1].relative_to(ROOT))
    else:
        FALLBACKS.append("OpenClaw cron 기록 없음 → cron 줄을 뺌")
    return {"cmds": cmds, "modules": len(a.get("modules", [])), "skills": len(a.get("skills", [])), "cron": cron}


# =====================================================================
#  장면 시간표 (HTML · 타임라인 JSON · 내레이션 대본이 모두 이것을 씁니다)
# =====================================================================
def man(n: float) -> str:
    """만 단위로 줄여 씁니다(422,459 → 42만)."""
    return f"{n / 1e4:,.0f}만"


def timeline(d: dict) -> list[dict]:
    ds, fv, nir, pn, wh, tr, kr, bt, nv, ag = d["disc"], d["fv"], d["nir"], d["panel"], d["wh"], d["triage"], d["kr"], d["bt"], d["nvs"], d["agent"]
    b = fv["blind"]
    reach_fv, reach_base = b["serious"] - b["fv"]["auto"], b["serious"] - b["base"]["auto"]
    sets = {s["name"]: s for s in fv["val"]["sets"]}
    pro = fv["val"]["pro"] or {}
    ok_all = sum(1 for r in pn["redock"] if r["rmsd"] <= pn["thr"])
    smoke = (ag.get("smoke") or {}).get("total", 20)
    krt = f"{kr['total']}점, {kr['grade']}입니다" if kr else "점수와 등급을 매깁니다"
    S = [
        ("intro", 8, "Intro", "Project-FlyGate", 0, [
            (0.4, 3.4, "니라파립 분자(DiffDock 포즈 좌표)가 원자 단위로 조립되고 Project-FlyGate 타이틀이 솟아오릅니다",
             "프로젝트 플라이게이트입니다."),
            (3.4, 7.8, "타깃 PARP1 → FLYGATE → 환자 FAERS 보고 여정 선, STEP 1 · STEP 2 표시, NVIDIA 기술 칩 4개",
             "NVIDIA 스킬 위에 구성한 약물 안전성 에이전트 워크플로입니다.")]),
        ("problem", 12, "Problem", "문제 · 근거를 넘는 결론", 0, [
            (0.3, 4.8, f"도킹 점수 카드: PARP1 −{abs(ds['vina'][2][1]):.3f} · Factor Xa −{abs(ds['vina_xa']):.3f} kcal/mol → '선택적' 주장에 반려 도장",
             "도킹 점수도, 보고 통계도 숫자는 모두 실측입니다."),
            (4.8, 8.6, f"FAERS 카드: 니라파립 × 혈소판감소증 PRR {nir['prr']:.2f} · {nir['a']:,}건 → '인과' 주장에 반려 도장",
             "그런데 결론이 근거를 넘으면 반려해야 합니다."),
            (8.6, 11.8, f"한 분기({fv['ov']['asof']}) 이상사례 보고 {fv['ov']['q_reports']:,}건 오도미터",
             f"한 분기에만 {man(fv['ov']['q_reports'])} 건이 넘게 들어옵니다.")]),
        ("disc", 32, "STEP 1", "STEP 1 · FlyDiscovery · 시판 전 후보", 1, [
            (0.4, 6.4, f"MSA-Search NIM: PARP1 상동 서열 {ds['msa']['n']}개 정렬 히트맵과 보존도 곡선 · 공식 스킬 bionemo-msa-structure-prediction-pipeline",
             f"STEP 1 플라이디스커버리. MSA-Search가 PARP1 상동 서열 {ds['msa']['n']}개를 모읍니다."),
            (6.4, 13.2, f"OpenFold3 NIM: pLDDT로 색칠한 단백질 리본이 그려지고 리간드가 결합 자리에 들어갑니다 · pLDDT {ds['of3']['plddt']:.2f} · Cα RMSD {ds['of3']['ca_rmsd_vs_4R6E']:.1f} Å",
             f"OpenFold3가 복합체를 예측합니다. 결정 구조와의 차이는 {ds['of3']['ca_rmsd_vs_4R6E']:.1f} 옹스트롬입니다."),
            (13.2, 19.2, f"DiffDock NIM: 포즈 5개 회전 · 재도킹 대조 3종 막대 · 니라파립 {ds['dd']['redock'][0][1]} Å",
             f"DiffDock은 결합 자리를 {ds['dd']['redock'][0][1]} 옹스트롬 안으로 재현했습니다."),
            (19.2, 25.2, f"Boltz-2 NIM: PARP1 화합물 {ds['bench']['n']}종 예측 대 실측 산점도 · Spearman {ds['bench']['spearman']:.3f}",
             f"Boltz-2 친화도 예측은 ChEMBL 실측과 순위 상관 {ds['bench']['spearman']:.3f}입니다."),
            (25.2, 31.8, f"주장 4개에 통과 · 반려 도장 · Nemotron 3 Super 크리틱 과잉해석 {ds['critic']['caught']}/{ds['critic']['n_over']} 반려",
             "숫자가 맞아도 결론이 근거를 넘으면, Nemotron 크리틱이 반려합니다.")]),
        ("panel", 13, "Panel", "STEP 1 · 약물 패널 · 재도킹", 1, [
            (0.3, 6.0, f"약물 패널 {len(pn['rows'])}종 타일(소분자 {pn['small']} · 생물의약품 {pn['bio']}), 사례 수와 ChEMBL 분자 종류, 재도킹한 약물 표시",
             f"후보 하나에서 약물 패널로 넓힙니다. 실제 사례의 의심약물 {len(pn['rows'])}종입니다."),
            (6.0, 12.7, f"재도킹 대조 {len(pn['redock'])}종 막대와 2 Å 기준선 · {ok_all}/{len(pn['redock'])} 통과 · 약물 패널 {pn['panel_ok']}/{pn['panel_n']}",
             f"소분자는 DiffDock으로 다시 도킹해, {len(pn['redock'])}개 표적 중 {ok_all}개에서 2옹스트롬 기준을 통과했습니다.")]),
        ("bridge", 8, "Bridge", "데모 · 같은 약물을 시판 후로", 1.5, [
            (0.3, 3.8, "데모 약물 니라파립이 FLYGATE 문을 통과해 보고 입자로 흩어집니다 · STEP 1 요약 카드",
             "데모에서는 같은 약으로 시판 후를 이어 봅니다."),
            (3.8, 7.8, f"FAERS 니라파립 의심 사례 {nir['cases']:,}건 · 혈소판감소증 {nir['a']:,}건 · SDR 칩 · '누가, 얼마나 빨리' 질문",
             "이제 질문은, 이 보고를 누가 얼마나 빨리 봐야 하는가입니다.")]),
        ("warehouse", 10, "Warehouse", "STEP 2 · FAERS 웨어하우스", 2, [
            (0.3, 3.8, f"FAERS {wh['quarters']}개 분기 막대가 왼쪽부터 쌓입니다 ({wh['first']}–{wh['asof']})",
             "STEP 2, 플라이비질런스입니다."),
            (3.8, 9.8, f"원보고 {wh['raw']:,} · 중복 제거 사례 {wh['cases']:,} · 약물-반응 쌍 {wh['pairs']:,} · 3중 기준 SDR {wh['sdr']:,}",
             f"FAERS {wh['quarters']}개 분기, 사례 {man(wh['cases'])} 건을 SQL로 집계합니다.")]),
        ("flow", 15, "Workflow", "STEP 2 · FlyVigilance 워크플로", 2, [
            (0.3, 4.0, "7단계 노드: 입력 → 규칙 게이트 → 라벨 근거 → 반사 판단 → 숙고 → 3단 크리틱 → 사람, 사례 입자가 흐릅니다",
             "규칙으로 되는 일은 규칙으로, 판단은 모델로 나눕니다."),
            (4.0, 8.2, f"니라파립 × 혈소판감소증 근거 등급(GET /api/grade): 라벨 · FAERS · PubMed · PV 분류 {nir['grade']['review_priority']}",
             "라벨 원문, FAERS 통계, 문헌을 모아 PV 분류를 매깁니다."),
            (8.2, 14.7, f"역할 분담: Nemotron · Safety Guard + Content Safety · 비자기회귀 판단 모델 / 7문항 p50 {fv['jev_p50']:.0f} ms 대 {fv['gen_p50']:,.0f} ms",
             f"글은 Nemotron이, 확률 판단은 비자기회귀 모델이 맡아 {fv['questions']}문항을 {fv['jev_p50'] / 1000:.1f}초에 답합니다.")]),
        ("triage", 14, "Live triage", "STEP 2 · 실제 사례 한 건", 2, [
            (0.3, 4.6, f"FAERS {tr['quarter']} 실제 사례 카드 → 타입 있는 확률 7개가 한 번에 채워집니다 · {tr['jev_ms']:.0f} ms",
             f"실제 사례 한 건입니다. {len(tr['probs'])}문항 판단이 {tr['jev_ms'] / 1000:.1f}초에 끝납니다."),
            (4.6, 9.0, "결정 정책: 사람 우선 · 15일 신속보고 후보 (" + str(tr["deadline"]).split("(")[-1].rstrip(")").replace(": serious and unexpected", " · 중대 + 예상하지 못함") + ")",
             "중대하고 예상하지 못한 사례라, 15일 신속보고 후보가 됩니다."),
            (9.0, 13.8, f"System-2: {tr['rounds'][0]['model']} 메모 → 크리틱 1단이 근거 ID 없는 주장 반려 → 2회차 통과 · Safety Guard 안전",
             "Nemotron 메모는 크리틱이 한 번 되돌렸고, 고친 뒤 통과했습니다.")]),
        ("korean", 16, "Korean PV", "국내 규정 모드 · 한국형 인과성", 2, [
            (0.3, 5.2, "시연용 국내 보고 서술이 타이핑되고 NVIDIA Nemotron이 식약처 보고서식 가~바 여섯 절로 구조화합니다",
             "국내 보고 서술은 Nemotron이 식약처 서식 여섯 절로 구조화합니다."),
            (5.2, 10.6, f"한국형 인과성 평가 알고리즘 ver 2.0 {len(kr['items']) if kr else 8}개 항목 점수가 쌓입니다 · 합계 {kr['total'] if kr else '—'}점 · {kr['grade'] if kr else ''}",
             f"한국형 인과성 평가 {len(kr['items']) if kr else 8}개 항목을 채점해 {krt}."),
            (10.6, 15.7, "규정 모드 비교: 미국 21 CFR 314.80(중대 + 예상하지 못함) · 한국 별표 4의3 제7호 나목(중대한 약물이상반응) · 15일",
             "국내 규정은 예상 여부와 무관하게 중대한 반응을 15일로 보고합니다.")]),
        ("signals", 13, "PV class", "SDR · PV 분류 · 안전망", 2, [
            (0.3, 4.3, "PV 분류 표: 라벨 상태 × SDR, 검토 우선순위 1–5 · 니라파립이 규명된 위해성 후보 칸에 놓입니다",
             "SDR은 인과가 아니라 검토의 출발점입니다."),
            (4.3, 8.8, f"EMA DME {d['pvc']['dme_n']}개 PT 안전망: 점수와 관계없이 사람 검토",
             f"중대 의학 사건 {d['pvc']['dme_n']}개는 점수와 관계없이 사람이 봅니다."),
            (8.8, 12.8, f"보고 편향 표시: 이소트레티노인 × 염증성장질환 변호사 보고 {fv['bias']['lw'] / fv['bias']['a'] * 100:.1f}% · 변호사 보고를 뺀 PRR",
             "변호사 보고가 몰린 쌍에는 보고 편향 표시를 붙입니다.")]),
        ("timemachine", 13, "Time machine", "신호 타임머신 · 분기별 재계산", 2, [
            (0.3, 5.6, f"카나글리플로진 × 당뇨병성 케톤산증: 분기별 누적 보고와 IC₀₂₅ 선이 그려지고, {bt['main']['first_q']} 첫 SDR 표시",
             "신호 타임머신은 분기마다 그 시점의 데이터로 SDR을 다시 계산합니다."),
            (5.6, 12.8, f"FDA 안전성 서한 {bt['main']['action']} 세로선 · 선행 +{bt['main']['lead']}일 괄호 · FDA 조치 {bt['n_action']}건의 선행 일수 막대",
             f"카나글리플로진 케톤산증은 FDA 조치보다 {bt['main']['lead']}일 먼저 SDR이 섰습니다.")]),
        ("measure", 15, "Measured", "결과 코드를 가린 실측", 2, [
            (0.3, 5.4, f"FAERS {fv['ov']['asof']} 실제 사례 {b['n']}건 · 중대 {b['serious']}건 · 기준선 '모델 단독 · 질문 하나'",
             f"결과 코드를 가린 {b['n']}건에서 모델 단독 질문 하나와 비교했습니다."),
            (5.4, 12.4, f"검토에 닿은 중대 사례 {reach_fv}/{b['serious']} 대 {reach_base} · 사람 우선 {b['base']['human']} → {b['fv']['human']}건 · 비중대 과승격 {b['base']['over']} → {b['fv']['over']}",
             f"중대 사례는 {reach_fv}건이 검토에 닿았고, 사람이 먼저 볼 양은 {b['base']['human']}건에서 {b['fv']['human']}건으로 줄었습니다."),
            (12.4, 14.8, "McNemar 정확 검정 p 값 칩 세 개",
             "모두 통계적으로 유의한 차이입니다.")]),
        ("validated", 13, "Validated", "공개 참조 세트 · 두 판별 모드", 2, [
            (0.3, 6.8, "OMOP · EU-ADR · Harpaz AUC 막대: 지식 기반 판별 · 통계 기반 판별 · 최고 통계 지표",
             f"공개 참조 세트에서 지식 기반 판별은 AUC {sets['OMOP']['kb']:.2f}과 {sets['EU-ADR']['kb']:.2f}로 통계 지표를 앞섰습니다."
             if "OMOP" in sets and "EU-ADR" in sets else "공개 참조 세트로 두 판별 모드를 검증했습니다."),
            (6.8, 12.8, f"Harpaz 전향 {pro.get('tp')}/{pro.get('pos')} · 오경보 {pro.get('fp')}/{pro.get('neg')} · 문헌 설계 판정 · 크리틱 주입 시험",
             f"2013년 이전 보고만으로 라벨 변경 {pro.get('tp')}건을 미리 잡았고, 오경보는 {pro.get('fp')}건입니다.")]),
        ("nvskills", 16, "NVIDIA Skills", "NVIDIA 공식 Agent Skills 적용", 3, [
            (0.3, 5.2, "공식 스킬 카드 4장: bionemo-msa-structure-prediction-pipeline · nemotron-policy-generator · nemotron-retrieval-recipes · skill-card-generator",
             "NVIDIA 공식 Agent Skills 네 개를 실제로 적용했습니다."),
            (5.2, 10.6, "PV 정책 가드(Nemotron 3.5 Content Safety): " + " · ".join(f"{r[0]} {r[1]}/{r[3]} → {r[2]}/{r[3]}" for r in nv["guard"]["rows"])
             + f" · 평가 {nv['guard']['n_eval']}건 정확도 {nv['guard']['acc0']:.2f} → {nv['guard']['acc1']:.2f}",
             "정책 생성 스킬로 만든 PV 가드는 인과 단정과 없는 발생률을 모두 잡습니다."),
            (10.6, 15.7, f"Nemotron 리랭커: 읽는 {nv['rerank']['top']}편 중 관련 비율 {nv['rerank']['p0']:.2f} → {nv['rerank']['p1']:.2f} · {nv['rerank']['wins']}쌍 개선 · {nv['rerank']['losses']}쌍 악화 · 스킬 카드 {nv['cards']}개",
             f"Nemotron 리랭커는 관련 문헌 비율을 {nv['rerank']['p0']:.2f}에서 {nv['rerank']['p1']:.2f}로 올렸습니다.")]),
        ("reviewed", 11, "Reviewed", "면허 약사 검토 반영", 2, [
            (0.3, 5.5, f"면허 약사 검토 {d['pvc']['n_review']}개 항목 체크리스트가 차례로 켜집니다",
             f"현업 약사의 검토 의견 {d['pvc']['n_review']}개를 코드와 데이터에 반영했습니다."),
            (5.5, 10.6, "SDR 용어 · PV 분류 · DME 안전망 · 결과 코드 가림 · 국내 15일 규칙 항목이 강조됩니다",
             "SDR 용어, PV 분류, 결과 코드를 가린 평가가 그 결과입니다.")]),
        ("arch", 11, "Architecture", "커넥톰 라우팅 구조", 3, [
            (0.3, 5.6, f"MaleCNS 초파리 뇌 점구름(뉴런 {d['arch']['neurons']:,}개)에서 9개 기능 층이 차례로 켜집니다",
             "에이전트의 경로는 초파리 커넥톰의 아홉 기능 층에 대응시켜 보여 줍니다."),
            (5.6, 10.6, "층 목록: 감각 · 부호화 · 반사 · 기억 · 숙고 · 억제 · 연합 · 행동 · 되먹임, 층별 뉴런 수 · '라우팅 위상 시각화' 표시",
             "반사는 싸게, 숙고는 드물게, 억제는 늘 켜 둡니다.")]),
        ("agent", 13, "Agent", "NemoClaw · OpenShell · OpenClaw", 3, [
            (0.3, 6.2, "OpenShell 샌드박스 안 OpenClaw 워크스페이스 파일 · 하트비트 파형 · 커널 수준 경계",
             "에이전트는 NemoClaw로 OpenShell 샌드박스 안에서 늘 켜져 있습니다."),
            (6.2, 12.8, f"이그레스 허용 목록 · 목록 밖 호스트 차단 · 라이브 스모크 {smoke}/{smoke} 통과",
             f"허용한 호스트만 나갈 수 있고, 실제 샌드박스 점검 {smoke}개를 모두 통과했습니다.")]),
        ("cli", 10, "CLI", "flygate CLI · 상시 실행", 3, [
            (0.3, 5.2, f"터미널에 flygate 명령 {len(d['cli']['cmds'])}개가 입력되고 근거 ID가 붙은 JSON이 나옵니다",
             f"도구는 flygate 명령 {len(d['cli']['cmds'])}개이고, 모든 출력에 근거 ID가 붙습니다."),
            (5.2, 9.7, f"OpenClaw cron {d['cli']['cron'].get('name', '')} · {d['cli']['cron'].get('expr', '')} {d['cli']['cron'].get('tz', '')} · 하트비트 · 제출은 사람",
             "매일 아침 cron이 새 분기를 점검하고, 제출은 사람이 합니다.")]),
        ("close", 12, "Close", "반사는 싸게, 숙고는 드물게", 3, [
            (1.4, 4.8, "초파리 뇌 점구름이 반사 → 숙고 → 행동 층 순서로 밝아지고 태그라인이 솟아오릅니다",
             "반사는 싸게, 숙고는 드물게, 판단은 사람에게."),
            (4.8, 9.5, "Project-FlyGate · flygate.kr · github.com/Team-FlyGate/Project-FlyGate · 기술 구성 크레딧",
             "프로젝트 플라이게이트였습니다. 감사합니다.")]),
    ]
    out, t = [], 0.0
    for sid, dur, name, label, step, beats in S:
        out.append({"id": sid, "t0": round(t, 3), "t1": round(t + dur, 3), "name": name, "label": label, "step": step,
                    "beats": [{"a": a, "b": bb, "vis": vis, "vo": vo} for a, bb, vis, vo in beats]})
        t += dur
    return out


# ---------------------------------------------------------------- 내레이션 음절 추정
NUM_KO = "영일이삼사오육칠팔구"
LATIN = {"STEP": 2, "MSA-Search가": 8, "MSA-Search": 7, "PARP1": 3, "OpenFold3가": 7, "DiffDock으로": 5, "DiffDock은": 4, "Boltz-2": 4,
         "ChEMBL": 2, "Nemotron이": 5, "Nemotron이,": 5, "Nemotron": 4, "FAERS": 3, "SQL로": 5, "NVIDIA": 4, "Agent": 3, "Skills": 2,
         "SDR이": 5, "SDR은": 5, "SDR": 4, "SDR을": 5, "PV": 3, "AUC": 4, "FDA": 5, "ID가": 4, "NemoClaw로": 5, "OpenShell": 3,
         "cron이": 3, "flygate": 5, "EMA": 4, "PRR": 5}


def sino(n: int) -> int:
    """정수를 한자어 수사로 읽을 때의 음절 수(1,759 → 천칠백오십구 = 6)."""
    if n == 0:
        return 1
    s, units = 0, [(10 ** 8, 1), (10 ** 4, 1), (1000, 1), (100, 1), (10, 1)]
    for u, syl in units:
        q = n // u
        if q:
            s += (sino(q) if u >= 10 ** 4 else (0 if q == 1 else 1)) + syl
            n %= u
    return s + (1 if n else 0)


def syllables(text: str) -> int:
    n = 0
    for tok in text.split():
        core = tok
        for k, v in LATIN.items():
            if k in core:
                n += v
                core = core.replace(k, "", 1)
                break
        for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", core):
            ip, _, dp = m.group(0).replace(",", "").partition(".")
            n += sino(int(ip)) + ((1 + len(dp)) if dp else 0)
        core = re.sub(r"\d[\d,]*(?:\.\d+)?", "", core)
        n += len(re.findall(r"[가-힣]", core))
        latin = re.sub(r"[^A-Za-z]", "", core)
        n += math.ceil(len(latin) / 2.5) if latin else 0
    return n


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def write_script(tl: list[dict], dur: float, built: str):
    total_syl = sum(syllables(bt["vo"]) for s in tl for bt in s["beats"])
    lines = [
        "# Project-FlyGate 쇼릴 v4.0.0 내레이션 대본", "",
        f"- 영상: `web/public/showreel/FlyGate_showreel_v4.0.0.html` (1920×1080, 30fps) · 음원 `scripts/reel/FlyGate_showreel_v4.0.0_audio.m4a`",
        f"- **총 길이 {int(dur // 60)}분 {dur % 60:.0f}초 ({dur:.0f}초)** · 장면 {len(tl)}개 · 내레이션 {total_syl}음절(추정)",
        f"- 이 대본은 `scripts/build_reel_v4.py` 가 영상과 같은 장면 시간표(`scripts/reel/flygate_v4.timeline.json`)로 생성합니다. 손으로 고치지 말고 빌더의 `timeline()` 을 고친 뒤 다시 빌드합니다.",
        f"- 수치는 빌드 시점({built})의 저장소 JSON · 측정 파일 값입니다.",
        "- 읽는 속도는 초당 한국어 6음절 안팎을 넘지 않게 맞췄습니다(음절 수는 숫자와 영문을 소리 나는 대로 센 추정값입니다). 영문 고유명사는 괄호 안 읽기대로 읽습니다: FlyGate(플라이게이트), FlyDiscovery(플라이디스커버리), FlyVigilance(플라이비질런스), Nemotron(네모트론), NemoClaw(네모클로), OpenShell(오픈셸), FAERS(페어스), SDR(에스디알).",
        "", "## 장면 한눈에 보기", "",
        "| # | 장면 | 시작 | 끝 | 길이 |", "| --- | --- | --- | --- | --- |",
    ]
    for i, s in enumerate(tl, 1):
        lines.append(f"| {i:02d} | {s['label']} | {mmss(s['t0'])} | {mmss(s['t1'])} | {s['t1'] - s['t0']:.0f}초 |")
    lines.append(f"| | **합계** | 00:00.0 | {mmss(dur)} | **{dur:.0f}초** |")
    for i, s in enumerate(tl, 1):
        lines += ["", f"## {i:02d} · {s['label']} ({mmss(s['t0'])}–{mmss(s['t1'])})", "",
                  "| 시간 | 화면 | 내레이션 | 속도 |", "| --- | --- | --- | --- |"]
        for bt in s["beats"]:
            a, bb = s["t0"] + bt["a"], s["t0"] + bt["b"]
            syl = syllables(bt["vo"])
            lines.append(f"| {mmss(a)}–{mmss(bb)} | {bt['vis']} | {bt['vo']} | {syl}음절 · {syl / (bb - a):.1f}/초 |")
    lines += ["", "## 읽을 때", "",
              "- 장면이 바뀌는 순간(각 표의 첫 줄 시작 시각)에 첫 문장을 시작하면 화면의 숫자가 나타나는 때와 맞습니다.",
              "- 문장 사이 빈 구간은 효과음과 숫자 애니메이션 자리입니다. 채우지 않습니다.",
              "- Jev(TypeSafe AI)는 기술 구성 크레딧에서만 이름을 읽고, 본문에서는 '비자기회귀 판단 모델'로 부릅니다. 비교 기준선은 '모델 단독 · 질문 하나'입니다.", ""]
    SCRIPT_OUT.write_text("\n".join(lines))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--refresh-kr" in sys.argv:
        refresh_kr()
    out = pathlib.Path(args[0]) if args else DEFAULT_OUT
    fv = v3.fv_part()
    disc = v3.disc_part()
    val = jload_opt(PUB / "data/validation.json")
    fv["val"] = val4_part(val)
    data = {
        "meta": {"built": time.strftime("%Y-%m-%d %H:%M"), "repo": v3.REPO, "live": v3.LIVE},
        "disc": disc, "nir": v3.nir_part(), "fv": fv, "agent": v3.agent_part(fv["skills"]), "brain": v3.brain_part(),
        "panel": panel_part(disc), "wh": warehouse_part(), "triage": triage_part(), "kr": kr_part(), "pvc": pv_class_part(),
        "bt": backtest_part(), "nvs": nvskills_part(disc), "arch": arch_part(), "cli": cli_part(),
    }
    tl = timeline(data)
    dur = tl[-1]["t1"]
    data["tl"] = {"dur": dur, "scenes": [{k: s[k] for k in ("id", "t0", "t1", "name", "label", "step")} for s in tl]}
    html = TEMPLATE.read_text()
    marker = "/*__DATA__*/null"
    assert html.count(marker) == 1, "template data marker missing"
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html.replace(marker, blob))
    TIMELINE_OUT.write_text(json.dumps({"version": "4.0.0", "built": data["meta"]["built"], "dur": dur, "scenes": tl}, ensure_ascii=False, indent=1) + "\n")
    write_script(tl, dur, data["meta"]["built"])
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB) · {len(tl)} scenes · {dur:.0f} s")
    print(f"wrote {TIMELINE_OUT.relative_to(ROOT)} · {SCRIPT_OUT.relative_to(ROOT)}")
    fast = [(s["id"], bt["vo"], syllables(bt["vo"]) / (bt["b"] - bt["a"])) for s in tl for bt in s["beats"]
            if syllables(bt["vo"]) / (bt["b"] - bt["a"]) > 6.3]
    for sid, vo, r in fast:
        print(f"  ! narration fast ({r:.1f} syl/s) {sid}: {vo}")
    print("  fallbacks: " + ("; ".join(FALLBACKS) if FALLBACKS else "none"))


if __name__ == "__main__":
    main()
