"""SIDER 파일럿 참조 세트의 쌍마다 Jev 에 novel 질문을 던져, 그 확률을 불균형 지표와 같은 ROC 로 잽니다.

sider_evaluate.py 는 PRR, ROR, 카이제곱, IC 가 라벨 기재 쌍을 얼마나 골라내는지 잽니다. 같은 참조 쌍에 Jev 의
noul 확률을 받으면 판단 모델이 그 지표보다 나은지 같은 그림 위에서 비교할 수 있습니다.

규칙
- 쌍 하나에 Jev 한 호출, 질문 하나입니다. 호출은 api/_fv/clients.py 의 jev() 를 씁니다(재시도 포함).
  질문(novel)과 state 모양은 하네스 벤치마크(bench_triage_scale.py 의 JEV_QUESTION_SETS["novel"], jev_state)와
  같게 옮겼습니다. 하네스에서 받은 캐시를 그대로 재생할 수 있게 캐시 키와 기록 모양도 같습니다.
- 팔은 둘입니다. novel 은 이름을 보입니다. blind 는 이름을 DRUG_A, REACTION_1 로 가려 숫자만 남깁니다.
  라벨 기재 여부는 맞힐 대상이라 state 에 넣지 않습니다.
- novel 질문의 참은 "라벨에 없는 새 신호일 수 있다" 입니다. 양성 쌍이 라벨 기재 쌍이므로 모델이 질문대로 답하면
  양성의 확률이 낮아야 합니다. 그래서 AUC 는 확률 그대로(auc)와 1 - 확률(auc_inverted)을 둘 다 적습니다.
- AUC, 문턱 스윕, ROC 점, 귀무 뒤섞기는 sider_evaluate.py 의 함수(안에서 api/_fv/pvstats.py)를 씁니다. 귀무 양성
  마스크는 참조 세트 전체에서 sider_evaluate 와 같은 시드로 만들고 Jev 확률이 있는 행으로 좁힙니다. 같은 행에서
  잰 지표 일곱 개의 AUC 도 함께 적어 --limit 표본에서도 비교가 되게 합니다.
- 실패한 호출은 확률을 None 으로 남기고 0 으로 채우지 않습니다. 평가는 확률이 있는 행만 쓰고 빠진 수를 적습니다.
- --limit N 은 참조 세트에서 시드(참조 세트의 seed)로 N 쌍을 무작위로 뽑습니다. 앞에서부터 자르면 한 약만 남습니다.
- 실제 호출 전에 쌍 수, 예상 입력 토큰, 예상 비용을 찍고 --yes 가 없으면 멈춥니다. 토큰 수는 요청 본문(state 와
  질문)을 JSON 으로 적은 글자 수를 4 로 나눈 어림이며 토크나이저로 센 값이 아닙니다. 잔액은 조회하지 않습니다.
- 모델은 config.JEV_MODEL 입니다(clients.jev 가 그 값을 보냅니다).

사용법:
  # 네트워크 없이 비용만 봅니다
  TZ=Asia/Seoul .venv/bin/python pipeline/refsets/sider_jev.py --arm novel --limit 200 --dry-run
  # 키를 넣고 200쌍 시험 실행
  TZ=Asia/Seoul .venv/bin/python pipeline/refsets/sider_jev.py --arm novel --limit 200 \\
      --jev-cache data/cache/jev_sider_novel.json --yes
"""
import argparse
import asyncio
import json
import os
import pathlib
import sys
import time
from datetime import date, datetime, timezone
from typing import Any, Callable

import httpx
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sider_evaluate as sev  # noqa: E402
from _fv import clients, config  # noqa: E402

OUT = ROOT / "data/derived/refsets"
QUESTION = "novel"
QUESTION_KEY = "needs_human"   # 하네스 캐시와 같은 키입니다
QUESTION_SPEC = {
    "instructions": ("Could this drug and reaction pair be a signal that is NOT yet described in the "
                     "product label? Judge from the counts, the measures and any label information "
                     "given. A reaction already described in the label is not a new signal, however "
                     "strong its disproportionality."),
    "true": "The pair could be a new signal: the disproportionality is not explained by "
            "what the label already describes.",
    "false": "The pair is not a new signal, either because the label already describes it "
             "or because the disproportionality is too weak to raise one.",
}
CHARS_PER_TOKEN = 4
CACHE_FLUSH_EVERY = 200


def questions() -> dict:
    return {QUESTION_KEY: {"type": "noul", "instructions": QUESTION_SPEC["instructions"],
                           "criteria": {"true": QUESTION_SPEC["true"], "false": QUESTION_SPEC["false"]}}}


def _num(x: Any) -> int | float | None:
    """numpy 수를 JSON 에 쓸 수 있는 파이썬 수로 바꿉니다. NaN 과 무한대는 None 입니다."""
    if x is None:
        return None
    x = float(x)
    if not np.isfinite(x):
        return None
    return int(x) if x.is_integer() else x


def pair_state(row: dict, *, blind: bool) -> dict[str, Any]:
    """쌍 하나의 Jev state 입니다. 보고 수(reports_with_this_reaction)는 2x2 의 a 입니다."""
    return {
        "drug": "DRUG_A" if blind else row["drug"],
        "reaction": "REACTION_1" if blind else row["pt"],
        "reports_with_this_reaction": _num(row["a"]),
        "contingency_2x2": {k: _num(row[k]) for k in ("a", "b", "c", "d")},
        "measures": {"PRR": _num(row["prr"]), "ROR": _num(row["ror"]), "chi_square_yates": _num(row["chi2_yates"])},
        "note": "Public FAERS carries no causality assessment and no narrative.",
    }


def jev_call(state: dict, qs: dict, *, timeout: float = 60.0) -> dict:
    """clients.jev 를 한 번 부르고 기록 모양({status, seconds, body} 또는 {status, error})으로 돌려줍니다.
    오류는 올리지 않고 기록으로 돌려줍니다. 실패도 남겨야 할 자료이기 때문입니다."""
    async def once():
        # state 는 문자열이 아니라 JSON 객체로 보냅니다. 하네스 캐시를 만든 요청과 같은 모양입니다
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0)) as cl:
            return await clients.jev(state, qs, client=cl)
    t0 = time.perf_counter()
    try:
        r = asyncio.run(once())
    except httpx.HTTPStatusError as e:
        return {"status": e.response.status_code, "seconds": round(time.perf_counter() - t0, 3),
                "error": e.response.text[:500]}
    except Exception as e:  # noqa: BLE001 - 키 없음, 네트워크, 파싱 오류를 모두 기록합니다
        return {"status": 0, "seconds": round(time.perf_counter() - t0, 3), "error": f"{type(e).__name__}: {e}"}
    return {"status": 200, "seconds": round(r["latency_ms"] / 1000, 3), "request_id": None,
            "body": {"model": r.get("model"), "answers": r["answers"], "usage": r.get("usage", {})}}


def noul_probability(result: dict) -> float | None:
    """noul 확률을 읽습니다. 호출이나 키가 실패하면 None 입니다(0.0 과 구별합니다)."""
    answer = ((result.get("body") or {}).get("answers") or {}).get(QUESTION_KEY)
    value = answer.get("noul") if isinstance(answer, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def input_tokens(result: dict) -> int | None:
    return ((result.get("body") or {}).get("usage") or {}).get("input_tokens")


def estimate_tokens(states: list[dict], qs: dict) -> int:
    """요청 본문 글자 수를 4 로 나눈 어림 토큰 수입니다."""
    return sum(len(json.dumps({"state": s, "questions": qs}, ensure_ascii=False)) for s in states) // CHARS_PER_TOKEN


def cost_lines(n_pairs: int, tokens: int, price_in: float) -> list[str]:
    per = tokens / n_pairs if n_pairs else 0.0
    return [f"쌍 수: {n_pairs:,}",
            f"예상 입력 토큰: {tokens:,} (쌍당 {per:.1f}, 요청 JSON 글자 수 / {CHARS_PER_TOKEN} 의 어림)",
            f"예상 비용: USD {tokens / 1e6 * price_in:.4f} (입력 USD {price_in}/M 토큰, 출력 무료)"]


def load_cache(path: pathlib.Path | None) -> dict[str, dict]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: pathlib.Path, cache: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def cache_key(arm: str, model: str, drug: str, pt: str) -> str:
    return f"{arm}|{model}|{drug}|{pt}"


def ask_pairs(frame: pd.DataFrame, *, arm: str, model: str, dry_run: bool, cache: dict[str, dict],
              cache_path: pathlib.Path | None = None, call: Callable[..., dict] = jev_call,
              timeout: float = 60.0, sleep: float = 0.0) -> list[dict]:
    """쌍마다 Jev 를 부르거나 캐시에서 꺼내 확률 행을 만듭니다.

    dry_run 이면 캐시에 있는 응답만 쓰고 네트워크로 나가지 않습니다. 성공(HTTP 200) 응답만 캐시에 넣고,
    cache_path 가 있으면 CACHE_FLUSH_EVERY 호출마다 파일로 내려 긴 실행이 끊겨도 받은 만큼은 남깁니다.
    """
    qs = questions()
    blind = arm == "blind"
    out: list[dict] = []
    fresh = 0
    for row in frame.to_dict("records"):
        key = cache_key(arm, model, row["drug"], row["pt"])
        result = cache.get(key)
        source = "cache" if result is not None else None
        if result is None and not dry_run:
            if fresh and sleep:
                time.sleep(sleep)
            result = call(pair_state(row, blind=blind), qs, timeout=timeout)
            fresh += 1
            source = "live"
            if result.get("status") == 200:
                cache[key] = result
                if cache_path is not None and fresh % CACHE_FLUSH_EVERY == 0:
                    save_cache(cache_path, cache)
        result = result or {}
        body = result.get("body") or {}
        out.append({"drug": row["drug"], "pt": row["pt"], "class": row["class"], "a": _num(row["a"]),
                    "probability": noul_probability(result), "request_id": result.get("request_id"),
                    "model": (body.get("model") if isinstance(body, dict) else None) or (model if result else None),
                    "seconds": result.get("seconds"), "http_status": result.get("status"),
                    "input_tokens": input_tokens(result), "error": result.get("error"), "source": source})
    return out


def evaluate(full: pd.DataFrame, rows: list[dict], *, seed: int, repeats: int) -> dict | None:
    """확률이 있는 행으로 Jev 의 AUC, 귀무 요약, 같은 행의 지표 AUC 를 냅니다. 양성과 음성이 모두 있어야 합니다."""
    prob = {(r["drug"], r["pt"]): r["probability"] for r in rows if r["probability"] is not None}
    keys = list(zip(full["drug"], full["pt"]))
    have = np.array([k in prob for k in keys], dtype=bool)
    y = full["label"].to_numpy()[have]
    if not have.any() or y.all() or not y.any():
        return None
    s = np.array([prob[k] for k, h in zip(keys, have) if h], dtype=float)
    block = sev.score_block(s, y, [0.5])
    block["auc_inverted"] = sev.auc(-s, y)
    null_sets = sev.null_positive_masks(full, seed, repeats)
    block["null"] = {
        "repeats": repeats, "seed_first": seed, "seed_last": seed + repeats - 1,
        "note": "귀무 양성은 참조 세트 전체에서 sider_evaluate 와 같은 시드로 만들고 확률이 있는 행으로 좁혔습니다.",
        "n_null_positive_in_rows": sev.summarise([int(n["mask"][have].sum()) for n in null_sets]),
        "auc": sev.summarise([sev.auc(s, n["mask"][have]) for n in null_sets]),
    }
    same = {}
    for m in sev.METRICS:
        v = full[m].to_numpy(dtype=float)[have]
        ok = ~np.isnan(v)
        same[m] = sev.auc(v[ok], y[ok])
    block["metrics_auc_same_rows"] = same
    return block


def sample_rows(frame: pd.DataFrame, limit: int | None, seed: int) -> pd.DataFrame:
    """limit 이 있으면 시드로 limit 쌍을 무작위로 뽑습니다. 순서는 참조 세트 순서로 되돌립니다."""
    if limit is None or limit >= len(frame):
        return frame
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(frame), size=limit, replace=False))
    return frame.iloc[idx].reset_index(drop=True)


def main(argv: list[str] | None = None, *, call: Callable[..., dict] = jev_call) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refset", type=pathlib.Path, default=sev.REFSET)
    ap.add_argument("--metrics-file", type=pathlib.Path, default=sev.METRICS_FILE)
    ap.add_argument("--arm", choices=["novel", "blind"], default="novel",
                    help="novel 은 이름을 보이고 blind 는 DRUG_A, REACTION_1 로 가립니다")
    ap.add_argument("--limit", type=int, default=None, help="시드로 뽑은 N 쌍만 부릅니다")
    ap.add_argument("--sleep", type=float, default=0.0, help="호출 사이 쉬는 초")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--price-in", type=float, default=config.PRICE["jev"]["in"], help="입력 USD / 백만 토큰")
    ap.add_argument("--dry-run", action="store_true", help="네트워크 없이 비용만 찍고, 캐시에 없는 쌍은 확률 null 로 씁니다")
    ap.add_argument("--jev-cache", type=pathlib.Path, help="Jev 응답 JSON. 있으면 재생하고, 새로 받은 성공 응답을 덧붙입니다")
    ap.add_argument("--yes", action="store_true", help="비용을 확인했고 실제로 부릅니다")
    ap.add_argument("--repeats", type=int, default=None, help="귀무 반복 수. 기본은 참조 세트 값")
    ap.add_argument("--label", default=None, help="파일 이름 꼬리. 기본은 팔 이름(dry-run 은 _dryrun)")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    model = config.JEV_MODEL
    refset = sev.read_refset(args.refset)
    meta = refset["meta"]
    full, unmatched = sev.load_frame(refset["rows"], args.metrics_file)
    chosen = sample_rows(full, args.limit, meta["seed"])
    qs = questions()
    tokens = estimate_tokens([pair_state(r, blind=args.arm == "blind") for r in chosen.to_dict("records")], qs)
    cache = load_cache(args.jev_cache)
    cached = sum(cache_key(args.arm, model, d, p) in cache for d, p in zip(chosen["drug"], chosen["pt"]))
    new_tokens = tokens * (len(chosen) - cached) // max(len(chosen), 1)

    print(f"팔: {args.arm}, 질문: {QUESTION}, 모델: {model}")
    for line in cost_lines(len(chosen), tokens, args.price_in):
        print(line)
    if cached:
        print(f"캐시에 있는 쌍: {cached:,}, 새로 부를 쌍의 예상 비용 USD {new_tokens / 1e6 * args.price_in:.4f}")
    if not args.dry_run:
        if not args.yes:
            print("실제 호출은 --yes 를 붙여야 합니다. 멈춥니다.")
            return 2
        if not config.TYPESAFE_API_KEY and cached < len(chosen):
            print("TYPESAFE_API_KEY 가 비어 있습니다. 멈춥니다.")
            return 2

    rows = ask_pairs(chosen, arm=args.arm, model=model, dry_run=args.dry_run, cache=cache,
                     cache_path=args.jev_cache, call=call, timeout=args.timeout, sleep=args.sleep)
    if args.jev_cache is not None and cache:
        save_cache(args.jev_cache, cache)

    repeats = args.repeats if args.repeats is not None else meta["null_repeats"]
    result = evaluate(full, rows, seed=meta["seed"], repeats=repeats)
    n_prob = sum(r["probability"] is not None for r in rows)
    secs = [r["seconds"] for r in rows if r["source"] == "live" and r["seconds"] is not None]
    label = args.label or (f"{args.arm}_dryrun" if args.dry_run else args.arm)
    doc = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "pipeline/refsets/sider_jev.py",
        "caveat": "양성은 SIDER 라벨 기재, 음성은 라벨 부재입니다. novel 질문의 참은 '라벨에 없는 새 신호'라 "
                  "질문대로 답하면 양성의 확률이 낮습니다. auc 와 auc_inverted 를 함께 읽습니다.",
        "arm": args.arm, "blind": args.arm == "blind", "question": QUESTION, "question_spec": qs,
        "model_requested": model, "dry_run": args.dry_run,
        "refset": meta.get("name"), "warehouse_asof": meta["warehouse"]["asof"], "seed": meta["seed"],
        "limit": args.limit, "n_refset_rows": int(len(full)), "refset_rows_without_metrics_row": unmatched,
        "n_pairs": len(rows), "n_with_probability": n_prob, "n_failed_or_missing": len(rows) - n_prob,
        "estimate": {"input_tokens": tokens, "method": f"요청 JSON 글자 수 / {CHARS_PER_TOKEN}",
                     "price_in_usd_per_m": args.price_in, "usd": tokens / 1e6 * args.price_in},
        "seconds": sev.summarise(secs),
        "jev": result,
        "pairs": rows,
    }
    out = args.out or OUT / f"sider_jev_{label}_{date.today().isoformat()}.json"
    sev.write_json(out, doc, indent=None)
    print(f"{out.name}: 쌍 {len(rows):,}, 확률 있음 {n_prob:,}")
    if result:
        print(f"  Jev {args.arm} AUC {result['auc']:.3f} (뒤집으면 {result['auc_inverted']:.3f}), "
              f"귀무 평균 {result['null']['auc'].get('mean', float('nan')):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
