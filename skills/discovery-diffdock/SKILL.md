---
name: "discovery-diffdock"
title: "Discovery DiffDock Poses"
version: "1.0.0"
description: "Use to compute protein-ligand binding poses for a pre-market candidate with the hosted NVIDIA BioNeMo DiffDock NIM, and to score a co-crystal redocking control with a symmetry-aware heavy-atom RMSD (success at 2.0 Å, no alignment). Do not read DiffDock confidence as binding strength, and do not treat an exploratory cross-docking pose as evidence that the molecule binds that target."
license: "Apache-2.0"
compatibility: "NVIDIA BioNeMo DiffDock NIM (health.api.nvidia.com/v1/biology/mit/diffdock), NVIDIA_API_KEY; Python 3.11+ with FastAPI and httpx. Shares the request body and response validation with the CLI runner api/_fv/docking.py. Follows NVIDIA-BioNeMo/bionemo-agent-toolkit diffdock-nim."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "reflex (fast structural judgment)"
  model: "DiffDock (NVIDIA BioNeMo NIM)"
  endpoint: "POST /api/discovery/diffdock"
  domain: "drug discovery"
  based_on: "NVIDIA-BioNeMo/bionemo-agent-toolkit diffdock-nim"
  tags:
    - drug-discovery
    - bionemo-nim
    - diffdock
    - docking
    - redocking
---

# Discovery DiffDock Poses

## When to Use

- A ligand (SMILES) has to be placed in a receptor taken from a crystal structure.
- A docking setup needs a control: redocking the co-crystal ligand and measuring the RMSD to its crystal pose.

## Do Not Use

- To rank affinity. Confidence is a pose-ranking score (rule D2).
- To compare scores across different proteins or to infer selectivity (rule D1).
- To claim binding from an exploratory cross-docking pose (rule D6).

## Receptor for a target chosen on screen

1. coordinates sent in the request, 2. the OpenFold3 prediction from step 2 (`receptor_structure_key`), 3. the RCSB experimental structure for the chosen PDB id and chain, downloaded and cached server-side.
A target chosen on screen has no co-crystal reference for the selected ligand, so the run reports `기준 결정 구조 없음` instead of an RMSD. The structure's own co-crystal ligand is used only to place the pocket view, and its code is named in that note.

## Requirements

`NVIDIA_API_KEY`. The receptor is ATOM records only (no HETATM, no water), as the official skill requires; SMILES go in as `ligand_file_type: "txt"`, never `"smiles"`.

## Contract

- Request body is built by `api/_fv/docking.py::build_body`, the same function the CLI uses: `{"protein","ligand","ligand_file_type":"txt","num_poses":5,"time_divisions":20,"steps":18,"save_trajectory":false,"is_staged":false}`.
- The response is validated by `api/_fv/docking.py::validate_result`: `ligand_positions` and `position_confidence` must be parallel lists of SDF poses and finite scores, or the run counts as a failure rather than a result.
- Scoring (`api/_fv/molgeom.py`): heavy-atom graph matching over element and connectivity finds every symmetry-equivalent atom mapping and takes the smallest RMSD, without superposition. That is the traditional redocking criterion (success ≤ 2.0 Å).
- A timeout is never retried automatically for DiffDock: the provider may already have accepted the work (the CLI contract in `api/_fv/docking.py`).

## Measured

| Pair | Role | Recorded top-1 RMSD | Live (this skill) |
| --- | --- | --- | --- |
| niraparib @ PARP1 4R6E | 공결정 재도킹 대조 | 0.71 Å (conf 0.696) | 0.299 Å (conf 0.814), 1.9 s |
| apixaban @ Factor Xa 2P16 | 재도킹 대조 | 0.56 Å | – |
| celecoxib @ COX-2 3LN1 | 재도킹 대조 | 0.55 Å | – |
| redock panel (5 FAERS demo drugs) | 재도킹 대조 | 0.71–2.12 Å | – |

Pure-Python RMSD reproduces the RDKit panel numbers in `fly_discovery/measurements/redock.json` to within 0.01 Å.

## Limits

Redocking checks the setup, not prospective prediction (rule D5). COX-2 3LN1 is a mouse protein and does not transfer to humans (rule D7).
Tests: `tests/test_discovery_api.py`, `tests/test_live_docking.py`.
