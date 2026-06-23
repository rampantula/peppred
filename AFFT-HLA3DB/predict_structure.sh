#!/bin/bash
#SBATCH --job-name=afft_hla3db
#SBATCH --time=0:30:00
#SBATCH -p {{PARTITION_GPU}}
#SBATCH --gres=gpu:1
#SBATCH -o inputgen.out
#SBATCH --error=inputgen.err

set -euo pipefail

targname=$1
params=$2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${PEPPRED_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
SIF="${PEPPRED_SIF:-${SIF:-}}"

if [[ -z "${SIF}" ]]; then
    module load cuda11.8/toolkit/11.8.0
    ALPHAFOLD_ENV=$(dirname "$(dirname "{{CONDA}}")")/envs/alphafold
    export LD_LIBRARY_PATH="${ALPHAFOLD_ENV}/lib:${LD_LIBRARY_PATH:-}"
    source {{CONDA}}
    conda activate alphafold

    if [[ ! -f "${params}" ]]; then
        echo "Model parameters file is missing: ${params}" >&2
        exit 1
    fi

    python run_prediction.py \
        --targets "${targname}/inputs/target.tsv" \
        --outfile_prefix "${targname}/outfile" \
        --model_names model_2_ptm_ft \
        --model_params_files "${params}" \
        --ignore_identities
    exit 0
fi

SCRATCH="${SCRATCH:-/scratch}"
: "${PEPPRED_NETMHCPAN_HOST_DIR:?Set PEPPRED_NETMHCPAN_HOST_DIR to the host NetMHCpan parent directory}"
NETMHCPAN_HOST_DIR="${PEPPRED_NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${PEPPRED_NETMHCPAN_CONTAINER_DIR:-/container/software/netmhcpan}"
ASSETS_HOST="${PEPPRED_ASSETS_HOST:-}"
ASSETS_CONTAINER="${PEPPRED_ASSETS_CONTAINER:-}"
ALPHAFOLD_ENV_CONTAINER="${ALPHAFOLD_ENV_CONTAINER:-/opt/conda/envs/alphafold}"
ALPHAFOLD_PYTHON_CONTAINER="${ALPHAFOLD_PYTHON_CONTAINER:-/opt/conda/envs/alphafold/bin/python}"

ASSET_BIND_ARGS=()
if [[ -n "${ASSETS_HOST}" && -n "${ASSETS_CONTAINER}" ]]; then
    ASSET_BIND_ARGS=(--bind "${ASSETS_HOST}:${ASSETS_CONTAINER}")
fi

host_path_for() {
    local path="$1"
    if [[ -n "${ASSETS_HOST}" && -n "${ASSETS_CONTAINER}" && "${path}" == "${ASSETS_CONTAINER}"* ]]; then
        printf '%s%s\n' "${ASSETS_HOST}" "${path#${ASSETS_CONTAINER}}"
    elif [[ "${path}" == /scratch/* && "${SCRATCH}" != "/scratch" ]]; then
        printf '%s%s\n' "${SCRATCH}" "${path#/scratch}"
    else
        printf '%s\n' "${path}"
    fi
}

params_host="$(host_path_for "${params}")"
if [[ ! -f "${params_host}" ]]; then
    echo "Model parameters file is missing: ${params} (host: ${params_host})" >&2
    exit 1
fi

singularity exec --cleanenv --nv \
    --bind "${ROOT}:${ROOT}" \
    --bind "${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR}" \
    --bind "${SCRATCH}:/scratch" \
    "${ASSET_BIND_ARGS[@]}" \
    --env PYTHONPATH= \
    --env ALPHAFOLD_ENV_CONTAINER="${ALPHAFOLD_ENV_CONTAINER}" \
    --env ALPHAFOLD_PYTHON_CONTAINER="${ALPHAFOLD_PYTHON_CONTAINER}" \
    "${SIF}" \
    /bin/bash --noprofile --norc -c '
        set -euo pipefail
        export PATH="${ALPHAFOLD_ENV_CONTAINER}/bin:${PATH}"
        export LD_LIBRARY_PATH="${ALPHAFOLD_ENV_CONTAINER}/lib:${LD_LIBRARY_PATH:-}"
        export XLA_FLAGS="${XLA_FLAGS:---xla_gpu_cuda_data_dir=${ALPHAFOLD_ENV_CONTAINER}}"
        exec "${ALPHAFOLD_PYTHON_CONTAINER}" run_prediction.py \
            --targets "$1/inputs/target.tsv" \
            --outfile_prefix "$1/outfile" \
            --model_names model_2_ptm_ft \
            --model_params_files "$2" \
            --ignore_identities
    ' _ "${targname}" "${params}"
