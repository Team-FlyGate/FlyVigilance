## Description: <br>
Use when building, rendering or explaining the FlyVigilance routing topology: the MaleCNS central-brain subgraph (49,244 neurons, 1,051,255 signed edges) mapped to the agent's nine layers, with a browser rate model that agent decisions drive. <br>

This skill is for research and development only. <br>

## Third-Party Community Consideration
This skill is not owned or developed by NVIDIA. This skill has been developed and built to a third-party's requirements for this application and use case; see link to Non-NVIDIA [Team FlyGate Agent Card](https://github.com/Team-FlyGate/Project-FlyGate). <br>

### License/Terms of Use: <br>
Apache 2.0 (code); MaleCNS data CC-BY-4.0 (Janelia FlyEM) <br>
## Use Case: <br>
Developers and demo presenters building or explaining the FlyVigilance routing visualization, which maps agent layers onto the MaleCNS Drosophila central-brain connectome and animates agent decisions in the browser. <br>

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
- [Subgraph selection](../../pipeline/connectome/select_subgraph.py) <br>
- [Web asset builder](../../pipeline/connectome/build_web_connectome.py) <br>
- [Browser rate model](../../web/src/lib/connectome.ts) <br>
- [MaleCNS data notes](../../docs/MaleCNS_데이터.md) <br>


## Skill Output: <br>
**Output Type(s):** [Files, Shell commands] <br>
**Output Format:** [Binary WebGL buffers (neurons.bin, edges.bin, cloud.bin), JSON metadata and a GLB mesh] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Routing visualization only; never used as clinical or causal evidence] <br>

## Skill Version(s): <br>
1.0.0 (source: frontmatter) <br>


