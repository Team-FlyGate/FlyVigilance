"""쇼릴 v2 를 파일 하나로 완결된 HTML 로 만듭니다.

템플릿(scripts/reel/showreel_v2.template.html)에 뇌 점구름과 실측 수치를 JSON 으로 넣습니다.
외부 폰트, CDN, fetch 를 쓰지 않으므로 파일만 따로 전달해도 어디서나 그대로 재생됩니다.

사용: build_reel_v2.py [출력 경로]
입력: web/public/showreel/brain_pts.json, web/public/data/{bench,validation,literature_eval,critic_probe,demo_case_v2}.json,
      web/public/data/faers/{overview,backtest}.json
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUB = ROOT / "web/public"
TEMPLATE = ROOT / "scripts/reel/showreel_v2.template.html"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else PUB / "showreel/FlyVigilance_showreel_v2.0.0.html"


def load(rel: str):
    return json.loads((PUB / rel).read_text())


def demo_part(d: dict) -> dict:
    """데모 케이스에서 화면에 쓰는 필드만 남깁니다."""
    c, t, a = d["case"], d["triage"], d["assess"]
    g = t.get("grounding") or {}
    lab = g.get("label") or {}
    ev = a.get("evidence", {})
    return {
        "case": {"primaryid": c["primaryid"], "quarter": c.get("quarter"), "age": c.get("age"), "sex": c.get("sex"),
                 "country": c.get("country"), "drugs": [{"drug": x["drug"], "role": x["role"]} for x in c["drugs"][:4]],
                 "reactions": c["reactions"][:6], "outcomes": c.get("outcomes", [])},
        "triage": {
            "suspect": t["suspect"], "latency_ms": t["jev"]["latency_ms"],
            "answers": {k: t["jev"]["answers"][k] for k in ("serious", "expected", "deep", "causality", "priority", "route")},
            "decision": {k: t["decision"].get(k) for k in ("action", "reasons", "deadline")},
            "grounding": {"found": lab.get("found", False), "brand": lab.get("brand"), "effective": lab.get("effective"),
                          "by_pt": {pt: v["sections"] for pt, v in (lab.get("by_pt") or {}).items()},
                          "expected": g.get("expected"), "source": g.get("expected_source"),
                          "latency_ms": g.get("latency_ms")},
        },
        "assess": {
            "verdict": a["verdict"],
            "rounds": [{"round": r["round"], "model": r["model"], "latency_ms": r["latency_ms"], "issues": len(r["issues"])}
                       for r in a["rounds"]],
            "claims": [{"id": x.get("id"), "text": x.get("text", ""), "evidence": x.get("evidence", [])[:2]}
                       for x in a["memo"].get("claims", [])[:4]],
            "grades": [{"pt": x["pt"], "grade": x["grade"], "grade_name": x["grade_name"],
                        "regulatory": x["axes"]["regulatory_name"], "signal": x["axes"]["signal"]}
                       for x in ev.get("grades", [])],
            "evidence_ms": a.get("evidence_ms"),
        },
        "total_ms": d.get("total_ms"),
    }


def main():
    pts = load("showreel/brain_pts.json")
    ov = load("data/faers/overview.json")
    bench = load("data/bench.json")
    val = load("data/validation.json")
    lit = load("data/literature_eval.json")
    bt = load("data/faers/backtest.json")
    demo = load("data/demo_case_v2.json")
    probe_path = PUB / "data/critic_probe.json"
    probe = json.loads(probe_path.read_text()) if probe_path.exists() else None

    ab = bench["ablation"]
    g = ab["grounding"]
    sets = []
    for k, r in val["refsets"].items():
        m = {x["key"]: x for x in r["methods"]}
        best = max((x for x in r["methods"] if x["family"] == "metric"), key=lambda x: x["auc"])
        sets.append({"key": k, "n": r["n"], "pos": r["pos"], "best": {"label": best["label"], "auc": best["auc"]},
                     "raw_blind": m["raw_blind"]["auc"], "fv": m["fv"]["auc"], "named": m["raw_named"]["auc"],
                     "model_beats_best": any(d.get("best_metric") and d["ci"][0] > 0 for d in r["deltas"]),
                     "model_below_best": [d["a"] for d in r["deltas"] if d.get("best_metric") and d["ci"][1] < 0]})
    pro = val["refsets"]["Harpaz-prospective"]
    omop = {x["key"]: x["auc"] for x in val["refsets"]["OMOP"]["methods"]}
    ds = bench["dataset"]
    data = {
        "pts": pts,
        "ov": {k: ov[k] for k in ("asof", "first", "quarters", "raw_reports", "cases", "deleted_cases", "triplets", "pairs", "all3")}
              | {"q_reports": ov["per_quarter"][-1]["reports"]},
        "bench": {
            "n": ds["cases"], "serious": round(ds["cases"] * ds["serious_rate"]), "source": ds["source"],
            "jev_p50": bench["jev_triage"]["latency_ms"]["p50"], "usd1k": bench["jev_triage"]["usd_per_1k"],
            "throughput": bench["jev_triage"]["throughput_cases_per_s"],
            "nim_p50": bench["nemotron"]["triage"]["latency_ms"]["p50"], "nim_n": bench["nemotron"]["triage"]["n"],
            "nim_model": bench["nemotron"]["model"],
            "blind_auroc": bench["blind_serious"]["jev"]["auroc"], "blind_n": bench["blind_serious"]["jev"]["n"],
            "arms": {k: ab[k] for k in ("raw_jev", "flyvigilance_ungrounded", "flyvigilance")}, "routes": ab["routes"],
            "grounding": {"label_found": g["label_found"], "cases": g["cases"], "mem": g["memory_vs_label"],
                          "label_p50": g["label_latency_ms"]["p50"]},
        },
        "val": {"sets": sets, "omop_named": omop["raw_named"], "omop_blind": omop["raw_blind"],
                "pro": {"pos": pro["pos"], "neg": pro["neg"], "N": pro["N"], **pro["points"]["triple"]}},
        "lit": {"n": lit["n"], "accuracy": lit["accuracy"], "group_accuracy": lit["group_accuracy"]},
        "probe": {"n_cases": probe["n_cases"], "summary": probe["summary"]} if probe else None,
        "bt": [{"drug": x["drug"], "pt": x["pt"], "lead": x["lead_days"]} for x in bt["items"]],
        "demo": demo_part(demo),
    }
    html = TEMPLATE.read_text()
    marker = "/*__DATA__*/null"
    assert html.count(marker) == 1, "template data marker missing"
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    OUT.write_text(html.replace(marker, blob))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
