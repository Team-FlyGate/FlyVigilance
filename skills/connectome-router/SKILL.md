---
name: connectome-router
description: Use when rendering or reasoning about FlyVigilance's routing topology — the MaleCNS central-brain subgraph (49,244 neurons, 1.05M signed edges) mapped to agent layers, with a browser rate model driven by agent decisions.
license: Apache-2.0 (code) · MaleCNS data CC-BY 4.0 (Janelia FlyEM)
metadata:
  author: FlyVigilance
  layer: all
  tags: [connectome, drosophila, malecns, visualization]
---

# Connectome Router

- Build: `pipeline/connectome/select_subgraph.py` → `build_roi_meshes.py` → `build_web_connectome.py`.
- Layer assignment by anatomy: sensory→intake channels, AL PN→encoding, LH→reflex, KC/MBON/DAN→memory, CX→deliberation, GABAergic intrinsic→critic, DN→action, AN→feedback.
- Edge weight = synapses / post-synaptic input total, signed by predicted neurotransmitter (ACh +, GABA/Glu −).
- Dynamics: `x ← 0.6x + 0.4·relu(tanh(8·Wx + I − 0.05 − 3a))`, adaptation `a ← a + 0.1(x − a)`.
- Agent decisions inject current into the matching populations; propagation is the real wiring. It is a routing visualization, never clinical evidence.
