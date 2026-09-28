---
name: "discovery-openfold3"
title: "Discovery OpenFold3 Structure"
version: "1.0.0"
description: "Use to predict a protein-ligand complex structure for a pre-market candidate: sends the target sequence with the MSA-Search A3M alignment and the ligand SMILES to the hosted NVIDIA BioNeMo OpenFold3 NIM, then scores the prediction against the public crystal structure with a symmetry-aware CA RMSD after Kabsch superposition. Do not use to claim binding strength, affinity or blind-prediction accuracy."
license: "Apache-2.0"
compatibility: "NVIDIA BioNeMo OpenFold3 NIM (health.api.nvidia.com/v1/biology/openfold/openfold3/predict), NVIDIA_API_KEY; Python 3.11+ with FastAPI and httpx, pure-Python geometry in api/_fv/molgeom.py (no RDKit or numpy). Follows NVIDIA/skills bionemo-msa-structure-prediction-pipeline step 2 and NVIDIA-BioNeMo/bionemo-agent-toolkit openfold3-nim."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "encode (feature encoding)"
  model: "OpenFold3 (NVIDIA BioNeMo NIM)"
  endpoint: "POST /api/discovery/openfold3"
  domain: "drug discovery"
  based_on: "NVIDIA/skills bionemo-msa-structure-prediction-pipeline"
  tags:
    - drug-discovery
    - bionemo-nim
    - openfold3
    - structure-prediction
    - plddt
---

# Discovery OpenFold3 Structure

## When to Use

- The alignment from `discovery-msa-search` is in hand and the complex structure is the next step.
- A predicted pose or complex has to be compared with a public crystal structure.

## Do Not Use

- As evidence of binding strength. pLDDT and pTM are structure confidence, not affinity (rule D8).
- As a blind-prediction benchmark: 4R6E is public and may be in the model's training data (rule D9).

## Requirements

`NVIDIA_API_KEY`. OpenFold2 is not used here: its endpoint returned HTTP 500 (CUDA illegal memory access) on six attempts in the recorded run, so the pipeline goes MSA-Search → OpenFold3 as the official skill describes.

## Contract

- Request (NVIDIA official skill shape): `{"inputs":[{"input_id","output_format":"pdb","molecules":[{"type":"protein","id":"A","sequence","diffusion_samples":1,"msa":{"uniref30":{"a3m":{"alignment","format":"a3m"}}}},{"type":"ligand","id":"L","smiles"}]}]}` — one input, 1–32 molecules, alignment starting with a FASTA header.
- Response is read as `outputs[0].structures_with_scores[0]` (`confidence_score`, `complex_plddt_score`, `ptm_score`, `iptm_score`, `complex_pde_score`) exactly as the official skill documents.
- Scoring (`api/_fv/molgeom.py`): sequence alignment pairs predicted CA with crystal CA, Kabsch superposition (Horn quaternion + Jacobi) gives the CA RMSD, and the ligand is scored with a symmetry-aware heavy-atom RMSD after the same transform.
- The screen receives the CA trace in the crystal frame, per-residue pLDDT, the ligand atoms and bonds, and the crystal overlay.

## Measured

| Run | pLDDT | pTM / ipTM | CA RMSD vs 4R6E | Ligand RMSD |
| --- | --- | --- | --- | --- |
| 2026-09-28 (recorded) | 95.95 | 0.828 / 0.658 | 1.0 Å (350 CA) | 1.16 Å |
| 2026-09-28 (live, this skill) | 95.95 | 0.8279 / 0.6577 | 0.997 Å (350 CA) | 1.156 Å |

Pure-Python geometry reproduces the RDKit numbers of `pipeline/discovery/redock.py` to within 0.01 Å.

## Limits

A CA RMSD against a public structure measures agreement with that structure, not prospective accuracy.
When the hosted endpoint fails or times out (HTTP 504 was seen on 2026-09-28), the API returns the recorded response labelled "지난 측정으로 대체" with the reason, never silently.
Tests: `tests/test_discovery_api.py`.
