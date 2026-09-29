[한국어](README.md) · **English**

# FlyDiscovery

**Pre-market discovery: a workbench that follows a candidate through structure prediction, docking and affinity, and rejects claims that outrun the evidence**

FlyDiscovery is STEP 1 of Project-FlyGate (pre-market discovery); FlyVigilance is STEP 2 (post-market surveillance).
We follow a candidate from the PARP1 crystal structure to an affinity benchmark, scoring each step against the
conventional criterion of that field. Post-market adverse events for the candidate are picked up by the
FlyVigilance [live triage](https://flygate.kr/#/triage).

## Why we built it

Deciding **what the results are allowed to say** matters more than producing more results. The three-tier critic does that job.

| Tier | Check | Model |
| --- | --- | --- |
| 1 | Does the claim carry an evidence ID? | not used |
| 2 | Do the numbers match the raw logs (`measurements/`)? | not used |
| 3 | Does the reasoning stay inside the evidence? | LLM |

A claim can be rejected at tier 3 even when every number is right. "PARP1 -10.178, Factor Xa -7.967, therefore it is
selective for PARP1" quotes two measured values, but docking scores from different proteins cannot be compared, so it
is rejected. The interpretation limits applied at tier 3 are in `DISCOVERY_RULES` (D1–D9) in `api/_fv/discovery.py`.

## Screens

Seven STEP 1 menus in the dashboard ([flygate.kr](https://flygate.kr)). The screen code is in `web/src/pages/Discovery*.tsx`.

| Menu | Content |
| --- | --- |
| Full pipeline | Five-step 3D autoplay, four headline metrics, drug panel (FAERS cases ↔ redocking ↔ STEP 2 links) |
| 1 MSA-Search | 100 homologous sequences aligning over the binding-pocket window, per-residue conservation |
| 2 OpenFold3 | The predicted structure drawn residue by residue, overlaid on the crystal structure (protein only, no drug) |
| 3 DiffDock | Docking that zooms into the binding pocket, a dock-it-yourself panel, a redocking stream |
| 4 Boltz-2 | Predicted pIC50 against measured ChEMBL values, 39-compound benchmark scatter |
| 5 Critic | PARP1 ↔ Factor Xa split screen, three-tier verdicts, two models compared |
| 6 Evidence check | Docking validation gate → pose-ranking reliability → selectivity evidence → candidate evidence card → STEP 2 |

Every step page carries a **flow bar** (what this step received from the previous one and what it passes on) and a
**live run card** (call this step's NIM again right now).

### What runs live

The screen can call NVIDIA NIMs for real. The server is `api/_fv/discovery.py`; the key stays on the server only.

- Each of the five steps (`POST /api/discovery/{msa,openfold3,diffdock,boltz2}`) and the critic
- **Run all five steps** — passes the MSA alignment (a3m) to OpenFold3 and Boltz-2, and the OpenFold3 predicted
  structure to DiffDock as its receptor, calling them in order
- Dock it yourself (`POST /api/dock`) — only combinations that are not already precomputed trigger a call
- **Any target and ligand** — searched on UniProt, RCSB and PubChem and fed straight into the pipeline (pasted SMILES included)
- Download the run record as JSON (evidence IDs, request IDs, numbers)

On failure we never substitute silently: the screen shows a **"replaced with the previous measurement" label together
with the reason**. Every measurement below is precomputed so the screens still work on a deployment without a key.

## Layout

| Path | Content |
| --- | --- |
| `measurements/measurements.json` | Source summary for the numbers on screen |
| `measurements/nim/` | 58 raw NVIDIA NIM responses (MSA, OpenFold3, DiffDock, Boltz-2, critic evaluation) |
| `measurements/pub/` | ChEMBL IDs and affinities, the PARP1 benchmark set |
| `measurements/redock.json` | Redocking summary |
| `measurements/redock_scenes.json` | Coordinates for the redocking 3D scenes |
| `measurements/hero_scene.json` | The lead 3D scene (five steps, three drugs) |
| `measurements/dock_library.json` · `dock_matrix.json` | Dock-it-yourself catalog and precomputed results |
| `measurements/validation.json` | Docking validation gate (five repeats) |
| `measurements/selectivity_evidence.json` | Measured ChEMBL binding records per cell of the docking grid |
| `measurements/evidence_cards.json` | Candidate evidence cards |
| `measurements/structure_candidates.json` | Structure search results for redocking (a human made the final pick) |
| `web/` | The earlier standalone screen. A static page of hardcoded constants with no build step; it remains embedded in the dashboard as an iframe |

Ten scripts in `pipeline/discovery/` produce these measurements.
`web/scripts/sync-discovery.mjs` copies `measurements/` into `web/public/discovery/data/` (automatic on predev and prebuild).

Five skills written to the NVIDIA skill specification live in `skills/discovery-*/`
(msa-search, openfold3, diffdock, boltz2-affinity, critic). Each `SKILL.md` states its `Do Not Use` and `Limits`.

## Measured results

### NVIDIA NIM (health.api.nvidia.com, called for real with an account key)

| NIM | Result |
| --- | --- |
| MSA-Search | 101 PARP1 homologs (Uniref30_2302), 63.6 s |
| OpenFold3 | pLDDT 95.95, pTM 0.828, ipTM 0.658 · **CA RMSD 1.0 Å** against crystal structure 4R6E, ligand 1.16 Å |
| DiffDock | 14 redockings + 266 precomputed dock-it-yourself combinations + 75 validation-gate repeats |
| Boltz-2 | 8 combinations + affinity prediction over a 39-compound PARP1 benchmark |
| OpenFold2 | HTTP 500 (CUDA error) on 6 attempts; no response was returned by the server, so we proceeded with OpenFold3 |

The MSA-Search → OpenFold3 pairing follows the specification of the official NVIDIA skill
`bionemo-msa-structure-prediction-pipeline`.

### Redocking (a control that puts the co-crystal ligand back in)

The criterion is symmetry-aware heavy-atom top-1 RMSD ≤ 2 Å without alignment. **8 of 14 pass.**

| Class | Passing |
| --- | --- |
| Soluble proteins | 8 / 9 |
| Membrane proteins (GPCRs, transporters) | **0 / 5** |

All five membrane proteins failed. The failing group clusters at cryo-EM 3.3–3.4 Å or X-ray 2.9 Å and worse.

### Docking validation gate (five repeats of the same input, 75 calls)

Structure quality, convergence across repeats and comparison with the crystal pose are combined into a grade:
**HIGH 8 · MEDIUM 3 · LOW 4** over 15 targets.

"It converged on the same place" and "that place is the right one" are different questions. Aripiprazole converged on
nearly the same pose all five times, but more than 10 Å away from the crystal pose, so it is LOW. On a new target with
no crystal structure, convergence alone would have been believed, so the grade puts the crystal comparison first.

### Pose-ranking reliability

We compared **all five** DiffDock poses against the crystal structure, not just the top-ranked one.

- In **10 of 13** redockings a lower-ranked pose landed closer to the truth than the top-ranked one.
- In **3** of those (risperidone, pimavanserin, sildenafil) the top-ranked pose fails the 2 Å criterion while a
  lower-ranked pose falls inside it — sildenafil goes from 2.87 Å at rank 1 to **1.02 Å at rank 3**.
- Failing to find the site and finding it but ranking it wrong are different failures.
  Confidence is a pose-ranking score, not binding strength (D2).

### Selectivity evidence (docking grid + measured ChEMBL)

ChEMBL pChEMBL records are overlaid on the 20-drug × 14-target grid.

- The known target is the **sole top-ranked** target by docking confidence for only **6 of 14** drugs.
- Of the 22 cells that carry a measured binding record, docking confidence also ranked that target first in **9**.
- The evidence grade looks only at whether records exist and at their median. **Docking confidence is not part of the grade.**

### Affinity prediction benchmark

From ChEMBL: 4,180 PARP1 IC50 activities → 3,370 unique compounds → 39 chosen to span the activity range evenly.
Boltz-2 predictions were compared against the ChEMBL median pChEMBL.

| Metric | Value |
| --- | --- |
| Spearman | 0.767 |
| Pearson | 0.746 |
| MAE | 0.71 log units |
| Enrichment (top 25%) | 2.41 (5 of 9) |
| Sensitivity / specificity (pIC50 ≥ 7) | 0.80 / 0.86 |

### Critic

Measured over 8 claims (4 overclaims, 4 valid).

| Model | Overclaims caught | Valid claims passed | Time |
| --- | --- | --- | --- |
| `nemotron-3-super-120b-a12b` | 4 / 4 | 3 / 4 | 41.8 s |
| `nemotron-3.5-lightning-30b-a3b` | 0 / 4 | 1 / 4 | 294.5 s |

Within the given output-token budget the Lightning model spent all its tokens reasoning before the `VERDICT:` line,
so the Super model is used for critic verdicts.

## Limits, stated plainly

- The 0.71 Å redocking RMSD is a **control**: the co-crystal ligand put back into its own structure. It shows the
  docking setup works; it does not mean the binding of a new candidate was predicted (D5).
- 4R6E is a public structure and may have been in the OpenFold3 training data (D9).
- **The affinity benchmark is n = 39 on a single target, PARP1.** Accuracy on the other targets is not established yet.
  We tried to widen it to 14 targets (`pipeline/discovery/benchmark_boltz2_targets.py`, results in
  `measurements/boltz2_targets.json`), but that run used a single sequence without an MSA, so it **cannot be compared
  directly** with the 39-compound benchmark, which used one. Those numbers are kept for reference only.
- **Boltz-2 predictions swing widely with the conditions and between runs.** A control on talazoparib@PARP1:

  | Condition | Predicted pIC50 | Measured (ChEMBL median) |
  | --- | --- | --- |
  | No MSA (single sequence), 3 runs | 6.23 · 6.12 · 6.48 (mean **6.28**) | 9.15 |
  | With MSA, 3 runs | 7.46 · 9.06 · 7.47 (mean **8.00**) | 9.15 |
  | 39-compound benchmark (with MSA) | 8.90 | 9.22 |

  An MSA brings the prediction closer to the measurement, but **three identical runs spread over 1.6 log units.**
  Both the 4R6E and 7KK3 sequences land near 6.2 without an MSA, so the cause is the missing MSA, not the structure.
  Do not pull a single predicted value and quote it (D3).
- The critic numbers come from 8 evaluated claims.
- COX-2 3LN1 is a **mouse** protein and does not transfer to humans (D7).
- Nirmatrelvir is a covalent inhibitor while DiffDock models only non-covalent binding, so that result is for reference only.
- For methotrexate/DHFR the NADPH cofactor was not included in the receptor (ATOM records only).
- Selectivity evidence uses ChEMBL as its only source. BindingDB was not queried separately.
- In the 3D scenes the order in which the ribbon is drawn, the path the pose flies along and the camera are staging.
  **The coordinates it arrives at and the numbers are exactly as returned by the NIMs, RCSB and ChEMBL.**

## Run it

The dashboard is the normal way in.

```bash
npm --prefix web install && npm --prefix web run dev     # http://localhost:5173/#/discovery
```

Live runs need an NVIDIA key on the API server (the key is passed as an environment variable only).

```bash
NVIDIA_API_KEY=... .venv/bin/uvicorn api.index:app --port 8000
```

To rebuild the measurements, run the scripts in `pipeline/discovery/` in order.

```bash
.venv/bin/python pipeline/discovery/redock.py            # redocking → redock.json
.venv/bin/python pipeline/discovery/validate_docking.py  # validation gate → validation.json
.venv/bin/python pipeline/discovery/build_hero_scene.py  # lead scene → hero_scene.json
```

To view only the earlier standalone screen you need a static server (because of `fetch`).

```bash
cd fly_discovery/web && python3 -m http.server 8777      # http://localhost:8777
```

## When you change something

- Check numbers against the raw files in `measurements/`. Where there is no evidence, leave `미조회` (not looked up) or
  `—` and do not fill in an estimate.
- If you rebuild a measurement, check that the file is also in the copy list in `web/scripts/sync-discovery.mjs`.
- The color, font and panel tokens in `web/index.html` hold the same values as the dashboard's `web/src/index.css`.
  Change one and change the other too.
- The credit line in the footer is a license requirement; do not remove it. The color and component tokens come from
  [FDDD](https://github.com/AwesomeZun/FDDD) (fly-connectome-template).

The original is the STEP 1 screen of [Geongyu/flygate](https://github.com/Geongyu/flygate).
