## PepPred
PepPred is a structural similarity prediction program that utilizes sequence information of 9mer peptide antigens and predicted binder HLA alleles to generate structural comparisons of the peptide backbone conformations between two alleles presenting a shared antigen.

Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
Licensed for academic and non-commercial use only. Commercial use requires a separate license.
See LICENSE file for details.

## Runtime Options

The recommended public runtime is the PepPred Singularity/Apptainer image plus
the companion model-asset archive. The pipeline still supports the original
host conda setup when `PEPPRED_SIF` is unset.

SIF runs require:
- Singularity or Apptainer
- Slurm
- the PepPred `.sif`
- the extracted companion model/tool asset archive
- a user-provided NetMHCpan install

Host conda runs require the original conda environments and host NetMHCpan
paths configured through `setup.py`, and set up throught the local_env folder.

## Local Environment Overview

This pipeline uses four conda environments:

| Environment | Purpose | Used by |
|---|---|---|
| `alphafold` | AlphaFold2 structure prediction | `AFFT-HLA3DB/` preprocessing scripts |
| `compare` | Main pipeline runtime, MHC scoring, dihedral calculation | `start.py`, `Inference/inference.sh` |
| `train` | Model inference and training | `Inference/1_extract.py` through `6_output.py` |
| `protpardelle` | Structural sampling via Protpardelle-1c | `protpardelle/run.sh` |

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/rampantula/peppred.git
cd peppred
```

### 2. Download and extract SIF release files

Download the public SIF release files from
<https://zenodo.org/records/20076767>:

```text
peppred-v0.1.0.sif
peppred-model-assets-v0.1.0.tar.zst
```

Verify the downloads if the  files are available, then extract the
companion asset archive:

```bash
tar -I zstd -xf peppred-model-assets-v0.1.0.tar.zst
```

This creates `peppred-model-assets-v0.1.0/`. Do not move individual model files
out of that directory; the runtime paths below point into the extracted asset
tree.

### 3. Configure SIF runtime paths

For SIF runs, copy the env template and edit the copy:

```bash
cp peppred-public.env.example peppred-public.env
```

Users normally set these values in `peppred-public.env`:

```bash
export PEPPRED_SIF=/path/to/peppred.sif
export PEPPRED_NETMHCPAN_HOST_DIR=/path/to/netmhcpan
export PEPPRED_ASSETS_HOST=/path/to/peppred-model-assets-v0.1.0
export PEPPRED_CPU_PARTITION=normal
export PEPPRED_GPU_PARTITION=gpu
export PEPPRED_GPU_GRES=gpu:1
export PEPPRED_GPU_CONSTRAINT=
```

The v0.1.0 SIF is validated on NVIDIA A100/compute capability 8.x. On Sherlock,
set `PEPPRED_GPU_CONSTRAINT=GPU_CC:8.0`. H100/compute capability 9.x requires an
updated image with compatible TensorFlow/JAX GPU builds.

Set `PEPPRED_ASSETS_HOST` to the extracted `peppred-model-assets-v0.1.0`
directory, not to the `.tar.zst` file.

The derived asset paths, `NUM_SAMPLES=2`, and `NUM_MPNN_SEQS=0` defaults in
`peppred-public.env.example` usually do not need to change. Keep
`NUM_MPNN_SEQS=0` unless intentionally testing an unvalidated path.

PyRosetta is attempted by default for dihedrals. If it is not installed in the
active Python environment, set `PEPPRED_PYROSETTA_PATH` to a compatible
PyRosetta package path. For SIF runs, also set `PEPPRED_PYROSETTA_HOST_PATH` and
`PEPPRED_PYROSETTA_CONTAINER_PATH` if that package is outside an already-bound
directory. Set `PEPPRED_ENABLE_PYROSETTA=0` to use the Biopython fallback.

Use runner flags for run-specific values:

```bash
./run_peppred.sh --env peppred-public.env --input input.csv --run-id my_run
```

### 4. ALTERNATE RUNTIME OPTION: Set up host conda environments

Use this path only when running without the SIF. Leave `PEPPRED_SIF` and `SIF`
unset. The scripts activate environments by name, so create `alphafold`,
`compare`, `train`, and `protpardelle` as named conda environments. If your HPC
home directory has limited space, configure conda to place named environments in
scratch before creating them.

```bash
conda env create -f alphafold.yml
conda env create -f compare.yml
conda env create -f train.yml

cd protpardelle
conda create -n protpardelle python=3.12 --yes
conda activate protpardelle
bash setup.sh
bash download_model_params.sh
cd ..
```

Host conda runs also require a host NetMHCpan install, Slurm, and the model/tool
assets expected by the pipeline. Follow `protpardelle/README.md` for
Protpardelle weights, Foldseek, and optional ProteinMPNN/ESMFold assets.

Configure runtime paths through environment variables, then run `setup.py` to
write the legacy placeholders:

```bash
unset PEPPRED_SIF SIF
export PEPPRED_ROOT="$PWD"
export PEPPRED_CONDA_ACTIVATE=/path/to/miniconda3/bin/activate
export PEPPRED_NETMHCPAN_BIN=/path/to/netMHCpan
export PEPPRED_GPU_PARTITION=gpu
export PEPPRED_CPU_PARTITION=normal
export PEPPRED_ROSETTA_DIR=/path/to/rosetta/main  # optional

# PyRosetta is attempted by default. Use 0 if running the Biopython fallback.
export PEPPRED_ENABLE_PYROSETTA=0

python setup.py
```

Verify the host environments before submitting a run:

```bash
conda activate compare && python -c "import pymol; import Bio"
conda activate train && python -c "import sklearn; import lightgbm"
conda activate alphafold && python -c "import jax; import openmm"
```

If using PyRosetta in host conda mode, install it into `compare` or set
`PEPPRED_PYROSETTA_PATH` to a Python-compatible package path before running the
pipeline.

## USAGE

### Prepare input

Fill `input.csv` with the following format:

```
Trial_Name,Peptide,Allele1,Allele2,...
```

- Allele format must match `A*02:01`; `A02:01` is also accepted and normalized
- Only 9mer peptides are supported
- Avoid `Trial_Name` values beginning with `pep`; those are treated as headers
- A test case is included in the repository

### Run the pipeline

For SIF runs:

```bash
./run_peppred.sh --env peppred-public.env --input <input.csv> --run-id my_run
```

For host conda runs:

```bash
unset PEPPRED_SIF SIF
python setup.py
conda activate compare
python start.py <input.csv>
```

The pipeline submits SLURM jobs automatically. Monitor progress with:

```bash
squeue -u <username>
```

### Output

Results are written to `results/`:
- `netMHCpan_coverage.csv` — binding allele coverage statistics
- `netmhcpan_text_summary.txt` — per-peptide summary of binders and coverage
- `Inference/structures/` — PDB structures from AlphaFold and Protpardelle
- `Inference/out/` — final pipeline outputs from `1_extract.py` through `6_output.py`
