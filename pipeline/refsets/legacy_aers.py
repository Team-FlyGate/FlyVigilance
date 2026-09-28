"""구형 AERS(2004Q1~2012Q3)를 전향적 검증 전용 DuckDB 로 적재합니다.

Harpaz 참조 세트의 양성은 2013년 라벨 변경입니다. 이 DB 는 그 이전에 FDA 에 들어온 보고만 담으므로
"라벨이 바뀌기 전에 보고 통계만으로 잡을 수 있었는가"를 잴 수 있습니다. 주 웨어하우스는 건드리지 않습니다.

- CASE 마다 가장 최근 ISR(최신 FDA_DT, 같으면 큰 ISR) 하나를 남깁니다
- 약물명은 주 웨어하우스의 규칙(norm_drug 매크로)과 학습된 상품명→성분 매핑(ref_drugname_map)으로 정규화합니다
- 평가 코드(evaluate.warehouse)가 그대로 쓰도록 같은 이름의 테이블(sig_triplet, core_case, core_drug ...)을 만듭니다

산출물: data/derived/aers_legacy.duckdb
"""
import pathlib
import re
import shutil
import tempfile
import time
import zipfile

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "data/aers_legacy"
DB = ROOT / "data/derived/aers_legacy.duckdb"
MAIN = ROOT / "data/derived/faers.duckdb"

KEEP = {
    "demo": ["isr", "case", "fda_dt", "occp_cod", "reporter_country"],
    "drug": ["isr", "drug_seq", "role_cod", "drugname", "dechal", "rechal"],
    "reac": ["isr", "pt"],
    "outc": ["isr", "outc_cod"],
    "indi": ["isr", "drug_seq", "indi_pt"],
}


def to_utf8(path: pathlib.Path):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    path.write_text(text.replace("\x00", ""), encoding="utf-8")


def main():
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    for t, cols in KEEP.items():
        con.execute(f"CREATE TABLE l_{t} ({', '.join(chr(34) + c + chr(34) + ' VARCHAR' for c in cols)}, quarter VARCHAR)")
    for z in sorted(SRC.glob("aers_ascii_*.zip")):
        m = re.search(r"(\d{4})q([1-4])", z.name)
        q = f"{m.group(1)}Q{m.group(2)}"
        t0 = time.time()
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="aers_"))
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(tmp, [n for n in zf.namelist() if n.lower().endswith(".txt")])
            files = {p.name.lower(): p for p in tmp.rglob("*") if p.suffix.lower() == ".txt"}
            for t, keep in KEEP.items():
                path = next((p for n, p in files.items() if n.startswith(t)), None)
                if path is None:
                    continue
                to_utf8(path)
                with open(path, encoding="utf-8") as fh:
                    header = [c.strip().lower() for c in fh.readline().rstrip("\r\n").split("$")]
                types = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in header) + "}"
                select = ", ".join(f'"{c}"' if c in header else f'NULL AS "{c}"' for c in keep)
                con.execute(f"""INSERT INTO l_{t} SELECT {select}, '{q}' FROM read_csv('{path}', delim='$', quote='', escape='',
                                header=false, skip=1, columns={types}, ignore_errors=true, null_padding=true, strict_mode=false)
                                WHERE isr IS NOT NULL AND isr <> ''""")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print(f"{q} loaded in {time.time() - t0:.1f}s", flush=True)

    sql = (ROOT / "pipeline/faers/model.sql").read_text()
    i, j = sql.index("CREATE OR REPLACE MACRO norm_drug0"), sql.index("-- 2014Q3")
    con.execute(sql[i:j])
    con.execute(f"ATTACH '{MAIN}' AS main_db (READ_ONLY)")
    con.execute("CREATE TABLE ref_map AS SELECT drugname, ai FROM main_db.ref_drugname_map")
    con.execute("DETACH main_db")
    t0 = time.time()
    con.execute("""
        CREATE TABLE core_case AS
        SELECT primaryid, caseid, quarter, occp_cod, reporter_country FROM (
          SELECT TRY_CAST(isr AS BIGINT) AS primaryid, TRY_CAST("case" AS BIGINT) AS caseid, quarter,
                 NULLIF(occp_cod, '') AS occp_cod, NULLIF(reporter_country, '') AS reporter_country,
                 row_number() OVER (PARTITION BY "case" ORDER BY fda_dt DESC NULLS LAST, TRY_CAST(isr AS BIGINT) DESC) AS rn
          FROM l_demo WHERE TRY_CAST(isr AS BIGINT) IS NOT NULL) WHERE rn = 1""")
    con.execute("""
        CREATE TABLE core_drug AS
        SELECT TRY_CAST(d.isr AS BIGINT) AS primaryid, TRY_CAST(d.drug_seq AS BIGINT) AS drug_seq, d.role_cod,
               regexp_replace(COALESCE(m.ai, norm_drug(NULL, d.drugname)), '-[A-Z]{4}$', '') AS drug,
               NULLIF(d.dechal, '') AS dechal, NULLIF(d.rechal, '') AS rechal
        FROM l_drug d JOIN core_case c ON c.primaryid = TRY_CAST(d.isr AS BIGINT)
        LEFT JOIN ref_map m ON m.drugname = upper(trim(d.drugname))""")
    con.execute("""CREATE TABLE core_reac AS SELECT DISTINCT TRY_CAST(r.isr AS BIGINT) AS primaryid, lower(trim(r.pt)) AS pt
                   FROM l_reac r JOIN core_case c ON c.primaryid = TRY_CAST(r.isr AS BIGINT) WHERE trim(r.pt) <> ''""")
    con.execute("""CREATE TABLE core_case_serious AS SELECT TRY_CAST(o.isr AS BIGINT) AS primaryid, bool_or(trim(o.outc_cod) = 'DE') AS death
                   FROM l_outc o JOIN core_case c ON c.primaryid = TRY_CAST(o.isr AS BIGINT) GROUP BY 1""")
    con.execute("""CREATE TABLE core_indi AS SELECT DISTINCT TRY_CAST(i.isr AS BIGINT) AS primaryid, TRY_CAST(i.drug_seq AS BIGINT) AS drug_seq,
                   lower(trim(i.indi_pt)) AS indi_pt FROM l_indi i JOIN core_case c ON c.primaryid = TRY_CAST(i.isr AS BIGINT)""")
    con.execute("""CREATE TABLE sig_triplet AS SELECT DISTINCT d.primaryid, d.drug, r.pt FROM core_drug d JOIN core_reac r USING (primaryid)
                   WHERE d.role_cod IN ('PS', 'SS') AND d.drug IS NOT NULL""")
    con.execute("CREATE TABLE sig_drug_n AS SELECT drug, count(DISTINCT primaryid) AS n_drug FROM sig_triplet GROUP BY 1")
    con.execute("CREATE TABLE sig_pt_n AS SELECT pt, count(DISTINCT primaryid) AS n_pt FROM sig_triplet GROUP BY 1")
    for t in ["l_demo", "l_drug", "l_reac", "l_outc", "l_indi"]:
        con.execute(f"DROP TABLE {t}")
    n = con.execute("SELECT count(*), min(quarter), max(quarter) FROM core_case").fetchone()
    print(f"model {time.time() - t0:.1f}s · cases {n[0]:,} ({n[1]}–{n[2]}) · triplets "
          f"{con.execute('SELECT count(*) FROM sig_triplet').fetchone()[0]:,}")
    con.close()


if __name__ == "__main__":
    main()
