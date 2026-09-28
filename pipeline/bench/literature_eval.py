"""문헌 읽기 단계의 Jev 판단을 검증합니다.

정답: PubMed(MEDLINE) 색인자가 붙인 출판 유형(Randomized Controlled Trial, Meta-Analysis, Case Reports, Review).
방법: 출판 유형을 가린 채 제목과 초록만 Jev 에 주고 연구 설계를 고르게 합니다(FlyVigilance 가 쓰는 같은 질문).
대상: 웨어하우스 3중 신호 상위 쌍의 PubMed 관련도 상위 문헌.
산출물: web/public/data/literature_eval.json
"""
import asyncio
import json
import pathlib
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from _fv import clients, evidence, literature  # noqa: E402
from _fv.labeltext import is_nonclinical as literature_nonclinical  # noqa: E402

CLASSES = ["meta_analysis", "rct", "case_report", "review"]
GROUP = {"meta_analysis": "analytic", "rct": "analytic", "cohort": "analytic", "case_control": "analytic",
         "case_report": "anecdotal", "case_series": "anecdotal", "review": "review", "pharmacovigilance": "other",
         "preclinical": "other", "other": "other"}


async def main():
    ov = json.loads((ROOT / "web/public/data/faers/overview.json").read_text())
    pairs = [(s["drug"], s["pt"]) for s in ov["top_signals"][:60]]
    # 보고가 많은 약물 상위 150개에서 3중 신호가 선 가장 흔한 반응 하나씩을 더합니다
    sig = evidence._signals()
    cols = sig["columns"]
    for drug, _ in sorted(sig["n_drug"].items(), key=lambda t: -t[1])[:150]:
        for r in sig["drugs"][drug]:
            rec = dict(zip(cols, r))
            if rec["evans"] and rec["ror_sig"] and rec["ic_sig"] and not literature_nonclinical(rec["pt"]):
                pairs.append((drug, rec["pt"]))
                break
    pairs = list(dict.fromkeys(pairs))
    arts = []
    async with httpx.AsyncClient() as c:
        for drug, pt in pairs:
            srch = await evidence.pubmed(drug, pt, c, retmax=8)
            if not srch.get("pmids"):
                continue
            st, body = await evidence.get_json(c, "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                                               {"db": "pubmed", "id": ",".join(srch["pmids"]), "retmode": "xml"},
                                               evidence.PUBMED, key=f"pubmed_fetch_{'_'.join(srch['pmids'])}")
            for a in (literature.parse_efetch(body) if st == 200 and isinstance(body, str) else []):
                if a["design_rule"] in CLASSES and a["abstract"] and a["pmid"] not in {x["pmid"] for x in arts}:
                    arts.append({**a, "drug": drug, "pt": pt})
    print(f"articles with indexed design: {len(arts)}")

    async def judge(batch):
        blocks = [f"[Article {i}] Title: {a['title']}\nAbstract: {a['abstract'][:1600]}" for i, a in enumerate(batch)]
        qs = {f"a{i}_design": {"type": "choice", "instructions": f"What is the study design of Article {i}?",
                               "criteria": literature.DESIGNS} for i in range(len(batch))}
        r = await clients.jev("\n\n".join(blocks), qs)
        return [(r["answers"][f"a{i}_design"]["choice"], r["answers"][f"a{i}_design"]["confidence"]) for i in range(len(batch))], r["latency_ms"]

    batches = [arts[i:i + 6] for i in range(0, len(arts), 6)]
    sem = asyncio.Semaphore(8)

    async def run(b):
        async with sem:
            return await judge(b)
    t0 = time.time()
    outs = await asyncio.gather(*(run(b) for b in batches))
    wall = time.time() - t0
    preds, lats = [], []
    for b, (res, lat) in zip(batches, outs):
        lats.append(lat)
        for a, (p, conf) in zip(b, res):
            preds.append({"pmid": a["pmid"], "truth": a["design_rule"], "pred": p, "confidence": conf, "year": a["year"]})
    acc = sum(p["pred"] == p["truth"] for p in preds) / len(preds)
    gacc = sum(GROUP[p["pred"]] == GROUP[p["truth"]] for p in preds) / len(preds)
    per = {c: {"n": sum(p["truth"] == c for p in preds),
               "recall": (sum(p["truth"] == c and p["pred"] == c for p in preds) / max(1, sum(p["truth"] == c for p in preds)))}
           for c in CLASSES}
    labels = CLASSES + sorted({p["pred"] for p in preds} - set(CLASSES))
    conf = {t: {q: sum(1 for p in preds if p["truth"] == t and p["pred"] == q) for q in labels} for t in CLASSES}
    out = {"generated": time.strftime("%Y-%m-%d %H:%M"), "n": len(preds), "accuracy": round(acc, 4),
           "group_accuracy": round(gacc, 4), "per_class": per, "confusion": conf, "labels": labels,
           "calls": len(batches), "articles_per_call": 6, "latency_ms_p50": sorted(lats)[len(lats) // 2], "wall_s": round(wall, 1),
           "truth_source": "PubMed publication type (MEDLINE indexing)", "pairs": len(pairs), "predictions": preds}
    (ROOT / "web/public/data/literature_eval.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "predictions"}, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
