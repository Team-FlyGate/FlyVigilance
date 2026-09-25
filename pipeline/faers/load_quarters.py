"""FAERS 분기 zip 을 DuckDB 원천 계층(raw_*)으로 증분 적재한다.

- 분기마다 다른 컬럼명(gndr_cod->sex, lot_nbr->lot_num, BOM)을 정규화한다
- 이미 적재한 분기는 건너뛴다 (etl_quarter 테이블로 추적)
- 원문은 latin-1 로 읽고 $ 구분, 따옴표 없음으로 처리한다

사용: .venv/bin/python pipeline/faers/load_quarters.py [--only 2026q2 ...]
"""
import argparse
import pathlib
import re
import shutil
import tempfile
import time
import zipfile

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data/faers/raw"
DB = ROOT / "data/derived/faers.duckdb"

RENAME = {"gndr_cod": "sex", "lot_nbr": "lot_num"}

TABLES = {
    "demo": ["primaryid", "caseid", "caseversion", "i_f_code", "event_dt", "init_fda_dt", "fda_dt",
             "rept_cod", "mfr_sndr", "age", "age_cod", "sex", "wt", "wt_cod", "occp_cod",
             "reporter_country", "occr_country"],
    "drug": ["primaryid", "caseid", "drug_seq", "role_cod", "drugname", "prod_ai", "route",
             "dechal", "rechal", "dose_amt", "dose_unit", "dose_freq"],
    "reac": ["primaryid", "pt", "drug_rec_act"],
    "outc": ["primaryid", "outc_cod"],
    "indi": ["primaryid", "indi_drug_seq", "indi_pt"],
    "ther": ["primaryid", "dsg_drug_seq", "start_dt", "end_dt"],
    "rpsr": ["primaryid", "rpsr_cod"],
}


def quarter_of(zip_path):
    m = re.search(r"(\d{4})q([1-4])", zip_path.name.lower())
    return f"{m.group(1)}Q{m.group(2)}"


def to_utf8(path):
    """분기마다 섞여 있는 UTF-8(BOM)과 latin-1 을 UTF-8 로 맞춘다."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    path.write_text(text.replace("\x00", ""), encoding="utf-8")


def header_cols(path):
    with open(path, "rb") as fh:
        line = fh.readline().decode("latin-1")
    cols = [c.strip().lstrip("﻿").lstrip("ï»¿").lower() for c in line.rstrip("\r\n").split("$")]
    return [RENAME.get(c, c) for c in cols]


def init(con):
    for t, cols in TABLES.items():
        col_sql = ", ".join(f"{c} VARCHAR" for c in cols)
        con.execute(f"CREATE TABLE IF NOT EXISTS raw_{t} ({col_sql}, quarter VARCHAR)")
    con.execute("CREATE TABLE IF NOT EXISTS raw_deleted (caseid VARCHAR, quarter VARCHAR)")
    con.execute("""CREATE TABLE IF NOT EXISTS etl_quarter (
        quarter VARCHAR PRIMARY KEY, source_file VARCHAR, loaded_at TIMESTAMP,
        seconds DOUBLE, demo_rows BIGINT, drug_rows BIGINT, reac_rows BIGINT)""")


def load_zip(con, zpath):
    q = quarter_of(zpath)
    t0 = time.time()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="faers_"))
    try:
        with zipfile.ZipFile(zpath) as z:
            members = [m for m in z.namelist() if m.lower().endswith(".txt")]
            z.extractall(tmp, members)
        files = {p.name.lower(): p for p in tmp.rglob("*.txt")}
        counts = {}
        for t, keep in TABLES.items():
            path = next((p for n, p in files.items() if n.startswith(t) and "delete" not in n), None)
            if path is None:
                continue
            to_utf8(path)
            cols = header_cols(path)
            types = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in cols) + "}"
            select = ", ".join(c if c in cols else f"NULL AS {c}" for c in keep)
            con.execute(f"""
                INSERT INTO raw_{t}
                SELECT {select}, '{q}' FROM read_csv('{path}', delim='$', quote='', escape='',
                    header=false, skip=1, columns={types},
                    ignore_errors=true, null_padding=true, strict_mode=false)
                WHERE primaryid IS NOT NULL AND primaryid <> ''
            """)
            counts[t] = con.execute(f"SELECT count(*) FROM raw_{t} WHERE quarter='{q}'").fetchone()[0]
        dele = next((p for n, p in files.items() if "delete" in n), None)
        if dele is not None:
            to_utf8(dele)
            con.execute(f"""INSERT INTO raw_deleted
                SELECT trim(column0), '{q}' FROM read_csv('{dele}', header=false, delim='$',
                    columns={{'column0':'VARCHAR'}}, ignore_errors=true)
                WHERE trim(column0) <> ''""")
        con.execute("INSERT INTO etl_quarter VALUES (?, ?, now(), ?, ?, ?, ?)",
                    [q, zpath.name, time.time() - t0, counts.get("demo"), counts.get("drug"), counts.get("reac")])
        print(f"{q}: demo {counts.get('demo'):,} drug {counts.get('drug'):,} reac {counts.get('reac'):,} "
              f"({time.time() - t0:.1f}s)", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    init(con)
    done = {r[0] for r in con.execute("SELECT quarter FROM etl_quarter").fetchall()}
    for z in sorted(RAW.glob("faers_ascii_*.zip")):
        q = quarter_of(z)
        if q in done or (args.only and q.lower() not in [o.lower() for o in args.only]):
            continue
        try:
            zipfile.ZipFile(z).testzip()
        except Exception as e:  # 받는 중이거나 깨진 파일
            print(f"skip {z.name}: {e}")
            continue
        con.begin()
        try:
            load_zip(con, z)
            con.commit()
        except Exception:
            con.rollback()
            raise
    con.close()


if __name__ == "__main__":
    main()
