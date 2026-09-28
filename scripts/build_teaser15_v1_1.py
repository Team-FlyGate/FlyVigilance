"""Project-FlyGate 15초 티저를 파일 하나로 완결된 HTML 로 만듭니다(가로 1920×1080, 세로 1080×1920).

쇼릴 v3 와 같은 시각 언어(캔버스 2D, 결정론적 타임라인)를 쓰되, 소셜 공유용으로 컷을 짧게 끊습니다.
템플릿(scripts/reel/flygate_teaser15_v1.template.html)의 `/*__DATA__*/null` 자리에 실측 수치를 JSON 으로 넣고,
세로판은 `/*__VERT__*/false` 자리를 true 로 바꿔 따로 씁니다(가로판도 ?v=1 을 붙이면 세로로 열립니다).
수치는 모두 빌드할 때 저장소의 JSON 에서 읽으므로, 측정을 다시 하면 이 스크립트만 다시 돌리면 됩니다.
외부 폰트, CDN, fetch 를 쓰지 않습니다. render_reel.py 가 쓰는 window.__reel.renderAt(t) / DUR 를 그대로 둡니다.

사용:
  .venv/bin/python scripts/build_teaser15.py [가로판 출력 경로] [세로판 출력 경로]
  기본값: web/public/showreel/FlyGate_teaser_15s_v1.0.0.html, web/public/showreel/FlyGate_teaser_15s_vertical_v1.0.0.html

입력(모두 저장소 안의 파일입니다):
  web/public/data/bench.json (jev_triage, ablation_blind), validation.json, guard_policy_eval.json, literature_rerank_eval.json,
  agent.json, faers/overview.json, fly_discovery/measurements/{measurements.json, redock.json, nim/*},
  api/_fv/triage.py (사례 하나에 묻는 질문 목록), web/public/showreel/brain_pts.json
"""
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUB = ROOT / "web/public"
DISC = ROOT / "fly_discovery/measurements"
TEMPLATE = ROOT / "scripts/reel/flygate_teaser15_v1_1.template.html"
OUT_H = PUB / "showreel/FlyGate_teaser_15s_v1.1.0.html"
OUT_V = PUB / "showreel/FlyGate_teaser_15s_vertical_v1.1.0.html"
LIVE = "https://flygate.kr"
HACK = "NVIDIA Korea Agentic AI Hackathon 2026"
KB_KEYS = ("raw_named", "knowledge", "fv_knowledge", "kb", "named")
STAT_NAME = {"a": "보고 건수", "prr": "PRR", "ror_lo": "ROR₀₂₅", "chi2s": "χ²", "ic025": "IC₀₂₅"}
# triage.py 의 질문 id 를 화면 이름으로 바꿉니다. 모르는 id 가 생기면 id 를 그대로 씁니다.
Q_KO = {"serious": "중대성", "expected": "라벨 기재 여부", "causality": "인과성 (WHO-UMC)", "special": "특수 상황",
        "priority": "검토 우선순위", "route": "다음 처리 경로", "deep": "정밀 검토 필요"}
Q_TYPE = {"noul": "예 · 아니오", "choice": "선택", "score": "점수"}


def jload(p: pathlib.Path):
    return json.loads(p.read_text())


def r2(v) -> float:
    return round(float(v), 2)


def parse_pdb(path: pathlib.Path):
    """OpenFold3 예측 복합체에서 사슬 A 의 Cα(좌표, pLDDT)와 리간드 중원자를 뽑습니다."""
    ca, plddt, lig, lig_el = [], [], [], []
    for line in path.read_text().splitlines():
        if line.startswith("ENDMDL"):
            break
        rec = line[:6].strip()
        if rec not in ("ATOM", "HETATM"):
            continue
        xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
        if rec == "ATOM" and line[12:16].strip() == "CA":
            ca += xyz
            plddt.append(round(float(line[60:66]), 1))
        elif rec == "HETATM":
            el = line[76:78].strip() or line[12:16].strip()[0]
            if el != "H":
                lig += xyz
                lig_el.append(el)
    return ca, plddt, lig, lig_el


def sdf_bonds(path: pathlib.Path):
    lines = path.read_text().splitlines()
    na, nb = int(lines[3][:3]), int(lines[3][3:6])
    el = [ln.split()[3] for ln in lines[4:4 + na]]
    bonds = [[int(ln[:3]) - 1, int(ln[3:6]) - 1, int(ln[6:9])] for ln in lines[4 + na:4 + na + nb]]
    return el, bonds


def disc_part() -> dict:
    m = jload(DISC / "measurements.json")
    of3 = m["openfold3_msa"]
    ca, plddt, lig, lig_el = parse_pdb(DISC / "nim/of3_parp1_niraparib.pdb")
    el0, bonds0 = sdf_bonds(DISC / "nim/niraparib_diffdock_pose1.sdf")
    dd = jload(DISC / "nim/dd_eval_all.json")
    # 공결정 재도킹: 쇼릴 v3 의 3건(dd_eval_all) + redock.json 의 추가 표적. 기준은 top-1 RMSD ≤ 2 Å 입니다.
    rd = {k: v["rmsd_xtal"] for k, v in dd.items() if v.get("rmsd_xtal") is not None}
    rj = jload(DISC / "redock.json") if (DISC / "redock.json").exists() else {"results": {}}
    rd |= {k: v["top1_rmsd"] for k, v in rj["results"].items() if v.get("top1_rmsd") is not None}
    b = m["parp1_affinity_benchmark"]
    return {
        "ca": [r2(v) for v in ca], "b": plddt, "lig": [r2(v) for v in lig], "lig_el": "".join(e[0] for e in lig_el),
        "lig_bonds": bonds0 if lig_el == el0 else None,
        "msa_n": of3["msa_homologs"], "plddt": of3["plddt"],
        "dd_rmsd": dd["parp1-4r6e-chain-a--niraparib"]["rmsd_xtal"],
        "redock_n": len(rd), "redock_ok": sum(v <= 2.0 for v in rd.values()),
        "boltz_n": b["n"], "boltz_rho": b["spearman"],
    }


def questions() -> list:
    src = (ROOT / "api/_fv/triage.py").read_text()
    body = src[src.index("def questions("):]
    body = body[:body.index("\ndef ", 10)]
    qs = re.findall(r'"(\w+)":\s*\{"type":\s*"(\w+)"', body)
    return [[Q_KO.get(k, k), Q_TYPE.get(t, t)] for k, t in qs]


def fv_part() -> dict:
    bench = jload(PUB / "data/bench.json")
    ov = jload(PUB / "data/faers/overview.json")
    jt = bench["jev_triage"]
    qs = questions()
    assert len(qs) == jt.get("questions_per_call", len(qs)), (len(qs), jt.get("questions_per_call"))
    last = ov["per_quarter"][-1]
    return {"quarter": last["quarter"], "q_reports": last["reports"], "p50": round(jt["latency_ms"]["p50"]), "qs": qs}


def blind_part() -> dict:
    ab = jload(PUB / "data/bench.json")["ablation_blind"]
    fv, base, tests = ab["flyvigilance"], ab["raw_jev"], ab["tests"]
    s = ab["serious"]
    return {"n": ab["n"], "serious": s,
            "fv_reached": s - fv["serious_without_review"], "base_reached": s - base["serious_without_review"],
            "p_unrev": tests["serious_unreviewed_fv_vs_raw"]["p"],
            "fv_human": fv["escalated"], "base_human": base["escalated"], "p_work": tests["workload_fv_vs_raw"]["p"],
            "fv_over": fv["over_escalated"], "base_over": base["over_escalated"]}


def auc_part() -> dict:
    """공개 참조 세트 가운데 OMOP 에서 지식 기반 판별(약·반응 이름 사용) AUC 와 통계 지표 최고값을 가져옵니다."""
    r = jload(PUB / "data/validation.json")["refsets"]["OMOP"]
    ms = r["methods"]
    kb = next((m for k in KB_KEYS for m in ms if m.get("key") == k), None) \
        or next(m for m in ms if m.get("family") in ("memory", "knowledge"))
    best = max((m for m in ms if m.get("family") == "metric"), key=lambda m: m["auc"])
    eu = jload(PUB / "data/validation.json")["refsets"].get("EU-ADR", {}).get("methods", [])
    eu_kb = next((m["auc"] for k in KB_KEYS for m in eu if m.get("key") == k), None)
    return {"set": "OMOP", "n": r["n"], "kb": round(kb["auc"], 3),
            "best_name": STAT_NAME.get(best["key"], best["key"]), "best": round(best["auc"], 3),
            "eu": round(eu_kb, 3) if eu_kb else None}


def guard_part() -> dict:
    """PV 정책 가드(배포 조합 runtime_a_or_c)가 근거를 넘는 주장(p1 인과 단정, p2 지어낸 발생률)을 잡은 수."""
    g = jload(PUB / "data/guard_policy_eval.json")["critic_probe"]
    keys = [k for k in ("p1", "p2") if k in g]
    return {"caught": sum(g[k]["runtime_a_or_c"]["flagged"] for k in keys), "n": sum(g[k]["n"] for k in keys)}


def rerank_part() -> dict:
    r = jload(PUB / "data/literature_rerank_eval.json")
    c = r["paired_vs_pubmed_pool20"][r["chosen"]["method"]]
    return {"wins": c["wins"], "losses": c["losses"], "ties": c["ties"]}


def agent_part() -> dict:
    a = jload(PUB / "data/agent.json")
    res = [x for x in (a.get("smoke") or {}).get("results", []) if isinstance(x, dict)]
    return {"skills": len(a.get("skills") or []), "smoke_pass": sum(bool(x.get("pass")) for x in res), "smoke_total": len(res)}


def brain_part(n_target: int = 6000) -> dict:
    """MaleCNS 점구름에서 뇌 부분만(복측 신경삭 제외) 약 6천 점을 고릅니다(도입부 배경과 마무리 로고 변형)."""
    p = jload(PUB / "showreel/brain_pts.json")
    idx = [i for i in range(len(p["x"])) if p["z"][i] >= 420]
    step = max(1, len(idx) // n_target)
    idx = idx[::step][:n_target]
    return {"layers": p["layers"], "x": [p["x"][i] for i in idx], "y": [p["y"][i] for i in idx],
            "z": [p["z"][i] for i in idx], "l": [p["l"][i] for i in idx]}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_h = pathlib.Path(args[0]) if args else OUT_H
    out_v = pathlib.Path(args[1]) if len(args) > 1 else OUT_V
    data = {
        "meta": {"built": time.strftime("%Y-%m-%d %H:%M"), "live": LIVE, "hack": HACK},
        "disc": disc_part(), "fv": fv_part(), "blind": blind_part(), "auc": auc_part(),
        "guard": guard_part(), "rerank": rerank_part(), "agent": agent_part(), "brain": brain_part(),
    }
    html = TEMPLATE.read_text()
    for marker in ("/*__DATA__*/null", "/*__VERT__*/false"):
        assert html.count(marker) == 1, f"template marker missing: {marker}"
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/null", blob)
    for out, vert in ((out_h, False), (out_v, True)):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html.replace("/*__VERT__*/false", "true" if vert else "false"))
        print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    b, d, f = data["blind"], data["disc"], data["fv"]
    print(f"  STEP1: MSA {d['msa_n']} · pLDDT {d['plddt']} · DiffDock {d['dd_rmsd']} Å · redock {d['redock_ok']}/{d['redock_n']}"
          f" · Boltz-2 ρ {d['boltz_rho']} (n={d['boltz_n']})")
    print(f"  STEP2: {f['quarter']} {f['q_reports']:,} reports · {len(f['qs'])} questions · p50 {f['p50']} ms")
    print(f"  blind: {b['fv_reached']}/{b['serious']} vs {b['base_reached']} (p={b['p_unrev']:.2g}) · human-first {b['base_human']} → {b['fv_human']}")
    print(f"  AUC: {data['auc']} · guard {data['guard']} · rerank {data['rerank']} · agent {data['agent']}"
          f" · brain {len(data['brain']['x'])} pts")


if __name__ == "__main__":
    main()
