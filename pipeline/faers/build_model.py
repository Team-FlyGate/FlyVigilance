"""model.sql 을 실행하고 API 와 대시보드가 읽을 산출물을 내보낸다.

api/_data/signals.json.gz          약물별 상위 반응 불균형 지표 (API 근거 도구)
api/_data/cases.json.gz            최신 분기 실제 케이스 층화 표본 (트리아지 데모, 벤치마크)
web/public/data/faers/overview.json 웨어하우스 규모, 분기 추이, 품질 지표, 분포
web/public/data/faers/backtest.json 규제 조치 사례의 누적 분기별 신호 궤적 (신호 타임머신)
web/public/data/faers/schema.json   계층별 테이블, 행 수, 컬럼
"""
import gzip
import json
import math
import pathlib
import time

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[2]
DB = ROOT / "data/derived/faers.duckdb"
API_DATA = ROOT / "api/_data"
WEB = ROOT / "web/public/data/faers"
API_DATA.mkdir(parents=True, exist_ok=True)
WEB.mkdir(parents=True, exist_ok=True)

# 규제 조치 날짜는 FDA Drug Safety Communication 공개일 기준
WATCHLIST = [
    {"drug": "CANAGLIFLOZIN", "pt": "diabetic ketoacidosis", "action": "2015-05-15",
     "what": "FDA Drug Safety Communication: SGLT2 inhibitors may cause ketoacidosis"},
    {"drug": "LEVOFLOXACIN", "pt": "aortic aneurysm", "action": "2018-12-20",
     "what": "FDA Drug Safety Communication: fluoroquinolones and aortic aneurysm/dissection"},
    {"drug": "CIPROFLOXACIN", "pt": "aortic dissection", "action": "2018-12-20",
     "what": "FDA Drug Safety Communication: fluoroquinolones and aortic aneurysm/dissection"},
    {"drug": "TOFACITINIB", "pt": "pulmonary embolism", "action": "2019-02-25",
     "what": "FDA Drug Safety Communication: pulmonary embolism with tofacitinib 10 mg twice daily",
     "note": "분기 누적 불균형 분석으로는 기준(PRR≥2)을 넘지 못했다. FDA 조치 근거는 무작위 임상시험(ORAL Surveillance) 중간 결과였다. 자발적 보고 통계만으로는 못 잡는 신호가 있다는 사례다."},
    {"drug": "DOLUTEGRAVIR", "pt": "neural tube defect", "action": "2018-05-18",
     "what": "FDA Drug Safety Communication: neural tube defects with dolutegravir at conception"},
    {"drug": "PREGABALIN", "pt": "respiratory depression", "action": "2019-12-19",
     "what": "FDA Drug Safety Communication: serious breathing difficulties with gabapentinoids"},
    {"drug": "GABAPENTIN", "pt": "respiratory depression", "action": "2019-12-19",
     "what": "FDA Drug Safety Communication: serious breathing difficulties with gabapentinoids"},
    {"drug": "MONTELUKAST", "pt": "suicidal ideation", "action": "2020-03-04",
     "what": "FDA Boxed Warning: serious neuropsychiatric events with montelukast"},
    {"drug": "METFORMIN", "pt": "lactic acidosis", "action": None,
     "what": "Positive control: boxed warning long before the warehouse window"},
]


def q2date(q):
    y, n = int(q[:4]), int(q[-1])
    return f"{y}-{3 * n:02d}-{[31, 30, 30, 31][n - 1]}"


def clean(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def export_signals(con):
    asof = con.execute("SELECT max(quarter) FROM etl_quarter").fetchone()[0]
    N = con.execute("SELECT count(DISTINCT primaryid) FROM sig_triplet").fetchone()[0]
    rows = con.execute("""
        WITH top_drugs AS (SELECT drug FROM sig_drug_n WHERE n_drug >= 200 ORDER BY n_drug DESC LIMIT 4000),
        ranked AS (
          SELECT s.*, row_number() OVER (PARTITION BY s.drug ORDER BY s.a DESC) AS r
          FROM sig_signal s JOIN top_drugs USING (drug))
        SELECT drug, pt, a, round(expected, 2), round(prr, 3), round(prr_lo, 3), round(prr_hi, 3),
               round(ror, 3), round(ror_lo, 3), round(ror_hi, 3), round(chi2_yates, 1), round(ic, 3), round(ic025, 3),
               evans_signal, ror_signal, ic_signal
        FROM ranked WHERE r <= 80 ORDER BY drug, a DESC
    """).fetchall()
    cols = ["pt", "a", "expected", "prr", "prr_lo", "prr_hi", "ror", "ror_lo", "ror_hi", "chi2", "ic", "ic025",
            "evans", "ror_sig", "ic_sig"]
    drugs = {}
    for r in rows:
        drugs.setdefault(r[0], []).append([clean(x) for x in r[1:]])
    n_drug = dict(con.execute("SELECT drug, n_drug FROM sig_drug_n WHERE n_drug >= 200").fetchall())
    out = {"asof": asof, "N": N, "columns": cols, "drugs": drugs, "n_drug": {d: n_drug[d] for d in drugs}}
    with gzip.open(API_DATA / "signals.json.gz", "wt") as f:
        json.dump(out, f, separators=(",", ":"))
    # 대시보드용 약물 목록
    (WEB / "drugs.json").write_text(json.dumps(sorted(({"drug": d, "n": n_drug[d]} for d in drugs),
                                                      key=lambda x: -x["n"]), separators=(",", ":")))
    print(f"signals: {len(drugs)} drugs, {len(rows):,} rows, asof {asof}, N={N:,}")
    return asof


def export_cases(con, asof):
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE sample_pid AS
        WITH base AS (
          SELECT c.primaryid, c.occp_cod,
                 coalesce(s.death, false) AS death,
                 (s.primaryid IS NOT NULL) AS serious,
                 c.age_years
          FROM core_case c LEFT JOIN core_case_serious s USING (primaryid)
          WHERE c.quarter = '{asof}'
            AND EXISTS (SELECT 1 FROM core_drug d WHERE d.primaryid = c.primaryid AND d.role_cod = 'PS' AND d.drug IS NOT NULL)
            AND EXISTS (SELECT 1 FROM core_reac r WHERE r.primaryid = c.primaryid)
        )
        SELECT primaryid, 'death' AS bucket FROM (SELECT * FROM (SELECT * FROM base WHERE death) USING SAMPLE 60 ROWS (reservoir, 7))
        UNION ALL SELECT primaryid, 'serious' FROM (SELECT * FROM (SELECT * FROM base WHERE serious AND NOT death) USING SAMPLE 170 ROWS (reservoir, 7))
        UNION ALL SELECT primaryid, 'nonserious' FROM (SELECT * FROM (SELECT * FROM base WHERE NOT serious) USING SAMPLE 170 ROWS (reservoir, 7))
        UNION ALL SELECT primaryid, 'pediatric' FROM (SELECT * FROM (SELECT * FROM base WHERE age_years < 12) USING SAMPLE 40 ROWS (reservoir, 7))
    """)
    demo = con.execute("""
        SELECT c.primaryid, c.caseid, c.quarter, c.fda_dt::VARCHAR, c.age_years, c.sex, c.weight_kg, c.occp_cod,
               c.reporter_country, c.rept_cod, sp.bucket
        FROM core_case c JOIN sample_pid sp USING (primaryid)""").fetchall()
    drugs = con.execute("""
        SELECT d.primaryid, d.drug_seq, d.role_cod, d.drug, d.route, d.dechal, d.rechal, i.indi_pt
        FROM core_drug d JOIN sample_pid USING (primaryid)
        LEFT JOIN core_indi i ON i.primaryid = d.primaryid AND i.drug_seq = d.drug_seq
        WHERE d.drug IS NOT NULL
        ORDER BY d.primaryid, CASE d.role_cod WHEN 'PS' THEN 0 WHEN 'SS' THEN 1 WHEN 'I' THEN 2 ELSE 3 END, d.drug_seq""").fetchall()
    reacs = con.execute("SELECT r.primaryid, r.pt FROM core_reac r JOIN sample_pid USING (primaryid)").fetchall()
    outs = con.execute("SELECT o.primaryid, o.outc_cod FROM core_outc o JOIN sample_pid USING (primaryid)").fetchall()
    D, R, O = {}, {}, {}
    for pid, seq, role, drug, route, de, re_, ind in drugs:
        lst = D.setdefault(pid, [])
        if any(x["drug"] == drug for x in lst):
            continue
        lst.append({"drug": drug, "role": role, "route": route, "dechal": de, "rechal": re_, "indication": ind})
    for pid, pt in reacs:
        R.setdefault(pid, []).append(pt)
    for pid, oc in outs:
        O.setdefault(pid, []).append(oc)
    cases = []
    for pid, cid, qtr, fdt, age, sex, wt, occp, ctry, rept, bucket in demo:
        cases.append({"primaryid": pid, "caseid": cid, "quarter": qtr, "fda_dt": fdt,
                      "age": round(age, 1) if age is not None and age < 120 else None, "sex": sex,
                      "weight": round(wt, 1) if wt else None, "occp_cod": occp, "country": ctry, "rept_cod": rept,
                      "bucket": bucket, "drugs": D.get(pid, [])[:10], "reactions": sorted(R.get(pid, []))[:15],
                      "outcomes": sorted(O.get(pid, []))})
    cases.sort(key=lambda c: (c["bucket"], c["primaryid"]))
    with gzip.open(API_DATA / "cases.json.gz", "wt") as f:
        json.dump(cases, f, separators=(",", ":"))
    print(f"cases: {len(cases)}")


def export_overview(con):
    one = lambda sql: con.execute(sql).fetchone()[0]
    ov = {
        "asof": one("SELECT max(quarter) FROM etl_quarter"),
        "first": one("SELECT min(quarter) FROM etl_quarter"),
        "quarters": one("SELECT count(*) FROM etl_quarter"),
        "raw_reports": one("SELECT count(*) FROM raw_demo"),
        "raw_drug_rows": one("SELECT count(*) FROM raw_drug"),
        "raw_reac_rows": one("SELECT count(*) FROM raw_reac"),
        "versions": one("SELECT count(*) FROM core_case_version"),
        "cases": one("SELECT count(*) FROM core_case"),
        "deleted_cases": one("SELECT count(*) FROM core_deleted"),
        "distinct_caseids": one("SELECT count(DISTINCT caseid) FROM core_case_version"),
        "drug_names_raw": one("SELECT count(DISTINCT drugname_raw) FROM core_drug"),
        "drug_names_norm": one("SELECT count(DISTINCT drug) FROM core_drug"),
        "drugname_map": one("SELECT count(*) FROM ref_drugname_map"),
        "pts": one("SELECT count(DISTINCT pt) FROM core_reac"),
        "triplets": one("SELECT count(*) FROM sig_triplet"),
        "pairs": one("SELECT count(*) FROM sig_signal"),
        "evans": one("SELECT count(*) FROM sig_signal WHERE evans_signal"),
        "ror_sig": one("SELECT count(*) FROM sig_signal WHERE ror_signal"),
        "ic_sig": one("SELECT count(*) FROM sig_signal WHERE ic_signal"),
        "all3": one("SELECT count(*) FROM sig_signal WHERE evans_signal AND ror_signal AND ic_signal"),
        "serious_cases": one("SELECT count(*) FROM core_case_serious"),
        "death_cases": one("SELECT count(*) FROM core_case_serious WHERE death"),
    }
    ov["per_quarter"] = [dict(zip(["quarter", "reports", "cases", "initial", "followups", "expedited", "periodic", "direct"], r))
                         for r in con.execute("SELECT * FROM ops_quarter").fetchall()]
    ov["etl"] = [dict(zip(["quarter", "seconds", "demo", "drug", "reac"], r)) for r in
                 con.execute("SELECT quarter, round(seconds,2), demo_rows, drug_rows, reac_rows FROM etl_quarter ORDER BY quarter").fetchall()]
    ov["outcomes"] = dict(con.execute("SELECT outc_cod, count(*) FROM core_outc GROUP BY 1 ORDER BY 2 DESC").fetchall())
    ov["reporters"] = dict(con.execute("SELECT coalesce(occp_cod,'NA'), count(*) FROM core_case GROUP BY 1 ORDER BY 2 DESC LIMIT 8").fetchall())
    ov["countries"] = con.execute("SELECT reporter_country, count(*) FROM core_case WHERE reporter_country IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 15").fetchall()
    ov["sex"] = dict(con.execute("SELECT coalesce(sex,'NA'), count(*) FROM core_case GROUP BY 1").fetchall())
    ov["age_bins"] = con.execute("""SELECT CAST(floor(least(age_years, 99)/10)*10 AS INT) AS b, count(*) FROM core_case
                                     WHERE age_years BETWEEN 0 AND 120 GROUP BY 1 ORDER BY 1""").fetchall()
    ov["top_drugs"] = con.execute("SELECT drug, n_drug FROM sig_drug_n ORDER BY n_drug DESC LIMIT 25").fetchall()
    ov["top_pts"] = con.execute("SELECT pt, n_pt FROM sig_pt_n ORDER BY n_pt DESC LIMIT 25").fetchall()
    ov["top_signals"] = [dict(zip(["drug", "pt", "a", "prr", "ror_lo", "ic025"], r)) for r in con.execute("""
        SELECT drug, pt, a, round(prr,2), round(ror_lo,2), round(ic025,2) FROM sig_signal
        WHERE evans_signal AND ror_signal AND ic_signal AND a >= 200
        ORDER BY ic025 DESC LIMIT 60""").fetchall()]
    # 최신 분기 케이스 기준 복잡도 분포 (트리아지 부하)
    asof = ov["asof"]
    ov["latest"] = {
        "cases": one(f"SELECT count(*) FROM core_case WHERE quarter='{asof}'"),
        "serious": one(f"SELECT count(*) FROM core_case c JOIN core_case_serious USING (primaryid) WHERE c.quarter='{asof}'"),
        "death": one(f"SELECT count(*) FROM core_case c JOIN core_case_serious s USING (primaryid) WHERE c.quarter='{asof}' AND s.death"),
        "expedited": one(f"SELECT count(*) FROM core_case WHERE quarter='{asof}' AND rept_cod='EXP'"),
    }
    (WEB / "overview.json").write_text(json.dumps(ov, default=str, separators=(",", ":")))
    print("overview:", {k: v for k, v in ov.items() if not isinstance(v, (list, dict))})


def export_backtest(con):
    con.execute("""
        CREATE OR REPLACE TEMP TABLE first_q AS
        SELECT caseid, min(quarter) AS fq FROM core_case_version GROUP BY caseid""")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE tq AS
        SELECT t.drug, t.pt, t.primaryid, f.fq FROM sig_triplet t
        JOIN core_case c USING (primaryid) JOIN first_q f ON f.caseid = c.caseid""")
    quarters = [r[0] for r in con.execute("SELECT quarter FROM etl_quarter ORDER BY quarter").fetchall()]
    N_q = dict(con.execute("SELECT fq, count(DISTINCT primaryid) FROM tq GROUP BY 1").fetchall())
    out = []
    for w in WATCHLIST:
        d, p = w["drug"], w["pt"]
        a_q = dict(con.execute("SELECT fq, count(DISTINCT primaryid) FROM tq WHERE drug=? AND pt=? GROUP BY 1", [d, p]).fetchall())
        nd_q = dict(con.execute("SELECT fq, count(DISTINCT primaryid) FROM tq WHERE drug=? GROUP BY 1", [d]).fetchall())
        np_q = dict(con.execute("SELECT fq, count(DISTINCT primaryid) FROM tq WHERE pt=? GROUP BY 1", [p]).fetchall())
        A = ND = NP = NN = 0
        series, first = [], None
        for q in quarters:
            A += a_q.get(q, 0); ND += nd_q.get(q, 0); NP += np_q.get(q, 0); NN += N_q.get(q, 0)
            b, c = ND - A, NP - A
            dd = NN - ND - NP + A
            rec = {"q": q, "a": A}
            if A >= 1 and b > 0 and c > 0 and dd > 0:
                prr = (A / (A + b)) / (c / (c + dd))
                chi = NN * max(abs(A * dd - b * c) - NN / 2, 0) ** 2 / ((A + b) * (c + dd) * (A + c) * (b + dd))
                ror = (A * dd) / (b * c)
                ror_lo = math.exp(math.log(ror) - 1.96 * math.sqrt(1 / A + 1 / b + 1 / c + 1 / dd))
                E = ND * NP / NN
                ic025 = math.log2((A + 0.5) / (E + 0.5)) - 3.3 * (A + 0.5) ** -0.5 - 2 * (A + 0.5) ** -1.5
                sig = prr >= 2 and chi >= 4 and A >= 3 and ror_lo > 1 and ic025 > 0
                rec.update({"prr": round(prr, 2), "ror_lo": round(ror_lo, 2), "ic025": round(ic025, 2), "chi2": round(chi, 1),
                            "signal": sig})
                if sig and first is None:
                    first = q
            series.append(rec)
        lead_days = None
        if first and w["action"]:
            from datetime import date
            lead_days = (date.fromisoformat(w["action"]) - date.fromisoformat(q2date(first))).days
        out.append({**w, "first_signal_quarter": first, "first_signal_date": q2date(first) if first else None,
                    "lead_days": lead_days, "left_censored": first == quarters[0], "series": series})
        print(f"backtest {d} / {p}: first {first}, lead {lead_days} d")
    (WEB / "backtest.json").write_text(json.dumps({"quarters": quarters, "items": out,
                                                   "criteria": "PRR>=2, chi2>=4, a>=3 (Evans) AND ROR025>1 AND IC025>0, cumulative by first-received quarter"},
                                                  separators=(",", ":")))


def export_schema(con):
    layers = {"raw": "원천 (분기 원문 그대로, VARCHAR)", "core": "정제 (중복제거, 정규화, 타입)",
              "ref": "참조 (학습된 매핑)", "sig": "신호 (불균형 분석)", "ops": "운영 지표", "etl": "적재 감사"}
    tables = []
    for (name,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name").fetchall():
        cols = con.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{name}' ORDER BY ordinal_position").fetchall()
        rows = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        tables.append({"name": name, "layer": name.split("_")[0], "rows": rows, "columns": [{"name": c, "type": t} for c, t in cols]})
    size = DB.stat().st_size
    (WEB / "schema.json").write_text(json.dumps({"layers": layers, "tables": tables, "db_bytes": size}, separators=(",", ":")))
    print(f"schema: {len(tables)} tables, db {size/1e9:.2f} GB")


def main():
    con = duckdb.connect(str(DB))
    t0 = time.time()
    con.execute((pathlib.Path(__file__).parent / "model.sql").read_text())
    print(f"model built in {time.time() - t0:.1f}s")
    asof = export_signals(con)
    export_cases(con, asof)
    export_overview(con)
    export_backtest(con)
    export_schema(con)


if __name__ == "__main__":
    main()
