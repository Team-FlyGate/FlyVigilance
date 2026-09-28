---
name: "discovery-critic"
title: "Discovery Critic"
version: "1.0.0"
description: "Use to check any claim written from pre-market discovery runs (MSA-Search, OpenFold3, DiffDock, Boltz-2) before it reaches a reader: tier 1 checks evidence IDs against the actual run outputs, tier 2 checks every number against the raw NIM responses, and tier 3 asks NVIDIA Nemotron 3 Super whether the reasoning goes beyond the evidence. Returns the claim with a reason when it fails. Do not use to write claims or to decide whether a compound works."
license: "Apache-2.0"
compatibility: "nvidia/nemotron-3-super-120b-a12b (fallback nvidia/nemotron-3-ultra-550b-a55b) via NVIDIA NIM integrate.api.nvidia.com/v1/chat/completions in JSON mode; Python 3.11+ with FastAPI and httpx. Shares tiers 1 and 2 with the post-market critic api/_fv/assess.py."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "critic (GABAergic inhibition)"
  model: "nvidia/nemotron-3-super-120b-a12b"
  endpoint: "POST /api/discovery/critic"
  domain: "drug discovery"
  based_on: "Team-FlyGate pv-critic (same three tiers, discovery rule set)"
  tags:
    - drug-discovery
    - nemotron
    - verification
    - overclaim
    - guardrails
---

# Discovery Critic

## When to Use

- A claim cites a discovery run: "DiffDock reproduced the crystal pose at 0.71 Å", "Boltz-2 predicted pIC50 8.9".
- A reviewer wants to inject a claim on purpose to see whether the critic catches it.

## Do Not Use

- To write an assessment: the critic only checks.
- As a decision about a compound. A claim that passes is a claim that stays inside its evidence, nothing more.

## Requirements

`NVIDIA_API_KEY` for tier 3. Tiers 1 and 2 use no model and still run when the model is unavailable; a tier-3 failure is reported, never treated as a pass.

## Contract

- Input: `{"claims": [{"id","text","evidence":[...]}], "runs": {kind: processed result}}`. With no claims, the API builds a default set from this session's live runs (valid claims and deliberate overinterpretations).
- Tier 1 (`api/_fv/assess.py::tier1_rules`): every claim carries at least one evidence ID and every ID exists in the bundle built from the runs (`msa:`, `openfold3:`, `diffdock:`, `boltz2:`, `chembl:`, `vina:`).
- Tier 2 (`api/_fv/assess.py::tier2_oracle`): every number in the claim matches a number in the bundle within 1.1%. Numbers inside names (Boltz-2, PARP1, 4R6E, pIC50) are stripped first (`strip_entity_numbers`), coordinates are never put in the bundle.
- Tier 3: Nemotron judges the interpretation against nine discovery rules and returns JSON verdicts.

| Rule | Reject when the claim … |
| --- | --- |
| D1 | compares docking scores across proteins or infers selectivity from them |
| D2 | reads DiffDock confidence as binding strength |
| D3 | calls a predicted pIC50 a measurement |
| D4 | computes a correlation over fewer than eight paired points |
| D5 | treats co-crystal redocking as prospective prediction |
| D6 | treats an exploratory cross-docking pose as evidence of binding |
| D7 | carries a non-human protein result (COX-2 3LN1 is mouse) to humans |
| D8 | reads structure confidence (pLDDT) as binding strength |
| D9 | presents a prediction against a public crystal structure as blind prediction |

## Measured

| Model | 과잉해석 적발 | 정상 통과 | 소요 |
| --- | --- | --- | --- |
| nemotron-3-super-120b-a12b (recorded, 8 claims) | 4 / 4 | 3 / 4 | 41.8 s |
| nemotron-3.5-lightning-30b-a3b (recorded, 8 claims) | 0 / 4 | 1 / 4 | 294.5 s |
| nemotron-3-super-120b-a12b (live, 8 claims from this session's runs) | 4 / 4 | 4 / 4 | 6.9 s |

The Lightning model spent its output budget on reasoning before the verdict line, so Super is the judge.

## Limits

Numbers that match and rules that pass do not make a claim true; they make it bounded by its evidence.
Tests: `tests/test_discovery_api.py`.
