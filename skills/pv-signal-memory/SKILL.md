---
name: pv-signal-memory
description: Use when a drug–event pair needs evidence — FAERS 2x2 disproportionality from the warehouse, openFDA label sections that mention the reaction, and PubMed hits — each returned with a citable evidence ID.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: memory (mushroom body)
  tags: [pharmacovigilance, signal-detection, openfda, pubmed]
---

# PV Signal Memory

Evidence IDs (the only IDs a memo may cite):
- `faers:2x2:<DRUG>:<pt>@<asof>` — a, expected, PRR (95% CI), ROR (95% CI), Yates χ², IC, IC025, Evans/ROR/IC flags
- `label:<setid>#<section>` — quote around the reaction in boxed_warning / warnings_and_cautions / adverse_reactions …
- `pubmed:<pmid>` — top relevance PMIDs for `"<drug>"[tiab] AND "<pt>"[tiab]`
- `faers:case:<primaryid>` — the case itself

Implementation: `api/_fv/evidence.py::bundle`. Allowed hosts: api.fda.gov, eutils.ncbi.nlm.nih.gov.
