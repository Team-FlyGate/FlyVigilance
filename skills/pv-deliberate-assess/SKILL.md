---
name: "pv-deliberate-assess"
title: "PV Deliberate Assess"
version: "1.0.0"
description: "Use when triage escalates a case to System-2: NVIDIA Nemotron writes an evidence-bound case assessment (3 to 6 claims with evidence IDs, assessment, narrative, open questions) from the evidence bundle only, and the pv-critic skill checks it before a human sees it. Do not use for routine cases that triage closes or monitors, or for regulatory submission text."
license: "Apache-2.0"
compatibility: "nvidia/nemotron-3-super-120b-a12b, falling back to nvidia/nemotron-3-ultra-550b-a55b and nvidia/nemotron-3.5-lightning-30b-a3b, via NVIDIA NIM integrate.api.nvidia.com/v1/chat/completions (JSON mode, thinking disabled); Python 3.11+ with FastAPI and httpx."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "deliberate (central complex)"
  model: "nvidia/nemotron-3-super-120b-a12b (fallback ultra-550b, 3.5-lightning-30b)"
  endpoint: "https://integrate.api.nvidia.com/v1/chat/completions"
  domain: "pharmacovigilance"
  tags:
    - pharmacovigilance
    - nemotron
    - nim
    - system-2
    - evidence-bound-generation
---

# PV Deliberate Assess

## When to Use

- `pv-reflex-triage` returned `expedite` or `signal_review`, or a reviewer explicitly asks for a written assessment.

## Do Not Use

- For `monitor` / `close` cases; the reflex decision and its reasons are the record there.
- As a final causality or reporting decision; the memo is a draft for a human reviewer.

## Requirements

Requires an NVIDIA API key (`NVIDIA_API_KEY`, build.nvidia.com) for Nemotron and a judgment-model API key (`TYPESAFE_API_KEY`) for the critic that follows. Without them the API answers 503 "not configured". Keep keys in the environment or an OpenShell provider, never in prompts or logs.

## Instructions

1. `POST /api/assess` with `{case, triage}` (the triage response). The API first builds the evidence bundle with `pv-signal-memory` (`api/_fv/evidence.py::bundle`).
2. The system prompt carries the 13 interpretation rules (R1–R13) and the list of allowed evidence IDs. Output is JSON only: `claims[{id,text,evidence[]}]` (3 to 6 claims), `assessment`, `narrative` (≤ 80 words), `open_questions`.
3. Thinking is disabled (`chat_template_kwargs.enable_thinking=false`) and JSON mode is requested to keep latency bounded; the model chain falls back on 503 or timeout.
4. `pv-critic` checks the memo. If it is returned, the issues are fed back once for a revision round (skipped when less than 35 s of the 100 s budget remain).
5. The response carries `verdict` (`pass` / `returned`), every round with model, latency and token usage, the guard result and the evidence bundle.

Implementation: `api/_fv/assess.py::assess`.
