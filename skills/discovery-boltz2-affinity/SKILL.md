---
name: "discovery-boltz2-affinity"
title: "Discovery Boltz-2 Affinity"
version: "1.0.0"
description: "Use to predict a protein-ligand complex and a binding affinity (pIC50 and binding probability) with the hosted NVIDIA BioNeMo Boltz-2 NIM, and to place that prediction next to the measured ChEMBL pChEMBL median and a 39-compound PARP1 benchmark. Do not present a predicted pIC50 as a measured affinity and do not compare predictions across targets."
license: "Apache-2.0"
compatibility: "NVIDIA BioNeMo Boltz-2 NIM (health.api.nvidia.com/v1/biology/mit/boltz2/predict), NVIDIA_API_KEY; Python 3.11+ with FastAPI and httpx, mmCIF reading in api/_fv/molgeom.py. Follows NVIDIA-BioNeMo/bionemo-agent-toolkit boltz2-nim."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "memory (evidence comparison)"
  model: "Boltz-2 (NVIDIA BioNeMo NIM)"
  endpoint: "POST /api/discovery/boltz2"
  domain: "drug discovery"
  based_on: "NVIDIA-BioNeMo/bionemo-agent-toolkit boltz2-nim"
  tags:
    - drug-discovery
    - bionemo-nim
    - boltz2
    - affinity
    - chembl
---

# Discovery Boltz-2 Affinity

## When to Use

- A candidate needs a predicted affinity next to the measured value for the same molecule and target.
- A complex structure with an affinity head is wanted in one call.

## Do Not Use

- To report a measured affinity: `affinity_pic50` is a prediction (rule D3). Measured values come from ChEMBL.
- To compare a prediction for one target with a prediction for another (rule D1), or to read pLDDT as binding strength (rule D8).

## Requirements

`NVIDIA_API_KEY`. Affinity is predicted for exactly one ligand per request, as the official skill states.

## Contract

- Request (NVIDIA official skill shape): `{"polymers":[{"id":"A","molecule_type":"protein","sequence","msa":{"msa_search":{"a3m":{"alignment","format":"a3m","rank":0}}}}],"ligands":[{"id":"L1","smiles","predict_affinity":true}],"recycling_steps":3,"sampling_steps":50,"diffusion_samples":1,"step_scale":1.638,"output_format":"mmcif"}`. The A3M record uses `alignment`/`format`/`rank`, never a stale `data` field.
- Response is read as `affinities.L.affinity_pic50`, `affinity_probability_binary`, `affinity_pred_value`, plus `confidence_scores`, `complex_plddt_scores`, `iptm_scores`, and the mmCIF structure.
- The screen shows the complex (CA trace by pLDDT plus the ligand) and a scatter of predicted pIC50 against the ChEMBL pChEMBL median for the 39-compound PARP1 benchmark.

## Measured

| Run | 예측 pIC50 | 결합 확률 | ipTM | ChEMBL 실측 중앙값 |
| --- | --- | --- | --- | --- |
| 2026-09-28 (recorded) | 7.98 | 0.609 | 0.946 | 7.79 (n=27) |
| 2026-09-28 (live, this skill) | 7.686 | 0.594 | 0.948 | 7.79 (n=27) |

Benchmark (PARP1, n=39, ChEMBL IC50): Spearman 0.767, Pearson 0.746, MAE 0.71 log, EF(top 25%) 2.41 (5/9), sensitivity/specificity at pIC50 ≥ 7 = 0.80 / 0.86.

## A target chosen on screen

`custom_target` carries the sequence (sliced to the chosen range) and `custom_ligand` carries a PubChem SMILES or a pasted one. There is no ChEMBL median for most such pairs, so the screen shows the prediction alone and says `대조값 없음` rather than inventing a comparison.

## Limits

The benchmark is one target and 39 compounds. Run-to-run variation is real: the same input gave 7.98 and 7.686 on the same day.
Tests: `tests/test_discovery_api.py`.
