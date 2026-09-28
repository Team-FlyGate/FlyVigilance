---
name: "discovery-msa-search"
title: "Discovery MSA Search"
version: "1.0.0"
description: "Use to fetch a multiple sequence alignment for a pre-market target before structure prediction: calls the hosted NVIDIA BioNeMo MSA-Search (ColabFold, GPU MMSeqs2) NIM with the target sequence, returns the A3M alignment plus per-column depth and conservation, and hands the same alignment to OpenFold3 and Boltz-2. Do not use to predict a structure, to dock a ligand, or to claim anything about binding."
license: "Apache-2.0"
compatibility: "NVIDIA BioNeMo MSA-Search NIM (health.api.nvidia.com/v1/biology/colabfold/msa-search/predict), NVIDIA_API_KEY; Python 3.11+ with FastAPI and httpx. Follows NVIDIA/skills bionemo-msa-structure-prediction-pipeline step 1 and NVIDIA-BioNeMo/bionemo-agent-toolkit msa-search-nim."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "sense (sensory intake)"
  model: "ColabFold MMSeqs2 (NVIDIA BioNeMo NIM)"
  endpoint: "POST /api/discovery/msa"
  domain: "drug discovery"
  based_on: "NVIDIA/skills bionemo-msa-structure-prediction-pipeline"
  tags:
    - drug-discovery
    - bionemo-nim
    - msa
    - colabfold
    - structure-prediction
---

# Discovery MSA Search

## When to Use

- A pre-market target needs evolutionary context before structure prediction. The default demo is PARP1 4R6E chain A; any protein found through `GET /api/discovery/search/protein` (UniProt) and `GET /api/discovery/protein/{accession}` can be used instead, with the sequence range picked from the best experimental structure or an annotated domain.
- The next step (`discovery-openfold3`, `discovery-boltz2`) asks for an A3M alignment.

## Do Not Use

- To predict a structure or a pose: that is `discovery-openfold3` and `discovery-diffdock`.
- To say anything about affinity or efficacy. Alignment depth is not evidence of binding.

## Requirements

`NVIDIA_API_KEY` in the environment (`api/_fv/config.py` reads the repo `.env` or the platform variable). Without it the API answers 503 "not configured". Keys never appear in a request summary, a log line or a screen.

## Contract

- Request (NVIDIA official skill shape): `{"sequence", "databases": ["Uniref30_2302"], "e_value": 1e-4, "output_alignment_formats": ["a3m"]}`.
  The official example also lists `colabfold_envdb_202108`; the hosted gateway returned HTTP 504 in 7 s with that database added (2026-09-28), and the request id it returned was not in `/v1/status`, so the default is Uniref30 alone and the envdb is opt-in (`databases` parameter).
- Response is read as `alignments[database].a3m.alignment`, exactly as the official skill documents.
- `api/_fv/discovery.py::process_msa` drops a3m insertion columns (lowercase), then returns the query, the alignment rows sorted by identity, per-column depth and conservation, and the alignment itself for the next step (plus `a3m_key`, a server-side handle).
- Long runs: the start request carries a short `NVCF-POLL-SECONDS`; a 202 returns the NVCF request id and the caller polls `GET /api/discovery/status/{req_id}`.
- Results are cached by input hash (memory, and `FV_CACHE_DIR` when set). `no_cache: true` forces a new call.

## Measured

| Run | Result |
| --- | --- |
| 2026-09-28 (recorded) | 101 alignment rows (query + 100 homologs), 63.6 s |
| 2026-09-28 (live, this skill) | 101 rows, 10.8 s, byte-identical alignment (42,523 chars) |

## Choosing a target

`GET /api/discovery/search/protein?q=` takes a gene name, a protein name, a UniProt accession or a PDB id and returns reviewed human entries first (gene, name, organism, length, number of PDB entries).
`GET /api/discovery/protein/{accession}` adds the sequence, the experimental structures sorted by resolution, the annotated domains, the candidate ranges and a check against the NIM input limits. The run request then carries `custom_target` (id, gene, organism, sequence, pdb, chain, start, end) instead of a catalog key.

## Limits

Alignment depth says how much evolutionary signal the structure predictor gets. It says nothing about binding, selectivity or efficacy.
Tests: `tests/test_discovery_api.py`.
