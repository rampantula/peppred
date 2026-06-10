#!/bin/bash

# =========================
# USER SETTINGS
# =========================
CONDA_ENV="compare"
PYTHON_SCRIPT="genlist.py"
LOG_DIR="logs"

ARRAY_TIME="04:00:00"
ARRAY_MEM="4G"
ARRAY_CPUS="1"

MERGE_TIME="00:30:00"
MERGE_MEM="2G"
MERGE_CPUS="1"

mkdir -p "$LOG_DIR"

# =========================
# SUBMIT ARRAY JOB
# =========================
ARRAY_JOB_ID=$(sbatch --parsable <<EOF
#!/bin/bash
#SBATCH --job-name=pdb_table
#SBATCH --output=${LOG_DIR}/pdb_table_%A_%a.out
#SBATCH --error=${LOG_DIR}/pdb_table_%A_%a.err
#SBATCH --time=${ARRAY_TIME}
#SBATCH --cpus-per-task=${ARRAY_CPUS}
#SBATCH --mem=${ARRAY_MEM}
#SBATCH --array=0-4

source {{CONDA}}
conda activate ${CONDA_ENV}

python ${PYTHON_SCRIPT}
EOF
)

# =========================
# SUBMIT MERGE JOB
# =========================
MERGE_JOB_ID=$(sbatch --parsable --dependency=afterok:${ARRAY_JOB_ID} <<EOF
#!/bin/bash
#SBATCH --job-name=merge_pdb_table
#SBATCH --output=${LOG_DIR}/merge_pdb_table_%j.out
#SBATCH --error=${LOG_DIR}/merge_pdb_table_%j.err
#SBATCH --time=${MERGE_TIME}
#SBATCH --cpus-per-task=${MERGE_CPUS}
#SBATCH --mem=${MERGE_MEM}

source {{CONDA}} 
conda activate ${CONDA_ENV}

export MERGE_PARTIALS=1
python ${PYTHON_SCRIPT}
EOF
)

echo "${MERGE_JOB_ID}"