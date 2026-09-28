## Description: <br>
Use when triage escalates a case to System-2: NVIDIA Nemotron writes an evidence-bound case assessment (3 to 6 claims with evidence IDs, assessment, narrative, open questions) from the evidence bundle only, and the pv-critic skill checks it before a human sees it. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Pharmacovigilance safety reviewers and developers who need an evidence-bound draft assessment for cases that triage escalates, written by NVIDIA Nemotron and checked by the critic before human review. <br>

### Deployment Geography for Use: <br>
Global <br>

## Requirements / Dependencies: <br>
**Requires API Key or External Credential:** [Yes] <br>
**Credential Type(s):** [API key] <br>  

Do not include secrets in prompts/logs/output; use least-privilege credentials; rotate keys as appropriate. See skill body for more details. <br>

## Known Risks and Mitigations: <br>
Risk: Review before execution as proposals could introduce incorrect or misleading guidance into skills. <br>
Mitigation: Review and scan skill before deployment. <br>

## Reference(s): <br>
- [Assessment implementation](../../api/_fv/assess.py) <br>
- [NIM client and model chain](../../api/_fv/clients.py) <br>
- [FlyVigilance Evaluation Report v2.0.0](../../docs/EVALUATION.md) <br>
- [Model configuration](../../api/_fv/config.py) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, API Calls] <br>
**Output Format:** [JSON memo (claims with evidence IDs, assessment, narrative, open questions) plus per-round critic issues] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [100 s total budget; at most one revision round; draft for a human reviewer] <br>

## Evaluation Tasks: <br>
Full path (triage, evidence bundle, Nemotron assessment, critic) on 8 real death/serious FAERS cases in the critic probe run (2026-09-27). <br>

## Evaluation Results: <br>
| Outcome | Memos |
|---|---:|
| Passed the critic | 6 / 8 |
| Returned to a human with reasons after one revision | 2 / 8 |

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


