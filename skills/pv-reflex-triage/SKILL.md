---
name: "pv-reflex-triage"
title: "PV Reflex Triage"
version: "1.0.0"
description: "Use when an ICSR needs an immediate triage decision: seriousness, expectedness, WHO-UMC causality, special situation, priority and next action, returned as typed calibrated probabilities from the non-autoregressive judgment model (System-1) in one call, then routed by a deterministic policy with label grounding, an EMA DME safety net and US/KR expedited-reporting regimes. Do not use for a written case assessment or a final regulatory decision."
license: "Apache-2.0"
compatibility: "Non-autoregressive judgment model (TypeSafe AI Jev jev-latest, api.typesafe.ai/v1/systemone), one call with 7 typed questions; openFDA drug/label (api.fda.gov) for expectedness grounding; Python 3.11+ with FastAPI and httpx."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "reflex (lateral horn)"
  model: "non-autoregressive judgment model (System-1)"
  endpoint: "POST /api/triage"
  domain: "pharmacovigilance"
  tags:
    - pharmacovigilance
    - triage
    - icsr
    - system-1
    - calibrated-probabilities
---

# PV Reflex Triage

## When to Use

- A new ICSR (FAERS case JSON, or a Korean report structured by `pv-kr-intake-causality`) must be sorted into `expedite`, `signal_review`, `monitor`, `close` or `follow_up` within seconds, with reasons.

## Do Not Use

- To write the case narrative or claims; escalate to `pv-deliberate-assess`.
- As the final seriousness, causality or reporting decision; `expedite` always goes to a human.

## Requirements

Requires a judgment-model API key (`TYPESAFE_API_KEY`). Without it the API answers 503 "not configured". openFDA needs no credential. Keep keys in the environment or an OpenShell provider, never in prompts or logs.

## Contract

- Input: one case (`api/_fv/triage.py::case_state`). `POST /api/triage` with the case JSON; add `?regime=KR` for the Korean rule.
- Rule gate first: ICH minimum four elements are checked from structured fields (`validity`). Never ask a model what a rule can compute. A missing element returns `follow_up` (a human handles it first when the case looks serious).
- Label grounding: the primary suspect's openFDA label is checked for up to 5 clinical reactions. When the label is found, expectedness is set by rule (all top-3 reactions listed → expected) and overrides the model's memory.
- One judgment-model call with 7 typed questions: `serious`, `expected`, `deep` (noul) · `causality`, `special`, `route` (choice) · `priority` (score, 4 levels).
- `route_policy` maps probabilities to an action with human-readable reasons:
  - US: serious ≥ 0.5 and expected < 0.5 → `expedite` with the 15-day deadline (21 CFR 314.80)
  - KR: serious ≥ 0.5 → `expedite` with the 15-day deadline unless WHO-UMC is `unlikely` with confidence ≥ 0.55 (then immediate human check)
  - priority ≥ 2.5 → `expedite` (human review, no 15-day deadline)
  - route = signal_review, deep ≥ 0.5, or confidence < 0.55 → `signal_review` (System-2)
  - otherwise `monitor` / `close`
  - A reported EMA designated medical event (DME) sends the case to human review regardless of scores.

## Limits

Judgment-model probabilities are population-calibrated, not certainty for one case (rule R10). Tests: `tests/test_routing.py`.
