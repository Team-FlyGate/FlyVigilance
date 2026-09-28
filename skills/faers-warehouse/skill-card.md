## Description: <br>
Use when building or refreshing the FlyVigilance FAERS warehouse: incremental quarterly ingest of FDA FAERS ASCII files into DuckDB, case de-duplication, drug-name normalization, disproportionality tables (PRR, ROR, chi-square, IC025) and the API/dashboard extracts. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Data engineers and pharmacovigilance developers refreshing the FAERS DuckDB warehouse each quarter and tracing any disproportionality number back to the SQL that produced it. <br>

### Deployment Geography for Use: <br>
Global <br>

## Requirements / Dependencies: <br>
**Requires API Key or External Credential:** [No] <br>
**Credential Type(s):** [None] <br>  

Do not include secrets in prompts/logs/output; use least-privilege credentials; rotate keys as appropriate. See skill body for more details. <br>

## Known Risks and Mitigations: <br>
Risk: Review before execution as proposals could introduce incorrect or misleading guidance into skills. <br>
Mitigation: Review and scan skill before deployment. <br>

## Reference(s): <br>
- [Warehouse model SQL](../../pipeline/faers/model.sql) <br>
- [Quarter loader](../../pipeline/faers/load_quarters.py) <br>
- [Extract builder](../../pipeline/faers/build_model.py) <br>
- [Statistics functions](../../api/_fv/pvstats.py) <br>
- [Pharmacovigilance overview](../../docs/약물감시_개요.md) <br>


## Skill Output: <br>
**Output Type(s):** [Files, Shell commands] <br>
**Output Format:** [DuckDB tables and gzipped JSON extracts] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Deterministic SQL; no model alters a number] <br>

## Evaluation Tasks: <br>
Offline unit tests in tests/test_pvstats.py check the 2x2 statistics against a hand calculation (5 tests, all passing on 2026-09-28). <br>

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


