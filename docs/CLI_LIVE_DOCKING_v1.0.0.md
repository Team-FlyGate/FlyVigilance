# FlyGate CLI · live DiffDock v1.0.0

The interactive guide is at https://project-flygate.vercel.app/#/cli.

## Run a new docking job

After `./scripts/install_flygate.sh`, set `NVIDIA_API_KEY` in the repository-root `.env` or your environment. Keys are never command arguments. From the repository root:

```bash
flygate discover --live \
  --protein fly_discovery/measurements/nim/of3_parp1_niraparib.pdb \
  --ligand-file agent/examples/niraparib.smi \
  --num-poses 5 --timeout 300
```

This example uses the existing PARP1 OpenFold3 predicted structure and the niraparib SMILES recorded in the project's NIM response. Replace these with your protein PDB and single-ligand SDF or SMILES file. Alternatively pass a single SMILES string using `--smiles`. The remote service validates chemical inputs. Only protein ATOM records, TER and END records are sent from the PDB, excluding co-crystallized ligands and solvent.

A new `data/discovery-runs/<run_id>/` directory stores input.json, manifest.json, response.json and pose_01.sdf (plus further poses). Each completed pose has an evidence ID. The manifest records the endpoint, UTC timestamps and input/output SHA-256 hashes. These run directories are gitignored; existing benchmark measurements are unchanged.

## Resume, without submitting another job

If `status` is `pending`, use the `run_dir` printed by the CLI:

```bash
flygate discover --resume data/discovery-runs/<run_id>
```

A known request ID is polled through `/v1/status/`. There are no automatic POST retries. If submission times out without a request ID, the outcome is `unknown`; investigate before issuing a new job. `failed` and `unknown` exit with code 1. `pending` indicates accepted or resumable work, not a completed prediction. Completed runs return their manifest on resume without a network call.

## Endpoint and interpretation

This implementation uses the project-tested hosted endpoint `https://health.api.nvidia.com/v1/biology/mit/diffdock`, already allowed by the OpenShell policy. The current reference page lists `/v1/molecular-docking/diffdock/generate`; it returned HTTP 404 in this environment on 2026-09-28, while the existing biology endpoint completed a fresh request. No automatic endpoint fallback or duplicate submission is performed.

The API returns ligand SDF poses and position confidence. This command does not calculate binding affinity or reference-pose RMSD. It does not automatically run MSA, structure prediction or Boltz-2. Other FlyDiscovery measurements remain available through `flygate discover parp1`.

API contract: https://docs.api.nvidia.com/nim/reference/mit-diffdock-infer
Output schema: https://docs.nvidia.com/nim/bionemo/diffdock/latest/getting-started.html

## Live verification

On 2026-09-28, run `20260928T065303Z-7e5e019558` completed using the example inputs and `--num-poses 1`. One SDF pose was saved; position confidence was -0.5751419663. This is connectivity/output verification, not an accuracy benchmark.
