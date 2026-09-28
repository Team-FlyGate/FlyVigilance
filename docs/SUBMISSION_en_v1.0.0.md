# Hackathon Submission Text (English)

NVIDIA Korea Agentic AI Hackathon 2026 · Section 02 · Service name: **Project-FlyGate**

- Service URL: https://flygate.kr
- GitHub: https://github.com/Team-FlyGate/Project-FlyGate
- Korean original: [SUBMISSION.md](SUBMISSION.md)

## (1) Problem Definition (about 300 characters)

Drug safety reviewers weigh scattered evidence: docking and affinity before approval; labels, adverse event reports and papers after. FAERS gets 420,000+ reports a quarter. Reading all by LLM is slow, costly; one-question screens miss serious cases or overload staff. Format checks miss overclaims.

<sub>298 characters including spaces · limit 300</sub>

## (2) Solution: Service Overview and Key Features (about 500 characters)

FlyGate is an agentic workflow on NVIDIA Skills. FlyDiscovery tests candidates with BioNeMo NIM (MSA-Search→OpenFold3→DiffDock→Boltz-2), rejecting overclaims. FlyVigilance triages FAERS cases (rules→FDA label→7-question judge→policy); Nemotron writes cited memos as needed, vetted by critic and Safety Guard. A non-autoregressive judge takes 296 ms. Outcomes hidden, 247/250 serious cases reached review (1-question: 234; p=0.004); human work fell 302→138. People and OpenClaw share one flygate CLI.

<sub>499 characters including spaces · limit 500</sub>

<details>
<summary>Reading notes for (1) and (2)</summary>

- **FAERS**: the U.S. Food and Drug Administration (FDA) Adverse Event Reporting System.
- **Docking / affinity**: computationally fitting a drug molecule into its target protein's binding site, and predicting how strongly it binds.
- **Overclaims**: claims whose numbers and sources are correct but whose conclusion goes beyond the evidence, such as inferring selectivity from docking scores on different proteins or reading a reporting ratio as causation.
- **FlyDiscovery (STEP 1)** covers pre-market candidates; **FlyVigilance (STEP 2)** covers post-market pharmacovigilance (PV) for marketed drugs. Niraparib (a PARP1 inhibitor) is the demo drug; both steps apply to other targets and drugs.
- **Non-autoregressive judge**: a model that returns probabilities for fixed questions in one pass instead of generating text token by token (296 ms versus 2,286 ms for autoregressive generation of the same questions).
- **Outcomes hidden**: measured on 440 real FAERS cases with outcome codes (death, hospitalization, etc.) masked. The single-question baseline reached 234/250 (McNemar test p = 0.0044), and human-priority workload fell from 302 to 138 cases.
- **flygate CLI**: installed in one line; humans and the OpenClaw agent inside the OpenShell sandbox run the same commands.

</details>

## (3) Core Technologies and AI Models (Tech Stack)

**NVIDIA models (build.nvidia.com NIM: NVIDIA Inference Microservices, OpenAI-compatible API)**
- NVIDIA Nemotron 3 Super 120B (`nvidia/nemotron-3-super-120b-a12b`): System-2 (deliberative stage) assessment memos, structuring of Korean domestic report forms, FlyDiscovery critic (the checking stage that rejects claims beyond the evidence) verdicts. Uses JSON mode
- NVIDIA Nemotron 3 Ultra 550B (`nvidia/nemotron-3-ultra-550b-a55b`), Nemotron 3.5 Lightning 30B (`nvidia/nemotron-3.5-lightning-30b-a3b`): fallback chain (the backup path when the primary model does not respond)
- NVIDIA Nemotron Safety Guard 8B v3 + NVIDIA Nemotron 3.5 Content Safety: both guards check every claim in a memo in parallel. A PV (pharmacovigilance) policy built with the official skill nemotron-policy-generator (treatment advice, causal claims drawn from the PRR (proportional reporting ratio), incidence rates from spontaneous reports, re-identification, use of non-permitted tools) is passed to Content Safety as custom_policy, so the guard layer catches PRR causal claims 7/7 and fabricated incidence rates 8/8 (accuracy on 50 evaluation items 0.58 → 0.84)
- NVIDIA Nemotron reranker (a model that re-sorts search results by relevance, llama-nemotron-rerank-vl-1b-v2): reorders 20 PubMed candidates, raising the share of relevant papers among the six read from 0.65 → 0.85
- NVIDIA BioNeMo NIM (health.api.nvidia.com): MSA-Search (multiple sequence alignment, 101 homologous sequences), OpenFold3 (PARP1 CA RMSD 1.0 Å; RMSD, root-mean-square deviation, is the distance from the crystal structure), DiffDock (redocking 0.71 Å), Boltz-2 (Spearman 0.767 on 39 ChEMBL compounds; Spearman is rank correlation)

**NVIDIA agent stack**
- NemoClaw v0.0.124 · OpenShell 0.0.116 · OpenClaw: OpenClaw workspace (SOUL · AGENTS · IDENTITY · USER · TOOLS · HEARTBEAT · MEMORY) and a heartbeat (periodic self-check) watch task. The OpenShell policy uses a deny-by-default (blocked by default, only allow-listed destinations open) network policy (per host, method, path and executable), a Landlock (Linux file path access restriction) file system and non-root execution, and opens no path for sending reports outside. The real sandbox smoke test (basic operation check) passed 20/20
- FlyGate Agent CLI (`flygate`, command-line interface): after cloning the repository, install with the single line `./scripts/install_flygate.sh`. All nine commands (login, chat, triage, grade, signals, kr-causality, critic, discover, watch) output JSON with evidence IDs attached. Typing `flygate` alone opens interactive mode, which proposes the command to run for a request such as "Show me the evidence for PARP1 candidates", asks for confirmation, then runs it. The NVIDIA key is stored in the OS secure keychain via `flygate login`. `flygate discover --live` calls the DiffDock NIM in real time, and people and the OpenClaw agent in the OpenShell sandbox use the same commands
- NVIDIA Agent Skills (github.com/NVIDIA/skills): our 11 capabilities are packaged as official-format SKILL.md files and skill cards (skill-card-generator), and the official skills bionemo-msa-structure-prediction-pipeline · nemotron-policy-generator · nemotron-retrieval-recipes are applied in the real pipeline

**Non-autoregressive judgment model** (a model that returns probabilities for fixed questions in one pass instead of generating text)
- TypeSafe AI Jev: 7-question reflex triage (case sorting) (296 ms; the same questions via autoregressive generation take 2,286 ms), knowledge-based discrimination (OMOP AUC 0.960; AUC measures discrimination accuracy), literature relevance and study-design classification (92.0% agreement with MEDLINE indexing), critic overinterpretation verdicts

**Data and software**
- FDA FAERS (the U.S. FDA Adverse Event Reporting System), 55 quarters (2012Q4–2026Q2, about 17.6 million unique cases) + 35 quarters of legacy AERS, openFDA labels, DailyMed, PubMed E-utilities, RCSB PDB (protein structure database), ChEMBL (compound activity database), the EMA DME list (adverse events the European Medicines Agency designates for special attention), OMOP · EU-ADR · Harpaz reference sets (evaluation lists with predefined ground truth)
- [MaleCNS v1.0](https://male-cns.janelia.org/) fruit fly connectome (a map of neuron-to-neuron connections): male Drosophila central nervous system data released by Janelia FlyEM and collaborators (CC-BY 4.0). Its central brain subgraph (49,244 neurons, 1,051,255 neuron-to-neuron connections) is mapped onto the agent's nine functional layers to visualize task branching and review routes.
- Python 3.12, DuckDB (five-layer warehouse; disproportionality metrics computed in SQL), FastAPI, React + Vite + TypeScript, Vercel
