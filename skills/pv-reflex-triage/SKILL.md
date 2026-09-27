---
name: pv-reflex-triage
description: Use when an ICSR needs an immediate triage decision — seriousness, expectedness, WHO-UMC causality, special situation, priority and next action — returned as typed calibrated probabilities from Jev (System-1) in one call.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: reflex (lateral horn)
  model: typesafe jev-latest
  tags: [pharmacovigilance, triage, jev, system-1]
---

# PV Reflex Triage

## Contract
- Input: one case (`api/_fv/triage.py::case_state`).
- Rule gate first: ICH minimum four elements are checked from structured fields (`validity`). Never ask a model what a rule can compute.
- One Jev call with 7 typed questions: `serious`, `expected`, `deep` (noul) · `causality`, `special`, `route` (choice) · `priority` (score, 4 levels).
- `route_policy` maps probabilities to an action with human-readable reasons:
  - serious ≥ 0.5 and expected < 0.5 → `expedite` (System-2 + human)
  - priority ≥ 2.5 → `expedite`
  - route = signal_review, deep ≥ 0.5, or confidence < 0.55 → `signal_review` (System-2)
  - otherwise `monitor` / `close`

## Endpoint
`POST /api/triage` with the case JSON.

## Limits
Jev probabilities are population-calibrated, not certainty for one case (rule R10).
