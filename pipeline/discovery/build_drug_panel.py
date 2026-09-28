"""FlyDiscovery 약물 패널: FlyVigilance 데모 케이스의 주의심약물 상위 N종을 시판 전 관점으로 정리한다.

- 건수와 중대 결과는 api/_data/cases.json.gz (FAERS 2026Q2 층화 표본 440건)에서 센다
- 분자 종류(소분자·항체·단백질)와 작용 기전, 타깃은 ChEMBL 공개 API 에서 받는다 (키 불필요)
- 도킹 칸은 pipeline/discovery/redock.py 결과가 있을 때만 채운다. 없으면 미조회, 생물의약품은 대상 아님
- 결과는 fly_discovery/measurements/drug_panel.json 이고, 화면(web/index.html)의 <script id="fd-panel"> 에도 넣는다
  (정적 화면이 파일 하나로 완결되도록. 배포 복사 스크립트를 건드리지 않아도 된다)

사용: .venv/bin/python pipeline/discovery/build_drug_panel.py [--top 20]
"""
import argparse
import collections
import gzip
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES = ROOT / "api/_data/cases.json.gz"
OUT = ROOT / "fly_discovery/measurements"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
SERIOUS = {"DE", "LT", "HO", "DS", "CA", "RI", "OT"}


def get(path, **params):
    url = f"{CHEMBL}/{path}.json?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(url, timeout=60))
        except Exception:  # noqa: BLE001  EBI 가 간헐적으로 느리다
            time.sleep(3 * (attempt + 1))
    return {}


def chembl_card(name):
    """성분명 하나를 ChEMBL 분자 한 개로 맞춘다. 복합제(A\\B)는 첫 성분만 본다."""
    first = name.split("\\")[0].strip()
    mols = get("molecule", pref_name__iexact=first, limit=1).get("molecules") or \
        get("molecule/search", q=first, limit=1).get("molecules") or []
    if not mols:
        return {"chembl_id": None}
    m = mols[0]
    parent = (m.get("molecule_hierarchy") or {}).get("parent_chembl_id") or m["molecule_chembl_id"]
    # 기전은 염이 아니라 모 분자에 달린 경우가 많다
    mech = get("mechanism", parent_molecule_chembl_id=parent, limit=5).get("mechanisms") or \
        get("mechanism", molecule_chembl_id=m["molecule_chembl_id"], limit=5).get("mechanisms") or []
    targets = []
    for x in mech:
        if x.get("target_chembl_id") and x["target_chembl_id"] not in [t["id"] for t in targets]:
            t = get(f"target/{x['target_chembl_id']}")
            targets.append({"id": x["target_chembl_id"], "name": t.get("pref_name"), "action": x.get("action_type")})
    return {"chembl_id": m["molecule_chembl_id"], "pref_name": m.get("pref_name"),
            "molecule_type": m.get("molecule_type"), "max_phase": m.get("max_phase"),
            "mechanism": mech[0].get("mechanism_of_action") if mech else None, "targets": targets[:2]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()
    cases = json.load(gzip.open(CASES))
    count, serious = collections.Counter(), collections.Counter()
    for c in cases:
        ps = [d for d in c["drugs"] if d.get("role") == "PS"] or c["drugs"][:1]
        name = ps[0]["drug"].upper()
        count[name] += 1
        serious[name] += bool(SERIOUS & set(c.get("outcomes") or []))

    redock_path = OUT / "redock.json"
    redock = json.loads(redock_path.read_text())["results"] if redock_path.exists() else {}
    by_drug = {v["drug"].upper(): v for v in redock.values() if "drug" in v}

    # 상위 N종에 더해, 재도킹한 약물은 순위 밖이어도 넣는다
    names = [n for n, _ in count.most_common(args.top)]
    names += [n for n in count if n not in names and any(p.strip() in by_drug for p in n.split("\\"))]
    rows = []
    for name in names:
        n = count[name]
        card = chembl_card(name)
        small = card.get("molecule_type") == "Small molecule"
        r = next((by_drug[p.strip()] for p in name.split("\\") if p.strip() in by_drug), None)
        if r and "top1_rmsd" in r:
            dock = {"status": "measured", "pdb": r["pdb"], "gene": r["gene"], "top1_rmsd": r["top1_rmsd"],
                    "success": r["top1_success"]}
        elif small:
            dock = {"status": "not_run"}
        else:
            dock = {"status": "not_applicable"}
        rows.append({"drug": name, "cases": n, "serious": serious[name], **card, "docking": dock})
        print(name, n, card.get("molecule_type"), dock["status"])
    panel = {
        "source": "api/_data/cases.json.gz (FAERS 2026Q2, 440 cases)", "n_cases": len(cases),
        "n_primary_suspect_drugs": len(count), "chembl": CHEMBL, "rows": rows,
        "updated": time.strftime("%Y-%m-%d %H:%M %Z")}
    (OUT / "drug_panel.json").write_text(json.dumps(panel, ensure_ascii=False, indent=1) + "\n")
    embed(panel, json.loads(redock_path.read_text()) if redock_path.exists() else {"results": {}})


def embed(panel, redock):
    """화면 HTML 의 <script id="fd-panel"> 내용을 바꾼다. '</' 는 스크립트가 끝나지 않게 이스케이프한다."""
    page = ROOT / "fly_discovery/web/index.html"
    html = page.read_text()
    head = '<script id="fd-panel" type="application/json">'
    a = html.index(head) + len(head)
    b = html.index("</script>", a)
    data = json.dumps({"panel": panel, "redock": redock}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page.write_text(html[:a] + data + html[b:])


if __name__ == "__main__":
    main()
