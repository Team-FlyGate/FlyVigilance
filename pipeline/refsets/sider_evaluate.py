"""SIDER 파일럿 참조 세트로 불균형 지표의 민감도, 특이도, PPV, ROC, AUC 를 잽니다.

sider_refset.py 가 만든 참조 행(양성 = 라벨 기재, 음성 = 라벨 부재)에 웨어하우스 sig_signal 지표를 붙여,
고정 문턱이 라벨 기재 쌍을 얼마나 골라내는지 잽니다. 수치는 라벨 기재 예측 성능이며 인과성이 아닙니다.

무엇을 재는가
- 지표 일곱 개: 점추정치 prr, ror, chi2_yates, ic 와 하한 prr_lo, ror_lo, ic025.
  지표마다 AUC(api/_fv/pvstats.auc, 동점은 평균 순위), 관례 문턱과 분위수 25개 문턱에서 "지표 >= 문턱" 의
  민감도·특이도·PPV(pvstats.sens_spec), ROC 점(pvstats.roc_points)을 냅니다.
- 고정 규칙: 웨어하우스 플래그 evans_signal(PRR>=2, chi2>=4, a>=3), ror_signal(ROR025>1, a>=3),
  ic_signal(IC025>0)과 세 기준 동시 충족(triple, FlyVigilance 의 SDR 과 같은 정의)을 한 점씩 냅니다.
- 귀무 뒤섞기: 선정 약 안에서 양성 쌍의 PT 를 약 사이에 뒤섞고, 참조 행에 있는 쌍을 양성과 같은 수가 될 때까지
  모아 "귀무 양성" 으로 두고 AUC 를 다시 잽니다. 100회, 시드는 참조 세트의 seed+i 입니다.
- 약별 AUC: 보고 수 상위 약은 라벨이 두꺼워 전체 AUC 가 낙관적일 수 있어 약마다 따로 잽니다.
- 지표 값이 NaN 인 행은 그 지표에서만 빼고 수를 남깁니다. 무한대는 순위상 가장 큰 값으로 남깁니다.

산출물
- data/derived/refsets/sider_metric_validation.json: 전체 결과(스윕, ROC, 귀무, 약별 AUC)
- docs/images/sider_metric_roc_<date>.png: ROC 그림. --jev 로 sider_jev.py 결과를 주면 Jev 곡선을 더한 그림을
  sider_metric_roc_jev_<date>.png 로 따로 그립니다.
  --omics 로 omics_plausibility.py --refset 결과를 주면 같은 행 기준 그림(sider_omics_roc_<date>.png)도 그립니다.
- api/_data/metrics.json: rules.evans / rules.triple 에 "sider-pilot" 항목을 더하고(evidence.metric_catalog 가
  metric:triple:sider-pilot@<asof> 근거로 인용합니다), 요약 수치를 "sider" 키에 둡니다. 다른 참조 세트 항목은 그대로 둡니다.
  웨어하우스 asof 가 metrics.json 의 asof 와 다르면 근거 ID 가 틀리므로 rules 에는 넣지 않고 "sider" 키만 씁니다.

날짜는 date.today() 이므로 팀 기준(KST)으로 맞추려면 TZ=Asia/Seoul 을 주고 실행합니다.

사용법:
  TZ=Asia/Seoul .venv/bin/python pipeline/refsets/sider_evaluate.py
  .venv/bin/python pipeline/refsets/sider_evaluate.py --plot-only --jev data/derived/refsets/sider_jev_novel_<date>.json
"""
import argparse
import gzip
import json
import math
import os
import pathlib
import sys
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from _fv import pvstats  # noqa: E402

REF = ROOT / "data/derived/refsets"
REFSET = REF / "sider_pairs.json.gz"
METRICS_FILE = REF / "sider_metrics.parquet"
RESULTS = REF / "sider_metric_validation.json"
METRICS_JSON = ROOT / "api/_data/metrics.json"
FIG_DIR = ROOT / "docs/images"
REFSET_KEY = "sider-pilot"

POINT_METRICS = ["prr", "ror", "chi2_yates", "ic"]
LOWER_METRICS = ["prr_lo", "ror_lo", "ic025"]
METRICS = POINT_METRICS + LOWER_METRICS
FIXED_RULES = {
    "evans_signal": "prr>=2 AND chi2_yates>=4 AND a>=3",
    "ror_signal": "ror_lo>1 AND a>=3",
    "ic_signal": "ic025>0",
}
TRIPLE_RULE = "evans_signal AND ror_signal AND ic_signal (FlyVigilance SDR, pvstats.two_by_two 의 triple)"
# 관례상 쓰는 문턱입니다. 스윕 표와 별도로 이 문턱의 성능을 적습니다
CONVENTIONAL = {"prr": [1, 2, 3], "ror": [1, 2, 3], "chi2_yates": [4], "ic": [0],
                "prr_lo": [1], "ror_lo": [1], "ic025": [0]}
N_SWEEP = 25          # 분위수 문턱 개수
N_ROC_POINTS = 400    # 그림용 ROC 점 상한
NULL_MAX_ROUNDS = 200
CAVEAT = "양성은 SIDER 라벨 기재, 음성은 라벨 부재입니다. 수치는 라벨 기재 예측 성능이며 인과성이 아닙니다."


# ---------------------------------------------------------------- 공용 함수 (sider_jev.py, omics_plausibility.py 도 씁니다)
def read_refset(path: pathlib.Path) -> dict:
    """참조 세트를 읽습니다. .json 과 .json.gz 를 모두 받습니다."""
    raw = pathlib.Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith(".gz") else raw)


def load_frame(rows: list[dict], metrics_file: pathlib.Path) -> tuple[pd.DataFrame, int]:
    """참조 행에 sig_signal 지표를 붙입니다. 지표 행이 없는 참조 행은 빼고 그 수를 돌려줍니다."""
    ref = pd.DataFrame(rows)[["drug", "pt", "class"]]
    m = pd.read_parquet(metrics_file).drop(columns=["class"], errors="ignore")
    frame = ref.merge(m, on=["drug", "pt"], how="left", indicator=True)
    unmatched = int((frame["_merge"] != "both").sum())
    frame = frame[frame["_merge"] == "both"].drop(columns="_merge").reset_index(drop=True)
    for r in FIXED_RULES:
        frame[r] = frame[r].fillna(False).astype(bool)
    frame["label"] = frame["class"] == "positive"
    return frame, unmatched


def auc(scores, labels) -> float | None:
    """pvstats.auc 를 numpy 배열로 부르는 얇은 감쌈입니다."""
    return pvstats.auc(np.asarray(scores, dtype=float).tolist(), np.asarray(labels, dtype=int).tolist())


def at_threshold(scores: np.ndarray, labels: np.ndarray, t: float) -> dict:
    return {"threshold": float(t), **pvstats.sens_spec((scores >= t).tolist(), labels.astype(int).tolist())}


def roc(scores: np.ndarray, labels: np.ndarray) -> list[list[float]]:
    return pvstats.roc_points(scores.tolist(), labels.astype(int).tolist(), max_points=N_ROC_POINTS)


def score_block(s: np.ndarray, y: np.ndarray, conventional: list[float] = ()) -> dict:
    """점수 하나의 AUC, 관례 문턱, 분위수 문턱 스윕, ROC 점입니다. s 에 NaN 이 없어야 합니다."""
    q = np.unique(np.quantile(s, np.linspace(0, 1, N_SWEEP))) if len(s) else []
    return {"n_used": int(len(s)), "n_positive": int(y.sum()), "n_negative": int((~y).sum()),
            "auc": auc(s, y), "conventional": [at_threshold(s, y, t) for t in conventional],
            "sweep": [at_threshold(s, y, t) for t in q], "roc": roc(s, y)}


def null_positive_masks(frame: pd.DataFrame, seed: int, repeats: int) -> list[dict]:
    """양성 쌍의 PT 를 약 사이에 뒤섞어 양성과 같은 수의 귀무 양성 마스크를 repeats 개 만듭니다.

    한 번 뒤섞으면 참조 행에 없는 (약, PT) 는 버려지므로, 같은 난수원으로 뒤섞기를 되풀이해 새로 맞은 쌍을 더하고,
    양성 수를 넘으면 마지막 회차에서 무작위로 잘라 정확히 맞춥니다.
    """
    pos = frame[frame["label"]]
    drugs, pts = pos["drug"].to_numpy(), pos["pt"].to_numpy()
    index = {k: i for i, k in enumerate(zip(frame["drug"], frame["pt"]))}
    target = len(pos)
    out = []
    for i in range(repeats):
        rng = np.random.default_rng(seed + i)
        chosen: list[int] = []
        seen: set[int] = set()
        rounds = 0
        while len(chosen) < target and rounds < NULL_MAX_ROUNDS:
            rounds += 1
            shuffled = pts[rng.permutation(len(pts))]
            new = []
            for d, p in zip(drugs, shuffled):
                j = index.get((d, p))
                if j is not None and j not in seen:
                    seen.add(j)
                    new.append(j)
            need = target - len(chosen)
            if len(new) > need:
                new = list(rng.choice(np.array(new), size=need, replace=False))
            chosen += new
        mask = np.zeros(len(frame), dtype=bool)
        mask[np.array(chosen, dtype=int)] = True
        out.append({"seed": seed + i, "mask": mask, "rounds": rounds, "n_null_positive": int(mask.sum()),
                    "overlap_with_positive": int((mask & frame["label"].to_numpy()).sum())})
    return out


def summarise(values: list) -> dict:
    arr = np.array([v for v in values if v is not None], dtype=float)
    if not len(arr):
        return {"n": 0}
    return {"n": int(len(arr)), "mean": float(arr.mean()), "p2_5": float(np.percentile(arr, 2.5)),
            "p97_5": float(np.percentile(arr, 97.5)), "min": float(arr.min()),
            "median": float(np.median(arr)), "max": float(arr.max())}


def finite(x):
    """JSON 에 NaN 과 무한대를 쓰지 않습니다. numpy 수는 파이썬 수로 바꿉니다."""
    if isinstance(x, dict):
        return {k: finite(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [finite(v) for v in x]
    if isinstance(x, np.generic):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def write_json(path: pathlib.Path, doc: dict, indent: int | None = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(finite(doc), ensure_ascii=False, indent=indent, allow_nan=False) + "\n"
    if path.suffix == ".gz":
        tmp.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))
    else:
        tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------- 평가
def evaluate(frame: pd.DataFrame, seed: int, repeats: int) -> dict:
    labels = frame["label"].to_numpy()
    metrics = {}
    for m in METRICS:
        v = frame[m].to_numpy(dtype=float)
        ok = ~np.isnan(v)
        metrics[m] = {"kind": "point" if m in POINT_METRICS else "lower_bound",
                      "n_nan_excluded": int((~ok).sum()), "n_inf": int(np.isinf(v[ok]).sum()),
                      **score_block(v[ok], labels[ok], CONVENTIONAL[m])}
    flags = {r: frame[r].to_numpy() for r in FIXED_RULES}
    flags["triple"] = flags["evans_signal"] & flags["ror_signal"] & flags["ic_signal"]
    rules = {r: {"rule": FIXED_RULES.get(r, TRIPLE_RULE), **pvstats.sens_spec(f.tolist(), labels.astype(int).tolist())}
             for r, f in flags.items()}

    null_sets = null_positive_masks(frame, seed, repeats)
    null = {"repeats": repeats, "seed_first": seed, "seed_last": seed + repeats - 1,
            "n_null_positive": summarise([n["n_null_positive"] for n in null_sets]),
            "overlap_with_label_positive": summarise([n["overlap_with_positive"] for n in null_sets]),
            "rounds": summarise([n["rounds"] for n in null_sets]), "auc": {}}
    for m in METRICS:
        v = frame[m].to_numpy(dtype=float)
        ok = ~np.isnan(v)
        null["auc"][m] = summarise([auc(v[ok], n["mask"][ok]) for n in null_sets])

    per_drug: dict[str, dict] = {m: {"by_drug": {}} for m in METRICS}
    for drug, g in frame.groupby("drug", sort=True):
        y = g["label"].to_numpy()
        for m in METRICS:
            v = g[m].to_numpy(dtype=float)
            ok = ~np.isnan(v)
            per_drug[m]["by_drug"][drug] = {"auc": auc(v[ok], y[ok]), "n_positive": int(y[ok].sum()),
                                            "n_negative": int((~y[ok]).sum())}
    for m in METRICS:
        per_drug[m]["summary"] = summarise([d["auc"] for d in per_drug[m]["by_drug"].values()])

    return {"prevalence": float(labels.mean()), "n_rows": int(len(frame)),
            "n_positive": int(labels.sum()), "n_negative": int((~labels).sum()),
            "metrics": metrics, "fixed_rules": rules, "null": null, "per_drug_auc": per_drug}


def compact(res: dict, figure: str | None) -> dict:
    """metrics.json 의 "sider" 키에 둘 요약입니다. 스윕과 ROC 점은 결과 파일에만 둡니다."""
    r4 = lambda x: None if x is None else round(x, 4)  # noqa: E731
    return {"refset": REFSET_KEY, "asof": res["warehouse_asof"], "n": res["n_rows"], "pos": res["n_positive"],
            "neg": res["n_negative"], "prevalence": r4(res["prevalence"]), "n_drugs": res["refset_meta"]["n_drugs"],
            "auc": {m: r4(v["auc"]) for m, v in res["metrics"].items()},
            "null_auc": {m: {k: r4(v.get(k)) for k in ("mean", "p2_5", "p97_5")} for m, v in res["null"]["auc"].items()},
            "per_drug_auc_median": {m: r4(v["summary"].get("median")) for m, v in res["per_drug_auc"].items()},
            "rules": {k: {**{f: v[f] for f in ("sens", "spec", "ppv", "tp", "fp", "tn", "fn")}, "rule": v["rule"]}
                      for k, v in res["fixed_rules"].items()},
            "caveat": CAVEAT, "results": str(RESULTS.relative_to(ROOT)), "figure": figure}


def update_metrics_json(res: dict, figure: str | None, path: pathlib.Path = METRICS_JSON) -> bool:
    """metrics.json 에 SIDER 항목을 더합니다. 다른 참조 세트 항목은 건드리지 않습니다. rules 에 넣었으면 True 입니다."""
    m = json.loads(path.read_text()) if path.exists() else {"asof": res["warehouse_asof"], "rules": {}}
    m["sider"] = compact(res, figure)
    same_asof = m.get("asof") == res["warehouse_asof"]
    for rule, key in (("evans", "evans_signal"), ("triple", "triple")):
        entry = m.setdefault("rules", {}).setdefault(rule, {})
        entry.pop(REFSET_KEY, None)
        if same_asof:
            v = res["fixed_rules"][key]
            entry[REFSET_KEY] = {**{f: v[f] for f in ("sens", "spec", "ppv", "tp", "fp", "tn", "fn")}, "n": res["n_rows"]}
    if not same_asof:
        print(f"경고: metrics.json asof {m.get('asof')} 와 웨어하우스 asof {res['warehouse_asof']} 가 달라 rules 에 넣지 않았습니다")
    path.write_text(json.dumps(m, indent=1, default=float))
    return same_asof


# ---------------------------------------------------------------- 그림
SURFACE, INK, INK_SOFT, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
# 지표 순서가 범주 팔레트 슬롯 순서입니다. 점추정치는 실선, 하한은 점선입니다
SERIES = {"prr": ("#2a78d6", "PRR", "-"), "ror": ("#eb6834", "ROR", "-"),
          "chi2_yates": ("#1baf7a", "Chi-square (Yates)", "-"), "ic": ("#eda100", "IC", "-"),
          "prr_lo": ("#e87ba4", "PRR lower 95%", "--"), "ror_lo": ("#008300", "ROR025", "--"),
          "ic025": ("#4a3aa7", "IC025", "--")}
RULE_MARKS = {"evans_signal": ("o", "Evans"), "ror_signal": ("s", "ROR signal"), "ic_signal": ("^", "IC signal"),
              "triple": ("D", "Triple (SDR)")}
JEV_STYLE = {"novel": ("Jev novel", "-."), "blind": ("Jev blind", ":")}
OMICS_STYLE = {"max_score": ("Open Targets association (all)", "-"),
               "max_score_no_literature_api": ("No literature (API)", "-."),
               "max_score_no_literature_local": ("No literature (local)", ":")}


def _axes(title: str, subtitle: str):
    """그림 틀입니다. 글꼴 파일을 저장소에 두지 않으려고 그림 글자는 영문으로 씁니다."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(8.0, 8.4), dpi=200, facecolor=SURFACE)
    ax = fig.add_axes([0.10, 0.18, 0.86, 0.68], facecolor=SURFACE)
    ax.plot([0, 1], [0, 1], color=AXIS, lw=1, zorder=1)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.set_xlabel("1 - specificity (label-absent pairs flagged)", color=INK_SOFT, fontsize=10.5)
    ax.set_ylabel("Sensitivity (labeled pairs flagged)", color=INK_SOFT, fontsize=10.5)
    ax.grid(color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    fig.text(0.10, 0.955, title, fontsize=14, color=INK, weight="bold", ha="left")
    fig.text(0.10, 0.925, subtitle, fontsize=9.5, color=INK_SOFT, ha="left", va="top", linespacing=1.4)
    return plt, fig, ax


def _curve(ax, pts, **kw):
    ax.plot([p[0] for p in pts], [p[1] for p in pts], lw=2, solid_capstyle="round", dash_capstyle="round", **kw)


def draw(res: dict, out: pathlib.Path, stamp: str, jev: list[dict] = ()) -> None:
    plt, fig, ax = _axes("Disproportionality metrics vs SIDER label listing (pilot)",
                         "ROC over all thresholds. Black markers are fixed FlyVigilance rules. "
                         "PRR, ROR and IC curves overlap.")
    for key in sorted(SERIES, key=lambda k: -(res["metrics"][k]["auc"] or 0)):
        color, label, ls = SERIES[key]
        _curve(ax, res["metrics"][key]["roc"], color=color, ls=ls, zorder=3,
               label=f"{label}  AUC {res['metrics'][key]['auc']:.3f}")
    for doc in jev:
        name, ls = JEV_STYLE[doc["arm"]]
        _curve(ax, doc["jev"]["roc"], color=INK, ls=ls, zorder=4,
               label=f"{name}  AUC {doc['jev']['auc']:.3f} ({doc['jev']['n_used']:,} pairs)")
    for key, (marker, name) in RULE_MARKS.items():
        r = res["fixed_rules"][key]
        ax.scatter([1 - r["spec"]], [r["sens"]], s=60, marker=marker, color=INK, edgecolor=SURFACE, linewidth=1.5,
                   zorder=5, label=f"{name}  sens {r['sens']:.2f} / spec {r['spec']:.2f}")
    ax.legend(loc="lower right", fontsize=8.5, frameon=True, framealpha=1, edgecolor=GRID, facecolor=SURFACE,
              labelcolor=INK, handlelength=2.6)
    m = res["refset_meta"]
    fig.text(0.10, 0.10,
             f"Reference set: SIDER 4.1 label PTs (MedDRA 16.1) vs FlyVigilance FAERS warehouse {res['warehouse_asof']},\n"
             f"{m['n_drugs']} drugs (top {m['top_n']} by reports + hand-picked), all pairs a>=3.\n"
             f"Positive (labeled) {res['n_positive']:,}, negative (label-absent, inside SIDER PT universe) "
             f"{res['n_negative']:,}, prevalence {res['prevalence']:.1%}.\n"
             f"Predicts label listing, not causality. Run date {stamp}.",
             fontsize=8.5, color=INK_SOFT, ha="left", va="top", linespacing=1.6)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def draw_omics(res: dict, omics: dict, out: pathlib.Path, stamp: str) -> None:
    """오믹스 점수가 있는 같은 행에서 지표 넷과 Open Targets 점수 셋의 ROC 를 그립니다."""
    ev = omics["evaluation"]
    plt, fig, ax = _axes("Mechanistic plausibility vs disproportionality (same rows)",
                         f"Open Targets {omics['source']['data_version']} target-disease association, max over the "
                         "drug's mechanism targets.\nNo literature: Europe PMC weight 0 (API) or max of non-literature "
                         "datatypes (local).")
    blocks = ev["metrics_same_rows"]
    for key in sorted(blocks, key=lambda k: -(blocks[k]["auc"] or 0)):
        color, label, ls = SERIES[key]
        _curve(ax, blocks[key]["roc"], color=color, ls=ls, zorder=3, label=f"{label}  AUC {blocks[key]['auc']:.3f}")
    for key, (name, ls) in OMICS_STYLE.items():
        b = ev["scores"].get(key)
        if b and b["auc"] is not None:
            _curve(ax, b["roc"], color=INK, ls=ls, zorder=4, label=f"{name}  AUC {b['auc']:.3f} ({b['n_used']:,} pairs)")
    ax.legend(loc="lower right", fontsize=8.5, frameon=True, framealpha=1, edgecolor=GRID, facecolor=SURFACE,
              labelcolor=INK, handlelength=2.6)
    ex = ev["excluded"]
    fig.text(0.10, 0.10,
             f"SIDER pilot vs FAERS warehouse {res['warehouse_asof']}: {ev['n_rows_evaluated']:,} of "
             f"{ev['n_rows_total']:,} pairs have an omics score\n(positive {ev['n_positive']:,}, negative {ev['n_negative']:,}). "
             f"Excluded: drug unresolved {ex['drug_unresolved']:,}, no drug targets {ex['drug_no_targets']:,}, "
             f"PT unmapped {ex['pt_unmapped']:,}.\nMetric curves re-measured on the same rows. "
             f"Predicts label listing, not causality. Run date {stamp}.",
             fontsize=8.5, color=INK_SOFT, ha="left", va="top", linespacing=1.6)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- 실행
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refset", type=pathlib.Path, default=REFSET)
    ap.add_argument("--metrics-file", type=pathlib.Path, default=METRICS_FILE)
    ap.add_argument("--repeats", type=int, default=None, help="귀무 반복 수. 기본은 참조 세트의 null_repeats")
    ap.add_argument("--out", type=pathlib.Path, default=RESULTS)
    ap.add_argument("--fig-dir", type=pathlib.Path, default=FIG_DIR)
    ap.add_argument("--metrics-json", type=pathlib.Path, default=METRICS_JSON)
    ap.add_argument("--no-metrics-json", action="store_true", help="api/_data/metrics.json 을 고치지 않습니다")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--plot-only", action="store_true", help="다시 계산하지 않고 --out 결과로 그림만 그립니다")
    ap.add_argument("--jev", type=pathlib.Path, action="append", default=[], help="sider_jev.py 결과. 여러 번 줄 수 있습니다")
    ap.add_argument("--omics", type=pathlib.Path, default=None, help="omics_plausibility.py --refset 결과")
    args = ap.parse_args(argv)
    stamp = date.today().isoformat()

    if args.plot_only:
        res = json.loads(args.out.read_text())
    else:
        refset = read_refset(args.refset)
        meta = refset["meta"]
        frame, unmatched = load_frame(refset["rows"], args.metrics_file)
        repeats = args.repeats if args.repeats is not None else meta["null_repeats"]
        res = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "script": "pipeline/refsets/sider_evaluate.py", "caveat": CAVEAT,
               "refset_meta": meta, "warehouse_asof": meta["warehouse"]["asof"], "seed": meta["seed"],
               "dropped": {**meta["dropped"], "refset_rows_without_metrics_row": unmatched},
               **evaluate(frame, meta["seed"], repeats)}
        write_json(args.out, res)
        print(f"행 {res['n_rows']:,}, 양성 {res['n_positive']:,}, 음성 {res['n_negative']:,}, 유병률 {res['prevalence']:.4f}")
        for m in METRICS:
            print(f"  {m:11s} AUC {res['metrics'][m]['auc']:.3f}  귀무 평균 {res['null']['auc'][m]['mean']:.3f}")
        for r, v in res["fixed_rules"].items():
            print(f"  {r:13s} 민감도 {v['sens']:.3f} 특이도 {v['spec']:.3f} PPV {v['ppv']:.3f}")

    figure = None
    if not args.no_plot:
        jev = []
        for p in args.jev:
            doc = json.loads(p.read_text())
            if doc.get("jev"):
                jev.append(doc)
            else:
                print(f"{p}: 확률이 없어 건너뜁니다")
        # Jev 곡선을 더한 그림은 따로 둡니다. metrics.json 이 가리키는 그림은 지표만 그린 것입니다
        fig_path = args.fig_dir / f"sider_metric_roc{'_jev' if jev else ''}_{stamp}.png"
        draw(res, fig_path, stamp, jev)
        figure = str(fig_path.relative_to(ROOT)) if fig_path.resolve().is_relative_to(ROOT) else fig_path.name
        print(figure)
        if args.omics:
            omics = read_refset(args.omics)
            op = args.fig_dir / f"sider_omics_roc_{stamp}.png"
            draw_omics(res, omics, op, stamp)
            print(op.name)
    if not args.plot_only and not args.no_metrics_json:
        update_metrics_json(res, figure, args.metrics_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
