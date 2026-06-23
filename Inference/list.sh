#!/bin/bash

set -euo pipefail

CONDA_ENV="compare"
PYTHON_SCRIPT="genlist.py"
LOG_DIR="logs"

ARRAY_TIME="04:00:00"
ARRAY_MEM="4G"
ARRAY_CPUS="1"

MERGE_TIME="00:30:00"
MERGE_MEM="2G"
MERGE_CPUS="1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIF="${PEPPRED_SIF:-${SIF:-}}"
ROOT="${PEPPRED_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
CPU_PARTITION="${PEPPRED_CPU_PARTITION:-normal}"
SCRATCH="${SCRATCH:-/scratch}"

mkdir -p "$LOG_DIR"

if [[ -z "${SIF}" ]]; then
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
    exit 0
fi

: "${PEPPRED_NETMHCPAN_HOST_DIR:?Set PEPPRED_NETMHCPAN_HOST_DIR to the host NetMHCpan parent directory}"
NETMHCPAN_HOST_DIR="${PEPPRED_NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${PEPPRED_NETMHCPAN_CONTAINER_DIR:-/container/software/netmhcpan}"

run_in_container() {
    singularity exec \
        --cleanenv \
        --bind "${ROOT}:${ROOT}" \
        --bind "${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR}" \
        --bind "${SCRATCH}:/scratch" \
        --env PYTHONPATH= \
        "${SIF}" \
        /opt/conda/bin/conda run -n ${CONDA_ENV} python "${PYTHON_SCRIPT}" "$@"
}

ARRAY_JOB_ID=$(sbatch --parsable --partition="${CPU_PARTITION}" <<EOF
#!/bin/bash
#SBATCH --job-name=pdb_table
#SBATCH --output=${LOG_DIR}/pdb_table_%A_%a.out
#SBATCH --error=${LOG_DIR}/pdb_table_%A_%a.err
#SBATCH --time=${ARRAY_TIME}
#SBATCH --cpus-per-task=${ARRAY_CPUS}
#SBATCH --mem=${ARRAY_MEM}
#SBATCH --array=0-4

SIF="${SIF}"
ROOT="${ROOT}"
CONDA_ENV="${CONDA_ENV}"
PYTHON_SCRIPT="${PYTHON_SCRIPT}"
SCRATCH="${SCRATCH:-/scratch}"
NETMHCPAN_HOST_DIR="${NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${NETMHCPAN_CONTAINER_DIR}"
cd "${ROOT}/Inference"
$(declare -f run_in_container)
run_in_container
EOF
)

MERGE_JOB_ID=$(sbatch --parsable --dependency=afterok:${ARRAY_JOB_ID} --partition="${CPU_PARTITION}" <<EOF
#!/bin/bash
#SBATCH --job-name=merge_pdb_table
#SBATCH --output=${LOG_DIR}/merge_pdb_table_%j.out
#SBATCH --error=${LOG_DIR}/merge_pdb_table_%j.err
#SBATCH --time=${MERGE_TIME}
#SBATCH --cpus-per-task=${MERGE_CPUS}
#SBATCH --mem=${MERGE_MEM}

export MERGE_PARTIALS=1
SIF="${SIF}"
ROOT="${ROOT}"
CONDA_ENV="${CONDA_ENV}"
PYTHON_SCRIPT="${PYTHON_SCRIPT}"
SCRATCH="${SCRATCH:-/scratch}"
NETMHCPAN_HOST_DIR="${NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${NETMHCPAN_CONTAINER_DIR}"
cd "${ROOT}/Inference"
$(declare -f run_in_container)
run_in_container
EOF
)

echo "${MERGE_JOB_ID}"
