---
name: pv-critic
description: Use to verify any AI-written pharmacovigilance claim — tier 1 evidence-ID rules, tier 2 numeric oracle against the evidence bundle, tier 3 overclaim judgment (Jev) plus NVIDIA safety guard — and return the claim to its author with reasons when it fails.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: critic (GABAergic inhibition)
  tags: [pharmacovigilance, verification, guardrails]
---

# PV Critic

| Tier | Checks | Model |
|---|---|---|
| T1 rules | claim non-empty, has evidence IDs, every ID exists in the bundle | none |
| T2 numeric oracle | every number in the claim matches a number in the case or bundle (±1.1%) | none |
| T3 overclaim | per-claim `noul` "violates a rule?" + `choice` "which rule" over R1–R12 | Jev |
| Guard | memo text → `nvidia/llama-3.1-nemotron-safety-guard-8b-v3`; "Unauthorized Advice" ⇒ R11 | NVIDIA NIM |

Rules R1–R12 live in `api/_fv/assess.py::OVERCLAIM_RULES` (disproportionality ≠ causation, no incidence from FAERS, no cross-drug ranking, …).
