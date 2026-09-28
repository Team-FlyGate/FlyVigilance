"""Signal Memory 층의 근거 도구입니다. 모든 결과에 근거 ID 를 붙입니다.

faers:2x2:<DRUG>:<pt>@<asof>   로컬 웨어하우스에서 계산한 불균형 지표 (SQL 계산, 모델 미개입)
label:<setid>#<section>        openFDA 라벨에서 반응명이 기재된 절. section 은 boxed_warning, warnings_and_cautions,
                               warnings, precautions(구형 일반 주의), adverse_reactions_ct(임상시험 6.1),
                               adverse_reactions_pm(시판 후 6.2), adverse_reactions_mixed(둘을 합친 절),
                               adverse_reactions(구형, 출처 구분 없음) 중 하나입니다. 금기·효능효과는 기재로 세지 않습니다
pubmed:<pmid>#<design>         PubMed 초록을 읽고 연구 설계를 판정한 문헌 (literature.py)
grade:<DRUG>:<pt>@<asof>       근거 등급 (grade.py)
metric:<rule>:<refset>@<asof>  참조 세트에서 잰 신호 기준의 민감도·특이도 (pipeline/refsets)
"""
import asyncio
import functools
import gzip
import json
import os
import pathlib
import re
import time

import httpx

from . import labeltext
from .config import DATA

UA = {"User-Agent": "FlyVigilance/1.0 (pharmacovigilance hackathon demo)"}


# ---------------------------------------------------------------- 호출 속도 제한
class _Spacer:
    """공개 API 의 초당 호출 제한을 지키려고 호출 사이 간격을 둡니다. 이벤트 루프마다 잠금을 따로 둡니다."""

    def __init__(self, gap: float):
        self.gap, self.last, self.locks = gap, 0.0, {}

    async def wait(self):
        loop = asyncio.get_running_loop()
        lock = self.locks.setdefault(id(loop), asyncio.Lock())
        async with lock:
            dt = time.monotonic() - self.last
            if dt < self.gap:
                await asyncio.sleep(self.gap - dt)
            self.last = time.monotonic()


OPENFDA = _Spacer(0.26)   # 키 없이 분당 240 회
PUBMED = _Spacer(0.36)    # 키 없이 초당 3 회


def _cache_dir() -> pathlib.Path | None:
    d = os.environ.get("FV_CACHE_DIR")
    if not d:
        return None
    p = pathlib.Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def get_json(client: httpx.AsyncClient, url: str, params: dict, spacer: _Spacer, key: str | None = None,
                   retries: int = 4) -> tuple[int, dict | str | None]:
    """제한 간격을 지키며 GET 합니다. FV_CACHE_DIR 이 있으면 결과를 디스크에 캐시합니다."""
    cdir = _cache_dir()
    cfile = cdir / (key.replace("/", "_") + ".json") if (cdir and key) else None
    if cfile and cfile.exists():
        d = json.loads(cfile.read_text())
        return d["status"], d["body"]
    status, body = 0, None
    for attempt in range(retries):
        await spacer.wait()
        try:
            r = await client.get(url, params=params, timeout=20, headers=UA)
        except httpx.HTTPError:
            await asyncio.sleep(1.0 + attempt)
            continue
        status = r.status_code
        if status in (429, 500, 502, 503):
            await asyncio.sleep(1.5 * (attempt + 1))
            continue
        body = r.json() if "json" in r.headers.get("content-type", "") else r.text
        break
    if cfile and status in (200, 404):
        cfile.write_text(json.dumps({"status": status, "body": body}))
    return status, body


# ---------------------------------------------------------------- FAERS 웨어하우스
def id_drug(drug: str) -> str:
    """근거 ID 에 쓰는 약물명입니다. FAERS 복합제 구분자 역슬래시(A\\B)는 모델이 JSON 으로 옮기며 자주 깨뜨려 + 로 바꿉니다."""
    return drug.upper().replace("\\", "+")


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
            rec["id"] = f"faers:2x2:{id_drug(drug)}:{pt.lower()}@{s['asof']}"
            rec["N"] = s["N"]
            return rec
    return {"id": f"faers:2x2:{id_drug(drug)}:{pt.lower()}@{s['asof']}", "pt": pt.lower(), "a": None,
            "note": "not among the 80 most-reported reactions exported for this drug; disproportionality not available here",
            "N": s["N"]}


@functools.lru_cache(maxsize=1)
def _metrics():
    p = DATA / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else {"rules": {}}


def metric_catalog() -> list[dict]:
    """신호 기준이 공개 참조 세트에서 보인 성능입니다. 모델이 'PRR 이 신호다'라고 말할 때 이 근거를 함께 인용합니다."""
    m = _metrics()
    out = []
    for refset, v in (m.get("rules", {}).get("triple") or {}).items():
        out.append({"id": f"metric:triple:{refset}@{m.get('asof')}",
                    "what": f"Signal rule Evans AND ROR025>1 AND IC025>0 on the {refset} reference set (n={v['n']}): "
                            f"sensitivity {v['sens']:.2f}, specificity {v['spec']:.2f}, PPV {v['ppv']:.2f}. "
                            "Measures agreement with labeled/literature reference pairs, not causality."})
    return out


def drug_profile(drug: str, limit: int = 25) -> list[dict]:
    s = _signals()
    rows = s["drugs"].get(drug.upper(), [])
    return [dict(zip(s["columns"], r)) for r in rows[:limit]]


def signal_tier(f: dict | None) -> str:
    """신호 기준을 명시합니다: Evans(PRR>=2, chi2>=4, a>=3) ∧ ROR025>1 ∧ IC025>0 세 개 모두면 strong."""
    if not f or f.get("a") is None:
        return "unavailable"
    if f["a"] < 3:
        return "insufficient"
    n = int(bool(f.get("evans"))) + int(bool(f.get("ror_sig"))) + int(bool(f.get("ic_sig")))
    return {3: "strong", 2: "weak", 1: "weak", 0: "none"}[n]


# ---------------------------------------------------------------- openFDA 라벨
ROUTE_MAP = {"ORAL": "ORAL", "INTRAVENOUS": "INTRAVENOUS", "SUBCUTANEOUS": "SUBCUTANEOUS", "INTRAMUSCULAR": "INTRAMUSCULAR",
             "TOPICAL": "TOPICAL", "OPHTHALMIC": "OPHTHALMIC", "TRANSDERMAL": "TRANSDERMAL", "INHALATION": "RESPIRATORY (INHALATION)"}
_LABEL_MEM: dict[str, dict | None] = {}


def _single_ingredient(d: dict, drug: str) -> bool:
    """복합제가 아니라 그 성분 하나만 든 라벨인지 봅니다 (염 이름은 허용합니다)."""
    for gn in d.get("openfda", {}).get("generic_name", []):
        g = gn.lower()
        if drug.lower() in g and not re.search(r"(\band\b|,|/|\+|;)", g):
            return True
    return False


def _pick_label(results: list[dict], route: str | None, drug: str = "") -> dict:
    """같은 성분 라벨이 여럿이면 단일 성분 라벨, 케이스 투여 경로와 맞는 것, 전신 제형, 최신 개정 순으로 고릅니다."""
    want = ROUTE_MAP.get((route or "").upper())
    systemic = {"ORAL", "INTRAVENOUS", "SUBCUTANEOUS", "INTRAMUSCULAR"}

    def score(d):
        routes = set(d.get("openfda", {}).get("route", []))
        return ((4 if drug and _single_ingredient(d, drug) else 0) + (2 if want and want in routes else 0)
                + (1 if routes & systemic else 0) + (1 if d.get("boxed_warning") or d.get("warnings_and_cautions") else 0),
                d.get("effective_time", ""))
    return max(results, key=score)


async def get_label(drug: str, client: httpx.AsyncClient, route: str | None = None) -> dict | None:
    """성분명으로 라벨 하나를 고릅니다. 결과는 메모리에(그리고 FV_CACHE_DIR 이 있으면 디스크에) 캐시합니다."""
    key = f"{drug.upper()}|{(route or '').upper()}"
    if key in _LABEL_MEM:
        return _LABEL_MEM[key]
    status, body = await get_json(client, "https://api.fda.gov/drug/label.json",
                                  {"search": f'openfda.generic_name:"{drug.lower()}"', "limit": 15},
                                  OPENFDA, key=f"openfda_label_{drug.upper()}")
    doc = None
    if status == 200 and isinstance(body, dict) and body.get("results"):
        d = _pick_label(body["results"], route, drug)
        doc = {"setid": d.get("set_id"), "effective": d.get("effective_time"),
               "brand": (d.get("openfda", {}).get("brand_name") or [None])[0],
               "route": d.get("openfda", {}).get("route", []),
               "sections": labeltext.label_sections(d)}
    _LABEL_MEM[key] = doc
    return doc


def label_facts(doc: dict | None, drug: str, pts: list[str]) -> dict:
    """라벨 문서에서 반응별 기재 절, 라벨 상태, 인과 미확립 단서, 금기·적응증 맥락을 뽑습니다.
    by_pt[pt] = {sections(기재 절, 강한 순), rank(정수 3 박스 경고 / 2 경고·주의 / 1 이상반응 / 0 미기재),
                 label_status, disclaimer, contraindication(금기 절 인용 또는 None), indication_term, matched_via}.
    listed[pt] 는 rank >= 1 과 같습니다. 금기 절이나 효능·효과 절에만 나온 반응은 기재가 아닙니다."""
    if not doc:
        return {"found": False, "drug": drug, "hits": [], "listed": {}, "by_pt": {}}
    hits, by_pt = [], {}
    for pt in pts:
        f = labeltext.pt_facts(doc.get("sections") or {}, pt)
        h = f.pop("primary")
        by_pt[pt] = f
        if h:
            hits.append({"id": f"label:{doc['setid']}#{h['section']}", "pt": pt, "section": h["section"],
                         "quote": h["quote"], "matched_via": h["matched_via"]})
    return {"found": True, "drug": drug, "setid": doc["setid"], "effective": doc["effective"], "route": doc["route"],
            "brand": doc["brand"], "hits": hits, "by_pt": by_pt,
            "listed": {pt: by_pt[pt]["rank"] >= 1 for pt in pts}}


async def label_lookup(drug: str, pts: list[str], client: httpx.AsyncClient, route: str | None = None) -> dict:
    doc = await get_label(drug, client, route)
    return label_facts(doc, drug, pts)


# ---------------------------------------------------------------- PubMed 검색
async def pubmed(drug: str, pt: str, client: httpx.AsyncClient, retmax: int = 5) -> dict:
    """약물명과 반응명이 제목·초록에 함께 나오는 문헌을 찾습니다. 반응명은 정확한 동의어(labeltext.EQUIV)를 OR 로 묶습니다
    (예: "pyrexia" OR "fever"). 동의어가 붙으면 검색식이 달라지므로 캐시 키도 따로 둡니다."""
    eq = labeltext.equivalents(pt)
    rx = " OR ".join(f'"{x}"[tiab]' for x in eq)
    term = f'"{drug.lower()}"[tiab] AND ' + (rx if len(eq) == 1 else f"({rx})")
    status, body = await get_json(client, "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                                  {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json", "sort": "relevance"},
                                  PUBMED, key=f"pubmed_search_{drug.upper()}_{pt.lower()}_{retmax}" + ("_eq" if len(eq) > 1 else ""))
    if status != 200 or not isinstance(body, dict):
        return {"query": term, "count": None, "pmids": [], "ids": [], "error": f"HTTP {status}"}
    es = body["esearchresult"]
    ids = es.get("idlist", [])
    return {"query": term, "count": int(es.get("count", 0)), "pmids": ids, "ids": [f"pubmed:{i}" for i in ids]}


# ---------------------------------------------------------------- 근거 묶음
async def bundle(case: dict, suspect: str, read_literature: bool = True) -> dict:
    """케이스 하나에 대한 근거 묶음입니다. 주 반응 3개까지 라벨·통계·문헌·근거 등급을 붙입니다."""
    from . import grade as grade_mod, literature  # 순환 import 를 피합니다

    pts = [p for p in case.get("reactions", []) if not labeltext.is_nonclinical(p)][:3] or case.get("reactions", [])[:3]
    ps_route = next((d.get("route") for d in case.get("drugs", []) if d.get("drug") == suspect), None)
    async with httpx.AsyncClient() as c:
        label_t = label_lookup(suspect, pts, c, ps_route)
        lit_t = [literature.read(suspect, pt, c) if read_literature else pubmed(suspect, pt, c) for pt in pts]
        label, *lits = await asyncio.gather(label_t, *lit_t)
    faers = [faers_2x2(suspect, pt) for pt in pts]
    grades = [grade_mod.grade_pair(suspect, pt, f, label, lit) for pt, f, lit in zip(pts, faers, lits)]

    # 인용 가능한 근거 ID 카탈로그입니다. 모델은 이 문자열만 그대로 쓸 수 있습니다.
    catalog = [{"id": f"faers:case:{case['primaryid']}", "what": "this ICSR (demographics, drugs, reactions, outcomes)"}]
    for f in faers:
        if f and f.get("prr"):
            catalog.append({"id": f["id"], "what": f"FAERS 2x2 for {suspect} / {f['pt']}: a={f['a']}, PRR={f['prr']} "
                            f"[{f['prr_lo']}-{f['prr_hi']}], ROR025={f['ror_lo']}, IC025={f['ic025']}, "
                            f"Evans={f['evans']}, ROR={f['ror_sig']}, IC={f['ic_sig']}"})
        elif f:
            catalog.append({"id": f["id"], "what": f"FAERS 2x2 for {suspect} / {f['pt']}: {f.get('note', 'not computed')}"})
    if label.get("found"):
        st = []
        for k, v in label.get("by_pt", {}).items():
            extra = (["named in contraindications only as a patient condition"] if v.get("contraindication") and not v["rank"]
                     else []) + (["also an indication term"] if v.get("indication_term") else [])
            st.append(f"{k}={v.get('label_status', 'unlisted')}" + (f" ({'; '.join(extra)})" if extra else ""))
        catalog.append({"id": f"label:{label['setid']}", "what": f"openFDA label for {suspect} ({label.get('brand')}, route "
                        f"{'/'.join(label.get('route', [])) or 'n/a'}), effective {label.get('effective')}; "
                        "reaction search (PT, US spelling, word order, exact MedDRA-equivalent synonyms) in boxed warning, "
                        "warnings and precautions, old-format warnings and general precautions, and adverse reactions split into "
                        "clinical trials / postmarketing / pooled parts; mentions in patient-population, indication, negated or "
                        "compound-term context are not counted, and contraindications and indications are context only, "
                        f"not listings: {', '.join(st)}"})
        for h in label.get("hits", []):
            catalog.append({"id": h["id"], "what": f"label section {h['section']} lists '{h['pt']}' "
                            f"(matched via {h.get('matched_via', 'literal')}): \"{h['quote']}\""})
    for pt, lit in zip(pts, lits):
        if lit.get("count") is not None:
            catalog.append({"id": f"pubmed:search:{pt}", "what": f"PubMed search {lit['query']}: {lit['count']} records"})
        for a in lit.get("articles", []):
            catalog.append({"id": a["id"], "what": f"PMID {a['pmid']} ({a.get('year')}), design {a['design']} "
                            f"[{a['design_source']}], reports association p={a['supports']:.2f}: {a.get('title', '')[:140]}"})
        for pid in ([] if lit.get("articles") else lit.get("pmids", [])):
            catalog.append({"id": f"pubmed:{pid}", "what": f"PubMed record PMID {pid} (top relevance for {pt})"})
    catalog += metric_catalog()
    for g in grades:
        catalog.append({"id": g["id"], "what": f"Evidence grade {g['grade']} ({g['grade_name']}) for {suspect} / {g['pt']}: "
                        f"{g['summary']}. Population-level evidence only; not individual-case causality."})
    ids = {c["id"] for c in catalog}
    return {"suspect": suspect, "reactions": pts, "faers": faers, "label": label, "literature": dict(zip(pts, lits)),
            "pubmed": {pt: {"count": lit.get("count"), "pmids": lit.get("pmids", []), "ids": lit.get("ids", [])}
                       for pt, lit in zip(pts, lits)},
            "grades": grades, "catalog": catalog, "ids": sorted(ids)}
