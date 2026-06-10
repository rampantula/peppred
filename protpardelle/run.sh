#!/usr/bin/env bash
set -euo pipefail
echo "========== protpardelle batch submitter =========="
ENV=$(python -c "from misc import constants; print(constants.condapath)")
echo "From Python: $ENV"
source $ENV
conda activate compare
timestamp=$(date +"%Y%m%d_%H%M%S")

LOC=$(python -c "from misc import constants; print(constants.mainpath)")
echo "From Python: $LOC"
rm -rf logs
mkdir logs

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

if [ -d "${LOC}/AFFT-HLA3DB/scoring" ]; then
    rm -rf "${LOC}/AFFT-HLA3DB/scoring"
    echo "[INFO] Cleared old scoring outputs from Alphafold"
else
    echo "[WARN] Failed to find old Scorings Dir"
fi

mkdir ${LOC}/AFFT-HLA3DB/MHC_pdbs
mkdir ${LOC}/AFFT-HLA3DB/scoring
python ${LOC}/AFFT-HLA3DB/shift.py ${LOC}
python ${LOC}/AFFT-HLA3DB/store.py
python ${LOC}/AFFT-HLA3DB/npz.py

if [ -d "${LOC}/protpardelle/MHC_pdbs" ]; then
    rm "${LOC}/protpardelle/MHC_pdbs"
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

conda activate protpardelle

PDB_DIR="${LOC}/protpardelle/MHC_pdbs"              
YAML="${LOC}/protpardelle/model_params/configs/peppred.yaml"
NUM_SAMPLES=16
NUM_MPNN_SEQS=0
PARTITION="{{PARTITION_GPU}}"
GPUS=1
CPUS=8
MEM="64G"
TIME="08:00:00"

ENV="${ENV%/bin/activate}"
FOLDSEEK_BIN="${ENV}/envs/protpardelle/bin/foldseek"

JOBS_DIR="${LOC}/protpardelle/jobs"
LOGS_DIR="${LOC}/protpardelle/logs"

MAX_INFLIGHT=10
POLL_SECONDS=15


mkdir -p "${JOBS_DIR}" "${LOGS_DIR}"

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
#SBATCH --gres=gpu:${GPUS}
#SBATCH --cpus-per-task=${CPUS}
#SBATCH --mem=${MEM}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGS_DIR}/pp_${pdb_stem}_%j.out
#SBATCH --error=${LOGS_DIR}/pp_${pdb_stem}_%j.err

set -euo pipefail

export FOLDSEEK_BIN=${FOLDSEEK_BIN}

cd ${LOC}/protpardelle

python3 src/protpardelle/sample.py ${YAML} \\
  --motif-pdb ${pdb_path} \\
  --num-samples ${NUM_SAMPLES} \\
  --num-mpnn-seqs ${NUM_MPNN_SEQS}
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

    if final_jid=$(sbatch --parsable \
        --dependency=afterok:${deps} \
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

