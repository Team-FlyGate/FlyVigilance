## Description: <br>
Use when an ICSR needs an immediate triage decision: seriousness, expectedness, WHO-UMC causality, special situation, priority and next action, returned as typed calibrated probabilities from the non-autoregressive judgment model (System-1) in one call, then routed by a deterministic policy with label grounding, an EMA DME safety net and US/KR expedited-reporting regimes. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Pharmacovigilance case processors and safety reviewers who need each incoming ICSR routed within seconds to expedite, signal review, monitor, close or follow-up, with deadlines and human-readable reasons. <br>

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
- [Triage and routing policy](../../api/_fv/triage.py) <br>
- [Label grounding](../../api/_fv/evidence.py) <br>
- [Routing tests](../../tests/test_routing.py) <br>
- [FlyVigilance Evaluation Report v2.0.0](../../docs/EVALUATION.md) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, API Calls] <br>
**Output Format:** [JSON (validity, grounding, typed judgments with probabilities, decision with action, tier, deadline and reasons)] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Probabilities are population-calibrated (R10); every expedite decision goes to a human] <br>

## Evaluation Tasks: <br>
440 real FAERS 2026Q2 cases (250 serious) with outcome codes hidden; FlyVigilance workflow versus a single-question baseline on the same judgment model; paired McNemar exact tests. <br>

## Evaluation Metrics Used: <br>
Reported benchmark dimensions: <br>
- Serious cases reaching review: Serious cases routed to human-first, System-2 review or follow-up rather than the automatic queue. <br>
- Human-first workload: Cases sent to a human first. <br>
- Specificity: Non-serious cases kept off the human-first path. <br>



## Evaluation Results: <br>
| Condition | Serious reaching review | Serious left in auto queue | Human-first | Specificity |
|---|---:|---:|---:|---:|
| FlyVigilance workflow | 247 / 250 | 3 | 138 | 0.984 |
| Single-question baseline | 234 / 250 | 16 | 302 | 0.642 |

Serious cases left in the automatic queue: 3 vs 16, McNemar p = 0.0044.

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


