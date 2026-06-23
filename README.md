# PepPred

PepPred predicts structural similarity for 9-mer peptide antigens across HLA alleles. This branch supports the recommended public Singularity/Apptainer image path while preserving the legacy host-conda execution path for development and collaborator use.

## Runtime Environments

The SIF contains four conda environments:

| Environment | Purpose |
| --- | --- |
| `alphafold` | AFFT/AlphaFold structure prediction |
| `compare` | NetMHC parsing, coverage, structure preprocessing, dihedrals |
| `train` | Final feature extraction, PCA, pairing, inference, visualization |
| `protpardelle` | Protpardelle sampling |

Use `conda run` inside the container rather than activating environments in job scripts.

## External Requirements

| Asset/tool | Bundled in SIF? | Current release policy |
| --- | --- | --- |
| NetMHCpan | No | User-provided under DTU terms |
| Rosetta/PyRosetta | No | Optional user-provided parity path |
| PepPred/AFFT model assets | No | Shipped in the companion `peppred-model-assets-v0.1.0.tar.zst` archive |
| Protpardelle model assets | No | Shipped in the companion `peppred-model-assets-v0.1.0.tar.zst` archive |
| Foldseek | No | Shipped in the companion archive for the validated path; review license before public upload |

## Release Artifacts

The validated SIF stays separate from the large model/tool assets. Download the
public release files from <https://zenodo.org/records/20076767>:

```text
peppred-v0.1.0.sif
peppred-v0.1.0.sif.sha256
peppred-model-assets-v0.1.0.tar.zst
peppred-model-assets-v0.1.0.tar.zst.sha256
peppred-model-assets-v0.1.0.MANIFEST.sha256
```

Verify the downloads if the checksum files are available, then extract the
companion asset archive:

```bash
sha256sum -c peppred-v0.1.0.sif.sha256
sha256sum -c peppred-model-assets-v0.1.0.tar.zst.sha256
tar -I zstd -xf peppred-model-assets-v0.1.0.tar.zst
```

This creates `peppred-model-assets-v0.1.0/`. Do not move individual model files
out of that directory; set `PEPPRED_ASSETS_HOST` to the extracted directory.

## Public Configuration

Start from:

```bash
cp peppred-public.env.example peppred-public.env
```

Users normally edit only `peppred-public.env` and the input CSV. The runner
script reads the env file and calls `start.py`.

For SIF runs, set these required runtime paths:

```bash
export PEPPRED_ROOT=/path/to/peppred
export PEPPRED_SIF=/path/to/peppred-v0.1.0.sif
export PEPPRED_ASSETS_HOST=/path/to/peppred-model-assets-v0.1.0
export PEPPRED_NETMHCPAN_HOST_DIR=/path/to/netmhcpan
```

For host-conda runs, leave `PEPPRED_SIF` and `SIF` unset. Configure the host
conda and NetMHCpan paths through `setup.py` or the host-conda environment
variables in the section below.

Set these cluster values:

```bash
export PEPPRED_SCHEDULER=slurm
export PEPPRED_CPU_PARTITION=normal
export PEPPRED_GPU_PARTITION=gpu
export PEPPRED_GPU_GRES=gpu:1
export PEPPRED_GPU_CONSTRAINT=
```

The v0.1.0 SIF is validated on NVIDIA A100/compute capability 8.x. On Sherlock,
set `PEPPRED_GPU_CONSTRAINT=GPU_CC:8.0`. H100/compute capability 9.x requires an
updated image with compatible TensorFlow/JAX GPU builds.

The derived asset paths and validated defaults in `peppred-public.env.example`
usually do not need to change:

```bash
export PEPPRED_ASSETS_CONTAINER=/scratch/peppred-model-assets-v0.1.0
export PEPPRED_MODEL_PARAMS_HOST="${PEPPRED_ASSETS_HOST}/model_params"
export PEPPRED_MODEL_PARAMS_CONTAINER="${PEPPRED_ASSETS_CONTAINER}/model_params"
export PEPPRED_AFFT_PARAMS="${PEPPRED_ASSETS_CONTAINER}/AFFT-HLA3DB/params/7WKJ_af_mhc_params_2351.pkl"
export PEPPRED_INFERENCE_MODEL_BUNDLE="${PEPPRED_ASSETS_CONTAINER}/Inference/peppred.pkl"
export FOLDSEEK_BIN="${PEPPRED_ASSETS_CONTAINER}/tools/foldseek/bin/foldseek"
export ALPHAFOLD_ENV_CONTAINER=/opt/conda/envs/alphafold
export ALPHAFOLD_PYTHON_CONTAINER=/opt/conda/envs/alphafold/bin/python
export NUM_SAMPLES=2
export NUM_MPNN_SEQS=0
```

Keep `NUM_MPNN_SEQS=0` unless intentionally testing an unvalidated path. Pass
run-specific values such as `--input`, `--run-id`, `--scheduler`, `--samples`,
and `--mpnn` to `run_peppred.sh` instead of editing the env file each run.

PyRosetta is attempted by default for dihedrals. If it is not installed in the
active Python environment, set `PEPPRED_PYROSETTA_PATH` to a compatible
PyRosetta package path. For SIF runs, also set `PEPPRED_PYROSETTA_HOST_PATH` and
`PEPPRED_PYROSETTA_CONTAINER_PATH` if that package is outside an already-bound
directory. Set `PEPPRED_ENABLE_PYROSETTA=0` to use the Biopython fallback.

## Runtime And Scheduler Modes

The unified checkout has two independent switches:

| Switch | Values | Effect |
| --- | --- | --- |
| `PEPPRED_SIF` | set or unset | Set it to run stages through Singularity/Apptainer. Leave it unset to use host conda environments and host paths. |
| `PEPPRED_SCHEDULER` | `slurm` or `local` | `slurm` submits jobs with dependencies. `local` runs the same stage order serially on the current node. |

The public runner accepts scheduler mode as a per-run flag, which is the easiest
way to switch Slurm versus local execution:

```bash
./run_peppred.sh --env peppred-public.env --input input.csv --scheduler slurm
./run_peppred.sh --env peppred-public.env --input input.csv --scheduler local
```

`run_peppred.sh` normalizes the flag or env value, then exports
`PEPPRED_SCHEDULER` before calling `start.py`. `start.py` reads that value for
the top-level NetMHC, coverage, and fold orchestration. Shell sub-stages source
`scripts/scheduler.sh`, which provides the shared `peppred_is_local` and
`peppred_is_slurm` checks.

In `slurm` mode, `start.py` submits NetMHC jobs, then coverage, then
`AFFT-HLA3DB/fold.sh` as dependent Slurm jobs. The fold, Protpardelle, list, and
inference stages continue submitting their validated Slurm fan-out and
dependency jobs. If `PEPPRED_SIF` is set, those jobs invoke the SIF. If it is
unset, they activate the host conda environments configured by `setup.py`.

In `local` mode, `start.py` runs NetMHC directly, runs coverage, then calls
`AFFT-HLA3DB/fold.sh` with `PEPPRED_SCHEDULER=local`. Downstream stages run
serial loops instead of `sbatch`. Local mode uses the SIF only when
`PEPPRED_SIF` is set; otherwise it uses the host-conda path.

## Host Conda Environments

Host conda remains a supported non-SIF runtime when `PEPPRED_SIF` and `SIF` are
unset. It is also useful for rebuilding the SIF and debugging individual
modules. The expected environment names are `alphafold`, `compare`, `train`,
and `protpardelle`. If your HPC home directory has limited space, configure
conda to place named environments in scratch before creating them.

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

Host conda use also requires a host NetMHCpan install and the model/tool assets
expected by the pipeline. Slurm is required only when using
`PEPPRED_SCHEDULER=slurm`; `PEPPRED_SCHEDULER=local` runs serially. Follow
`protpardelle/README.md` for Protpardelle weights, Foldseek, and optional
ProteinMPNN/ESMFold assets.

Configure paths through environment variables before running `setup.py`:

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

Verify the host environments before using them:

```bash
conda activate compare && python -c "import pymol; import Bio"
conda activate train && python -c "import sklearn; import lightgbm"
conda activate alphafold && python -c "import jax; import openmm"
```

If using PyRosetta in host conda mode, install it into `compare` or set
`PEPPRED_PYROSETTA_PATH` to a Python-compatible package path before running the
pipeline.

## Input

`input.csv` rows are:

```text
Trial_Name,Peptide,Allele1,Allele2,...
```

Example:

```text
PHOX2B,QYNPIRTTF,A*24:02
```

Alleles may also be written as `A24:02`; they are normalized to `A*24:02`.
Avoid `Trial_Name` values beginning with `pep`; those are treated as headers.

## Slurm-Oriented Run

The current validated public workflow submits Slurm jobs from the host and each
job invokes the SIF. Host-conda Slurm mode remains available when `PEPPRED_SIF`
is unset and `setup.py` has written the host paths. Do not start SIF mode from
inside an already-entered container unless nested Singularity/Apptainer is
available.

```bash
cd "$PEPPRED_ROOT"
./run_peppred.sh --env peppred-public.env --input input.csv --scheduler slurm --run-id my_run
```

Monitor with:

```bash
squeue -u "$USER"
```

## Local Serial Run

Local mode is implemented for single-node testing and passed the PHOX2B SIF
smoke test on 2026-06-14. It runs each stage serially instead of submitting
nested Slurm jobs. With `PEPPRED_SIF` set, it uses the same SIF, external
NetMHCpan bind, and companion asset configuration. With `PEPPRED_SIF` unset, it
uses the host-conda path. Runtime and GPU behavior still depend on input size,
driver compatibility, and local resources:

```bash
cd "$PEPPRED_ROOT"
./run_peppred.sh --env peppred-public.env --input input.csv --scheduler local --run-id local_smoke
```

Expected local execution order: NetMHCpan, coverage, AFFT initialization, serial AFFT predictions, serial Protpardelle sampling, PDB listing, dihedrals, final inference, and `6_output.py` packaging. Keep `NUM_MPNN_SEQS=0`; the ProteinMPNN path was not part of the PHOX2B smoke test. Set `PEPPRED_PROTPARDELLE_SEED` only when you need deterministic Protpardelle sampling.

## Collaborator Checklist

The current internal collaborator checklist records the exact validated SIF,
checksum, result path, fixture settings, and release blockers. Keep public
release notes free of Sherlock-specific scratch paths unless they are clearly
marked as validation provenance.
