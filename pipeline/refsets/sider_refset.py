"""SIDER 4.1 라벨과 FAERS 웨어하우스로 SIDER 파일럿 참조 세트를 만듭니다.

OMOP·EU-ADR·Harpaz 세트(build_refsets.py)는 쌍이 수백 개라 고정 문턱의 민감도·특이도를 넓게 재기 어렵습니다.
이 스크립트는 약 30여 종, 쌍 수만 개 규모의 참조 세트를 SIDER 라벨에서 만듭니다.
양성은 "라벨 기재"이고 인과성이 확정된 쌍이 아닙니다. 음성은 "라벨 부재"이고 "일어나지 않음"이 아닙니다.

규칙
- 약 매칭: drug_names.tsv 이름 가운데 여러 STITCH flat ID 가 나눠 쓰는 이름(대문자로 바꿔 비교)을 빼고,
  남은 이름을 대문자로 바꿔 웨어하우스 sig_drug_n.drug 와 정확히 맞춥니다. 뺀 수와 맞지 않은 수를 남깁니다.
- 약 선정: 맞은 약 가운데 n_drug(PS/SS 의심약 사례 수) 상위 N 종(동률은 성분명 순)과 손 선정 약의 합집합입니다.
  손 선정 약이 매칭에서 빠졌으면 빠졌다고 적습니다.
- 양성: 그 약의 SIDER PT(meddra_all_se 4열이 PT 인 행) 가운데 웨어하우스 sig_signal 에 행이 있는 쌍입니다.
  sig_signal 은 a>=3 인 쌍만 담으므로 a>=3 이 함께 성립합니다. 웨어하우스 행이 없어 빠진 양성 수를 남깁니다.
- 음성: 같은 약의 sig_signal PT 가운데 그 약의 SIDER 목록에 없고 SIDER 전체 PT 우주에는 있는 것 전부입니다.
  비교는 소문자로 합니다. 우주 밖이라 걸러진 PT(행정·결과 용어 등)의 수와 예시를 남깁니다.
- 귀무 쌍은 저장하지 않습니다. 시드(기본 20260928)와 반복 수만 적고 sider_evaluate.py 가 재생성합니다.

입력
- SIDER 4.1 파일(drug_names.tsv, meddra_all_se.tsv.gz). --download 를 주면 sideeffects.embl.de 에서 curl 로 받고 md5 를 적습니다.
- 웨어하우스 DuckDB(pipeline/faers 가 만든 data/derived/faers.duckdb). 다른 위치는 환경변수 FV_DB 로 줍니다.
  TSV 추출 단계 없이 DuckDB 를 읽기 전용으로 직접 엽니다.

산출물 (build_refsets.py 와 같은 data/derived/refsets/ 아래)
- sider_pairs.json.gz: {"meta": 구성과 출처, "rows": [{drug, pt, class, source}]}. gzip mtime 0 이라 같은 입력이면 같은 바이트입니다.
- sider_metrics.parquet: 참조 행마다 sig_signal 의 2x2 와 지표·신호 플래그. sider_evaluate.py, sider_jev.py,
  omics_plausibility.py 가 이 파일을 읽으므로 웨어하우스 없이도 평가가 돕니다.

사용법:
  .venv/bin/python pipeline/refsets/sider_refset.py --download
  FV_DB=<웨어하우스 경로> .venv/bin/python pipeline/refsets/sider_refset.py --sider-dir <SIDER 폴더>
"""
import argparse
import gzip
import hashlib
import json
import os
import pathlib
import subprocess
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
DB_ENV = "FV_DB"
DB = pathlib.Path(os.environ[DB_ENV]) if os.environ.get(DB_ENV) else ROOT / "data/derived/faers.duckdb"
SIDER_DIR = ROOT / "data/refsets/sider"
OUT = ROOT / "data/derived/refsets"
REFSET = OUT / "sider_pairs.json.gz"
METRICS = OUT / "sider_metrics.parquet"
REFSET_NAME = "sider-pilot"

SIDER_URL = "https://sideeffects.embl.de/media/download"
SIDER_FILES = ("drug_names.tsv", "meddra_all_se.tsv.gz")
# 2026-09-27 에 같은 URL 에서 받은 파일의 md5 입니다. 다르면 경고만 하고 새 값을 메타에 적습니다
SIDER_MD5 = {"drug_names.tsv": "ffec201670bf8599a7a22b2dd811fc89",
             "meddra_all_se.tsv.gz": "e05270a185a67b059466e26549da425e"}
SIDER_RELEASE = "SIDER 4.1 (2015-10-21)"
MEDDRA_VERSION = "16.1"
A_THRESHOLD = 3
DEFAULT_TOP_N = 30
DEFAULT_EXTRA = ["CLOZAPINE", "WARFARIN", "LENALIDOMIDE", "ATORVASTATIN"]
DEFAULT_SEED = 20260928
NULL_REPEATS = 100

# 참조 행에 붙이는 sig_signal 열입니다. 2x2 네 칸은 Jev state 에, 지표는 평가에 씁니다
METRIC_COLS = ["a", "b", "c", "d", "expected", "prr", "prr_lo", "prr_hi", "ror", "ror_lo", "ror_hi",
               "chi2_yates", "ic", "ic025", "evans_signal", "ror_signal", "ic_signal"]

SOURCE_POSITIVE = "sider4.1:label_pt"
SOURCE_NEGATIVE = "sider4.1:label_absent+faers:a>=3"
# 행의 source 는 짧은 꼬리표로 쓰고 풀이는 메타에 한 번만 둡니다. 행이 수만 개라 파일을 줄이려는 것입니다
SOURCES = {
    SOURCE_POSITIVE: "SIDER 4.1 meddra_all_se 4열이 PT 인 행에 있는 쌍(라벨 기재)",
    SOURCE_NEGATIVE: "그 약의 SIDER PT 목록에 없고 SIDER PT 우주에 있으며 웨어하우스 a>=3 인 쌍(라벨 부재)",
}
DRUG_RULE = ("drug_names.tsv 이름 가운데 여러 flat ID 가 나눠 쓰는 이름을 빼고, 대문자로 바꿔 웨어하우스 "
             "sig_drug_n.drug 와 정확히 일치하는 약. 그 가운데 n_drug 상위 {top_n}종(동률은 성분명 순)과 "
             "손 선정 약 {extra} 의 합집합.")
NULL_RULE = ("선정 약 안에서 양성 쌍의 PT 를 약 사이에 뒤섞어 양성과 같은 수의 귀무 쌍을 만듭니다. "
             "시드는 seed+i(i=0..null_repeats-1)입니다. 쌍은 저장하지 않고 sider_evaluate.py 가 재생성합니다.")
SQL = {
    "asof": "SELECT min(quarter), max(quarter), count(*) FROM etl_quarter",
    "drug_n": "SELECT drug, n_drug FROM sig_drug_n",
    "pairs": f"SELECT drug, pt, {', '.join(METRIC_COLS)} FROM sig_signal WHERE drug IN (<선정 약>)",
}


def md5(path: pathlib.Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def display(path: pathlib.Path) -> str:
    """메타에 적을 경로입니다. 저장소 밖 경로는 계정 경로가 남지 않게 파일 이름만 적습니다."""
    path = pathlib.Path(path).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return f"<저장소 밖>/{path.name}"


def download(sider_dir: pathlib.Path) -> None:
    """SIDER 4.1 파일 둘을 curl 로 받습니다. 이미 있으면 건너뜁니다."""
    sider_dir.mkdir(parents=True, exist_ok=True)
    for f in SIDER_FILES:
        dest = sider_dir / f
        if dest.exists():
            continue
        subprocess.run(["curl", "-fsSL", "--http1.1", "-o", str(dest), f"{SIDER_URL}/{f}"], check=True)


def read_sider(sider_dir: pathlib.Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(flat_id, name) 표와 (flat_id, pt) PT 쌍 표를 돌려줍니다. pt 는 소문자입니다."""
    names = pd.read_csv(sider_dir / "drug_names.tsv", sep="\t", header=None,
                        names=["flat_id", "name"], dtype=str, keep_default_na=False)
    se = pd.read_csv(sider_dir / "meddra_all_se.tsv.gz", sep="\t", header=None,
                     names=["flat_id", "stereo_id", "label_umls", "kind", "pt_umls", "term"],
                     dtype=str, keep_default_na=False)
    pt = se.loc[se["kind"] == "PT", ["flat_id", "term"]].copy()
    pt["pt"] = pt["term"].str.lower()
    pt = pt[["flat_id", "pt"]].drop_duplicates().reset_index(drop=True)
    return names, pt


def match_drugs(names: pd.DataFrame, warehouse_drugs: set[str]) -> tuple[dict[str, str], dict]:
    """이름 규칙을 적용해 {웨어하우스 성분명: flat_id} 와 제외 수 일람을 돌려줍니다.

    공유 여부는 대문자로 바꾼 이름으로 가립니다. 대소문자만 다른 두 이름(예 Fe 와 fe)도 같은 성분명에
    떨어져 어느 flat ID 인지 정할 수 없기 때문입니다.
    """
    names = names.assign(key=names["name"].str.upper())
    ids_per_key = names.groupby("key")["flat_id"].nunique()
    shared = set(ids_per_key[ids_per_key > 1].index)
    eligible = sorted(set(ids_per_key.index) - shared)
    first_id = names.drop_duplicates("key").set_index("key")["flat_id"]
    matched = {k: first_id[k] for k in eligible if k in warehouse_drugs}
    unmatched = [k for k in eligible if k not in warehouse_drugs]
    exclusions = {
        "sider_flat_ids": int(names["flat_id"].nunique()),
        "sider_names_case_insensitive": int(len(ids_per_key)),
        "excluded_shared_names": len(shared),
        "excluded_shared_flat_ids": int(names["key"].isin(shared).sum()),
        # 첫 글자 대문자 이름을 빼던 규칙은 일반명(Abarelix 등)까지 빼서 없앴습니다. 이전 결과와 맞대 보려고 0 으로 남깁니다
        "excluded_capitalized_names": 0,
        "eligible_names": len(eligible),
        "unmatched_in_warehouse": len(unmatched),
        "matched_drugs": len(matched),
        "unmatched_examples": unmatched[:15],
    }
    return matched, exclusions


def select_drugs(matched: dict[str, str], drug_n: pd.DataFrame, top_n: int,
                 extra: list[str]) -> tuple[list[dict], list[str]]:
    """보고 수 상위 top_n 과 손 선정 약을 합칩니다. 매칭에 없는 손 선정 약은 두 번째 값으로 돌려줍니다."""
    counts = dict(zip(drug_n["drug"], drug_n["n_drug"].astype(int)))
    ranked = sorted(matched, key=lambda d: (-counts[d], d))
    chosen = {d: "top_n" for d in ranked[:top_n]}
    missing = []
    for d in extra:
        d = d.upper()
        if d not in matched:
            missing.append(d)
        elif d not in chosen:
            chosen[d] = "extra"
    rank = {d: i + 1 for i, d in enumerate(ranked)}
    selected = [{"drug": d, "flat_id": matched[d], "n_drug": counts[d], "rank_among_matched": rank[d], "reason": why}
                for d, why in sorted(chosen.items(), key=lambda kv: rank[kv[0]])]
    return selected, missing


def build_rows(selected: list[dict], sider_pt: pd.DataFrame,
               pairs: pd.DataFrame) -> tuple[list[dict], dict, list[dict]]:
    """양성과 음성 행, 버린 수, 약별 구성을 만듭니다. pairs 는 sig_signal 의 (drug, pt, a) 입니다."""
    universe = set(sider_pt["pt"])
    rows: list[dict] = []
    per_drug = []
    dropped_pos = 0
    outside = Counter()      # 우주 밖 PT 의 a 합계입니다. 예시를 고르는 데 씁니다
    outside_rows = 0
    for s in selected:
        label = set(sider_pt.loc[sider_pt["flat_id"] == s["flat_id"], "pt"])
        wh = pairs.loc[pairs["drug"] == s["drug"], ["pt", "a"]]
        wh_pts = dict(zip(wh["pt"].str.lower(), wh["pt"]))
        pos = sorted(p for p in label if p in wh_pts)
        neg = sorted(p for p in wh_pts if p not in label and p in universe)
        out = [p for p in wh_pts if p not in universe]
        outside_rows += len(out)
        for p, a in zip(wh["pt"].str.lower(), wh["a"]):
            if p not in universe:
                outside[p] += int(a)
        dropped_pos += len(label) - len(pos)
        rows += [{"drug": s["drug"], "pt": wh_pts[p], "class": "positive", "source": SOURCE_POSITIVE} for p in pos]
        rows += [{"drug": s["drug"], "pt": wh_pts[p], "class": "negative", "source": SOURCE_NEGATIVE} for p in neg]
        per_drug.append({**s, "sider_pts": len(label), "warehouse_pts": len(wh_pts),
                         "positive": len(pos), "negative": len(neg),
                         "positive_without_warehouse_row": len(label) - len(pos),
                         "warehouse_pts_outside_universe": len(out)})
    dropped = {
        "sider_positive_without_warehouse_row": dropped_pos,
        "warehouse_pairs_outside_sider_universe": outside_rows,
        "warehouse_pts_outside_sider_universe": len(outside),
        "outside_universe_examples_by_a": [p for p, _ in outside.most_common(15)],
    }
    return rows, dropped, per_drug


def dump_refset(meta: dict, rows: list[dict]) -> str:
    """메타는 들여쓰고 행은 한 줄에 하나씩 씁니다. 행이 수만 개라 diff 와 grep 이 쉬워집니다."""
    body = ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows)
    return '{"meta": ' + json.dumps(meta, ensure_ascii=False, indent=1) + ',\n "rows": [\n' + body + "\n ]}\n"


def read_warehouse(con, drugs: list[str] | None = None) -> tuple[dict, pd.DataFrame, pd.DataFrame | None]:
    """웨어하우스에서 기간, sig_drug_n 전체, 그리고 drugs 가 있으면 그 약들의 sig_signal 행을 읽습니다."""
    first, last, n = con.execute(SQL["asof"]).fetchone()
    drug_n = con.execute(SQL["drug_n"]).df()
    pairs = None
    if drugs is not None:
        con.register("sel_df", pd.DataFrame({"drug": drugs}))
        pairs = con.execute(f"SELECT drug, pt, {', '.join(METRIC_COLS)} FROM sig_signal "
                            "WHERE drug IN (SELECT drug FROM sel_df) ORDER BY drug, pt").df()
    return {"asof": last, "first_quarter": first, "n_quarters": int(n)}, drug_n, pairs


def main(argv: list[str] | None = None, con=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sider-dir", type=pathlib.Path, default=SIDER_DIR)
    ap.add_argument("--download", action="store_true", help="SIDER 파일이 없으면 curl 로 받습니다")
    ap.add_argument("--db", type=pathlib.Path, default=DB, help=f"웨어하우스 DuckDB. 기본은 ${DB_ENV} 또는 data/derived/faers.duckdb")
    ap.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    ap.add_argument("--extra-drugs", nargs="*", default=DEFAULT_EXTRA)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", type=pathlib.Path, default=REFSET)
    ap.add_argument("--metrics-out", type=pathlib.Path, default=METRICS)
    args = ap.parse_args(argv)

    if args.download:
        download(args.sider_dir)
    missing = [f for f in SIDER_FILES if not (args.sider_dir / f).exists()]
    if missing:
        print(f"SIDER 파일이 없습니다: {missing}. --download 를 붙이거나 --sider-dir 을 주십시오.")
        return 2
    sider_md5 = {f: md5(args.sider_dir / f) for f in SIDER_FILES}
    for f, h in sider_md5.items():
        if h != SIDER_MD5[f]:
            print(f"경고: {f} md5 {h} 가 기록된 값 {SIDER_MD5[f]} 와 다릅니다")

    names, sider_pt = read_sider(args.sider_dir)
    if con is None:
        import duckdb
        con = duckdb.connect(str(args.db), read_only=True)
        con.execute("SET memory_limit='8GB'")
    period, drug_n, _ = read_warehouse(con)
    matched, exclusions = match_drugs(names, set(drug_n["drug"]))
    selected, missing_extra = select_drugs(matched, drug_n, args.top_n, args.extra_drugs)
    _, _, pairs = read_warehouse(con, [s["drug"] for s in selected])
    rows, dropped, per_drug = build_rows(selected, sider_pt, pairs)

    metrics = pd.DataFrame(rows)[["drug", "pt", "class"]].merge(pairs, on=["drug", "pt"], how="left")
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_parquet(args.metrics_out, index=False)

    n_pos = sum(r["class"] == "positive" for r in rows)
    n_neg = len(rows) - n_pos
    meta = {
        "name": REFSET_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "pipeline/refsets/sider_refset.py",
        "sider": {"release": SIDER_RELEASE, "meddra_version": MEDDRA_VERSION, "url": SIDER_URL,
                  "dir": display(args.sider_dir), "md5": sider_md5,
                  "pt_pairs": int(len(sider_pt)), "pt_universe": int(sider_pt["pt"].nunique())},
        "warehouse": {**period, "path": display(args.db), "sql": SQL,
                      "metrics_file": display(args.metrics_out), "metrics_md5": md5(args.metrics_out)},
        "sources": SOURCES,
        "drug_rule": DRUG_RULE.format(top_n=args.top_n, extra=", ".join(args.extra_drugs)),
        "top_n": args.top_n, "extra_drugs": args.extra_drugs, "extra_drugs_not_matched": missing_extra,
        "n_drugs": len(selected), "a_threshold": A_THRESHOLD,
        "seed": args.seed, "null_repeats": NULL_REPEATS, "null_rule": NULL_RULE,
        "exclusions": exclusions, "dropped": dropped,
        "counts": {"positive": n_pos, "negative": n_neg,
                   "prevalence": round(n_pos / len(rows), 6) if rows else None,
                   "negative_per_positive": round(n_neg / n_pos, 4) if n_pos else None},
        "drugs": per_drug,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    text = dump_refset(meta, rows)
    if args.out.suffix == ".gz":
        tmp.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))
    else:
        tmp.write_text(text)
    os.replace(tmp, args.out)
    print(f"{display(args.out)}: 약 {len(selected)}종, 양성 {n_pos:,}, 음성 {n_neg:,}, 유병률 {meta['counts']['prevalence']}, "
          f"웨어하우스 {period['asof']}")
    print(f"제외: 공유 이름 {exclusions['excluded_shared_names']}, 웨어하우스 불일치 {exclusions['unmatched_in_warehouse']}, "
          f"손 선정 불일치 {missing_extra}, 웨어하우스 행 없는 양성 {dropped['sider_positive_without_warehouse_row']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
