"""FlyDiscovery 재도킹 후보 찾기: 데모 케이스의 주의심약물마다 '그 약이 작용 타깃에 붙은 공결정 구조'를 찾는다.

- 약물 → ChEMBL 분자(소분자만) → 작용 기전의 타깃 UniProt 번호
- 약물 → UniChem(ChEMBL → PDBe) → PDB 리간드 코드
- RCSB 에서 리간드 코드와 타깃 UniProt 을 둘 다 가진 구조를 해상도 순으로 고른다
- 결과는 fly_discovery/measurements/structure_candidates.json. 재도킹 대상은 여기서 사람이 고른다

사용: .venv/bin/python pipeline/discovery/find_structures.py
"""
import collections
import gzip
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES = ROOT / "api/_data/cases.json.gz"
OUT = ROOT / "fly_discovery/measurements/structure_candidates.json"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"


def get(url):
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(url, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            time.sleep(2 * (attempt + 1))
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return {}


def rcsb_search(query):
    req = urllib.request.Request("https://search.rcsb.org/rcsbsearch/v2/query", data=json.dumps(query).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        raw = urllib.request.urlopen(req, timeout=60).read()
        return json.loads(raw).get("result_set", []) if raw else []
    except Exception:  # noqa: BLE001
        return []


def chembl_molecule(name):
    q = urllib.parse.urlencode({"pref_name__iexact": name, "limit": 1})
    mols = get(f"{CHEMBL}/molecule.json?{q}").get("molecules") or []
    return mols[0] if mols else None


def targets_of(parent_id):
    mech = get(f"{CHEMBL}/mechanism.json?parent_molecule_chembl_id={parent_id}&limit=10").get("mechanisms") or []
    out = []
    for m in mech:
        tid = m.get("target_chembl_id")
        if not tid:
            continue
        t = get(f"{CHEMBL}/target/{tid}.json")
        accs = [c.get("accession") for c in t.get("target_components") or [] if c.get("accession")]
        out.append({"target": t.get("pref_name"), "action": m.get("action_type"), "uniprot": accs[:6]})
    return out


def pdb_ligand_codes(chembl_id):
    """UniChem v1: ChEMBL(src 1) 번호로 PDBe 화학 성분 코드를 찾는다."""
    req = urllib.request.Request("https://www.ebi.ac.uk/unichem/api/v1/compounds",
                                 data=json.dumps({"type": "sourceID", "compound": chembl_id, "sourceID": 1}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=60))
    except Exception:  # noqa: BLE001
        return []
    return sorted({s["compoundId"] for c in d.get("compounds", []) for s in c.get("sources", [])
                   if s.get("shortName") == "pdbe"})


def structures(comp_id, uniprots):
    q = {"query": {"type": "group", "logical_operator": "and", "nodes": [
        {"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id", "operator": "exact_match", "value": comp_id}},
        {"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
            "operator": "in", "value": uniprots}}]},
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": 5},
                            "sort": [{"sort_by": "rcsb_entry_info.resolution_combined", "direction": "asc"}]}}
    return [x["identifier"] for x in rcsb_search(q)]


def main():
    cases = json.load(gzip.open(CASES))
    count = collections.Counter()
    for c in cases:
        ps = [d for d in c["drugs"] if d.get("role") == "PS"] or c["drugs"][:1]
        count[ps[0]["drug"].upper()] += 1
    rows = []
    for name, n in count.most_common():
        for part in name.split("\\"):
            m = chembl_molecule(part.strip())
            if not m or m.get("molecule_type") != "Small molecule":
                continue
            parent = (m.get("molecule_hierarchy") or {}).get("parent_chembl_id") or m["molecule_chembl_id"]
            tg = targets_of(parent)
            accs = sorted({a for t in tg for a in t["uniprot"]})
            codes = pdb_ligand_codes(parent) or pdb_ligand_codes(m["molecule_chembl_id"])
            hits = []
            for code in codes[:3]:
                for e in structures(code, accs) if accs else []:
                    hits.append({"pdb": e, "ligand": code})
            rows.append({"drug": part.strip(), "cases": n, "chembl": parent, "targets": tg, "ligand_codes": codes,
                         "structures": hits[:5]})
            print(f"{part.strip():28s} {n:3d} codes={codes[:3]} hits={[h['pdb'] for h in hits[:3]]}", flush=True)
    OUT.write_text(json.dumps({"n_drugs": len(count), "rows": rows, "updated": time.strftime("%Y-%m-%d %H:%M %Z")},
                              ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
