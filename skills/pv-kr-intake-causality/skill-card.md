## Description: <br>
Use when a Korean adverse event report (MFDS professional form, consumer report, or hospital/pharmacist narrative) must be structured into the MFDS form sections and a triage case, scored with the Korean causality algorithm ver 2.0 (seven items judged by the non-autoregressive judgment model, the known-information item by label/literature rules, score summed by rule), and routed under Korean expedited-reporting rules. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Korean pharmacovigilance practitioners (hospital and pharmacist reporters, safety reviewers) structuring Korean adverse event reports into the MFDS form and scoring the Korean causality algorithm ver 2.0 for reviewer confirmation. <br>

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
- [Korean module](../../api/_fv/kr.py) <br>
- [Routing and regimes](../../api/_fv/triage.py) <br>
- [Pharmacovigilance overview](../../docs/약물감시_개요.md) <br>
- [Pharmacist review notes](../../docs/PHARMACIST_REVIEW.md) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, API Calls] <br>
**Output Format:** [JSON (kr_form sections, triage case, algorithm items with scores and needs_review flags, total, grade, WHO-UMC)] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [MFDS label is not auto-checked; the known-information item always requires reviewer confirmation] <br>

## Evaluation Tasks: <br>
13 offline unit tests in tests/test_kr.py (score range -13 to 19, grade bands, the team document's patient A scoring 11, rule-only known-information item, form normalization), all passing on 2026-09-28. <br>

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


