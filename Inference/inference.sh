#!/bin/bash
#SBATCH --job-name=peppred2
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=logs/peppred2_%j.out
#SBATCH --error=logs/peppred2_%j.err

#Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
#Licensed for academic and non-commercial use only. Commercial use requires a separate license.
#See LICENSE file for details.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIF="${PEPPRED_SIF:-${SIF:-}}"

if [[ -z "${SIF}" ]]; then
    ENV=$(python -c "from constants import *; print(condapath)")
    echo "From Python: $ENV"
    source "$ENV"
    conda activate compare

    timestamp=$(date +"%m%d%y%H%M%S")
    LOC=$(python -c "from constants import *; print(mainpath)")
    echo "From Python: $LOC"

    mkdir -p stored
    [ -d out ] && mv out "stored/out_${timestamp}"
    mkdir -p out logs
    find logs -maxdepth 1 -type f -delete

    if [ -d "${LOC}/Inference/structures" ]; then
        mv "${LOC}/Inference/structures" "${LOC}/Inference/stored/structures_${timestamp}"
        echo "[INFO] moved MHC_pdbs to storage"
    else
        echo "[WARN] no previous MHCs dir found in Compare directory"
    fi

    mv "${LOC}/AFFT-HLA3DB/scorings" "${LOC}/Inference/scorings"
    python "${LOC}/protpardelle/move.py"
    python reorder.py
    MERGE_ID=$(bash list.sh)
    echo "Submitted Merge Job ${MERGE_ID}"

    DIHED_ID=$(sbatch --parsable --dependency=afterok:${MERGE_ID} <<EOF
#!/bin/bash
#SBATCH --job-name=dihedrals
#SBATCH --output=logs/dihedrals_%j.out
#SBATCH --error=logs/dihedrals_%j.err
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G

source ${ENV}
conda activate compare
python dihedrals.py
EOF
)
    echo "Submitted Dihedral Job ${DIHED_ID}"

    INFERENCE=$(sbatch --parsable --dependency=afterok:${DIHED_ID} <<EOF
#!/bin/bash
#SBATCH --job-name=inference
#SBATCH --output=logs/inference_%j.out
#SBATCH --error=logs/inference_%j.err
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G

source ${ENV}
conda activate train
python 1_extract.py
python 2_PCA.py
python pairings.py
python 3_interpreter.py
python 4_runinference.py
python 5_visualize.py
python 6_output.py
rm -rf ${LOC}/Inference/structures
rm -rf ${LOC}/Inference/scorings
EOF
)
    echo "Submitted Inference Job ${INFERENCE}"
    exit 0
fi

ROOT="${PEPPRED_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
: "${PEPPRED_NETMHCPAN_HOST_DIR:?Set PEPPRED_NETMHCPAN_HOST_DIR to the host NetMHCpan parent directory}"
NETMHCPAN_HOST_DIR="${PEPPRED_NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${PEPPRED_NETMHCPAN_CONTAINER_DIR:-/container/software/netmhcpan}"
CPU_PARTITION="${PEPPRED_CPU_PARTITION:-normal}"
SCRATCH="${SCRATCH:-/scratch}"
ASSETS_HOST="${PEPPRED_ASSETS_HOST:-}"
ASSETS_CONTAINER="${PEPPRED_ASSETS_CONTAINER:-}"
INFERENCE_MODEL_BUNDLE="${PEPPRED_INFERENCE_MODEL_BUNDLE:-}"
PYROSETTA_ENABLE="${PEPPRED_ENABLE_PYROSETTA:-1}"
PYROSETTA_HOST_PATH="${PEPPRED_PYROSETTA_HOST_PATH:-}"
PYROSETTA_CONTAINER_PATH="${PEPPRED_PYROSETTA_CONTAINER_PATH:-${PYROSETTA_HOST_PATH}}"
PYROSETTA_PATH="${PEPPRED_PYROSETTA_PATH:-${PYROSETTA_CONTAINER_PATH}}"

export PEPPRED_ROOT="${ROOT}"
export PEPPRED_SIF="${SIF}"
export PEPPRED_ASSETS_HOST="${ASSETS_HOST}"
export PEPPRED_ASSETS_CONTAINER="${ASSETS_CONTAINER}"
export PEPPRED_INFERENCE_MODEL_BUNDLE="${INFERENCE_MODEL_BUNDLE}"
export PEPPRED_ENABLE_PYROSETTA="${PYROSETTA_ENABLE}"
export PEPPRED_PYROSETTA_HOST_PATH="${PYROSETTA_HOST_PATH}"
export PEPPRED_PYROSETTA_CONTAINER_PATH="${PYROSETTA_CONTAINER_PATH}"
export PEPPRED_PYROSETTA_PATH="${PYROSETTA_PATH}"

run_compare() {
    local bind_args=(
        --bind "${ROOT}:${ROOT}"
        --bind "${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR}"
        --bind "${SCRATCH}:/scratch"
    )
    if [[ -n "${ASSETS_HOST:-}" && -n "${ASSETS_CONTAINER:-}" ]]; then
        bind_args+=(--bind "${ASSETS_HOST}:${ASSETS_CONTAINER}")
    fi
    if [[ -n "${PYROSETTA_HOST_PATH:-}" && -n "${PYROSETTA_CONTAINER_PATH:-}" ]]; then
        bind_args+=(--bind "${PYROSETTA_HOST_PATH}:${PYROSETTA_CONTAINER_PATH}")
    fi
    singularity exec \
        --cleanenv \
        "${bind_args[@]}" \
        --env PYTHONPATH= \
        --env PEPPRED_ENABLE_PYROSETTA="${PYROSETTA_ENABLE:-}" \
        --env PEPPRED_PYROSETTA_PATH="${PYROSETTA_PATH:-}" \
        --env PEPPRED_RUN_ID="${PEPPRED_RUN_ID:-}" \
        --env PROJECT_NAME="${PROJECT_NAME:-}" \
        --env PROTPARDELLE_OUTPUT_DIR="${PROTPARDELLE_OUTPUT_DIR:-}" \
        --env PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME:-}" \
        --env PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_PROJECT_NAME:-}" \
        "${SIF}" \
        /opt/conda/bin/conda run -n compare python "$@"
}

run_train() {
    local bind_args=(
        --bind "${ROOT}:${ROOT}"
        --bind "${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR}"
        --bind "${SCRATCH}:/scratch"
    )
    if [[ -n "${ASSETS_HOST:-}" && -n "${ASSETS_CONTAINER:-}" ]]; then
        bind_args+=(--bind "${ASSETS_HOST}:${ASSETS_CONTAINER}")
    fi
    if [[ -n "${PYROSETTA_HOST_PATH:-}" && -n "${PYROSETTA_CONTAINER_PATH:-}" ]]; then
        bind_args+=(--bind "${PYROSETTA_HOST_PATH}:${PYROSETTA_CONTAINER_PATH}")
    fi
    singularity exec \
        --cleanenv \
        "${bind_args[@]}" \
        --env PYTHONPATH= \
        --env PEPPRED_ENABLE_PYROSETTA="${PYROSETTA_ENABLE:-}" \
        --env PEPPRED_PYROSETTA_PATH="${PYROSETTA_PATH:-}" \
        --env PEPPRED_RUN_ID="${PEPPRED_RUN_ID:-}" \
        --env PROJECT_NAME="${PROJECT_NAME:-}" \
        --env PROTPARDELLE_OUTPUT_DIR="${PROTPARDELLE_OUTPUT_DIR:-}" \
        --env PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME:-}" \
        --env PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_PROJECT_NAME:-}" \
        --env PEPPRED_INFERENCE_MODEL_BUNDLE="${PEPPRED_INFERENCE_MODEL_BUNDLE:-}" \
        "${SIF}" \
        /opt/conda/bin/conda run -n train python "$@"
}

LOC=$(python3 -c "from constants import *; print(mainpath)")
echo "From Python: $LOC"
mkdir -p "${LOC}/Inference/stored" "${LOC}/Inference/out" "${LOC}/Inference/logs"

timestamp=$(date +"%m%d%y%H%M%S")
mkdir -p stored
[ -d out ] && mv out "stored/out_${timestamp}"
mkdir -p out
find logs -maxdepth 1 -type f \
    ! -name "peppred2_${SLURM_JOB_ID:-current}.out" \
    ! -name "peppred2_${SLURM_JOB_ID:-current}.err" \
    -delete

if [ -d "${LOC}/Inference/structures" ]; then
    mv "${LOC}/Inference/structures" "${LOC}/Inference/stored/structures_${timestamp}"
    echo "[INFO] moved MHC_pdbs to storage"
else
    echo "[WARN] no previous MHCs dir found in Compare directory"
fi

if [ -d "${LOC}/AFFT-HLA3DB/scorings" ]; then
    rm -rf "${LOC}/Inference/scorings"
    mv "${LOC}/AFFT-HLA3DB/scorings" "${LOC}/Inference/scorings"
    echo "[INFO] moved AFFT scoring outputs into Inference"
elif [ -d "${LOC}/Inference/scorings" ]; then
    echo "[INFO] using existing Inference/scorings"
else
    echo "[WARN] no scoring outputs found for inference"
fi

run_compare "${LOC}/protpardelle/move.py"
run_compare reorder.py
MERGE_ID=$(bash list.sh)
echo "Submitted Merge Job ${MERGE_ID}"

DIHED_ID=$(sbatch --parsable --dependency=afterok:${MERGE_ID} --partition="${CPU_PARTITION}" <<EOF
#!/bin/bash
#SBATCH --job-name=dihedrals
#SBATCH --output=logs/dihedrals_%j.out
#SBATCH --error=logs/dihedrals_%j.err
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G

SIF="${SIF}"
ROOT="${ROOT}"
SCRATCH="${SCRATCH:-/scratch}"
NETMHCPAN_HOST_DIR="${NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${NETMHCPAN_CONTAINER_DIR}"
ASSETS_HOST="${ASSETS_HOST}"
ASSETS_CONTAINER="${ASSETS_CONTAINER}"
PYROSETTA_ENABLE="${PYROSETTA_ENABLE}"
PYROSETTA_HOST_PATH="${PYROSETTA_HOST_PATH}"
PYROSETTA_CONTAINER_PATH="${PYROSETTA_CONTAINER_PATH}"
PYROSETTA_PATH="${PYROSETTA_PATH}"
PEPPRED_INFERENCE_MODEL_BUNDLE="${INFERENCE_MODEL_BUNDLE}"
export PEPPRED_ROOT="${ROOT}"
export PEPPRED_SIF="${SIF}"
export PEPPRED_RUN_ID="${PEPPRED_RUN_ID:-}"
export PROJECT_NAME="${PROJECT_NAME:-}"
export PEPPRED_ASSETS_HOST="${ASSETS_HOST}"
export PEPPRED_ASSETS_CONTAINER="${ASSETS_CONTAINER}"
export PEPPRED_ENABLE_PYROSETTA="${PYROSETTA_ENABLE}"
export PEPPRED_PYROSETTA_HOST_PATH="${PYROSETTA_HOST_PATH}"
export PEPPRED_PYROSETTA_CONTAINER_PATH="${PYROSETTA_CONTAINER_PATH}"
export PEPPRED_PYROSETTA_PATH="${PYROSETTA_PATH}"
export PEPPRED_INFERENCE_MODEL_BUNDLE="${PEPPRED_INFERENCE_MODEL_BUNDLE}"
export PROTPARDELLE_OUTPUT_DIR="${PROTPARDELLE_OUTPUT_DIR:-}"
export PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME:-}"
export PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_PROJECT_NAME:-}"
cd "${ROOT}/Inference"
$(declare -f run_compare)
run_compare dihedrals.py
EOF
)
echo "Submitted Dihedral Job ${DIHED_ID}"

INFERENCE=$(sbatch --parsable --dependency=afterok:${DIHED_ID} --partition="${CPU_PARTITION}" <<EOF
#!/bin/bash
#SBATCH --job-name=inference
#SBATCH --output=logs/inference_%j.out
#SBATCH --error=logs/inference_%j.err
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G

SIF="${SIF}"
ROOT="${ROOT}"
SCRATCH="${SCRATCH:-/scratch}"
NETMHCPAN_HOST_DIR="${NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${NETMHCPAN_CONTAINER_DIR}"
ASSETS_HOST="${ASSETS_HOST}"
ASSETS_CONTAINER="${ASSETS_CONTAINER}"
PYROSETTA_ENABLE="${PYROSETTA_ENABLE}"
PYROSETTA_HOST_PATH="${PYROSETTA_HOST_PATH}"
PYROSETTA_CONTAINER_PATH="${PYROSETTA_CONTAINER_PATH}"
PYROSETTA_PATH="${PYROSETTA_PATH}"
PEPPRED_INFERENCE_MODEL_BUNDLE="${INFERENCE_MODEL_BUNDLE}"
export PEPPRED_ROOT="${ROOT}"
export PEPPRED_SIF="${SIF}"
export PEPPRED_RUN_ID="${PEPPRED_RUN_ID:-}"
export PROJECT_NAME="${PROJECT_NAME:-}"
export PEPPRED_ASSETS_HOST="${ASSETS_HOST}"
export PEPPRED_ASSETS_CONTAINER="${ASSETS_CONTAINER}"
export PEPPRED_ENABLE_PYROSETTA="${PYROSETTA_ENABLE}"
export PEPPRED_PYROSETTA_HOST_PATH="${PYROSETTA_HOST_PATH}"
export PEPPRED_PYROSETTA_CONTAINER_PATH="${PYROSETTA_CONTAINER_PATH}"
export PEPPRED_PYROSETTA_PATH="${PYROSETTA_PATH}"
export PEPPRED_INFERENCE_MODEL_BUNDLE="${PEPPRED_INFERENCE_MODEL_BUNDLE}"
export PROTPARDELLE_OUTPUT_DIR="${PROTPARDELLE_OUTPUT_DIR:-}"
export PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME:-}"
export PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_PROJECT_NAME:-}"
cd "${ROOT}/Inference"
$(declare -f run_train)
run_train 1_extract.py
run_train 2_PCA.py
run_train pairings.py
run_train 3_interpreter.py
run_train 4_runinference.py
run_train 5_visualize.py
run_train 6_output.py
rm -rf ${LOC}/Inference/structures
rm -rf ${LOC}/Inference/scorings
EOF
)
echo "Submitted Inference Job ${INFERENCE}"
