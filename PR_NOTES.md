# Minimal SIF Compatibility Checkout

This checkout does not add local/no-Slurm execution. The workflow remains:

1. `start.py` submits NetMHC jobs.
2. `start.py` submits coverage after NetMHC.
3. `start.py` submits `AFFT-HLA3DB/fold.sh`.
4. `fold.sh` fans out AFFT GPU jobs and then submits Protpardelle.
5. `protpardelle/run.sh` fans out Protpardelle GPU jobs and then submits inference.
6. `Inference/list.sh` keeps the Slurm array plus merge pattern.

SIF behavior is opt-in through `PEPPRED_SIF` or `SIF`. If no SIF is set, scripts keep using the original host conda/setup placeholders.

PyRosetta dihedrals are attempted by default; set `PEPPRED_ENABLE_PYROSETTA=0` to use the SIF-compatible Biopython fallback.

`run_peppred.sh` is a thin Slurm-only wrapper for loading an optional `peppred-public.env` file, setting common run metadata, and calling `python3 start.py`.
