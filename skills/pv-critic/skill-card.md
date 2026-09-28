## Description: <br>
Use to verify any AI-written pharmacovigilance claim: tier 1 evidence-ID rules, tier 2 numeric oracle against the evidence bundle, tier 3 overclaim judgment by the non-autoregressive judgment model plus two per-claim NVIDIA Nemotron safety guards (the stock Safety Guard and the pharmacovigilance BYO policy from pv-guardrail-policy). <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Pharmacovigilance developers and safety reviewers who need every AI-written claim checked for evidence IDs, numbers, overclaims and individual treatment advice before it reaches a human reviewer. <br>

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
- [Critic implementation](../../api/_fv/assess.py) <br>
- [Critic probe benchmark](../../pipeline/bench/critic_probe.py) <br>
- [Critic probe results](../../web/public/data/critic_probe.json) <br>
- [FlyVigilance Evaluation Report v2.0.0](../../docs/EVALUATION.md) <br>
- [Model configuration](../../api/_fv/config.py) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, API Calls] <br>
**Output Format:** [JSON (claims, issues with tier/rule/detail, guard verdict)] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Fail-closed: an unreadable or unavailable guard verdict is marked for human check, never safe; 20 s guard budget] <br>

## Evaluation Tasks: <br>
Overclaim injection on 8 real death/serious FAERS cases: four wrong claims built from each case's real evidence (causal claim from PRR, invented incidence, fake label ID, individual treatment advice) plus 6 control claims that must pass (pipeline/bench/critic_probe.py, 2026-09-27). <br>

## Evaluation Metrics Used: <br>
Reported benchmark dimensions: <br>
- Detection: Share of injected wrong claims returned by at least one critic tier or the safety guard. <br>
- Control pass rate: Share of valid Nemotron claims that pass all tiers. <br>



## Evaluation Results: <br>
| Injected claim | Caught | Tier that caught it |
|---|---:|---|
| Causal claim from PRR | 7 / 7 | T3 R1 7, guard 1 |
| Invented incidence | 8 / 8 | T2 8, T3 R2 8 |
| Fake evidence ID | 8 / 8 | T1 8, T3 6 |
| Individual treatment advice | 8 / 8 | T3 R11 8, guard 8 |
| Controls (must pass) | 6 / 6 passed | - |

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


