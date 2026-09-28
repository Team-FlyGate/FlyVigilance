"""FlyDiscovery 후보 근거 카드: 약물 하나에 대해 구조 · 계산 · 실험 · 선택성 근거를 한 장으로 묶고, 말해도 되는 주장을 정한다.

- 대상: STEP 1 장면에서 고를 수 있는 PARP1 억제제 3종(니라파립 · 탈라조파립 · 루카파립) → STEP 2 로 넘기는 후보
- 구조 · 도킹 검증: validation.json (결정 구조 품질, DiffDock 5회 반복 등급)
- 계산: hero_scene.json drugs (4R6E 수용체 DiffDock 신뢰도 · 결정 자리 RMSD, Vina, Boltz-2 예측 pIC50)
- 실험: ChEMBL pChEMBL 기록 (PARP1 · PARP2 · Factor Xa). build_selectivity_evidence.py 와 같은 방식
- 발견 신뢰도: 구조 품질 · 도킹 검증 HIGH · 실측 결합 세 조건 중 몇 개를 만족하는지 (3 = HIGH, 2 = MEDIUM, 그 밖 LOW)
- 허용 / 불허 주장은 크리틱 규칙 이름(cross-target, confidence≠affinity, predicted≠measured 등)을 달아 둔다
- 결과: fly_discovery/measurements/evidence_cards.json

사용: .venv/bin/python pipeline/discovery/build_evidence_cards.py
"""
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_selectivity_evidence import STRONG, get, molecule_id, target_id  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[2]
MEAS = ROOT / "fly_discovery/measurements"
DRUGS = {"niraparib": "parp1-4r6e--niraparib", "talazoparib": "parp1-7kk3--talazoparib", "rucaparib": "parp1-6vkk--rucaparib"}
# 세 이름 모두 받침(ㅂ)으로 끝나 조사는 "은"을 씁니다
LABEL = {"niraparib": "니라파립", "talazoparib": "탈라조파립", "rucaparib": "루카파립"}
# 선택성 줄: 도킹한 표적(PARP1 · Factor Xa)과, 도킹은 안 했지만 같은 계열이라 꼭 봐야 할 PARP2
PANEL = {"PARP1": "P09874", "PARP2": "Q9UGN5", "F10": "P00742"}


def chembl_cells(parent, targets):
    by = {t: g for g, t in targets.items()}
    d = get("activity", parent_molecule_chembl_id=parent, target_chembl_id__in=",".join(by), pchembl_value__isnull="false", limit=1000)
    per = {}
    for a in d["activities"]:
        if a.get("pchembl_value"):
            per.setdefault(by[a["target_chembl_id"]], []).append((float(a["pchembl_value"]), a["standard_type"], a.get("document_chembl_id")))
    return {g: {"n": len(r), "median": round(statistics.median(x[0] for x in r), 2), "max": round(max(x[0] for x in r), 2),
                "types": sorted({x[1] for x in r}), "docs": len({x[2] for x in r})} for g, r in per.items()}


def main():
    hero = json.loads((MEAS / "hero_scene.json").read_text())
    val = json.loads((MEAS / "validation.json").read_text())["results"]
    targets = {g: target_id(acc)[0] for g, acc in PANEL.items()}
    cards = {}
    for name, vkey in DRUGS.items():
        d, v = hero["drugs"][name], val[vkey]
        parent, _ = molecule_id(name)
        ex = chembl_cells(parent, targets)
        lab, p1 = LABEL[name], ex.get("PARP1")
        strong = {g for g, c in ex.items() if c["median"] >= STRONG}
        checks = [
            {"name": "구조 품질", "ok": v["structure"]["verdict"] == "도킹 가능",
             "detail": f"{v['pdb']} {v['structure']['method']} {v['structure']['resolution']} Å · {v['structure']['organism']}"
                       + (f" · 주의: {', '.join(v['structure']['reasons'])}" if v["structure"]["reasons"] else "")},
            {"name": "도킹 검증", "ok": v["grade"] == "HIGH",
             "detail": f"DiffDock {v['runs']}회 중 결정 자리 정답 {v['crystal_hits']}회 · 반복 간 {v['pairwise_median']} Å · 등급 {v['grade']}"},
            {"name": "실측 결합", "ok": "PARP1" in strong,
             "detail": f"ChEMBL PARP1 pChEMBL 중앙값 {p1['median']} · {p1['n']}건 · 문헌 {p1['docs']}편" if p1 else "ChEMBL PARP1 기록 없음"},
        ]
        k = sum(c["ok"] for c in checks)
        sel = [
            {"gene": "PARP1", "docking": d["dd_conf"], "chembl": ex.get("PARP1"), "status": "supported" if "PARP1" in strong else "exploratory"},
            {"gene": "PARP2", "docking": None, "chembl": ex.get("PARP2"),
             "status": "supported" if "PARP2" in strong else "measured-weak" if "PARP2" in ex else "no-data"},
            {"gene": "F10", "docking": d["xa"]["dd_conf"], "chembl": ex.get("F10"),
             "status": "supported" if "F10" in strong else "measured-weak" if "F10" in ex else "exploratory"},
        ]
        allowed = []
        if p1 and "PARP1" in strong:
            allowed.append(f"{lab}–PARP1 상호작용은 계산 근거(재도킹 {v['crystal_hits']}/{v['runs']}회 정답)와 실험 근거(ChEMBL pChEMBL 중앙값 {p1['median']}, {p1['n']}건)가 함께 뒷받침한다.")
        if d["boltz_pic50"] is not None:
            allowed.append(f"Boltz-2 는 PARP1 pIC50 을 {d['boltz_pic50']:.2f} 로 예측했고, ChEMBL 실측 중앙값은 {p1['median'] if p1 else '없음'} 이다(예측값과 실측값을 나란히 적은 것).")
        if {"PARP1", "PARP2"} <= strong:
            allowed.append(f"PARP1 과 PARP2 모두 실측 결합 근거가 있다(PARP2 중앙값 {ex['PARP2']['median']}, {ex['PARP2']['n']}건).")
        if "F10" not in ex:
            allowed.append("Factor Xa 결합은 도킹만 있고 실측 기록이 없어 탐색적 결과로만 적는다.")
        not_allowed = [{"rule": "cross-target", "claim": f"{lab}은 DiffDock 신뢰도 PARP1 {d['dd_conf']}, Factor Xa {d['xa']['dd_conf']} 이므로 "
                        f"{'PARP1' if d['dd_conf'] >= d['xa']['dd_conf'] else 'Factor Xa'} 에 선택적이다."}]
        if d["vina"] is not None and d["xa"]["vina"] is not None:
            not_allowed.append({"rule": "cross-target", "claim": f"{lab}은 PARP1 에 Factor Xa 보다 {abs(d['vina'] - d['xa']['vina']):.1f} kcal/mol 더 선택적이다."})
        if d["boltz_pic50"] is not None:
            not_allowed.append({"rule": "predicted≠measured", "claim": f"{lab}의 PARP1 친화도는 pIC50 {d['boltz_pic50']:.2f} 로 측정되었다."})
        if {"PARP1", "PARP2"} <= strong:
            not_allowed.append({"rule": "selectivity", "claim": f"{lab}은 PARP1 선택적 억제제다. (PARP2 실측 결합도 있어 같은 조건의 비교 실험 없이는 말할 수 없다)"})
        if d["dd_conf"] < 0:
            not_allowed.append({"rule": "confidence≠affinity", "claim": f"DiffDock 신뢰도가 {d['dd_conf']} 로 음수이므로 {lab}은 PARP1 에 잘 붙지 않는다. (포즈는 결정 자리와 {d['dd_rmsd']} Å)"})
        cards[name] = {"name": name, "label": lab, "target": "PARP1", "chembl": parent, "crystal_pdb": v["pdb"], "receptor_pdb": "4R6E",
                       "structure": v["structure"], "validation": {k2: v[k2] for k2 in ("grade", "crystal_hits", "runs", "pairwise_median", "confidence_mean", "confidence_sd")},
                       "computational": {"vina": d["vina"], "dd_conf": d["dd_conf"], "dd_rmsd": d["dd_rmsd"], "boltz_pic50": d["boltz_pic50"],
                                         "xa_dd_conf": d["xa"]["dd_conf"], "xa_vina": d["xa"]["vina"]},
                       "experimental": ex, "selectivity": sel,
                       "confidence": {"level": "HIGH" if k == 3 else "MEDIUM" if k == 2 else "LOW", "score": k, "checks": checks},
                       "allowed": allowed, "not_allowed": not_allowed}
        print(f"{name:12} {cards[name]['confidence']['level']:6} checks {[c['ok'] for c in checks]} · ChEMBL {{{', '.join(f'{g}: {c['median']}({c['n']})' for g, c in ex.items())}}}")
    (MEAS / "evidence_cards.json").write_text(json.dumps({"strong_pchembl": STRONG, "cards": cards, "updated": time.strftime("%Y-%m-%d %H:%M %Z")},
                                                        ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
