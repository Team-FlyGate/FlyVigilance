## Description: <br>
Use when a drug–event pair needs its top PubMed articles read and typed: the top 20 PubMed candidates are reordered by the NVIDIA Nemotron reranker, then the top 6 are typed for study design (PubMed publication type by rule, otherwise a judgment-model choice), whether the article actually studies the pair, design-specific items (dechallenge, rechallenge, onset, effect, comparator, dose) and support for the association, with citable pubmed:<pmid>#<design> IDs. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 <br>
## Use Case: <br>
Pharmacovigilance reviewers and developers who need the most relevant PubMed articles for a drug-event pair read and typed with citable IDs, feeding the evidence grade, the Korean algorithm's case-report rule and the System-2 evidence catalog. <br>

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
- [Literature reader](../../api/_fv/literature.py) <br>
- [Design accuracy benchmark](../../pipeline/bench/literature_eval.py) <br>
- [Rerank benchmark](../../pipeline/bench/literature_rerank_eval.py) <br>
- [FlyVigilance Evaluation Report v2.0.0](../../docs/EVALUATION.md) <br>
- [Model configuration](../../api/_fv/config.py) <br>


## Skill Output: <br>
**Output Type(s):** [Analysis, API Calls] <br>
**Output Format:** [JSON (articles with pubmed:<pmid>#<design> IDs, gate and design-specific verdicts, summary status, rerank metadata)] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Abstract text is used for judgment only and not retained; at most 6 articles per pair; falls back to PubMed order when reranking fails] <br>

## Evaluation Tasks: <br>
Study-design typing on 598 PubMed articles from 210 warehouse SDR pairs with publication types hidden (truth: MEDLINE indexing); candidate reranking on 30 pairs and 575 articles labeled by the literature gate. <br>

## Evaluation Metrics Used: <br>
Reported benchmark dimensions: <br>
- Design accuracy: Agreement of the typed study design with MEDLINE publication-type indexing. <br>
- Gate-relevant share in top 6: Share of the 6 articles read that the literature gate accepts (focus or reported). <br>



## Evaluation Results: <br>
| Measure | Value |
|---|---:|
| Design accuracy (598 articles) | 0.920 |
| Design accuracy, 3 groups (analytic, case, review) | 0.957 |
| Gate-relevant share in top 6, PubMed order | 0.65 |
| Gate-relevant share in top 6, Nemotron rerank | 0.85 |
| Per-pair AUC, PubMed order vs Nemotron rerank | 0.43 vs 0.78 |

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


