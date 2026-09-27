---
name: faers-warehouse
description: Use when building or refreshing the FlyVigilance FAERS warehouse — incremental quarterly ingest of FDA FAERS ASCII files into DuckDB, case de-duplication, drug-name normalization, and disproportionality tables.
license: Apache-2.0
metadata:
  author: FlyVigilance
  layer: sense + encode
  tags: [pharmacovigilance, faers, duckdb, etl]
---

# FAERS Warehouse

Sensory Intake and Feature Encoding layers. Deterministic; no model is called.

## Steps
1. `scripts/download_faers.sh` — fetch new quarterly zips from fis.fda.gov (skips existing, validates zip).
2. `.venv/bin/python pipeline/faers/load_quarters.py` — load each quarter into `raw_*` (VARCHAR, UTF-8 normalized, one transaction per quarter, audited in `etl_quarter`).
3. `.venv/bin/python pipeline/faers/build_model.py` — run `pipeline/faers/model.sql` and export API/dashboard artifacts.

## Rules
- De-duplicate by `caseid`, keep highest `caseversion`, then latest `fda_dt`; drop every caseid in any DELETE file.
- Drug = `prod_ai` first; learned brand→ingredient map for pre-2014Q3; strip salt/hydrate suffixes; group biosimilar suffixes.
- Only PS/SS roles enter disproportionality. PRR/ROR/IC025 are computed in SQL; models never alter them.
