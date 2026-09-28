---
name: "faers-warehouse"
title: "FAERS Warehouse"
version: "1.0.0"
description: "Use when building or refreshing the FlyVigilance FAERS warehouse: incremental quarterly ingest of FDA FAERS ASCII files into DuckDB, case de-duplication, drug-name normalization, disproportionality tables (PRR, ROR, chi-square, IC025) and the API/dashboard extracts. Do not use to interpret a signal or assess a single case."
license: "Apache-2.0"
compatibility: "Python 3.11+ with DuckDB; bash, curl and unzip; FDA FAERS quarterly ASCII files from fis.fda.gov. Deterministic SQL; calls no model endpoint."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "sense + encode"
  domain: "pharmacovigilance"
  tags:
    - pharmacovigilance
    - faers
    - duckdb
    - etl
    - disproportionality
---

# FAERS Warehouse

Sensory Intake and Feature Encoding layers. Deterministic; no model is called.

## When to Use

- A new FAERS quarter is published and the warehouse, `api/_data/signals.json.gz` and the dashboard extracts need refreshing.
- A disproportionality number must be traced back to the SQL that produced it.

## Do Not Use

- To decide whether a signal is causal or a case is serious; that belongs to `pv-evidence-grade`, `pv-reflex-triage` and human review.

## Requirements

No credentials. FAERS quarterly files are public downloads from fis.fda.gov.

## Instructions

1. `scripts/download_faers.sh` fetches new quarterly zips from fis.fda.gov (skips files that already pass `unzip -t`).
2. `.venv/bin/python pipeline/faers/load_quarters.py` loads each quarter into `raw_*` tables (VARCHAR, UTF-8 normalized, one transaction per quarter, audited in `etl_quarter`).
3. `.venv/bin/python pipeline/faers/build_model.py` runs `pipeline/faers/model.sql` and exports `api/_data/signals.json.gz`, `api/_data/cases.json.gz` and `web/public/data/faers/*.json`.
4. Optional: `.venv/bin/python pipeline/faers/export_reporter_mix.py` writes the reporter-mix table behind the reporting-bias flag in `pv-evidence-grade`.

## Rules

- De-duplicate by `caseid`, keep highest `caseversion`, then latest `fda_dt`; drop every caseid in any DELETE file.
- Drug = `prod_ai` first; learned brand→ingredient map for quarters before 2014Q3; strip salt/hydrate suffixes; group biosimilar suffixes.
- Only PS/SS roles enter disproportionality. PRR/ROR (95% CI), Yates chi-square, IC and IC025 are computed in SQL (`api/_fv/pvstats.py` mirrors the formulas); models never alter them.
