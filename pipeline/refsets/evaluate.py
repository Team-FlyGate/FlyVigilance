"""참조 세트 검증입니다 (확장 계획 제안 1).

같은 약물–반응 쌍에서 다음을 잽니다.
  통계 지표   : 보고 건수 a, PRR, ROR025, 부호 있는 카이제곱, IC025 (웨어하우스 SQL 과 같은 공식)
  규칙 기준점 : Evans(PRR>=2, chi2>=4, a>=3), 세 기준 동시 충족(Evans ∧ ROR025>1 ∧ IC025>0)
  FlyVigilance 지식 기반 판별 : 약·반응 이름을 주고 공인된 연관인지 묻습니다(api/_fv/knowledge.py 와 같은 질문)
  FlyVigilance 통계 기반 판별 : 이름을 가리고, 웨어하우스에서 계산한 사례군 특성(시기별 일관성, 주의심약 비율,
                중대·사망, 의료인 보고, 중단 후 호전·재투여 재발, 보고 국가 수, 적응증 교란)을 약물감시 평가 기준 질문으로 묻습니다
  모델 단독 · 이름 가림      : 이름을 가리고 불균형 숫자만 준 기준선입니다

참조 세트의 양성은 라벨·문헌이 인정한 조합이므로, 이 측정은 '공인된 약물-이상반응 연관을 가려내는가'를 잽니다.
Harpaz 전향 조건은 2013년 이전 보고만 쓰는 방법(통계 지표, 통계 기반 판별)으로 잽니다.
OMOP 음성 대조군의 분류 논의(Hauben et al. 2016)도 함께 참고합니다.

산출물: web/public/data/validation.json, api/_data/metrics.json
"""
import argparse
import asyncio
import hashlib
import json
import pathlib
import sys
import time

import duckdb
import httpx
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from _fv import clients, config, knowledge, pvstats  # noqa: E402

DB = ROOT / "data/derived/faers.duckdb"
REF = ROOT / "data/derived/refsets"
CACHE = ROOT / "data/cache/jev_refset.jsonl"
EN = {"OMOP Acute Liver Failure 1": "acute liver injury", "OMOP Acute Renal Failure 1": "acute kidney injury",
      "OMOP Acute myocardial Infarction  1": "acute myocardial infarction", "HOI Upper GI #3": "upper gastrointestinal bleeding",
      "OMOP Aplastic Anemia 1": "aplastic anemia", "Anaphylaxis #1": "anaphylaxis",
      "Stevens-Johnson Syndrome #1": "Stevens-Johnson syndrome or toxic epidermal necrolysis",
      "Leukopenia Including Neutropenia and Agranulocytosis": "leukopenia including neutropenia and agranulocytosis",
      "Rhabdomyolysis #1": "rhabdomyolysis", "Cardiac Valve Fibrosis #1": "cardiac valve fibrosis"}
ERAS = [("2012Q4–2016", "2016Q4"), ("2017–2021", "2021Q4"), ("2022–2026Q2", "9999Q9")]
LEGACY_DB = ROOT / "data/derived/aers_legacy.duckdb"
LEGACY_ERAS = [("2004–2006", "2006Q4"), ("2007–2009", "2009Q4"), ("2010–2012Q3", "9999Q9")]
SOURCES = {"main": "FAERS 2012Q4-2026Q2, deduplicated to the latest case version, FDA deletions removed.",
           "legacy": "legacy AERS 2004Q1-2012Q3 (all reports received before 2013), deduplicated to the latest case version."}


# ---------------------------------------------------------------- 웨어하우스 특성
def warehouse(pairs: pd.DataFrame, events: dict, db: pathlib.Path = DB, eras: list = ERAS) -> tuple[dict, dict]:
    con = duckdb.connect(str(db), read_only=True)
    con.execute("SET memory_limit='12GB'")
    ev_rows = [(k, p) for k in set(pairs.event) for p in events[k]["pts"]]
    con.register("ev_df", pd.DataFrame(ev_rows, columns=["event", "pt"]))
    con.register("pr_df", pairs[["drug", "event"]].drop_duplicates())
    t0 = time.time()
    con.execute("CREATE TEMP TABLE ev AS SELECT * FROM ev_df")
    con.execute("CREATE TEMP TABLE pr AS SELECT * FROM pr_df")
    con.execute("CREATE TEMP TABLE ev_cases AS SELECT DISTINCT e.event, t.primaryid FROM sig_triplet t JOIN ev e ON e.pt = t.pt")
    con.execute("""CREATE TEMP TABLE drug_cases AS SELECT DISTINCT t.drug, t.primaryid FROM sig_triplet t
                   WHERE t.drug IN (SELECT DISTINCT drug FROM pr)""")
    con.execute("""CREATE TEMP TABLE a_cases AS SELECT p.drug, p.event, d.primaryid FROM pr p
                   JOIN drug_cases d ON d.drug = p.drug JOIN ev_cases e ON e.event = p.event AND e.primaryid = d.primaryid""")
    case_expr = "CASE " + " ".join(f"WHEN quarter <= '{ub}' THEN {k}" for k, (_, ub) in enumerate(eras)) + " END"
    con.execute(f"""CREATE TEMP TABLE case_era AS SELECT primaryid, {case_expr} AS era
                   FROM core_case WHERE primaryid IN (SELECT DISTINCT primaryid FROM sig_triplet)""")
    N = con.execute("SELECT count(*) FROM case_era").fetchone()[0]
    N_era = dict(con.execute("SELECT era, count(*) FROM case_era GROUP BY 1").fetchall())
    n_d = dict(con.execute("SELECT drug, count(*) FROM drug_cases GROUP BY 1").fetchall())
    n_e = dict(con.execute("SELECT event, count(*) FROM ev_cases GROUP BY 1").fetchall())
    a = {(d, e): n for d, e, n in con.execute("SELECT drug, event, count(*) FROM a_cases GROUP BY 1, 2").fetchall()}
    nd_era = {(d, r): n for d, r, n in con.execute(
        "SELECT drug, era, count(*) FROM drug_cases JOIN case_era USING (primaryid) GROUP BY 1, 2").fetchall()}
    ne_era = {(e, r): n for e, r, n in con.execute(
        "SELECT event, era, count(*) FROM ev_cases JOIN case_era USING (primaryid) GROUP BY 1, 2").fetchall()}
    a_era = {(d, e, r): n for d, e, r, n in con.execute(
        "SELECT drug, event, era, count(*) FROM a_cases JOIN case_era USING (primaryid) GROUP BY 1, 2, 3").fetchall()}
    base = {(d, e): dict(zip(["n", "serious", "death", "hcp", "countries"], r)) for d, e, *r in con.execute("""
        SELECT ac.drug, ac.event, count(*),
               avg(CASE WHEN s.primaryid IS NOT NULL THEN 1 ELSE 0 END),
               avg(CASE WHEN s.death THEN 1 ELSE 0 END),
               avg(CASE WHEN c.occp_cod IN ('MD', 'PH', 'OT', 'HP') THEN 1 ELSE 0 END),
               count(DISTINCT c.reporter_country)
        FROM a_cases ac JOIN core_case c USING (primaryid) LEFT JOIN core_case_serious s USING (primaryid)
        GROUP BY 1, 2""").fetchall()}
    con.execute("""CREATE TEMP TABLE a_drug AS
        SELECT ac.drug, ac.event, ac.primaryid, bool_or(cd.role_cod = 'PS') AS is_ps,
               max(CASE WHEN cd.dechal = 'Y' THEN 2 WHEN cd.dechal = 'N' THEN 1 ELSE 0 END) AS dechal,
               max(CASE WHEN cd.rechal = 'Y' THEN 2 WHEN cd.rechal = 'N' THEN 1 ELSE 0 END) AS rechal,
               list(cd.drug_seq) AS seqs
        FROM a_cases ac JOIN core_drug cd ON cd.primaryid = ac.primaryid AND cd.drug = ac.drug
        GROUP BY 1, 2, 3""")
    drugf = {(d, e): dict(zip(["ps", "dechal_known", "dechal_pos", "rechal_pos"], r)) for d, e, *r in con.execute("""
        SELECT drug, event, avg(CASE WHEN is_ps THEN 1 ELSE 0 END), sum(CASE WHEN dechal > 0 THEN 1 ELSE 0 END),
               sum(CASE WHEN dechal = 2 THEN 1 ELSE 0 END), sum(CASE WHEN rechal = 2 THEN 1 ELSE 0 END)
        FROM a_drug GROUP BY 1, 2""").fetchall()}
    indi = {(d, e): n for d, e, n in con.execute("""
        SELECT ad.drug, ad.event, count(DISTINCT ad.primaryid) FROM a_drug ad
        JOIN core_indi i ON i.primaryid = ad.primaryid AND list_contains(ad.seqs, i.drug_seq)
        JOIN ev ON ev.event = ad.event AND ev.pt = i.indi_pt GROUP BY 1, 2""").fetchall()}
    print(f"warehouse features in {time.time() - t0:.1f}s, N={N:,}")

    feats = {}
    for d, e in pairs[["drug", "event"]].drop_duplicates().itertuples(index=False):
        aa = a.get((d, e), 0)
        st = pvstats.two_by_two(aa, n_d.get(d, 0), n_e.get(e, 0), N)
        eras = []
        for r in range(3):
            s = pvstats.two_by_two(a_era.get((d, e, r), 0), nd_era.get((d, r), 0), ne_era.get((e, r), 0), N_era.get(r, 1))
            eras.append({"a": s["a"], "ic025": round(s["ic025"], 2)})
        b = base.get((d, e), {})
        f = drugf.get((d, e), {})
        feats[(d, e)] = {
            **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()},
            "n_drug": n_d.get(d, 0), "n_event": n_e.get(e, 0), "eras": eras,
            "serious": b.get("serious"), "death": b.get("death"), "hcp": b.get("hcp"), "countries": b.get("countries", 0),
            "ps": f.get("ps"), "dechal_known": f.get("dechal_known", 0), "dechal_pos": f.get("dechal_pos", 0),
            "rechal_pos": f.get("rechal_pos", 0), "indication_overlap": (indi.get((d, e), 0) / aa) if aa else 0.0,
        }
    return feats, {"N": N}


# ---------------------------------------------------------------- 판단 모델 상태와 질문
state_named = knowledge.state   # 지식 기반 판별은 서비스와 같은 질문·상태를 씁니다


def state_blind(f: dict) -> str:
    if not f["a"]:
        return "Drug: DRUG_A (masked). Event: EVENT_1 (masked).\nFAERS spontaneous reports: no co-reported cases (a = 0)."
    return ("Drug: DRUG_A (masked). Event: EVENT_1 (masked).\n"
            f"FAERS spontaneous reports: co-reported cases a = {f['a']}, expected = {f['expected']:.1f}, "
            f"PRR = {_n(f['prr'])} (95% CI {_n(f['prr_lo'])}-{_n(f['prr_hi'])}), ROR025 = {_n(f['ror_lo'])}, "
            f"IC025 = {f['ic025']:.2f}, chi-square = {f['chi2']:.1f}.")


def state_flyvigilance(f: dict, n_pts: int, eras: list = ERAS, source: str = SOURCES["main"]) -> str:
    """FlyVigilance 가 신호 평가자에게 주는 형태의 상태입니다. 이름은 가리고, 계산된 사례군 특성만 줍니다."""
    lines = [f"Drug: DRUG_A (masked). Event: EVENT_1 (masked; defined by {n_pts} MedDRA preferred terms).",
             f"Source: {source}"]
    if not f["a"]:
        lines.append("Disproportionality: no co-reported cases (a = 0).")
        return "\n".join(lines)
    lines.append(f"Disproportionality: a = {f['a']} co-reported cases vs {f['expected']:.1f} expected; "
                 f"PRR {_n(f['prr'])} (95% CI {_n(f['prr_lo'])}-{_n(f['prr_hi'])}); ROR025 {_n(f['ror_lo'])}; "
                 f"IC025 {f['ic025']:.2f}; chi-square {f['chi2']:.1f}.")
    lines.append("Consistency over time (IC025 by era, a in brackets): " +
                 "; ".join(f"{name} {e['ic025']:+.2f} [{e['a']}]" for (name, _), e in zip(eras, f["eras"])))
    lines.append(f"Case series: drug is the primary suspect in {_p(f['ps'])} of cases; serious outcome {_p(f['serious'])}; "
                 f"fatal {_p(f['death'])}; reported by health professionals {_p(f['hcp'])}; {f['countries']} reporting countries.")
    dk = f["dechal_known"]
    lines.append(f"Dechallenge: positive in {f['dechal_pos']} of {dk} cases with dechallenge information"
                 + (f" ({f['dechal_pos'] / dk:.0%})" if dk else "") + f"; positive rechallenge in {f['rechal_pos']} cases.")
    lines.append(f"Possible confounding by indication: the event is also the recorded indication of the drug in "
                 f"{f['indication_overlap']:.0%} of cases.")
    return "\n".join(lines)


def _n(x):
    return "n/a" if x is None else f"{x:.2f}"


def _p(x):
    return "n/a" if x is None else f"{x:.0%}"


Q_NAMED = knowledge.QUESTION
Q_BLIND = {"causes": {"type": "noul", "instructions": "Based only on these reporting statistics, is DRUG_A likely to cause EVENT_1?"}}
Q_FV = {
    "credible": {"type": "noul", "instructions":
                 "As a pharmacovigilance signal assessor, weigh strength of disproportionality, consistency across eras, "
                 "case-series quality (primary suspect share, health-professional reports, seriousness), dechallenge and "
                 "rechallenge evidence, and confounding by indication. Is this a credible adverse drug reaction signal?"},
    "alternative": {"type": "choice", "instructions": "What is the most likely non-causal explanation, if any?",
                    "criteria": {"none": "no obvious alternative explanation",
                                 "indication": "confounding by indication or protopathic bias",
                                 "comedication": "co-medication or co-reporting artifact",
                                 "sparse": "too few cases to judge",
                                 "artifact": "stimulated, duplicate or notoriety-driven reporting"}},
}


def _key(state: str, qs: dict) -> str:
    return hashlib.sha256((state + json.dumps(qs, sort_keys=True)).encode()).hexdigest()[:24]


async def run_jev(jobs: list[tuple[str, str, dict]], conc: int) -> dict:
    """(job_id, state, questions) 목록을 병렬로 부릅니다. 같은 입력은 캐시에서 읽어 재실행 비용을 없앱니다."""
    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            r = json.loads(line)
            cache[r["k"]] = r["v"]
    # 이름을 가리면 서로 다른 쌍의 상태가 똑같아질 수 있습니다(예: a = 0). 같은 입력은 한 번만 불러 같은 점수를 줍니다
    out, todo, waiting = {}, [], {}
    for jid, st, qs in jobs:
        k = _key(st, qs)
        if k in cache:
            out[jid] = cache[k]
        elif k in waiting:
            waiting[k].append(jid)
        else:
            waiting[k] = [jid]
            todo.append((k, st, qs))
    sem = asyncio.Semaphore(conc)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as cl:
        async def one(k, st, qs):
            async with sem:
                try:
                    r = await clients.jev(st, qs, client=cl)
                    v = {"answers": r["answers"], "latency_ms": r["latency_ms"], "usage": r["usage"]}
                except Exception as e:
                    v = {"error": f"{type(e).__name__}"}
                for jid in waiting[k]:
                    out[jid] = v
                if "error" not in v:
                    with CACHE.open("a") as fh:
                        fh.write(json.dumps({"k": k, "v": v}) + "\n")
        await asyncio.gather(*(one(*t) for t in todo))
    print(f"jev: {len(jobs)} jobs, {len(todo)} new calls")
    return out


# ---------------------------------------------------------------- 평가
METHODS = [
    ("a", "보고 건수 a", "metric"), ("prr", "PRR", "metric"), ("ror_lo", "ROR₀₂₅", "metric"),
    ("chi2s", "χ² (부호)", "metric"), ("ic025", "IC₀₂₅", "metric"),
    ("raw_blind", "모델 단독 · 이름 가림", "raw"), ("fv", "FlyVigilance · 통계 기반 판별 (이름 가림)", "flyvigilance"),
    ("raw_named", "FlyVigilance · 지식 기반 판별 (이름 사용)", "knowledge"),
]


def score(row: dict, key: str) -> float:
    f = row["f"]
    if key == "a":
        return float(f["a"])
    if key == "prr":
        return f["prr"] or 0.0
    if key == "ror_lo":
        return f["ror_lo"] or 0.0
    if key == "chi2s":
        return (f["chi2"] or 0.0) * (1 if (f["prr"] or 0) > 1 else -1)
    if key == "ic025":
        return f["ic025"]
    return row.get(key, 0.0)


def evaluate(rows: list[dict], skip: tuple = ()) -> dict:
    y = [r["truth"] for r in rows]
    methods = []
    for key, label, fam in METHODS:
        if key in skip:
            continue
        s = [score(r, key) for r in rows]
        m = {"key": key, "label": label, "family": fam, "auc": round(pvstats.auc(s, y), 4),
             "ci": pvstats.bootstrap_auc(s, y), "roc": pvstats.roc_points(s, y)}
        if fam in ("raw", "flyvigilance", "knowledge"):
            m["at_0.5"] = pvstats.sens_spec([v >= 0.5 for v in s], y)
        methods.append(m)
    points = {"evans": pvstats.sens_spec([r["f"]["evans"] for r in rows], y),
              "triple": pvstats.sens_spec([r["f"]["triple"] for r in rows], y)}
    sc = {k: [score(r, k) for r in rows] for k, _, _ in METHODS if k not in skip}
    deltas = [
        {"a": "fv", "b": "ic025", **pvstats.bootstrap_delta(sc["fv"], sc["ic025"], y)},
        {"a": "fv", "b": "raw_blind", **pvstats.bootstrap_delta(sc["fv"], sc["raw_blind"], y)},
    ]
    # 각 판별 방식을 그 세트의 최고 통계 지표와 같은 방식(짝지은 부트스트랩)으로 비교합니다
    best = max((m for m in methods if m["family"] == "metric"), key=lambda m: m["auc"])["key"]
    for k in [x for x in ("raw_named", "raw_blind", "fv") if x in sc]:
        if not any(d["a"] == k and d["b"] == best for d in deltas):
            deltas.append({"a": k, "b": best, **pvstats.bootstrap_delta(sc[k], sc[best], y)})
    for d in deltas:
        d["best_metric"] = d["b"] == best
    return {"n": len(rows), "pos": sum(y), "neg": len(y) - sum(y), "methods": methods, "points": points, "deltas": deltas}


async def main(args):
    pairs = pd.read_parquet(REF / "pairs.parquet")
    events = json.loads((REF / "events.json").read_text())
    ev_pairs = pairs[pairs.evaluable].copy()
    feats, meta = warehouse(ev_pairs, events)

    jobs = []
    for d, e in ev_pairs[["drug", "event"]].drop_duplicates().itertuples(index=False):
        f = feats[(d, e)]
        label_en = EN[e[2:]] if e.startswith("O:") else e[2:]
        jobs.append((f"named|{d}|{e}", state_named(d, label_en), Q_NAMED))
        jobs.append((f"blind|{d}|{e}", state_blind(f), Q_BLIND))
        jobs.append((f"fv|{d}|{e}", state_flyvigilance(f, len(events[e]["pts"])), Q_FV))
    jr = await run_jev(jobs, args.conc)

    def pick(jid, q):
        v = jr.get(jid, {})
        return v.get("answers", {}).get(q, {}).get("noul", 0.0) if "error" not in v else 0.0

    # 전향적 검증: Harpaz 쌍을 2013년 이전 보고(구형 AERS)만으로 다시 잽니다
    legacy = None
    if LEGACY_DB.exists():
        hz = ev_pairs[ev_pairs.refset == "Harpaz"].copy()
        lfeats, lmeta = warehouse(hz, events, LEGACY_DB, LEGACY_ERAS)
        hz = hz[[lfeats[(d, e)]["n_drug"] > 0 for d, e in hz[["drug", "event"]].itertuples(index=False)]].copy()
        ljobs = []
        for d, e in hz[["drug", "event"]].drop_duplicates().itertuples(index=False):
            f = lfeats[(d, e)]
            ljobs.append((f"blind|{d}|{e}|legacy", state_blind(f), Q_BLIND))
            ljobs.append((f"fv|{d}|{e}|legacy", state_flyvigilance(f, len(events[e]["pts"]), LEGACY_ERAS, SOURCES["legacy"]), Q_FV))
        jr.update(await run_jev(ljobs, args.conc))
        hz["refset"] = "Harpaz-prospective"
        legacy = (hz, lfeats, lmeta)
        jobs += ljobs

    results, table = {}, {}
    lat = [v["latency_ms"] for v in jr.values() if "latency_ms" in v]
    sets = ["OMOP", "EU-ADR", "Harpaz"] + (["Harpaz-prospective"] if legacy else [])
    for refset in sets:
        if refset == "Harpaz-prospective":
            sub, fsrc, sfx = legacy[0], legacy[1], "|legacy"
        else:
            sub, fsrc, sfx = ev_pairs[ev_pairs.refset == refset], feats, ""
        rows = []
        for r in sub.itertuples():
            f = fsrc[(r.drug, r.event)]
            fvj = jr.get(f"fv|{r.drug}|{r.event}{sfx}", {})
            rows.append({"drug": r.drug, "drug_ref": r.drug_ref, "drug_match": r.drug_match, "event": r.event,
                         "truth": r.truth, "f": f,
                         "raw_named": pick(f"named|{r.drug}|{r.event}", "causes"),
                         "raw_blind": pick(f"blind|{r.drug}|{r.event}{sfx}", "causes"),
                         "fv": pick(f"fv|{r.drug}|{r.event}{sfx}", "credible"),
                         "fv_alt": fvj.get("answers", {}).get("alternative", {}).get("choice")})
        # 지식 기반 판별은 현재 지식을 쓰므로, 2013년 이전 정보만 쓰는 전향 조건에는 넣지 않습니다
        res = evaluate(rows, skip=("raw_named",) if refset == "Harpaz-prospective" else ())
        base_ref = "Harpaz" if refset == "Harpaz-prospective" else refset
        res["excluded"] = [{"drug": d, "event": e} for d, e in pairs[(pairs.refset == base_ref) & ~pairs.evaluable][["drug_ref", "event"]].itertuples(index=False)]
        if refset == "Harpaz-prospective":
            res["window"] = "AERS 2004Q1–2012Q3 (all before the 2013 label changes)"
            res["N"] = legacy[2]["N"]
            res["not_marketed_before_2013"] = int((ev_pairs.refset == "Harpaz").sum() - len(sub))
        results[refset] = res
        table[refset] = [{"drug": r["drug"], "drug_ref": r["drug_ref"], "event": r["event"], "truth": r["truth"],
                          "a": r["f"]["a"], "prr": r["f"]["prr"], "ror_lo": r["f"]["ror_lo"], "ic025": r["f"]["ic025"],
                          "evans": r["f"]["evans"], "triple": r["f"]["triple"], "raw_named": round(r["raw_named"], 3),
                          "raw_blind": round(r["raw_blind"], 3), "fv": round(r["fv"], 3), "fv_alt": r["fv_alt"],
                          "dechal": [r["f"]["dechal_pos"], r["f"]["dechal_known"]], "indication": round(r["f"]["indication_overlap"], 3)}
                         for r in rows]
        best = max((m for m in res["methods"] if m["family"] == "metric"), key=lambda m: m["auc"])
        fv = next(m for m in res["methods"] if m["key"] == "fv")
        print(f"{refset}: n={res['n']} pos={res['pos']} | best metric {best['label']} {best['auc']:.3f} | "
              f"raw_blind {next(m['auc'] for m in res['methods'] if m['key'] == 'raw_blind'):.3f} | FV {fv['auc']:.3f} "
              f"| knowledge {next((m['auc'] for m in res['methods'] if m['key'] == 'raw_named'), float('nan')):.3f} | deltas {res['deltas']}")
        print("   evans", res["points"]["evans"], "\n   triple", res["points"]["triple"])

    asof = "2026Q2"
    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M"), "asof": asof, "N": meta["N"],
        "jev": {"calls": len(jobs), "latency_ms_p50": sorted(lat)[len(lat) // 2] if lat else None},
        "refsets": results, "pairs": table,
        "events": {k: {"label": v["label_ko"], "source": v["source"], "pts": v["pts"], "note": v["note"]}
                   for k, v in events.items() if k in set(ev_pairs.event)},
        "sources": [
            {"name": "OMOP reference set (Ryan et al. 2013)", "url": "https://link.springer.com/article/10.1007/s40264-013-0097-8"},
            {"name": "EU-ADR reference set (Coloma et al. 2013)", "url": "https://ohdsi.github.io/MethodEvaluation/reference/euadrReferenceSet.html"},
            {"name": "Time-indexed reference standard (Harpaz et al. 2014)", "url": "https://www.nature.com/articles/sdata201443"},
            {"name": "OMOP negative control misclassification (Hauben et al. 2016)", "url": "https://pubmed.ncbi.nlm.nih.gov/26879560"},
        ],
    }
    (ROOT / "web/public/data/validation.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=float))
    # 다른 스크립트가 더한 항목(sider_evaluate.py 의 sider-pilot, "sider" 키)은 asof 가 같을 때만 남깁니다
    mpath = ROOT / "api/_data/metrics.json"
    old = json.loads(mpath.read_text()) if mpath.exists() else {}
    old = old if old.get("asof") == asof else {}
    metrics = {**old, "asof": asof, "rules": {}}
    for rule in ("evans", "triple"):
        keep = {k: v for k, v in (old.get("rules", {}).get(rule) or {}).items() if k not in results}
        metrics["rules"][rule] = {**{k: {**v["points"][rule], "n": v["n"]} for k, v in results.items()}, **keep}
    mpath.write_text(json.dumps(metrics, indent=1, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--conc", type=int, default=12)
    asyncio.run(main(ap.parse_args()))
