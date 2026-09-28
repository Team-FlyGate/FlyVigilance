"""보고자 구성(변호사·소비자·의료인)으로 보고 편향이 의심되는 약물-반응 쌍을 표시합니다.

약사 검토 의견: 이소트레티노인-염증성장질환은 FAERS 보고의 대부분이 변호사 보고였습니다. PRR 이 크다고 근거가
단단한 것은 아닙니다. 그래서 웹 추출본(api/_data/signals.json.gz)의 쌍마다 보고자 구성을 계산해, 두 가지 표시를 붙입니다.

- flag_lw (변호사 보고 주도): 변호사 보고 비율 >= 20%, FAERS 배경 비율의 5배 이상, 변호사 보고 10건 이상
- flag_cn (소비자 보고 편중): 20건 이상, 소비자 보고 >= 90%, 같은 약 전체의 소비자 비율보다 30%p 이상 높음

표시된 쌍은 변호사 보고를 뺀 경우와 의료인 보고만 남긴 경우로 불균형 지표를 다시 계산합니다(민감도 분석).
표시는 등급을 자동으로 내리지 않습니다. 보고 편향 '의심'을 근거와 함께 보여 줄 뿐입니다.

사용: .venv/bin/python pipeline/faers/export_reporter_mix.py
입력: data/derived/faers.duckdb(읽기 전용), api/_data/signals.json.gz
산출물: api/_data/reporter_mix.json.gz
"""
import gzip
import json
import pathlib
import time

import duckdb
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
SQL = pathlib.Path(__file__).parent / "sql"
OUT = ROOT / "api/_data/reporter_mix.json.gz"


def run_sql(con, path: pathlib.Path):
    for st in path.read_text().split(";"):
        if any(ln.strip() and not ln.strip().startswith("--") for ln in st.splitlines()):
            con.execute(st)


def main():
    t0 = time.perf_counter()
    s = json.load(gzip.open(ROOT / "api/_data/signals.json.gz", "rt"))
    cols = s["columns"]
    rec = []
    for drug, rows in s["drugs"].items():
        for r in rows:
            d = dict(zip(cols, r))
            rec.append({"drug": drug, "pt": d["pt"], "a_extract": d["a"], "prr": d["prr"], "ror_lo": d["ror_lo"],
                        "ic025": d["ic025"], "evans": d["evans"], "ror_sig": d["ror_sig"], "ic_sig": d["ic_sig"]})
    con = duckdb.connect(str(ROOT / "data/derived/faers.duckdb"), read_only=True)
    con.register("pairs_df", pd.DataFrame(rec))
    con.execute("CREATE TEMP TABLE pairs AS SELECT * FROM pairs_df")
    run_sql(con, SQL / "reporter_mix.sql")
    run_sql(con, SQL / "reporter_sensitivity.sql")
    bg = con.execute("SELECT n, lw, cn, hcp FROM bg").fetchone()
    rows = con.execute("""
        SELECT m.drug, m.pt, m.a, m.n_lw, m.n_cn, m.n_hcp, m.drug_lw_share, m.drug_cn_share, m.flag_lw, m.flag_cn,
               s.a_nolw, s.prr_nolw, s.ror_lo_nolw, s.ic025_nolw, s.chi2_nolw,
               h.a_hcp, h.prr_hcp, h.ror_lo_hcp, h.ic025_hcp, h.chi2_hcp
        FROM mix m LEFT JOIN sens s USING (drug, pt) LEFT JOIN sens_hcp h USING (drug, pt)
        WHERE m.flag_lw OR m.flag_cn ORDER BY m.drug, m.a DESC""").fetchall()

    def strong(a, prr, chi2, ror_lo, ic025):
        return bool(a is not None and a >= 3 and (prr or 0) >= 2 and (chi2 or 0) >= 4 and (ror_lo or 0) > 1 and (ic025 or -9) > 0)

    r4 = lambda x: None if x is None else round(float(x), 4)
    pairs: dict[str, dict] = {}
    for (drug, pt, a, n_lw, n_cn, n_hcp, dlw, dcn, flw, fcn, a0, prr0, ror0, ic0, chi0, ah, prrh, rorh, ich, chih) in rows:
        pairs.setdefault(drug, {})[pt] = {
            "a": a, "n_lw": n_lw, "n_cn": n_cn, "n_hcp": n_hcp, "drug_lw_share": r4(dlw), "drug_cn_share": r4(dcn),
            "flag_lw": bool(flw), "flag_cn": bool(fcn),
            "no_lawyer": {"a": a0, "prr": r4(prr0), "ic025": r4(ic0), "sdr": strong(a0, prr0, chi0, ror0, ic0)},
            "hcp_only": {"a": ah, "prr": r4(prrh), "ic025": r4(ich), "sdr": strong(ah, prrh, chih, rorh, ich)},
        }
    out = {"asof": s["asof"], "N": s["N"], "generated": time.strftime("%Y-%m-%d %H:%M"),
           "background": {"n": bg[0], "lw": round(bg[1], 4), "cn": round(bg[2], 4), "hcp": round(bg[3], 4)},
           "rules": {"flag_lw": "lawyer share >= 0.20 and >= 5x background and >= 10 lawyer reports",
                     "flag_cn": "a >= 20 and consumer share >= 0.90 and >= 0.30 above the drug's own consumer share"},
           "n_flag_lw": sum(1 for d in pairs.values() for v in d.values() if v["flag_lw"]),
           "n_flag_cn": sum(1 for d in pairs.values() for v in d.values() if v["flag_cn"]),
           "pairs": pairs}
    with gzip.open(OUT, "wt") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"background LW {bg[1]:.2%} CN {bg[2]:.2%} HCP {bg[3]:.2%}; flag_lw {out['n_flag_lw']} flag_cn {out['n_flag_cn']} "
          f"-> {OUT} ({OUT.stat().st_size / 1024:.0f} KB, {time.perf_counter() - t0:.1f}s)")


if __name__ == "__main__":
    main()
