# Unified SIF Scheduler Checkout

Purpose: public SIF support plus one repo that can run either the Slurm fan-out workflow or serial local workflow.

The user-facing switch is:

```bash
export PEPPRED_SCHEDULER=slurm
# or
export PEPPRED_SCHEDULER=local
```

Shell stages share scheduler parsing through `scripts/scheduler.sh`; `start.py` has the equivalent Python-side parser for the top-level NetMHC/coverage/fold decision. Slurm remains the validated production default. Local mode is additive and should be documented as smoke-tested unless a full no-Slurm validation is run.

PyRosetta dihedrals are attempted by default; set `PEPPRED_ENABLE_PYROSETTA=0` to use the SIF-compatible Biopython fallback.

`run_peppred.sh` loads an optional `peppred-public.env` file, accepts `--scheduler slurm|local`, sets common run metadata, and calls `python3 start.py`.
