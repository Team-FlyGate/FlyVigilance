# Hackathon Submission (Final, as submitted)

NVIDIA Korea Agentic AI Hackathon 2026 · Section 02 · Service: **Project-FlyGate** · Team FlyGate · submitted 2026-09-28

- Service URL: https://flygate.kr (English: https://flygate.kr/?lang=en)
- GitHub: https://github.com/Team-FlyGate/Project-FlyGate
- Showreel (4 min 10 s): https://flygate.kr/showreel/FlyGate_showreel_v4.3.0-en.html (English) · [Korean](https://flygate.kr/showreel/FlyGate_showreel_v4.3.0.html)
- Submitted PDF (7 pages, Korean): [docs/submission/NVIDIA_해커톤_FlyGate_Final_제출버전.pdf](submission/NVIDIA_해커톤_FlyGate_Final_제출버전.pdf)

This is an English translation of the final text in the submitted PDF ([Korean original](SUBMISSION.md)). The earlier English draft is kept as `SUBMISSION_en_v1.0.0.md`.

## (1) Problem Definition

Drug safety, which protects patients' lives, requires evidence across the whole lifecycle: from binding predictions during development to patients' adverse-event reports after launch. Yet during development, teams often look only at a raw binding score and over-trust that a compound binds just its intended target. After launch, the FDA alone receives more than 420,000 adverse-event reports per quarter, far too many for conventional LLMs (large language models) or human reviewers to read one by one in reasonable time and cost. Filtering them mechanically with a single question misses risk signals, and it also fails to catch a dangerous distortion: reading raw report counts as proof that a drug causes an effect.

## (2) Solution and Key Features

Project-FlyGate is an AI drug-safety agent that applies the gating principle of the fruit-fly brain connectome, which filters sensory signals at very high speed, to verify the entire path from pre-launch development predictions to post-launch adverse events. Stage 1, FlyDiscovery, simulates target binding with NVIDIA BioNeMo NIM (MSA-Search → OpenFold3 → DiffDock → Boltz-2) and automatically rejects exaggerated conclusions that lack evidence. Stage 2, FlyVigilance, first filters large volumes of adverse-event reports through rule gates and official approved drug labels; then Jev, a non-autoregressive judgment model, answers 7 core questions in 0.3 seconds (296 ms). Only the cases that need close review go to NVIDIA Nemotron 3 Super 120B, which writes an in-depth assessment with numbered evidence, while NVIDIA Safety Guard blocks causal distortions. In a 440-case evaluation, FlyGate brought 247 of 250 serious cases to review and cut the human review load from 302 to 138 cases (54% less). Every function is called through the flygate CLI and NemoClaw on OpenShell.

## (3) Core Technologies and AI Models (Tech Stack)

### NVIDIA models (build.nvidia.com NIM: NVIDIA inference microservices, OpenAI-compatible API)

- **NVIDIA Nemotron 3 Super 120B** (`nvidia/nemotron-3-super-120b-a12b`): System-2 (deliberation stage) assessment memos, structuring Korean domestic reports into the regulator's form, and FlyDiscovery critic verdicts (the check that rejects claims beyond the evidence). Uses JSON mode.
- **NVIDIA Nemotron 3 Ultra 550B** (`nvidia/nemotron-3-ultra-550b-a55b`), **Nemotron 3.5 Lightning 30B** (`nvidia/nemotron-3.5-lightning-30b-a3b`): fallback chain (the backup path when the primary model does not respond).
- **NVIDIA Nemotron Safety Guard 8B v3 + NVIDIA Nemotron 3.5 Content Safety**: both guards check every claim in a memo at the same time. Content Safety receives, as `custom_policy`, a PV (pharmacovigilance) policy built with the official skill nemotron-policy-generator (treatment advice, causal claims from PRR (proportional reporting ratio), incidence rates from spontaneous reports, re-identification, tool use outside the allow list). The guard layer catches PRR-as-causation 7/7 and invented incidence 8/8 (accuracy on 50 evaluation sentences 0.58 → 0.84).
- **NVIDIA Nemotron reranker** (a model that re-orders search results by relevance, `llama-nemotron-rerank-vl-1b-v2`): re-ranks 20 PubMed candidates; the share of relevant papers among the 6 that are read rises from 0.65 to 0.85.
- **NVIDIA BioNeMo NIM** (health.api.nvidia.com): MSA-Search (multiple sequence alignment, 101 homologous sequences), OpenFold3 (PARP1 Cα RMSD 1.0 Å; RMSD is the distance to the crystal structure), DiffDock (redocking 0.71 Å), Boltz-2 (Spearman 0.767 on 39 ChEMBL compounds; Spearman is rank correlation).

### NVIDIA agent stack

- **NemoClaw v0.0.124 · OpenShell 0.0.116 · OpenClaw**: OpenClaw workspace (SOUL · AGENTS · IDENTITY · USER · TOOLS · HEARTBEAT · MEMORY) and a heartbeat (periodic self-check) watch job. The OpenShell policy is deny-by-default networking (blocked unless allow-listed, per host · method · path · executable), a Landlock (Linux file-path access restriction) file system, and non-root execution; no path exists for sending reports out. Real sandbox smoke test (basic operation check): 20/20 passed.
- **FlyGate Agent CLI** (`flygate`, command-line interface): after cloning the repository, one line, `./scripts/install_flygate.sh`, installs it. All 9 commands (login, chat, triage, grade, signals, kr-causality, critic, discover, watch) print JSON with evidence IDs. Typing just `flygate` opens an interactive mode that, for a request such as "show me the evidence for the PARP1 candidates", proposes the command to run and executes it after confirmation. The NVIDIA key is stored in the OS secure keychain with `flygate login`. `flygate discover --live` calls the DiffDock NIM in real time, and humans and the OpenClaw agent in the OpenShell sandbox use the same commands.
- **NVIDIA Agent Skills** (github.com/NVIDIA/skills): our 11 capabilities are packaged as official-format SKILL.md files with skill cards (skill-card-generator), and the official skills bionemo-msa-structure-prediction-pipeline · nemotron-policy-generator · nemotron-retrieval-recipes are applied in the real pipeline.

### Non-autoregressive judgment model (a model that does not generate text but returns the probabilities for fixed questions in one pass)

- **TypeSafe AI Jev**: reflex triage (case sorting) with 7 questions (296 ms, versus 2,286 ms for autoregressive generation of the same questions), knowledge-based discrimination (OMOP AUC 0.960; AUC is discrimination accuracy), literature relevance and study-design classification (92.0% agreement with MEDLINE indexing), and critic over-interpretation verdicts.

### Data and software

- FDA FAERS (FDA Adverse Event Reporting System) 55 quarters (2012Q4–2026Q2, about 17.6 million unique cases) + 35 quarters of legacy AERS, openFDA labels, DailyMed, PubMed E-utilities, RCSB PDB (protein structure database), ChEMBL (compound activity database), the EMA DME list (designated medical events flagged by the European Medicines Agency), and the OMOP · EU-ADR · Harpaz reference sets (evaluation lists with predefined answers).
- MaleCNS v1.0 fruit-fly connectome (a map of connections between neurons): male Drosophila central nervous system data released by Janelia FlyEM and others (CC-BY 4.0). Its central-brain subgraph (49,244 neurons, 1,051,255 neuron-to-neuron connections) is mapped onto the agent's 9 functional layers to visualize task branching and review paths.
- Python 3.12, DuckDB (5-layer warehouse; disproportionality metrics computed in SQL), FastAPI, React + Vite + TypeScript, Vercel.

## Other pages in the PDF

Besides the three sections above, the PDF contains the following pages; their content matches the corresponding documents in this repository.

- Cover: key numbers 247/250 · 302 → 138 · 296 ms · Boltz-2 0.767 · sandbox smoke 20/20 · 92.0% MEDLINE indexing agreement
- Architecture: the NemoClaw · OpenShell · OpenClaw agent running FlyDiscovery and FlyVigilance through the flygate CLI
- NVIDIA technology usage: for each technology, the code location, the demo screen, its place in the architecture diagram, and real call records ([NVIDIA_CALL_LOG_v1.0.0.md](NVIDIA_CALL_LOG_v1.0.0.md), Korean)
- FlyGate Agent CLI installation and use (flygate.kr/#/cli)
- NVIDIA call log (flygate.kr/#/calls)
