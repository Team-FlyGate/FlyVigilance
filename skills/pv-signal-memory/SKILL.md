---
name: "pv-signal-memory"
title: "PV Signal Memory"
version: "1.0.0"
description: "Use when a drug–event pair or a case needs its evidence bundle: FAERS 2x2 disproportionality from the warehouse, openFDA label sections that list the reaction, PubMed articles, the evidence grade and reference-set metrics, each returned with a citable evidence ID that System-2 memos must use. Do not use to interpret the evidence; interpretation belongs to pv-evidence-grade, pv-deliberate-assess and the human reviewer."
license: "Apache-2.0"
compatibility: "FAERS warehouse extract (api/_data/signals.json.gz), openFDA drug/label (api.fda.gov) and PubMed E-utilities (eutils.ncbi.nlm.nih.gov); no model computes a number. Literature typing reuses pv-literature-reading. Python 3.11+ with httpx."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "memory (mushroom body)"
  endpoint: "GET /api/signals/{drug} · POST /api/assess (bundle)"
  domain: "pharmacovigilance"
  tags:
    - pharmacovigilance
    - signal-detection
    - openfda
    - pubmed
    - evidence-ids
---

# PV Signal Memory

## When to Use

- Before `pv-deliberate-assess` writes a memo: the bundle defines the only evidence IDs the memo may cite.
- When a reviewer wants the top disproportionality rows for one drug (`GET /api/signals/{drug}`, `flygate signals`).

## Do Not Use

- To decide whether a signal is real or causal. The bundle carries numbers and quotes, not conclusions.

## Requirements

FAERS, openFDA and PubMed lookups need no credential. Literature typing inside the bundle uses `TYPESAFE_API_KEY` when it is set and leaves articles `not_judged` otherwise.

## Evidence IDs

The bundle covers up to 3 principal clinical reactions of the case. These are the only IDs a memo may cite:

- `faers:case:<primaryid>` — the case itself
- `faers:2x2:<DRUG>:<pt>@<asof>` — a, expected, PRR (95% CI), ROR025, Yates χ², IC, IC025, Evans/ROR/IC flags
- `label:<setid>` — the openFDA label record and the search scope used
- `label:<setid>#<section>` — quote around the reaction in boxed_warning / warnings_and_cautions / warnings / precautions / adverse_reactions (clinical trials, postmarketing, pooled); contraindications and indications are context only
- `pubmed:search:<pt>` — the PubMed query and hit count (a count is not evidence strength, R7)
- `pubmed:<pmid>#<design>` — an article typed by `pv-literature-reading` (`pubmed:<pmid>` when literature is not read)
- `grade:<DRUG>:<pt>@<asof>` — the evidence grade from `pv-evidence-grade`
- `metric:triple:<refset>@<asof>` — sensitivity, specificity and PPV of the triple criterion on a public reference set

Combination products use `+` in IDs (`DARATUMUMAB+HYALURONIDASE`). Implementation: `api/_fv/evidence.py::bundle`. Allowed hosts: api.fda.gov, eutils.ncbi.nlm.nih.gov. Tests: `tests/test_label_facts.py`, `tests/test_pvstats.py`.
