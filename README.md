## PepPred

PepPred is a structural similarity prediction program that utilizes sequence information of 9mer peptide antigens and predicted binder HLA alleles to generate structural comparisons of the peptide backbone conformations between two alleles presenting a shared antigen.

## Program Dependencies

This program requires the following pre-installed dependencies:
- Anaconda: https://www.anaconda.com/download
- Rosetta: https://docs.rosettacommons.org/demos/latest/tutorials/install_build/install_build
- TensorFlow (Recommend using conda to create a Tensor-specific environment): https://www.tensorflow.org/install/pip
- NetMHCpan 4.1: https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/

Additionally, this program utilizes SLURM job scheduling to parallelize prediction and inference jobs.

## Environment Overview

This pipeline uses four conda environments:

| Environment | Purpose | Used by |
|---|---|---|
| `alphafold` | AlphaFold2 structure prediction | `AFFT-HLA3DB/` preprocessing scripts |
| `compare` | Main pipeline runtime, MHC scoring, dihedral calculation | `start.py`, `Inference/inference.sh` |
| `train` | Model inference and training | `Inference/1_extract.py` through `6_output.py` |
| `protpardelle` | Structural sampling via Protpardelle-1c | `protpardelle/run.sh` |

## SETUP

### 1. Clone the repository

```bash
git clone https://github.com/rampantula/peppred.git
cd peppred
```

### 2. Set up Protpardelle

Protpardelle is included as a subdirectory. Follow the instructions in `protpardelle/README.md` to:
- Create the `protpardelle` conda environment
- Download model weights from Zenodo
- Install Foldseek

### 3. Download custom parameters

Download from: https://zenodo.org/records/20076767

Follow the README inside the `parameters/` directory to install each file in its correct location.

### 4. Create conda environments

```bash
# Install to a location you control (replace /your/path/ with an absolute path)
conda env create -f alphafold.yml --prefix /your/path/alphafold
conda env create -f compare.yml --prefix /your/path/compare
conda env create -f train.yml --prefix /your/path/train
```

> **Note:** The yml files have hardcoded `prefix:` lines pointing to the original developer's paths. The `--prefix` flag overrides these. Choose a location with sufficient storage (e.g., `$SCRATCH/peppred/envs/` on Sherlock).

If you encounter Jax version issues with the alphafold environment, resolve with:

```bash
conda activate alphafold
pip install --upgrade "jax==0.4.1" "jaxlib==0.4.1+cuda11.cudnn86" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
```

### 5. Configure paths and partitions

Open `setup.py` and fill in the configuration section at the top:

```python
ROOT = "/full/path/to/peppred"          # absolute path to this repo
ROSETTA = "/full/path/to/rosetta/main"  # Rosetta main directory
CONDA = "/full/path/to/anaconda3/bin/activate"
TENSOR = "..."                          # tensorrt lib path (ask your cluster admin)
NMHC = "/full/path/to/netMHCpan-4.1/netMHCpan"
PARTITION_GPU = "gpu"                   # SLURM partition for GPU jobs
PARTITION_SHORT = "normal"              # SLURM partition for short CPU jobs
```

Then run:

```bash
python setup.py
```

This replaces all `{{VARIABLE}}` placeholders in the configuration files. The script modifies files in place and creates `.bak` backups of the originals.

> **Important:** If you change any path or partition values, re-run `python setup.py`.

### 6. Verify the installation

```bash
conda activate compare && python -c "import pymol"
conda activate train && python -c "import sklearn; import lightgbm"
conda activate alphafold && python -c "import jax; import openmm"
```

## USAGE

### Prepare input

Fill `input.csv` with the following format:

```
Trial_Name, peptide sequence, Allele1, Allele 2, ...
```

- Allele format must match `A*02:01` (e.g., `A0201` is also accepted and auto-corrected)
- Only 9mer peptides are supported
- `Trial_Name` must not contain special characters (underscore `_` is allowed) or spaces
- A test case is included in the repository

### Run the pipeline

```bash
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