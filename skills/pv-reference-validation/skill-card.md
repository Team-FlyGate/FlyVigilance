## Description: <br>
Use to measure how signal-detection methods perform on public reference sets (OMOP, EU-ADR, Harpaz time-indexed incl. a pre-2013 prospective window from legacy AERS): ROC/AUC with bootstrap CIs for report count, PRR, ROR025, chi-square and IC025, the FlyVigilance knowledge-based mode (drug and event names), the statistics-based mode (names hidden) and a single-question baseline. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Pharmacovigilance method developers measuring signal-detection rules and judgment modes against public reference sets before relying on them in the evidence grade or dashboard. <br>

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
- [Reference-set evaluation](../../pipeline/refsets/evaluate.py) <br>
- [Reference-set builder](../../pipeline/refsets/build_refsets.py) <br>
- [Legacy AERS loader](../../pipeline/refsets/legacy_aers.py) <br>
- [Validation results](../../web/public/data/validation.json) <br>
- [FlyVigilance Evaluation Report v2.0.0](../../docs/EVALUATION.md) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, Files] <br>
**Output Format:** [JSON (ROC points, AUC with bootstrap 95% CI, paired deltas, sensitivity/specificity/PPV)] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Measures recognition of established reference pairs, not individual-case causality] <br>

## Evaluation Tasks: <br>
OMOP (387 pairs), EU-ADR (93), Harpaz time-indexed (137) and a Harpaz prospective window from legacy AERS 2004Q1-2012Q3 (127); stratified bootstrap 2,000 resamples. <br>

## Evaluation Results: <br>
| Reference set | Best statistical metric | Knowledge-based mode | Statistics-based mode |
|---|---:|---:|---:|
| OMOP | chi-square 0.815 | 0.960 | 0.790 |
| EU-ADR | chi-square 0.919 | 0.983 | 0.929 |
| Harpaz (all years) | PRR 0.733 | 0.761 | 0.662 |
| Harpaz prospective | PRR 0.720 | - | 0.695 |

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


