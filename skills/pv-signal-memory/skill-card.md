## Description: <br>
Use when a drug–event pair or a case needs its evidence bundle: FAERS 2x2 disproportionality from the warehouse, openFDA label sections that list the reaction, PubMed articles, the evidence grade and reference-set metrics, each returned with a citable evidence ID that System-2 memos must use. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Pharmacovigilance developers and System-2 assessors who need a case's evidence bundle (FAERS statistics, label sections, literature, grade, reference-set metrics) with the exact evidence IDs a memo may cite. <br>

### Deployment Geography for Use: <br>
Global <br>

## Requirements / Dependencies: <br>
**Requires API Key or External Credential:** [Optional] <br>
**Credential Type(s):** [API key] <br>  

Do not include secrets in prompts/logs/output; use least-privilege credentials; rotate keys as appropriate. See skill body for more details. <br>

## Known Risks and Mitigations: <br>
Risk: Review before execution as proposals could introduce incorrect or misleading guidance into skills. <br>
Mitigation: Review and scan skill before deployment. <br>

## Reference(s): <br>
- [Evidence bundle](../../api/_fv/evidence.py) <br>
- [Statistics functions](../../api/_fv/pvstats.py) <br>
- [Label text processing](../../api/_fv/labeltext.py) <br>
- [openFDA drug label API](https://open.fda.gov/apis/drug/label/) <br>
- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, API Calls] <br>
**Output Format:** [JSON bundle (faers, label, literature, grades, catalog of evidence IDs, ids)] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Numbers come from SQL and public APIs; no model computes a number] <br>

## Evaluation Tasks: <br>
Offline unit tests: tests/test_pvstats.py (5) for the 2x2 statistics and tests/test_label_facts.py (8) for label facts, synonym search and catalog scope, all passing on 2026-09-28. <br>

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


