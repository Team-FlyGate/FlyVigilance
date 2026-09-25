---
name: pv-guardrail-policy
description: Use when configuring the FlyVigilante content-safety policy — custom pharmacovigilance categories layered on NVIDIA Nemotron safety guard, following the nemotron-policy-generator skill's BYO-policy pattern.
license: Apache-2.0
metadata:
  author: FlyVigilante
  based_on: NVIDIA/skills nemotron-policy-generator
  tags: [guardrails, nemotron-content-safety, pharmacovigilance]
---

# PV Guardrail Policy

Custom categories (in addition to the guard model's defaults):

| ID | Category | Action |
|---|---|---|
| PV-1 | Individual treatment, dosing or discontinuation advice | block (R11) |
| PV-2 | Causal claim from disproportionality alone | return to author (R1) |
| PV-3 | Incidence/risk estimate from spontaneous reports | return to author (R2) |
| PV-4 | Re-identification attempt of a reporter or patient | block |
| PV-5 | Tool/network use outside allowed hosts | deny + audit |

Allowed egress: `api.fda.gov`, `eutils.ncbi.nlm.nih.gov`, `api.typesafe.ai`, `integrate.api.nvidia.com`.
