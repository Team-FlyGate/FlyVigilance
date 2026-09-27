---
name: pv-deliberate-assess
description: Use when triage escalates a case to System-2 — NVIDIA Nemotron writes an evidence-bound case assessment (claims JSON with evidence IDs, narrative, open questions) that is then checked by the pv-critic skill.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: deliberate (central complex)
  model: nvidia/nemotron-3-super-120b-a12b (fallback ultra-550b, 3.5-lightning-30b)
  endpoint: https://integrate.api.nvidia.com/v1/chat/completions
  tags: [pharmacovigilance, nemotron, nim, system-2]
---

# PV Deliberate Assess

- Called only for `expedite` / `signal_review` actions (or on explicit reviewer request).
- Prompt carries the 12 interpretation rules; output is JSON only: `claims[{id,text,evidence[]}]`, `assessment`, `narrative`, `open_questions`.
- Thinking disabled (`chat_template_kwargs.enable_thinking=false`) to keep latency bounded.
- If the critic rejects, the issues are fed back once for a revision round.
- `POST /api/assess` with `{case, triage}`.
