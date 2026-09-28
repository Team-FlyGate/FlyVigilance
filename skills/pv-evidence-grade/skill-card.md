## Description: <br>
Use when a drug–event pair needs a population-level evidence classification: a PV class candidate (label status × SDR) and a one-letter grade (A/B/C/L/D/U) built by fixed rules from the openFDA label section, the FAERS triple-criterion SDR and PubMed literature, returned with its basis (evidence IDs), gaps and flags. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Pharmacovigilance reviewers and developers who need a rule-based, population-level classification of a drug-event pair (label status by SDR) with its basis, gaps and bias flags. <br>

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
- [Grade rules](../../api/_fv/grade.py) <br>
- [Label text processing](../../api/_fv/labeltext.py) <br>
- [Pharmacist review notes](../../docs/PHARMACIST_REVIEW.md) <br>
- [FlyVigilance Evaluation Report v2.0.0](../../docs/EVALUATION.md) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis] <br>
**Output Format:** [JSON (PV class candidate, letter grade, axes, flags, basis evidence IDs, gaps)] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Candidate labels only; population-level context, never individual-case causality (critic rule R13)] <br>

## Evaluation Tasks: <br>
Re-grading of the three team-prototype pairs (clozapine-neutropenia, niraparib-thrombocytopenia, isotretinoin-inflammatory bowel disease) plus 9 offline unit tests in tests/test_grade.py. <br>

## Evaluation Results: <br>
| Pair | Team prototype | FlyVigilance PV class | Label status and statistics |
|---|---|---|---|
| Clozapine - neutropenia | A | Identified risk candidate | Boxed warning, triple-criterion SDR |
| Niraparib - thrombocytopenia | B | Identified risk candidate | Warnings and precautions, triple-criterion SDR |
| Isotretinoin - IBD | C | Identified risk candidate | Warnings and precautions, triple-criterion SDR; lawyer reports 94.9% (reporting-bias flag) |

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


