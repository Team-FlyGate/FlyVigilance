---
name: discovery-evidence
description: Use when a pre-market (STEP 1 FlyDiscovery) question comes up — PARP1 / Factor Xa / COX-2 structure, docking or affinity for niraparib and its comparators. Reads the measured NVIDIA BioNeMo NIM results (MSA-Search, OpenFold3, DiffDock, Boltz-2) and ChEMBL values through `flygate discover`, applies the discovery claim rules, and hands the same molecule to STEP 2 FlyVigilance.
license: Apache-2.0
metadata:
  author: Project-FlyGate
  stage: discovery
  tool: flygate discover
---

# Discovery evidence (STEP 1 FlyDiscovery)

## Run

```bash
flygate discover parp1     # PARP1 4R6E-A: structure, 4 PARP ligands, affinity benchmark, critic record
flygate discover xa        # Factor Xa 2P16: apixaban redock control + exploratory niraparib cross-dock
flygate discover cox2      # COX-2 3LN1 (mouse protein): celecoxib redock control + exploratory cross-dock
```

Every number in the output carries an evidence ID: `msa:`, `openfold3:`, `vina:`, `diffdock:`, `boltz2:`, `chembl:`.
Copy IDs exactly when writing a claim, then run the claim through `flygate critic`.

## What the measurements say

| Step | NVIDIA BioNeMo NIM | Measured (PARP1) |
|---|---|---|
| Homolog search | MSA-Search | 101 homologs, 63.6 s |
| Structure | OpenFold3 | pLDDT 95.95, CA RMSD 1.0 Å vs crystal 4R6E |
| Pose | DiffDock | niraparib redock 0.71 Å (setup control) |
| Affinity | Boltz-2 | 39-compound PARP1 benchmark vs ChEMBL, Spearman 0.767 |

## Claim rules (reject when a claim …)

| Rule | Reject when the claim … |
|---|---|
| `cross-target` | compares docking scores across different proteins or infers selectivity from them |
| `confidence≠affinity` | reads DiffDock confidence as binding strength |
| `predicted≠measured` | calls a Boltz-2 pIC50 a measurement |
| `n<8` | computes a correlation over fewer than eight paired points |
| `redock≠prospective` | treats co-crystal redocking as prospective prediction |
| `cross-dock` | treats an exploratory cross-docking pose as evidence of binding |
| `species` | carries a non-human protein result (COX-2 3LN1 is mouse) to humans |
| `plddt≠affinity` | reads structure confidence as binding strength |

Example: "niraparib PARP1 -10.178 vs Factor Xa -7.967, so PARP1-selective" is rejected under `cross-target`;
both numbers are real, the comparison is not defined across proteins. Selectivity comes from measured affinity (ChEMBL).

## Hand-off to STEP 2

`handoff_to_vigilance` names the next command for the same molecule:
`flygate grade NIRAPARIB thrombocytopenia` (post-market FAERS SDR, label section, literature → PV class candidate).
