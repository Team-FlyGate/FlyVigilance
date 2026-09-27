"""Signal Memory 층의 근거 도구. 모든 결과에 근거 ID 를 붙인다.

faers:2x2:<DRUG>:<pt>@<asof>   로컬 웨어하우스에서 계산한 불균형 지표 (SQL 계산, 모델 미개입)
label:<setid>#<section>        openFDA 라벨 원문에서 반응명을 찾은 위치
pubmed:<pmid>                  PubMed E-utilities 검색 결과
"""
import asyncio
import functools
import gzip
import json
import re

import httpx

from .config import DATA

LABEL_SECTIONS = ["boxed_warning", "warnings_and_cautions", "warnings", "adverse_reactions", "precautions",
                  "contraindications"]


@functools.lru_cache(maxsize=1)
def _signals():
    p = DATA / "signals.json.gz"
    if not p.exists():
        return {"asof": None, "N": 0, "drugs": {}}
    with gzip.open(p, "rt") as f:
        return json.load(f)


def faers_2x2(drug: str, pt: str) -> dict | None:
    s = _signals()
    rows = s["drugs"].get(drug.upper())
    if not rows:
        return None
    cols = s["columns"]
    for r in rows:
        rec = dict(zip(cols, r))
        if rec["pt"] == pt.lower():
            rec["id"] = f"faers:2x2:{drug.upper()}:{pt.lower()}@{s['asof']}"
            rec["N"] = s["N"]
            return rec
    return {"id": f"faers:2x2:{drug.upper()}:{pt.lower()}@{s['asof']}", "pt": pt.lower(), "a": None,
            "note": "not among the 80 most-reported reactions exported for this drug; disproportionality not available here",
            "N": s["N"]}


def drug_profile(drug: str, limit: int = 25) -> list[dict]:
    s = _signals()
    rows = s["drugs"].get(drug.upper(), [])
    return [dict(zip(s["columns"], r)) for r in rows[:limit]]


ROUTE_MAP = {"ORAL": "ORAL", "INTRAVENOUS": "INTRAVENOUS", "SUBCUTANEOUS": "SUBCUTANEOUS", "INTRAMUSCULAR": "INTRAMUSCULAR",
             "TOPICAL": "TOPICAL", "OPHTHALMIC": "OPHTHALMIC", "TRANSDERMAL": "TRANSDERMAL", "INHALATION": "RESPIRATORY (INHALATION)"}


def _pick_label(results: list[dict], route: str | None) -> dict:
    """같은 성분 라벨이 여럿이면 케이스 투여 경로와 맞는 것을, 경로가 없으면 전신 제형을 고른다."""
    want = ROUTE_MAP.get((route or "").upper())
    systemic = {"ORAL", "INTRAVENOUS", "SUBCUTANEOUS", "INTRAMUSCULAR"}
    def score(d):
        routes = set(d.get("openfda", {}).get("route", []))
        return (2 if want and want in routes else 0) + (1 if routes & systemic else 0) + (1 if d.get("boxed_warning") or d.get("warnings_and_cautions") else 0)
    return max(results, key=score)


async def label_lookup(drug: str, pts: list[str], client: httpx.AsyncClient, route: str | None = None) -> dict:
    q = f'openfda.generic_name:"{drug.lower()}"'
    try:
        r = await client.get("https://api.fda.gov/drug/label.json", params={"search": q, "limit": 15}, timeout=15)
        if r.status_code != 200:
            return {"found": False, "drug": drug, "status": r.status_code}
        d = _pick_label(r.json()["results"], route)
    except Exception as e:
        return {"found": False, "drug": drug, "error": type(e).__name__}
    setid = d.get("set_id")
    hits = []
    for pt in pts:
        term = pt.lower()
        for sec in LABEL_SECTIONS:
            text = " ".join(d.get(sec, []))
            i = text.lower().find(term)
            if i >= 0:
                snippet = re.sub(r"\s+", " ", text[max(0, i - 90): i + len(term) + 110]).strip()
                hits.append({"id": f"label:{setid}#{sec}", "pt": pt, "section": sec, "quote": snippet})
                break
    return {"found": True, "drug": drug, "setid": setid, "effective": d.get("effective_time"),
            "route": d.get("openfda", {}).get("route", []),
            "brand": (d.get("openfda", {}).get("brand_name") or [None])[0], "hits": hits,
            "listed": {pt: any(h["pt"] == pt for h in hits) for pt in pts}}


async def pubmed(drug: str, pt: str, client: httpx.AsyncClient) -> dict:
    term = f'"{drug.lower()}"[tiab] AND "{pt.lower()}"[tiab]'
    err = "rate_limited"
    for attempt in range(3):
        try:
            r = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                                 params={"db": "pubmed", "term": term, "retmax": 5, "retmode": "json", "sort": "relevance"},
                                 timeout=15)
            if r.status_code == 429:
                await asyncio.sleep(1.0 + attempt)
                continue
            es = r.json()["esearchresult"]
            ids = es.get("idlist", [])
            return {"query": term, "count": int(es.get("count", 0)), "pmids": ids,
                    "ids": [f"pubmed:{i}" for i in ids]}
        except Exception as e:
            err = type(e).__name__
    return {"query": term, "count": None, "pmids": [], "ids": [], "error": err}


async def bundle(case: dict, suspect: str) -> dict:
    """케이스 하나에 대한 근거 묶음. 주 반응 3개까지."""
    pts = case.get("reactions", [])[:3]
    async with httpx.AsyncClient(headers={"User-Agent": "FlyVigilance/1.0 (hackathon demo)"}) as c:
        ps_route = next((d.get("route") for d in case.get("drugs", []) if d.get("drug") == suspect), None)
        label_t = label_lookup(suspect, pts, c, ps_route)
        pub_t = [pubmed(suspect, pt, c) for pt in pts]
        label, *pubs = await asyncio.gather(label_t, *pub_t)
    faers = [faers_2x2(suspect, pt) for pt in pts]
    # 인용 가능한 근거 ID 카탈로그: 모델은 이 문자열만 그대로 쓸 수 있다
    catalog = [{"id": f"faers:case:{case['primaryid']}", "what": "this ICSR (demographics, drugs, reactions, outcomes)"}]
    for f in faers:
        if f and f.get("prr"):
            catalog.append({"id": f["id"], "what": f"FAERS 2x2 for {suspect} / {f['pt']}: a={f['a']}, PRR={f['prr']} "
                            f"[{f['prr_lo']}-{f['prr_hi']}], ROR025={f['ror_lo']}, IC025={f['ic025']}, "
                            f"Evans={f['evans']}, ROR={f['ror_sig']}, IC={f['ic_sig']}"})
        elif f:
            catalog.append({"id": f["id"], "what": f"FAERS 2x2 for {suspect} / {f['pt']}: {f.get('note', 'not computed')}"})
    if label.get("found"):
        listed = ", ".join(f"{k}={'listed' if v else 'not found'}" for k, v in label.get("listed", {}).items())
        catalog.append({"id": f"label:{label['setid']}", "what": f"openFDA label for {suspect} ({label.get('brand')}, route {'/'.join(label.get('route', [])) or 'n/a'}), "
                        f"effective {label.get('effective')}; reaction search in warnings/adverse reactions: {listed}"})
        for h in label.get("hits", []):
            catalog.append({"id": h["id"], "what": f"label section {h['section']} mentions '{h['pt']}': \"{h['quote']}\""})
    for pt, p in zip(pts, pubs):
        if p.get("count") is not None:
            catalog.append({"id": f"pubmed:search:{pt}", "what": f"PubMed search {p['query']}: {p['count']} records"})
        for pid in p.get("pmids", []):
            catalog.append({"id": f"pubmed:{pid}", "what": f"PubMed record PMID {pid} (top relevance for {pt})"})
    ids = {c["id"] for c in catalog}
    return {"suspect": suspect, "reactions": pts, "faers": faers, "label": label,
            "pubmed": dict(zip(pts, pubs)), "catalog": catalog, "ids": sorted(ids)}
