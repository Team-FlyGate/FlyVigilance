---
name: pv-critic
description: Use to verify any AI-written pharmacovigilance claim — tier 1 evidence-ID rules, tier 2 numeric oracle against the evidence bundle, tier 3 overclaim judgment (Jev) plus a per-claim NVIDIA safety guard — and return the claim to its author with reasons when it fails.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: critic (GABAergic inhibition)
  tags: [pharmacovigilance, verification, guardrails]
---

# PV Critic

| Tier | Checks | Model |
|---|---|---|
| T1 rules | memo has at least one claim (an unparseable or empty memo is returned, never passed); each claim is non-empty, has evidence IDs, and every ID exists in the bundle | none |
| T2 numeric oracle | every number in the claim matches a number in the case or bundle (±1.1%) | none |
| T3 overclaim | per-claim `noul` "violates a rule?" + `choice` "which rule" over R1–R13 | Jev |
| Guard | each claim and the narrative separately → `nvidia/llama-3.1-nemotron-safety-guard-8b-v3` (fallback `nvidia/nemotron-3.5-content-safety`); "Unauthorized Advice" ⇒ R11 on that claim | NVIDIA NIM |

Rules R1–R13 live in `api/_fv/assess.py::OVERCLAIM_RULES` (disproportionality ≠ causation, no incidence from FAERS, no cross-drug ranking, evidence grade is population context, …).

## Operating rules

- **Evidence IDs**: before T1, an ID copied together with its catalog description (`ID :: description`) is cut back to the ID. The ID itself must still match exactly. FAERS combination products use `+` in IDs (`DARATUMUMAB+HYALURONIDASE`) because a raw backslash breaks the writer's JSON.
- **Guard granularity**: the guard runs per claim. When the whole memo was joined into one string, a single treatment-advice sentence was judged safe in 8 of 8 memos.
- **Time budget**: deliberation gets 100 s in total and the guard 20 s, to fit the 120 s serverless limit. If both guards fail or the verdict cannot be read, the result is "human check", never "safe".
- **Rewrite**: a returned memo goes back to the writer once with the reasons. If it still fails, it reaches the human queue with the reasons attached.

## Measured

`pipeline/bench/critic_probe.py` takes 8 real death/serious FAERS cases and injects four wrong claims into each: a causal claim from PRR, an invented incidence, a fake label ID, and individual treatment advice. All 31 were caught. All 6 controls (Nemotron claims that had passed the critic) passed. Output: `web/public/data/critic_probe.json`.
