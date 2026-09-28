---
name: "pv-critic"
title: "PV Critic"
version: "1.0.0"
description: "Use to verify any AI-written pharmacovigilance claim: tier 1 evidence-ID rules, tier 2 numeric oracle against the evidence bundle, tier 3 overclaim judgment by the non-autoregressive judgment model plus two per-claim NVIDIA Nemotron safety guards (the stock Safety Guard and the pharmacovigilance BYO policy from pv-guardrail-policy). Returns the claim to its author with reasons when it fails. Do not use to write assessments or to decide causality."
license: "Apache-2.0"
compatibility: "nvidia/llama-3.1-nemotron-safety-guard-8b-v3 (fallback nvidia/nemotron-3.5-content-safety) and nvidia/nemotron-3.5-content-safety with the PV BYO policy (custom_policy) via NVIDIA NIM integrate.api.nvidia.com/v1/chat/completions; non-autoregressive judgment model (TypeSafe AI Jev, api.typesafe.ai/v1/systemone) for tier 3; Python 3.11+ with httpx."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "critic (GABAergic inhibition)"
  model: "nvidia/llama-3.1-nemotron-safety-guard-8b-v3 + nvidia/nemotron-3.5-content-safety (PV policy) + non-autoregressive judgment model"
  endpoint: "POST /api/critic"
  domain: "pharmacovigilance"
  tags:
    - pharmacovigilance
    - verification
    - guardrails
    - nemotron-safety-guard
    - overclaim
---

# PV Critic

## When to Use

- A Nemotron memo from `pv-deliberate-assess` must be checked before it reaches a reviewer.
- A reviewer or test wants to inject claims directly (`POST /api/critic` with `{claims, state, bundle}`, or `flygate critic`).

## Do Not Use

- To generate claims or narratives; the critic only accepts or returns them.
- As a replacement for the human safety reviewer; a pass means the claim stays inside its evidence, not that it is clinically correct.

## Requirements

Requires an NVIDIA API key (`NVIDIA_API_KEY`, build.nvidia.com) for the safety guard and a judgment-model API key (`TYPESAFE_API_KEY`) for tier 3. Without them the API answers 503 "not configured" and nothing is marked safe. Keep keys in the environment or an OpenShell provider, never in prompts or logs.

## Tiers

| Tier | Checks | Model |
|---|---|---|
| T1 rules | memo has at least one claim (an unparseable or empty memo is returned, never passed); each claim is non-empty, has evidence IDs, and every ID exists in the bundle | none |
| T2 numeric oracle | every number in the claim matches a number in the case or bundle (±1.1%); four-digit years are skipped | none |
| T3 overclaim | per-claim `noul` "violates a rule?" + `choice` "which rule" over R1–R13; flagged when p ≥ 0.5 and the rule is not `none` | judgment model |
| Guards | each claim and the narrative separately, two guards in parallel: `nvidia/llama-3.1-nemotron-safety-guard-8b-v3` (fallback `nvidia/nemotron-3.5-content-safety` default taxonomy) and `nvidia/nemotron-3.5-content-safety` with the PV BYO policy (`pv-guardrail-policy`, PV-1..PV-5). Either guard firing returns the claim; a PV category maps to its rule (PV-1 ⇒ R11, PV-2 ⇒ R1, PV-3 ⇒ R2, PV-4, PV-5), otherwise R11 | NVIDIA NIM |

Rules R1–R13 live in `api/_fv/assess.py::OVERCLAIM_RULES` (disproportionality ≠ causation, no incidence from FAERS, no cross-drug ranking, evidence grade is population context, …).

## Operating Rules

- **Evidence IDs**: before T1, an ID copied together with its catalog description (`ID :: description`) is cut back to the ID. The ID itself must still match exactly. FAERS combination products use `+` in IDs (`DARATUMUMAB+HYALURONIDASE`) because a raw backslash breaks the writer's JSON.
- **Guard granularity**: the guard runs per claim. When the whole memo was joined into one string, a single treatment-advice sentence was judged safe in 8 of 8 memos.
- **Time budget**: deliberation gets 100 s in total and the guard stage 20 s, to fit the 120 s serverless limit. If neither guard fires but either one fails or returns an unreadable verdict, the result is "human check", never "safe".
- **Rewrite**: a returned memo goes back to the writer once with the reasons. If it still fails, it reaches the human queue with the reasons attached.

## Measured

`pipeline/bench/critic_probe.py` takes 8 real death/serious FAERS cases and injects four wrong claims into each: a causal claim from PRR, an invented incidence, a fake label ID, and individual treatment advice. All 31 were caught. All 6 controls (Nemotron claims that had passed the critic) passed. Output: `web/public/data/critic_probe.json`. The guard layer alone is measured in `pipeline/bench/guard_policy_eval.py` (`web/public/data/guard_policy_eval.json`): with the PV policy the combined guards catch 7/7 causal claims from PRR, 8/8 invented incidences and 8/8 treatment-advice claims; fake evidence IDs are left to tier 1. Offline unit tests: `tests/test_critic.py`, `tests/test_guard_policy.py`.
