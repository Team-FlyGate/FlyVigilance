"""FlyDiscovery 선택성 근거: 도킹 격자(약물 20 × 표적 14)의 칸마다 ChEMBL 실측 결합 기록을 붙인다.

- 표적: 도킹 표적 유전자(12종)의 사람 UniProt → ChEMBL 단일 단백질 표적 (Mpro 는 SARS-CoV-2 polyprotein 1ab)
- 약물: ChEMBL 이름 검색 → 부모 분자(염 · 수화물을 묶음). 활성 기록은 parent_molecule_chembl_id 로 모은다
- 칸마다 pChEMBL 값(IC50 · Ki · Kd · EC50 를 -log 몰 농도로 맞춘 값)이 있는 기록의 개수 · 중앙값 · 최댓값 · 측정 종류
- 근거 등급: 실측 결합(중앙값 pChEMBL ≥ 6, 1 µM 이하) / 측정됨 · 약함(< 6) / 기록 없음. 도킹 신뢰도는 등급에 넣지 않는다
- BindingDB 는 따로 부르지 않았다. ChEMBL 이 문헌 활성값을 모으는 방식이 비슷해 한 출처로 충분하다고 보고, 화면에 출처를 ChEMBL 로 적는다
- 결과: fly_discovery/measurements/selectivity_evidence.json. 원본 응답은 data/discovery/chembl/ 에 캐시(gitignore)

사용: .venv/bin/python pipeline/discovery/build_selectivity_evidence.py
"""
import json
import pathlib
import statistics
import time
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[2]
MEAS = ROOT / "fly_discovery/measurements"
CACHE = ROOT / "data/discovery/chembl"
API = "https://www.ebi.ac.uk/chembl/api/data"
STRONG = 6.0  # pChEMBL 6 = 1 µM

# 도킹 표적 유전자 → 사람(또는 병원체) UniProt. 결정 구조가 다른 생물종이어도 약물의 실제 표적 기준으로 찾는다
UNIPROT = {"PARP1": "P09874", "NR3C1": "P04150", "DRD2": "P14416", "JAK2": "O60674", "CRBN": "Q96SW2",
           "Mpro (nsp5)": "P0DTD1", "HTR2A": "P28223", "SLC5A2": "P31639", "F10": "P00742", "OPRM1": "P35372",
           "PDE5A": "O76074", "DHFR": "P00374"}
# ChEMBL 이름이 도킹 라이브러리 이름과 다른 약물
NAME = {"medroxyprogesterone": "MEDROXYPROGESTERONE ACETATE"}


def get(path, **params):
    q = urllib.parse.urlencode({**params, "format": "json"})
    key = CACHE / (path.replace("/", "_") + "_" + urllib.parse.quote(q, safe="")[:180] + ".json")
    if key.exists():
        return json.loads(key.read_text())
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"{API}/{path}?{q}", timeout=90) as r:
                d = json.loads(r.read().decode())
            key.parent.mkdir(parents=True, exist_ok=True)
            key.write_text(json.dumps(d))
            return d
        except Exception:  # noqa: BLE001  ChEMBL 이 가끔 느리거나 502 를 낸다
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def target_id(acc):
    ts = get("target", target_components__accession=acc, target_type="SINGLE PROTEIN")["targets"]
    if not ts:
        ts = get("target", target_components__accession=acc)["targets"]
    return ts[0]["target_chembl_id"], ts[0]["pref_name"]


def molecule_id(name):
    want = NAME.get(name, name).upper()
    ms = get("molecule", pref_name__iexact=want)["molecules"] or get("molecule/search", q=name)["molecules"]
    m = ms[0]
    parent = (m.get("molecule_hierarchy") or {}).get("parent_chembl_id") or m["molecule_chembl_id"]
    return parent, m["pref_name"]


def main():
    lib = json.loads((MEAS / "dock_library.json").read_text())
    genes = sorted({t["gene"] for t in lib["targets"]})
    tgt = {g: dict(zip(("chembl", "pref_name"), target_id(UNIPROT[g])), uniprot=UNIPROT[g]) for g in genes}
    for g, t in tgt.items():
        print(f"{g:12} {t['uniprot']} {t['chembl']} {t['pref_name']}")
    by_chembl = {t["chembl"]: g for g, t in tgt.items()}
    ligs, cells = {}, {}
    for lig in lib["ligands"]:
        name = lig["name"]
        try:
            parent, pref = molecule_id(name)
        except Exception as e:  # noqa: BLE001  못 찾은 약물은 사유와 함께 남긴다
            ligs[name] = {"chembl": None, "error": str(e)[:120]}
            continue
        ligs[name] = {"chembl": parent, "pref_name": pref}
        acts, offset = [], 0
        while True:
            d = get("activity", parent_molecule_chembl_id=parent, target_chembl_id__in=",".join(by_chembl),
                    pchembl_value__isnull="false", limit=1000, offset=offset)
            acts += d["activities"]
            if not d["page_meta"]["next"]:
                break
            offset += 1000
        per = {}
        for a in acts:
            g = by_chembl.get(a["target_chembl_id"])
            if g and a.get("pchembl_value"):
                per.setdefault(g, []).append((float(a["pchembl_value"]), a["standard_type"], a.get("document_chembl_id")))
        for g, rows in per.items():
            v = [r[0] for r in rows]
            med = round(statistics.median(v), 2)
            cells[f"{g}|{name}"] = {"n": len(v), "median": med, "max": round(max(v), 2),
                                    "types": sorted({r[1] for r in rows}), "docs": len({r[2] for r in rows}),
                                    "evidence": "strong" if med >= STRONG else "weak"}
        print(f"{name:24} {parent:14} targets with records: {', '.join(f'{g}({len(r)})' for g, r in per.items()) or '-'}")
    out = {"source": "ChEMBL activity API (pchembl_value, parent molecule)", "strong_pchembl": STRONG,
           "targets": tgt, "ligands": ligs, "cells": cells, "updated": time.strftime("%Y-%m-%d %H:%M %Z")}
    (MEAS / "selectivity_evidence.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("cells", len(cells), "strong", sum(c["evidence"] == "strong" for c in cells.values()))


if __name__ == "__main__":
    main()
