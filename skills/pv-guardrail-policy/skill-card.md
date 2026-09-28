## Description: <br>
Use when configuring or changing the FlyVigilance content-safety policy: the pharmacovigilance BYO policy (PV-1..PV-5 on top of the relevant Nemotron Content Safety V2 categories) that runs on nvidia/nemotron-3.5-content-safety via chat_template_kwargs.custom_policy, next to the stock Llama-3.1 Nemotron Safety Guard 8B v3. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Pharmacovigilance developers and safety owners who define, version and re-measure the BYO content-safety policy that the FlyVigilance critic sends to NVIDIA Nemotron Content Safety for every claim of an AI-written assessment. <br>

### Deployment Geography for Use: <br>
Global <br>

## Requirements / Dependencies: <br>
**Requires API Key or External Credential:** [Not Specified] <br>
**Credential Type(s):** [None identified] <br>  

Do not include secrets in prompts/logs/output; use least-privilege credentials; rotate keys as appropriate. See skill body for more details. <br>

## Known Risks and Mitigations: <br>
Risk: Review before execution as proposals could introduce incorrect or misleading guidance into skills. <br>
Mitigation: Review and scan skill before deployment. <br>

## Reference(s): <br>
- [Policy document](policy.md) <br>
- [Policy taxonomy (JSON)](policy_taxonomy.json) <br>
- [custom_policy prompt](system_prompt.txt) <br>
- [Policy JSON schema (from nemotron-policy-generator)](schema/policy_json_schema.json) <br>
- [Runtime guard wiring](../../api/_fv/assess.py) <br>
- [Guard policy benchmark](../../pipeline/bench/guard_policy_eval.py) <br>
- [Guard policy results](../../web/public/data/guard_policy_eval.json) <br>
- [NVIDIA/skills nemotron-policy-generator](https://github.com/NVIDIA/skills/tree/main/skills/nemotron-policy-generator) <br>


## Skill Output: <br>
**Output Type(s):** [Files, API Calls] <br>
**Output Format:** [Markdown policy, JSON taxonomy and a plain-text custom_policy prompt; at runtime, per-claim guard verdicts with PV categories] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Deployed with thinking off (/no_think); an unreadable verdict is treated as human check, never safe] <br>

## Evaluation Tasks: <br>
Guard layer only: the stored injection claims from the critic probe (8 cases) and a held-out set of 50 hand-written PV claims (per category 6 violations and 4 adjacent valid claims) from evals/evals.json (pipeline/bench/guard_policy_eval.py). <br>

## Evaluation Metrics Used: <br>
Reported benchmark dimensions: <br>
- Accuracy: Share of the 50 PV claims classified correctly (violation flagged, adjacent valid claim passed). <br>
- Recall: Share of violating PV claims the guard flags. <br>
- False-positive rate: Share of adjacent valid claims the guard flags. <br>



## Evaluation Results: <br>
| Guard | Accuracy | Recall | False-positive rate |
|---|---:|---:|---:|
| Safety Guard 8B v3 (stock) | 0.58 | 0.33 | 0.05 |
| Nemotron-3.5 Content Safety (stock) | 0.72 | 0.53 | 0.00 |
| Nemotron-3.5 + PV policy (/no_think, deployed) | 0.84 | 0.80 | 0.10 |
| Nemotron-3.5 + PV policy (/think, 49 readable verdicts) | 0.90 | 0.90 | 0.10 |

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


