---
name: "connectome-router"
title: "Connectome Router"
version: "1.0.0"
description: "Use when building, rendering or explaining the FlyVigilance routing topology: the MaleCNS central-brain subgraph (49,244 neurons, 1,051,255 signed edges) mapped to the agent's nine layers, with a browser rate model that agent decisions drive. Do not use for clinical, causal or regulatory conclusions; the connectome is a routing visualization."
license: "Apache-2.0 (code); MaleCNS data CC-BY-4.0 (Janelia FlyEM)"
compatibility: "Python 3.11+ with DuckDB, pandas, pyarrow, numpy, trimesh for the build; MaleCNS v1.0 flat connectome and ROI meshes (Janelia FlyEM); WebGL browser for the view. Calls no model endpoint."
metadata:
  version: "1.0.0"
  author: "Team FlyGate"
  layer: "all"
  domain: "visualization"
  tags:
    - connectome
    - drosophila
    - malecns
    - visualization
    - agent-routing
---

# Connectome Router

## When to Use

- Rebuilding the connectome assets after a MaleCNS update or a change to the layer mapping.
- Explaining which agent layer a brain population stands for, or why a decision lights up a region in the dashboard.
- Tuning the browser rate model (gain, decay, adaptation) in `web/src/lib/connectome.ts`.

## Do Not Use

- As evidence for a pharmacovigilance claim. Propagation shows routing only and never supports causality, seriousness or a signal.
- For FAERS statistics or case triage; use `faers-warehouse`, `pv-signal-memory` or `pv-reflex-triage`.

## Requirements

No credentials. MaleCNS files are public downloads from the `flyem-male-cns` Google Cloud Storage bucket, and the view runs in the browser.

## Instructions

1. Fetch data: `scripts/download_malecns.sh` (flat connectome, skeletons) and `scripts/download_malecns_rois.py` (neuropil meshes).
2. `.venv/bin/python pipeline/connectome/select_subgraph.py` keeps central-brain superclasses, drops edges under 5 synapses, keeps the 32 strongest inputs per post-synaptic neuron and signs each neuron by predicted neurotransmitter (ACh +, GABA/Glu/histamine −). Output: `data/derived/connectome/`.
3. `.venv/bin/python pipeline/connectome/build_roi_meshes.py` merges ROI meshes into `web/public/data/brain_rois.glb`.
4. `.venv/bin/python pipeline/connectome/build_web_connectome.py` writes `web/public/data/connectome/` (`meta.json`, `neurons.bin`, `cloud.bin`, `edges.bin`, `skeletons.json`).

## Layer Mapping

Sensory neurons → intake channels · antennal-lobe PN → encoding · lateral horn → reflex · KC/MBON/DAN → memory · central complex → deliberation · GABAergic intrinsic → critic · protocerebrum intrinsic → association · descending neurons → action · ascending neurons → reviewer feedback.

## Dynamics

- Edge weight = synapses / total synaptic input of the post-synaptic neuron, signed by neurotransmitter.
- Rate: `x ← 0.6x + 0.4·relu(tanh(8·Wx + I − 0.05 − 3a))`; adaptation `a ← a + 0.1(x − a)`.
- Agent decisions inject current into the matching populations; propagation follows the real wiring.
