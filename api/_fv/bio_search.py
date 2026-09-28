"""임의의 단백질·리간드를 찾아 라이브 파이프라인 입력으로 만드는 조회기.

- 단백질: UniProt REST (이름·유전자·번호 검색, 서열, PDB 상호참조, 도메인 구간)
- 구조: RCSB (PDB 파일 내려받기, 체인 ATOM 만 추출, 공결정 리간드 위치)
- 리간드: PubChem PUG REST (이름 → SMILES·CID·분자량), 또는 붙여 넣은 SMILES 를 직접 검사

파싱과 검사는 순수 함수로 두어 네트워크 없이 시험합니다(tests/test_bio_search.py).
NIM 한계는 NVIDIA 공식 스킬 문서를 따릅니다: MSA-Search 1–4096 잔기, Boltz-2 사슬 4096 잔기,
OpenFold3 는 약 1800 잔기를 넘으면 80 GB GPU 가 필요해 호스팅 경로에서 실패할 수 있습니다.
"""
import asyncio
import json
import re
import time

import httpx

from . import molgeom as mg

UNIPROT = "https://rest.uniprot.org/uniprotkb"
RCSB_FILES = "https://files.rcsb.org/download"
PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_AC = "https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound"
UA = {"User-Agent": "Project-FlyGate/1.0 (hackathon demo; contact via repo)"}

# NVIDIA 공식 스킬 문서의 입력 한계입니다
MSA_MAX_AA = 4096
BOLTZ_MAX_AA = 4096
OF3_SOFT_MAX_AA = 1800   # 이 이상은 80 GB GPU 가 필요합니다(openfold3-nim: "Sequences over roughly 1800 residues")
PIPELINE_MAX_AA = 4096

PDB_ID = re.compile(r"^[0-9][A-Za-z0-9]{3}$")
ACCESSION = re.compile(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$")
SMILES_CHARS = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)=#$:/\\.%*]+$")
AA_ONLY = re.compile(r"^[ACDEFGHIKLMNPQRSTVWYXBZUO]+$")


# ---------------------------------------------------------------- 검사
def looks_like_pdb_id(q: str) -> bool:
    return bool(PDB_ID.match(q.strip()))


def looks_like_accession(q: str) -> bool:
    return bool(ACCESSION.match(q.strip().upper()))


def valid_smiles(s: str) -> tuple[bool, str]:
    """붙여 넣은 SMILES 를 가볍게 검사합니다. 화학 정합성까지 보지는 않고, 모양이 아닌 것만 걸러 냅니다."""
    s = (s or "").strip()
    if not s:
        return False, "SMILES 가 비어 있습니다."
    if len(s) > 600:
        return False, "SMILES 가 600자를 넘습니다."
    if any(ch.isspace() for ch in s):
        return False, "SMILES 에 공백이 있습니다. 이름 없이 분자 문자열만 넣어 주세요."
    if not SMILES_CHARS.match(s):
        return False, "SMILES 에 쓸 수 없는 문자가 있습니다."
    for open_c, close_c in (("(", ")"), ("[", "]")):
        depth = 0
        for ch in s:
            depth += (ch == open_c) - (ch == close_c)
            if depth < 0:
                return False, f"괄호 {open_c}{close_c} 가 맞지 않습니다."
        if depth:
            return False, f"괄호 {open_c}{close_c} 가 맞지 않습니다."
    if not re.search(r"[A-Za-z]", s):
        return False, "원자가 없습니다."
    return True, ""


def clean_sequence(seq: str) -> str:
    return re.sub(r"[^A-Za-z]", "", seq or "").upper()


def check_sequence(seq: str) -> dict:
    """NIM 한계에 비춘 판정입니다. ok=False 면 그대로는 돌릴 수 없습니다.
    공백과 줄바꿈만 지우고 보기 때문에 숫자나 기호가 섞이면 반려합니다(FASTA 는 clean_sequence 로 먼저 정리합니다)."""
    seq = re.sub(r"\s+", "", seq or "").upper()
    n = len(seq)
    if n == 0:
        return {"ok": False, "length": 0, "reason": "서열이 비어 있습니다.", "openfold3_ok": False}
    if not AA_ONLY.match(seq):
        return {"ok": False, "length": n, "reason": "아미노산이 아닌 문자가 있습니다.", "openfold3_ok": False}
    if n > PIPELINE_MAX_AA:
        return {"ok": False, "length": n, "openfold3_ok": False,
                "reason": f"{n}잔기입니다. MSA-Search 와 Boltz-2 의 상한이 {PIPELINE_MAX_AA}잔기이므로 도메인 구간을 골라 주세요."}
    if n > OF3_SOFT_MAX_AA:
        return {"ok": True, "length": n, "openfold3_ok": False,
                "reason": f"{n}잔기입니다. OpenFold3 는 약 {OF3_SOFT_MAX_AA}잔기를 넘으면 80 GB GPU 가 필요해 호스팅 경로에서 실패할 수 있습니다."
                          " 구조 예측은 도메인 구간으로 줄여 실행하시기 바랍니다."}
    return {"ok": True, "length": n, "openfold3_ok": True, "reason": ""}


# ---------------------------------------------------------------- UniProt 파싱
def _is_reviewed(d: dict) -> bool:
    et = (d.get("entryType") or "").lower()
    return "unreviewed" not in et and "reviewed" in et


def _name_of(d: dict) -> str:
    pd = d.get("proteinDescription") or {}
    rec = pd.get("recommendedName") or {}
    if rec.get("fullName", {}).get("value"):
        return rec["fullName"]["value"]
    sub = (pd.get("submissionNames") or [{}])[0]
    return sub.get("fullName", {}).get("value") or d.get("uniProtkbId") or d.get("primaryAccession", "")


def _gene_of(d: dict) -> str:
    genes = d.get("genes") or []
    return (genes[0].get("geneName", {}) or {}).get("value", "") if genes else ""


def parse_structures(entry: dict) -> list[dict]:
    """UniProt 의 PDB 상호참조를 해상도·체인·잔기 구간으로 풉니다(예: Chains 'A=695-1022')."""
    out = []
    for x in entry.get("uniProtKBCrossReferences") or []:
        if x.get("database") != "PDB":
            continue
        props = {p["key"]: p["value"] for p in x.get("properties", [])}
        res = props.get("Resolution", "")
        m = re.match(r"([\d.]+)", res or "")
        chains_raw = props.get("Chains", "")
        chain, start, end = None, None, None
        cm = re.match(r"([A-Za-z0-9]+)(?:/[A-Za-z0-9]+)*=(\d+)-(\d+)", chains_raw)
        if cm:
            chain, start, end = cm.group(1), int(cm.group(2)), int(cm.group(3))
        out.append({"pdb": x["id"], "method": props.get("Method", ""),
                    "resolution": float(m.group(1)) if m else None,
                    "chain": chain, "start": start, "end": end, "chains_raw": chains_raw})
    return out


def pick_structure(structures: list[dict]) -> dict | None:
    """실험 구조 가운데 가장 좋은 것. X-ray 해상도 우선, 없으면 EM, 그다음 NMR 순입니다."""
    def rank(s):
        method = (s.get("method") or "").upper()
        tier = 0 if "X-RAY" in method else 1 if "EM" in method else 2
        return (tier, s.get("resolution") if s.get("resolution") is not None else 99.0,
                -(s.get("end") or 0) + (s.get("start") or 0))
    usable = [s for s in structures if s.get("chain")]
    return sorted(usable or structures, key=rank)[0] if (usable or structures) else None


def parse_domains(entry: dict) -> list[dict]:
    out = []
    for f in entry.get("features") or []:
        if f.get("type") not in ("Domain", "Region"):
            continue
        loc = f.get("location") or {}
        s, e = (loc.get("start") or {}).get("value"), (loc.get("end") or {}).get("value")
        if not s or not e or e - s < 40:
            continue
        out.append({"label": f.get("description") or f.get("type"), "start": s, "end": e})
    return out[:8]


def parse_uniprot_search(body: dict) -> list[dict]:
    """검색 결과를 화면용으로 줄입니다. 검토(Swiss-Prot)와 사람 항목을 앞에 둡니다."""
    hits = []
    for d in body.get("results") or []:
        reviewed = _is_reviewed(d)
        org = (d.get("organism") or {}).get("scientificName", "")
        pdbs = [x["id"] for x in (d.get("uniProtKBCrossReferences") or []) if x.get("database") == "PDB"]
        hits.append({"id": d.get("primaryAccession"), "uniprot_id": d.get("uniProtkbId"),
                     "name": _name_of(d), "gene": _gene_of(d), "organism": org, "reviewed": reviewed,
                     "length": (d.get("sequence") or {}).get("length"), "n_pdb": len(pdbs),
                     "pdb": pdbs[0] if pdbs else None})
    hits.sort(key=lambda h: (not h["reviewed"], h["organism"] != "Homo sapiens", -(h["n_pdb"] or 0)))
    return hits


def parse_uniprot_entry(entry: dict) -> dict:
    """항목 하나를 서열·구조·도메인·권장 구간까지 정리합니다."""
    seq = clean_sequence((entry.get("sequence") or {}).get("value", ""))
    structures = parse_structures(entry)
    best = pick_structure(structures)
    domains = parse_domains(entry)
    ranges = [{"kind": "full", "label": "전체 서열", "start": 1, "end": len(seq)}]
    if best and best.get("start") and best.get("end") <= len(seq):
        ranges.insert(0, {"kind": "structure", "label": f"{best['pdb']} 체인 {best['chain']} 구간",
                          "start": best["start"], "end": best["end"]})
    for d in domains:
        if d["end"] <= len(seq):
            ranges.append({"kind": "domain", "label": d["label"], "start": d["start"], "end": d["end"]})
    # 권장: 구조 구간 → 도메인 → 전체. OpenFold3 한계를 넘지 않는 첫 구간을 고릅니다
    pick = next((r for r in ranges if r["end"] - r["start"] + 1 <= OF3_SOFT_MAX_AA), ranges[-1])
    return {"id": entry.get("primaryAccession"), "uniprot_id": entry.get("uniProtkbId"),
            "name": _name_of(entry), "gene": _gene_of(entry),
            "organism": (entry.get("organism") or {}).get("scientificName", ""),
            "reviewed": _is_reviewed(entry),
            "length": len(seq), "sequence": seq,
            "structures": sorted(structures, key=lambda s: (s["resolution"] is None, s["resolution"] or 99))[:8],
            "best_structure": best, "domains": domains, "ranges": ranges, "recommended_range": pick,
            "check": check_sequence(seq[pick["start"] - 1:pick["end"]])}


# ---------------------------------------------------------------- PubChem 파싱
def parse_pubchem_properties(body: dict) -> dict | None:
    rows = ((body or {}).get("PropertyTable") or {}).get("Properties") or []
    if not rows:
        return None
    p = rows[0]
    smiles = p.get("IsomericSMILES") or p.get("SMILES") or p.get("CanonicalSMILES") or p.get("ConnectivitySMILES")
    if not smiles:
        return None
    mw = p.get("MolecularWeight")
    return {"cid": p.get("CID"), "name": p.get("Title") or "", "smiles": smiles,
            "mw": float(mw) if mw not in (None, "") else None, "source": "PubChem"}


def parse_pubchem_autocomplete(body: dict) -> list[str]:
    return list(((body or {}).get("dictionary_terms") or {}).get("compound") or [])


# ---------------------------------------------------------------- 구조 파일
def chain_atoms(pdb_text: str, chain: str | None) -> str:
    """DiffDock 에 넣을 수용체입니다. 고른 체인의 ATOM 줄만 남깁니다(HETATM·물 제외)."""
    lines = [ln for ln in pdb_text.splitlines()
             if ln.startswith("ATOM") and (chain is None or ln[21:22] == chain) and ln[16:17] in (" ", "A")]
    if not lines:
        lines = [ln for ln in pdb_text.splitlines() if ln.startswith("ATOM") and ln[16:17] in (" ", "A")]
    return "\n".join(lines) + "\nEND\n"


SKIP_HET = {"HOH", "WAT", "SO4", "PO4", "GOL", "EDO", "PEG", "MES", "TRS", "ACT", "CL", "NA", "K", "MG", "ZN",
            "CA", "MN", "NAG", "BOG", "DMS", "IOD", "FMT", "EPE"}


def cocrystal_ligand(pdb_text: str, chain: str | None) -> dict | None:
    """가장 큰 공결정 리간드(물·염·당 제외)입니다. 주머니 중심을 잡는 데만 씁니다."""
    atoms = mg.parse_pdb(pdb_text)
    groups: dict[tuple, list] = {}
    for a in atoms:
        if not a["het"] or a["resn"] in SKIP_HET or a["el"] == "H":
            continue
        if chain and a["chain"] != chain:
            continue
        groups.setdefault((a["resn"], a["chain"], a["resi"]), []).append(a)
    if not groups:
        return None
    (resn, ch, resi), best = max(groups.items(), key=lambda kv: len(kv[1]))
    if len(best) < 6:
        return None
    return {"code": resn, "chain": ch, "resi": resi,
            "atoms": [[a["el"], *[round(v, 3) for v in a["xyz"]]] for a in best],
            "bonds": [[i, j] for i, j, _ in mg.proximity_bonds(best)],
            "center": [round(v, 3) for v in mg.centroid([a["xyz"] for a in best])]}


# ---------------------------------------------------------------- 네트워크 (캐시는 호출자가 합니다)
_TIMEOUT = httpx.Timeout(20.0, connect=8.0)


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None, tries: int = 2):
    last = None
    for k in range(tries):
        try:
            r = await client.get(url, params=params, headers=UA, timeout=_TIMEOUT, follow_redirects=True)
        except httpx.HTTPError as e:
            last = f"{type(e).__name__}"
            await asyncio.sleep(0.4 * (k + 1))
            continue
        if r.status_code == 404:
            return None
        if r.status_code >= 500:
            last = f"HTTP {r.status_code}"
            await asyncio.sleep(0.4 * (k + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"{url.split('/')[2]} HTTP {r.status_code}")
        return r
    raise RuntimeError(f"{url.split('/')[2]} 연결 실패: {last}")


SEARCH_FIELDS = "accession,id,protein_name,gene_names,organism_name,length,reviewed,xref_pdb"


async def search_protein(q: str, limit: int = 8) -> dict:
    """이름·유전자·UniProt 번호·PDB ID 로 찾습니다. 사람 검토 항목을 앞에 둡니다."""
    q = (q or "").strip()
    if len(q) < 2:
        return {"query": q, "hits": []}
    t0 = time.perf_counter()
    async with httpx.AsyncClient() as c:
        if looks_like_pdb_id(q):
            r = await _get(c, f"{UNIPROT}/search", {"query": f"xref:pdb-{q.upper()}", "fields": SEARCH_FIELDS,
                                                    "format": "json", "size": limit})
            hits = parse_uniprot_search(r.json()) if r else []
            for h in hits:
                h["pdb"] = q.upper()
                h["matched_pdb"] = q.upper()
            if hits:
                return {"query": q, "hits": hits, "ms": round((time.perf_counter() - t0) * 1000, 1)}
        if looks_like_accession(q):
            r = await _get(c, f"{UNIPROT}/search", {"query": f"accession:{q.upper()}", "fields": SEARCH_FIELDS,
                                                    "format": "json", "size": limit})
            hits = parse_uniprot_search(r.json()) if r else []
            if hits:
                return {"query": q, "hits": hits, "ms": round((time.perf_counter() - t0) * 1000, 1)}
        query = f'({q}) AND (reviewed:true)'
        r = await _get(c, f"{UNIPROT}/search", {"query": query, "fields": SEARCH_FIELDS, "format": "json",
                                               "size": limit})
        hits = parse_uniprot_search(r.json()) if r else []
        if not hits:
            r = await _get(c, f"{UNIPROT}/search", {"query": q, "fields": SEARCH_FIELDS, "format": "json",
                                                   "size": limit})
            hits = parse_uniprot_search(r.json()) if r else []
    return {"query": q, "hits": hits[:limit], "ms": round((time.perf_counter() - t0) * 1000, 1)}


ENTRY_FIELDS = "accession,id,protein_name,gene_names,organism_name,sequence,xref_pdb,ft_domain,ft_region,reviewed"


async def get_protein(accession: str) -> dict:
    """서열·구조 후보·도메인 구간을 한 번에 돌려줍니다."""
    async with httpx.AsyncClient() as c:
        r = await _get(c, f"{UNIPROT}/{accession.upper()}.json", {"fields": ENTRY_FIELDS})
    if r is None:
        raise KeyError(f"UniProt 에 {accession} 가 없습니다")
    return parse_uniprot_entry(r.json())


async def fetch_pdb(pdb: str) -> str:
    async with httpx.AsyncClient() as c:
        r = await _get(c, f"{RCSB_FILES}/{pdb.upper()}.pdb")
    if r is None:
        raise KeyError(f"RCSB 에 {pdb} 가 없습니다")
    return r.text


async def search_ligand(q: str, limit: int = 6) -> dict:
    """이름으로 PubChem 에서 찾고, 붙여 넣은 SMILES 는 그대로 받습니다."""
    q = (q or "").strip()
    if not q:
        return {"query": q, "hits": []}
    ok, why = valid_smiles(q)
    looks_smiles = ok and (len(q) > 8 and any(ch in q for ch in "()=#[]") or q.count("C") > 3) and " " not in q
    t0 = time.perf_counter()
    hits: list[dict] = []
    async with httpx.AsyncClient() as c:
        r = await _get(c, f"{PUBCHEM}/compound/name/{httpx.URL(q).path.lstrip('/') or q}/property/SMILES,IsomericSMILES,CanonicalSMILES,MolecularWeight,Title/JSON")
        one = parse_pubchem_properties(r.json()) if r else None
        if one:
            hits.append(one)
        if len(hits) < limit:
            ac = await _get(c, f"{PUBCHEM_AC}/{q}/json", {"limit": limit})
            names = [n for n in (parse_pubchem_autocomplete(ac.json()) if ac else []) if n.lower() != q.lower()]
            for name in names[: max(0, limit - len(hits))]:
                rr = await _get(c, f"{PUBCHEM}/compound/name/{name}/property/SMILES,IsomericSMILES,CanonicalSMILES,MolecularWeight,Title/JSON")
                got = parse_pubchem_properties(rr.json()) if rr else None
                if got:
                    hits.append(got)
    if looks_smiles and not any(h["smiles"] == q for h in hits):
        hits.insert(0, {"cid": None, "name": "붙여 넣은 SMILES", "smiles": q, "mw": None, "source": "직접 입력"})
    return {"query": q, "hits": hits[:limit], "ms": round((time.perf_counter() - t0) * 1000, 1),
            "smiles_note": "" if ok else why}


def json_dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False)
