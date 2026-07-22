#!/bin/bash
#SBATCH --job-name=gen_inputs
#SBATCH --time=00:20:00
#SBATCH -p {{PARTITION_SHORT}}
#SBATCH --mem=8G
#SBATCH -o inputgen.out
#SBATCH --error=inputgen.err

#Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
#Licensed for academic and non-commercial use only. Commercial use requires a separate license.
#See LICENSE file for details.


set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${PEPPRED_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
SIF="${PEPPRED_SIF:-${SIF:-}}"

if [[ -z "${SIF}" ]]; then
    mkdir -p outfiles runlogs
    cd "${ROOT}/AFFT-HLA3DB"
    module load cuda11.8/toolkit/11.8.0

    ALPHAFOLD_ENV=$(dirname "$(dirname "{{CONDA}}")")/envs/alphafold
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$ALPHAFOLD_ENV/lib
    source {{CONDA}}
    conda activate alphafold

    params=params/7WKJ_af_mhc_params_2351.pkl
    python initialize.py

    job_ids=()
    shopt -s nullglob

    for inputfile in ./input_seq/*.txt; do
        targname=$(basename "$inputfile" | cut -f 1 -d '_')
        olog="runlogs/${targname}.out"
        elog="runlogs/${targname}.err"

        jid=$(sbatch --parsable \
            --partition={{PARTITION_GPU}} \
            --gres=gpu:1 \
            --mem=64G \
            --output="$olog" \
            --error="$elog" \
            predict_structure.sh "$targname" "$params")

        job_ids+=("$jid")
        echo "Submitted AFFT job $jid for $targname"
    done

    shopt -u nullglob

    if [ ${#job_ids[@]} -gt 0 ]; then
        deps=$(IFS=:; echo "${job_ids[*]}")
        echo "Dependency string: afterok:${deps}"

        final_jid=$(sbatch --parsable \
            --dependency=afterok:${deps} \
            --chdir="${ROOT}/protpardelle" \
            "${ROOT}/protpardelle/run.sh")

        echo "Submitted dependent job $final_jid after AFFT jobs finish"
    else
        echo "No AFFT jobs submitted, skipping dependent job."
    fi
    exit 0
fi

SCRATCH="${SCRATCH:-/scratch}"
: "${PEPPRED_NETMHCPAN_HOST_DIR:?Set PEPPRED_NETMHCPAN_HOST_DIR to the host NetMHCpan parent directory}"
NETMHCPAN_HOST_DIR="${PEPPRED_NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${PEPPRED_NETMHCPAN_CONTAINER_DIR:-/container/software/netmhcpan}"
NETMHCPAN_VERSION_DIR="${PEPPRED_NETMHCPAN_VERSION_DIR:-netMHCpan-4.2-linux}"
ASSETS_HOST="${PEPPRED_ASSETS_HOST:-}"
ASSETS_CONTAINER="${PEPPRED_ASSETS_CONTAINER:-}"
ALPHAFOLD_ENV_CONTAINER="${ALPHAFOLD_ENV_CONTAINER:-/opt/conda/envs/alphafold}"
ALPHAFOLD_PYTHON_CONTAINER="${ALPHAFOLD_PYTHON_CONTAINER:-/opt/conda/envs/alphafold/bin/python}"
CPU_PARTITION="${PEPPRED_CPU_PARTITION:-normal}"
GPU_PARTITION="${PEPPRED_GPU_PARTITION:-gpu}"
GPU_GRES="${PEPPRED_GPU_GRES:-gpu:1}"
GPU_CONSTRAINT="${PEPPRED_GPU_CONSTRAINT:-}"
AFFT_TIME="${PEPPRED_AFFT_TIME:-01:00:00}"
AFFT_MEM="${PEPPRED_AFFT_MEM:-64G}"

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

mkdir -p outfiles runlogs
cd "${ROOT}/AFFT-HLA3DB"

params="${PEPPRED_AFFT_PARAMS:-params/7WKJ_af_mhc_params_2351.pkl}"
params_host="$(host_path_for "${params}")"
if [[ ! -f "${params_host}" ]]; then
    echo "AFFT model parameters file is missing: ${params} (host: ${params_host})" >&2
    exit 1
fi

singularity exec \
    --cleanenv \
    --bind "${ROOT}:${ROOT}" \
    --bind "${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR}" \
    --bind "${SCRATCH}:/scratch" \
    "${ASSET_BIND_ARGS[@]}" \
    --env PYTHONPATH= \
    --env ALPHAFOLD_ENV_CONTAINER="${ALPHAFOLD_ENV_CONTAINER}" \
    --env ALPHAFOLD_PYTHON_CONTAINER="${ALPHAFOLD_PYTHON_CONTAINER}" \
    "${SIF}" \
    /bin/bash --noprofile --norc -c '
        export PATH="${ALPHAFOLD_ENV_CONTAINER}/bin:${PATH}"
        export LD_LIBRARY_PATH="${ALPHAFOLD_ENV_CONTAINER}/lib:${LD_LIBRARY_PATH:-}"
        export XLA_FLAGS="${XLA_FLAGS:---xla_gpu_cuda_data_dir=${ALPHAFOLD_ENV_CONTAINER}}"
        exec "${ALPHAFOLD_PYTHON_CONTAINER}" initialize.py
    '

job_ids=()
shopt -s nullglob

for inputfile in ./input_seq/*.txt; do
    targname=$(basename "$inputfile" | cut -f 1 -d '_')
    olog="runlogs/${targname}.out"
    elog="runlogs/${targname}.err"

    sbatch_args=(
        --parsable
        --partition="${GPU_PARTITION}"
        --gres="${GPU_GRES}"
        --mem="${AFFT_MEM}"
        --time="${AFFT_TIME}"
        --output="$olog"
        --error="$elog"
        --open-mode=truncate
    )
    if [[ -n "${GPU_CONSTRAINT}" ]]; then
        sbatch_args+=(--constraint="${GPU_CONSTRAINT}")
    fi

    jid=$(sbatch "${sbatch_args[@]}" \
        --export=ALL,SIF="${SIF}",PEPPRED_SIF="${SIF}",PEPPRED_ROOT="${ROOT}",PEPPRED_NETMHCPAN_HOST_DIR="${NETMHCPAN_HOST_DIR}",PEPPRED_NETMHCPAN_CONTAINER_DIR="${NETMHCPAN_CONTAINER_DIR}",PEPPRED_NETMHCPAN_VERSION_DIR="${NETMHCPAN_VERSION_DIR}",PEPPRED_ASSETS_HOST="${ASSETS_HOST}",PEPPRED_ASSETS_CONTAINER="${ASSETS_CONTAINER}",ALPHAFOLD_ENV_CONTAINER="${ALPHAFOLD_ENV_CONTAINER}",ALPHAFOLD_PYTHON_CONTAINER="${ALPHAFOLD_PYTHON_CONTAINER}" \
        "${ROOT}/AFFT-HLA3DB/predict_structure.sh" "$targname" "$params")

    job_ids+=("$jid")
    echo "Submitted AFFT job $jid for $targname"
done

shopt -u nullglob

if [ ${#job_ids[@]} -gt 0 ]; then
    deps=$(IFS=:; echo "${job_ids[*]}")
    echo "Dependency string: afterok:${deps}"

    final_jid=$(sbatch --parsable \
        --dependency=afterok:${deps} \
        --partition="${CPU_PARTITION}" \
        --export=ALL,SIF="${SIF}",PEPPRED_SIF="${SIF}",PEPPRED_ROOT="${ROOT}",PEPPRED_NETMHCPAN_HOST_DIR="${NETMHCPAN_HOST_DIR}",PEPPRED_NETMHCPAN_CONTAINER_DIR="${NETMHCPAN_CONTAINER_DIR}",PEPPRED_NETMHCPAN_VERSION_DIR="${NETMHCPAN_VERSION_DIR}",PEPPRED_ASSETS_HOST="${ASSETS_HOST}",PEPPRED_ASSETS_CONTAINER="${ASSETS_CONTAINER}",PEPPRED_MODEL_PARAMS_HOST="${PEPPRED_MODEL_PARAMS_HOST:-}",PEPPRED_MODEL_PARAMS_CONTAINER="${PEPPRED_MODEL_PARAMS_CONTAINER:-}",PEPPRED_INFERENCE_MODEL_BUNDLE="${PEPPRED_INFERENCE_MODEL_BUNDLE:-}",FOLDSEEK_BIN="${FOLDSEEK_BIN:-${PEPPRED_FOLDSEEK_BIN:-}}",ALPHAFOLD_ENV_CONTAINER="${ALPHAFOLD_ENV_CONTAINER}",ALPHAFOLD_PYTHON_CONTAINER="${ALPHAFOLD_PYTHON_CONTAINER}",PEPPRED_RUN_ID="${PEPPRED_RUN_ID:-}",PROJECT_NAME="${PROJECT_NAME:-}" \
        --chdir="${ROOT}/protpardelle" \
        "${ROOT}/protpardelle/run.sh")

    echo "Submitted dependent job $final_jid after AFFT jobs finish"
else
    echo "No AFFT jobs submitted, skipping dependent job."
fi
