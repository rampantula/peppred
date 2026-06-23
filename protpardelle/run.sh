#!/usr/bin/env bash
set -euo pipefail
echo "========== protpardelle batch submitter =========="
# Change note (2026-06-14, wyattb/codex):
# SIF compatibility: keep Protpardelle as Slurm GPU fan-out by default, allow
# serial local sampling through PEPPRED_SCHEDULER=local, and choose SIF versus
# host-conda execution from PEPPRED_SIF.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIF="${PEPPRED_SIF:-${SIF:-}}"
SCRATCH="${SCRATCH:-/scratch}"
LOC="${PEPPRED_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
source "${LOC}/scripts/scheduler.sh"
SCHEDULER="$(peppred_scheduler_mode)"

if [[ -z "${SIF}" ]]; then
    ENV=$(python -c "from misc import constants; print(constants.condapath)")
    echo "From Python: $ENV"
    source "$ENV"
    conda activate compare
    timestamp=$(date +"%Y%m%d_%H%M%S")

    LOC=$(python -c "from misc import constants; print(constants.mainpath)")
    echo "From Python: $LOC"
    rm -rf logs
    mkdir logs
    mkdir -p "${LOC}/Inference/stored"

    rm -rf "${LOC}/protpardelle/MHC_pdbs"
    [ -d "${LOC}/Inference/scorings" ] && mv "${LOC}/Inference/scorings" "${LOC}/Inference/stored/scorings_${timestamp}"
    rm -rf "${LOC}/AFFT-HLA3DB/MHC_pdbs" "${LOC}/AFFT-HLA3DB/scoring" "${LOC}/AFFT-HLA3DB/scorings"
    mkdir -p "${LOC}/AFFT-HLA3DB/MHC_pdbs" "${LOC}/AFFT-HLA3DB/scorings"

    python "${LOC}/AFFT-HLA3DB/shift.py" "${LOC}"
    python "${LOC}/AFFT-HLA3DB/store.py"
    python "${LOC}/AFFT-HLA3DB/npz.py"

    rm -rf "${LOC}/protpardelle/MHC_pdbs"
    [ -d "${LOC}/Inference/scorings" ] && mv "${LOC}/Inference/scorings" "${LOC}/Inference/stored/scorings_${timestamp}"
    mv "${LOC}/AFFT-HLA3DB/MHC_pdbs" "${LOC}/protpardelle/"
    mv "${LOC}/AFFT-HLA3DB/scorings" "${LOC}/Inference/"

    conda activate protpardelle

    PDB_DIR="${LOC}/protpardelle/MHC_pdbs"
    if [[ -n "${PEPPRED_MODEL_PARAMS_HOST:-}" ]]; then
        YAML="${PEPPRED_MODEL_PARAMS_HOST}/configs/peppred.yaml"
    else
        YAML="${LOC}/protpardelle/model_params/configs/peppred.yaml"
    fi
    NUM_SAMPLES="${NUM_SAMPLES:-16}"
    NUM_MPNN_SEQS="${NUM_MPNN_SEQS:-0}"
    PARTITION="${PARTITION:-${PEPPRED_GPU_PARTITION:-{{PARTITION_GPU}}}}"
    GPUS="${GPUS:-1}"
    GPU_GRES="${PEPPRED_GPU_GRES:-gpu:${GPUS}}"
    GPU_CONSTRAINT="${GPU_CONSTRAINT:-${PEPPRED_GPU_CONSTRAINT:-}}"
    CPU_PARTITION="${PEPPRED_CPU_PARTITION:-{{PARTITION_SHORT}}}"
    CPUS="${CPUS:-8}"
    MEM="${MEM:-64G}"
    TIME="${TIME:-08:00:00}"
    RUN_ID="${PEPPRED_RUN_ID:-$(date +"%Y%m%d_%H%M%S")}"
    PROJECT_NAME="${PROJECT_NAME:-peppred_${RUN_ID}}"
    PROTPARDELLE_OUTPUT_DIR="${PEPPRED_PROTPARDELLE_OUTPUT_DIR:-${LOC}/protpardelle/results/${PROJECT_NAME}}"
    PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME:-$(basename "${YAML}" .yaml)}"
    PROTPARDELLE_SEED="${PEPPRED_PROTPARDELLE_SEED:-${PROTPARDELLE_SEED:-}}"
    SEED_ARGS=()
    if [[ -n "${PROTPARDELLE_SEED}" ]]; then
        SEED_ARGS=(--seed "${PROTPARDELLE_SEED}")
    fi

    ENV_ROOT="${ENV%/bin/activate}"
    FOLDSEEK_BIN="${FOLDSEEK_BIN:-${ENV_ROOT}/envs/protpardelle/bin/foldseek}"

    JOBS_DIR="${LOC}/protpardelle/jobs"
    LOGS_DIR="${LOC}/protpardelle/logs"
    mkdir -p "${JOBS_DIR}" "${LOGS_DIR}" "${PROTPARDELLE_OUTPUT_DIR}"

    if [[ ! -d "${PDB_DIR}" ]]; then
      echo "ERROR: PDB_DIR does not exist: ${PDB_DIR}"
      exit 1
    fi
    if [[ ! -f "${YAML}" ]]; then
      echo "ERROR: YAML not found: ${YAML}"
      exit 1
    fi
    if [[ ! -x "${FOLDSEEK_BIN}" ]]; then
      echo "ERROR: FOLDSEEK_BIN is not executable: ${FOLDSEEK_BIN}"
      exit 1
    fi

    mapfile -t PDBS < <(find "${PDB_DIR}" -maxdepth 1 -type f \( -name "*.pdb" -o -name "*.PDB" \) | sort)
    if [[ ${#PDBS[@]} -eq 0 ]]; then
      echo "ERROR: No PDB files found in ${PDB_DIR}"
      exit 1
    fi

    export FOLDSEEK_BIN PROTPARDELLE_OUTPUT_DIR PROTPARDELLE_CONFIG_NAME
    export PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_CONFIG_NAME}"

    if peppred_is_local; then
        echo "Running ${#PDBS[@]} Protpardelle target(s) locally."
        for pdb_path in "${PDBS[@]}"; do
            pdb_base="$(basename "${pdb_path}")"
            pdb_stem="${pdb_base%.*}"
            echo "Running local Protpardelle for ${pdb_stem}"
            python3 src/protpardelle/sample.py "${YAML}" \
              --project-name "${PROJECT_NAME}" \
              --motif-pdb "${pdb_path}" \
              --num-samples "${NUM_SAMPLES}" \
              --num-mpnn-seqs "${NUM_MPNN_SEQS}" \
              "${SEED_ARGS[@]}"
            echo "Finished local Protpardelle for ${pdb_stem}"
        done

        mkdir -p "${LOC}/Inference/logs"
        cd "${LOC}/Inference"
        PEPPRED_SCHEDULER=local bash "${LOC}/Inference/inference.sh"
        exit 0
    fi

    SBATCH_CONSTRAINT_LINE=""
    if [[ -n "${GPU_CONSTRAINT}" ]]; then
        SBATCH_CONSTRAINT_LINE="#SBATCH --constraint=${GPU_CONSTRAINT}"
    fi

    job_ids=()
    for pdb_path in "${PDBS[@]}"; do
        pdb_base="$(basename "${pdb_path}")"
        pdb_stem="${pdb_base%.*}"
        jobfile="${JOBS_DIR}/run_${pdb_stem}.sbatch"

cat > "${jobfile}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=pp_${pdb_stem}
#SBATCH --partition=${PARTITION}
#SBATCH --gres=${GPU_GRES}
${SBATCH_CONSTRAINT_LINE}
#SBATCH --cpus-per-task=${CPUS}
#SBATCH --mem=${MEM}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGS_DIR}/pp_${pdb_stem}_%j.out
#SBATCH --error=${LOGS_DIR}/pp_${pdb_stem}_%j.err

set -euo pipefail
source ${ENV}
conda activate protpardelle
export FOLDSEEK_BIN=${FOLDSEEK_BIN}
export PROTPARDELLE_OUTPUT_DIR=${PROTPARDELLE_OUTPUT_DIR}
export PROTPARDELLE_CONFIG_NAME=${PROTPARDELLE_CONFIG_NAME}
export PROTPARDELLE_PROJECT_NAME=${PROTPARDELLE_CONFIG_NAME}
export PROTPARDELLE_SEED=${PROTPARDELLE_SEED}

SEED_ARGS=()
if [[ -n "\${PROTPARDELLE_SEED}" ]]; then
  SEED_ARGS=(--seed "\${PROTPARDELLE_SEED}")
fi

cd ${LOC}/protpardelle
python3 src/protpardelle/sample.py ${YAML} \\
  --project-name ${PROJECT_NAME} \\
  --motif-pdb ${pdb_path} \\
  --num-samples ${NUM_SAMPLES} \\
  --num-mpnn-seqs ${NUM_MPNN_SEQS} \\
  "\${SEED_ARGS[@]}"
EOF

        chmod +x "${jobfile}"
        jid=$(sbatch --parsable "${jobfile}")
        job_ids+=("$jid")
        echo "submitted $jid for ${pdb_stem}"
    done

    echo "submitted ${#PDBS[@]} Protpardelle jobs."
    if [ ${#job_ids[@]} -gt 0 ]; then
        deps=$(IFS=:; echo "${job_ids[*]}")
        final_jid=$(sbatch --parsable \
            --dependency=afterok:${deps} \
            --partition="${CPU_PARTITION}" \
            --export=ALL,PEPPRED_ROOT="${LOC}",PEPPRED_RUN_ID="${RUN_ID}",PROJECT_NAME="${PROJECT_NAME}",PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME}",PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_CONFIG_NAME}",PROTPARDELLE_OUTPUT_DIR="${PROTPARDELLE_OUTPUT_DIR}" \
            --chdir="${LOC}/Inference" \
            "${LOC}/Inference/inference.sh")
        echo "submitted inference $final_jid"
    else
        echo "No Protpardelle jobs submitted."
    fi
    exit 0
fi

: "${PEPPRED_NETMHCPAN_HOST_DIR:?Set PEPPRED_NETMHCPAN_HOST_DIR to the host NetMHCpan parent directory}"
NETMHCPAN_HOST_DIR="${PEPPRED_NETMHCPAN_HOST_DIR}"
NETMHCPAN_CONTAINER_DIR="${PEPPRED_NETMHCPAN_CONTAINER_DIR:-/container/software/netmhcpan}"
NETMHCPAN_VERSION_DIR="${PEPPRED_NETMHCPAN_VERSION_DIR:-netMHCpan-4.2-linux}"
ASSETS_HOST="${PEPPRED_ASSETS_HOST:-}"
ASSETS_CONTAINER="${PEPPRED_ASSETS_CONTAINER:-}"
if [[ -n "${PEPPRED_MODEL_PARAMS_HOST:-}" ]]; then
    MODEL_PARAMS_HOST="${PEPPRED_MODEL_PARAMS_HOST}"
elif [[ -n "${ASSETS_HOST}" ]]; then
    MODEL_PARAMS_HOST="${ASSETS_HOST}/model_params"
else
    MODEL_PARAMS_HOST="${SCRATCH}/peppred/model_params"
fi
if [[ -n "${PEPPRED_MODEL_PARAMS_CONTAINER:-}" ]]; then
    MODEL_PARAMS_CONTAINER="${PEPPRED_MODEL_PARAMS_CONTAINER}"
elif [[ -n "${ASSETS_CONTAINER}" ]]; then
    MODEL_PARAMS_CONTAINER="${ASSETS_CONTAINER}/model_params"
else
    MODEL_PARAMS_CONTAINER="/scratch/peppred/model_params"
fi
if [[ -n "${FOLDSEEK_BIN:-}" ]]; then
    FOLDSEEK_BIN="${FOLDSEEK_BIN}"
elif [[ -n "${PEPPRED_FOLDSEEK_BIN:-}" ]]; then
    FOLDSEEK_BIN="${PEPPRED_FOLDSEEK_BIN}"
elif [[ -n "${ASSETS_CONTAINER}" ]]; then
    FOLDSEEK_BIN="${ASSETS_CONTAINER}/tools/foldseek/bin/foldseek"
else
    FOLDSEEK_BIN="/scratch/peppred/tools/foldseek/bin/foldseek"
fi
PROTPARDELLE_RESULTS_DIR="${LOC}/protpardelle/results"
YAML_HOST="${MODEL_PARAMS_HOST}/configs/peppred.yaml"
YAML_CONTAINER="${MODEL_PARAMS_CONTAINER}/configs/peppred.yaml"
RUN_ID="${PEPPRED_RUN_ID:-$(date +"%Y%m%d_%H%M%S")}"
PROJECT_NAME="${PROJECT_NAME:-peppred_${RUN_ID}}"
PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME:-$(basename "${YAML_HOST}" .yaml)}"
PROTPARDELLE_OUTPUT_DIR="${PEPPRED_PROTPARDELLE_OUTPUT_DIR:-${PROTPARDELLE_RESULTS_DIR}/${PROJECT_NAME}}"
PROJECT_OUTPUT_DIR="${PROTPARDELLE_OUTPUT_DIR}/${PROTPARDELLE_CONFIG_NAME}"
PROTPARDELLE_SEED="${PEPPRED_PROTPARDELLE_SEED:-${PROTPARDELLE_SEED:-}}"
SEED_ARGS=()
if [[ -n "${PROTPARDELLE_SEED}" ]]; then
    SEED_ARGS=(--seed "${PROTPARDELLE_SEED}")
fi

export PEPPRED_RUN_ID="${RUN_ID}"
export PEPPRED_ROOT="${LOC}"
export PEPPRED_SIF="${SIF}"
export PEPPRED_NETMHCPAN_HOST_DIR="${NETMHCPAN_HOST_DIR}"
export PEPPRED_NETMHCPAN_CONTAINER_DIR="${NETMHCPAN_CONTAINER_DIR}"
export PEPPRED_NETMHCPAN_VERSION_DIR="${NETMHCPAN_VERSION_DIR}"
export PEPPRED_ASSETS_HOST="${ASSETS_HOST}"
export PEPPRED_ASSETS_CONTAINER="${ASSETS_CONTAINER}"
export PEPPRED_MODEL_PARAMS_HOST="${MODEL_PARAMS_HOST}"
export PEPPRED_MODEL_PARAMS_CONTAINER="${MODEL_PARAMS_CONTAINER}"
export FOLDSEEK_BIN
export PROJECT_NAME
export PROTPARDELLE_CONFIG_NAME
export PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_CONFIG_NAME}"
export PROTPARDELLE_OUTPUT_DIR
export PROTPARDELLE_SEED

ASSET_BIND_ARGS=()
ASSET_BIND_LINE=""
if [[ -n "${ASSETS_HOST}" && -n "${ASSETS_CONTAINER}" ]]; then
    ASSET_BIND_ARGS=(--bind "${ASSETS_HOST}:${ASSETS_CONTAINER}")
    ASSET_BIND_LINE="  --bind ${ASSETS_HOST}:${ASSETS_CONTAINER} \\"
fi

run_compare() {
    singularity exec \
        --cleanenv \
        --bind "${LOC}:${LOC}" \
        --bind "${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR}" \
        --bind "${SCRATCH}:/scratch" \
        "${ASSET_BIND_ARGS[@]}" \
        --env PYTHONPATH= \
        "${SIF}" \
        /opt/conda/bin/conda run -n compare python "$@"
}

timestamp=$(date +"%Y%m%d_%H%M%S")

echo "From Python: $LOC"
rm -rf logs
mkdir logs
mkdir -p "${LOC}/Inference/stored"

if [ -d "${LOC}/protpardelle/MHC_pdbs" ]; then
    rm -rf "${LOC}/protpardelle/MHC_pdbs"
    echo "[INFO] removed previous MHC_pdbs"
else
    echo "[WARN] no previous MHCs dir"
fi

if [ -d "${LOC}/Inference/scorings" ]; then
    mv "${LOC}/Inference/scorings" "${LOC}/Inference/stored/scorings_${timestamp}"
    echo "[INFO] moved scorings to storage"
else
    echo "[WARN] no previous NPZ dir"
fi

if [ -d "${LOC}/AFFT-HLA3DB/MHC_pdbs" ]; then
    rm -rf "${LOC}/AFFT-HLA3DB/MHC_pdbs"
    echo "[INFO] Cleared Old PDBS"
else
    echo "[WARN] Failed to find old MHC_pds Dir"
fi

if [ -d "${LOC}/AFFT-HLA3DB/scorings" ]; then
    rm -rf "${LOC}/AFFT-HLA3DB/scorings"
    echo "[INFO] Cleared old scoring outputs from Alphafold"
else
    echo "[WARN] Failed to find old Scorings Dir"
fi

mkdir -p ${LOC}/AFFT-HLA3DB/MHC_pdbs
mkdir -p ${LOC}/AFFT-HLA3DB/scorings
run_compare ${LOC}/AFFT-HLA3DB/shift.py ${LOC}
run_compare ${LOC}/AFFT-HLA3DB/store.py
run_compare ${LOC}/AFFT-HLA3DB/npz.py

if [ -d "${LOC}/protpardelle/MHC_pdbs" ]; then
    rm -rf "${LOC}/protpardelle/MHC_pdbs"
    echo "[INFO] removed previous MHC_pdbs"
else
    echo "[WARN] no previous MHCs dir"
fi

if [ -d "${LOC}/Inference/scorings" ]; then
    mv "${LOC}/Inference/scorings" "${LOC}/Inference/stored/scorings_${timestamp}"
    echo "[INFO] moved scorings to storage"
else
    echo "[WARN] no previous NPZ dir"
fi

if [ -d "${LOC}/AFFT-HLA3DB/MHC_pdbs" ]; then
    mv "${LOC}/AFFT-HLA3DB/MHC_pdbs" "${LOC}/protpardelle/"
    echo "[INFO] Imported PDB outputs from Alphafold"
else
    echo "[WARN] Failed to find MHC_pds Dir in AFFT-HLA3DB"
fi

if [ -d "${LOC}/AFFT-HLA3DB/scorings" ]; then
    mv "${LOC}/AFFT-HLA3DB/scorings" "${LOC}/Inference/"
    echo "[INFO] Imported scoring outputs from Alphafold"
else
    echo "[WARN] Failed to find Scorings Dir in AFFT-HLA3DB"
fi
PDB_DIR="${LOC}/protpardelle/MHC_pdbs"              
NUM_SAMPLES="${NUM_SAMPLES:-16}"
NUM_MPNN_SEQS="${NUM_MPNN_SEQS:-0}"
GPUS="${GPUS:-1}"
PARTITION="${PARTITION:-${PEPPRED_GPU_PARTITION:-gpu}}"
GPU_GRES="${PEPPRED_GPU_GRES:-gpu:${GPUS}}"
GPU_CONSTRAINT="${GPU_CONSTRAINT:-${PEPPRED_GPU_CONSTRAINT:-}}"
CPU_PARTITION="${PEPPRED_CPU_PARTITION:-normal}"
CPUS="${CPUS:-8}"
MEM="${MEM:-64G}"
TIME="${TIME:-08:00:00}"

JOBS_DIR="${LOC}/protpardelle/jobs"
LOGS_DIR="${LOC}/protpardelle/logs"

MAX_INFLIGHT=10
POLL_SECONDS=15


mkdir -p "${JOBS_DIR}" "${LOGS_DIR}"
rm -rf "${PROJECT_OUTPUT_DIR}"
mkdir -p "${PROTPARDELLE_OUTPUT_DIR}"

SBATCH_CONSTRAINT_LINE=""
if [[ -n "${GPU_CONSTRAINT}" ]]; then
    SBATCH_CONSTRAINT_LINE="#SBATCH --constraint=${GPU_CONSTRAINT}"
fi

if [[ ! -d "${PDB_DIR}" ]]; then
  echo "ERROR: PDB_DIR does not exist: ${PDB_DIR}"
  exit 1
fi
if [[ ! -f "${YAML_HOST}" ]]; then
  echo "ERROR: YAML not found: ${YAML_HOST}"
  exit 1
fi
if ! singularity exec \
    --cleanenv \
    --bind "${LOC}:${LOC}" \
    --bind "${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR}" \
    --bind "${SCRATCH}:/scratch" \
    "${ASSET_BIND_ARGS[@]}" \
    --env PYTHONPATH= \
    "${SIF}" \
    test -x "${FOLDSEEK_BIN}"; then
  echo "ERROR: FOLDSEEK_BIN is not executable: ${FOLDSEEK_BIN}"
  exit 1
fi

mapfile -t PDBS < <(find "${PDB_DIR}" -maxdepth 1 -type f \( -name "*.pdb" -o -name "*.PDB" \) | sort)
if [[ ${#PDBS[@]} -eq 0 ]]; then
  echo "ERROR: No PDB files found in ${PDB_DIR}"
  exit 1
fi

if peppred_is_local; then
    echo "Running ${#PDBS[@]} Protpardelle target(s) locally."
    for pdb_path in "${PDBS[@]}"; do
        pdb_base="$(basename "${pdb_path}")"
        pdb_stem="${pdb_base%.*}"
        echo "Running local Protpardelle for ${pdb_stem}"

        singularity exec --cleanenv --nv \
          --bind "${LOC}:${LOC}" \
          --bind "${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR}" \
          --bind "${SCRATCH}:/scratch" \
          "${ASSET_BIND_ARGS[@]}" \
          --env PYTHONPATH= \
          --env FOLDSEEK_BIN="${FOLDSEEK_BIN}" \
          --env PROTPARDELLE_MODEL_PARAMS="${MODEL_PARAMS_CONTAINER}" \
          --env PROTPARDELLE_OUTPUT_DIR="${PROTPARDELLE_OUTPUT_DIR}" \
          --env PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME}" \
          --env PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_CONFIG_NAME}" \
          "${SIF}" \
          /opt/conda/bin/conda run -n protpardelle python src/protpardelle/sample.py "${YAML_CONTAINER}" \
          --project-name "${PROJECT_NAME}" \
          --motif-pdb "${pdb_path}" \
          --num-samples "${NUM_SAMPLES}" \
          --num-mpnn-seqs "${NUM_MPNN_SEQS}" \
          "${SEED_ARGS[@]}"

        echo "Finished local Protpardelle for ${pdb_stem}"
    done

    echo "All local Protpardelle targets completed."
    mkdir -p "${LOC}/Inference/logs"
    cd "${LOC}/Inference"
    PEPPRED_SCHEDULER=local bash "${LOC}/Inference/inference.sh"
    exit 0
fi


count_inflight() {
  squeue -u "${USER}" -h -o "%T" | awk '$1=="RUNNING" || $1=="PENDING"{c++} END{print c+0}'
}

job_ids=()


for pdb_path in "${PDBS[@]}"; do
    pdb_base="$(basename "${pdb_path}")"
    pdb_stem="${pdb_base%.*}"
    jobfile="${JOBS_DIR}/run_${pdb_stem}.sbatch"

cat > "${jobfile}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=pp_${pdb_stem}
#SBATCH --partition=${PARTITION}
#SBATCH --gres=${GPU_GRES}
${SBATCH_CONSTRAINT_LINE}
#SBATCH --cpus-per-task=${CPUS}
#SBATCH --mem=${MEM}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGS_DIR}/pp_${pdb_stem}_%j.out
#SBATCH --error=${LOGS_DIR}/pp_${pdb_stem}_%j.err

set -euo pipefail

export FOLDSEEK_BIN=${FOLDSEEK_BIN}
export PROTPARDELLE_MODEL_PARAMS=${MODEL_PARAMS_CONTAINER}
export PROTPARDELLE_OUTPUT_DIR=${PROTPARDELLE_OUTPUT_DIR}
export PROTPARDELLE_CONFIG_NAME=${PROTPARDELLE_CONFIG_NAME}
export PROTPARDELLE_PROJECT_NAME=${PROTPARDELLE_CONFIG_NAME}
export PROTPARDELLE_SEED=${PROTPARDELLE_SEED}

SEED_ARGS=()
if [[ -n "\${PROTPARDELLE_SEED}" ]]; then
  SEED_ARGS=(--seed "\${PROTPARDELLE_SEED}")
fi

cd ${LOC}/protpardelle

singularity exec --cleanenv --nv \\
  --bind ${LOC}:${LOC} \\
  --bind ${NETMHCPAN_HOST_DIR}:${NETMHCPAN_CONTAINER_DIR} \\
  --bind ${SCRATCH}:/scratch \\
${ASSET_BIND_LINE}
  --env PYTHONPATH= \\
  --env FOLDSEEK_BIN=${FOLDSEEK_BIN} \\
  --env PROTPARDELLE_MODEL_PARAMS=${MODEL_PARAMS_CONTAINER} \\
  --env PROTPARDELLE_OUTPUT_DIR=${PROTPARDELLE_OUTPUT_DIR} \\
  --env PROTPARDELLE_CONFIG_NAME=${PROTPARDELLE_CONFIG_NAME} \\
  --env PROTPARDELLE_PROJECT_NAME=${PROTPARDELLE_CONFIG_NAME} \\
  --env PROTPARDELLE_SEED=${PROTPARDELLE_SEED} \\
  ${SIF} \\
  /opt/conda/bin/conda run -n protpardelle python src/protpardelle/sample.py ${YAML_CONTAINER} \\
  --project-name ${PROJECT_NAME} \\
  --motif-pdb ${pdb_path} \\
  --num-samples ${NUM_SAMPLES} \\
  --num-mpnn-seqs ${NUM_MPNN_SEQS} \\
  "\${SEED_ARGS[@]}"
EOF

    chmod +x "${jobfile}"

    jid=$(sbatch --parsable "${jobfile}")
    job_ids+=("$jid")

    echo "submitted $jid for ${pdb_stem}"
done

echo "submitted ${#PDBS[@]} Protpardelle jobs."

if [ ${#job_ids[@]} -gt 0 ]; then
    deps=$(IFS=:; echo "${job_ids[*]}")
    echo "Dependency string: afterok:${deps}"
    mkdir -p "${LOC}/Inference/logs"

    if final_jid=$(sbatch --parsable \
        --dependency=afterok:${deps} \
        --partition="${CPU_PARTITION}" \
        --export=ALL,SIF="${SIF}",PEPPRED_SIF="${SIF}",PEPPRED_ROOT="${LOC}",PEPPRED_NETMHCPAN_HOST_DIR="${NETMHCPAN_HOST_DIR}",PEPPRED_NETMHCPAN_CONTAINER_DIR="${NETMHCPAN_CONTAINER_DIR}",PEPPRED_NETMHCPAN_VERSION_DIR="${NETMHCPAN_VERSION_DIR}",PEPPRED_ASSETS_HOST="${ASSETS_HOST}",PEPPRED_ASSETS_CONTAINER="${ASSETS_CONTAINER}",PEPPRED_MODEL_PARAMS_HOST="${MODEL_PARAMS_HOST}",PEPPRED_MODEL_PARAMS_CONTAINER="${MODEL_PARAMS_CONTAINER}",PEPPRED_INFERENCE_MODEL_BUNDLE="${PEPPRED_INFERENCE_MODEL_BUNDLE:-}",FOLDSEEK_BIN="${FOLDSEEK_BIN}",PEPPRED_RUN_ID="${RUN_ID}",PROJECT_NAME="${PROJECT_NAME}",PROTPARDELLE_CONFIG_NAME="${PROTPARDELLE_CONFIG_NAME}",PROTPARDELLE_PROJECT_NAME="${PROTPARDELLE_CONFIG_NAME}",PROTPARDELLE_OUTPUT_DIR="${PROTPARDELLE_OUTPUT_DIR}" \
        --chdir="${LOC}/Inference" \
        "${LOC}/Inference/inference.sh"); then

        echo "submitted inference $final_jid"
    else
        echo "dependency error"
        exit 1
    fi
else
    echo "No Protpardelle jobs submitted."
fi
