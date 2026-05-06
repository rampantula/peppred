#!/bin/bash
#SBATCH --job-name=peppred2
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=${LOG_DIR}/pdb_table_%A_%a.out
#SBATCH --error=${LOG_DIR}/pdb_table_%A_%a.err

# CONDA ACTIVATIONS #
ENV=$(python -c "from constants import *; print(condapath)")
echo "From Python: $ENV"
source $ENV
conda activate compare

timestamp=$(date +"%m%d%y%H%M%S")

LOC=$(python -c "from constants import *; print(mainpath)")
echo "From Python: $LOC"


mkdir -p stored
[ -d out ] && mv out "stored/out_${timestamp}"
mkdir -p out

rm logs/*

if [ -d "${LOC}/Inference/structures" ]; then
    mv "${LOC}/Inference/structures" "${LOC}/Inference/stored/structures_${timestamp}"
    echo "[INFO] moved MHC_pdbs to storage"
else
    echo "[WARN] no previous MHCs dir found in Compare directory"
fi


mv "${LOC}/AFFT-HLA3DB/scorings" "${LOC}/Inference/scorings"

python ${LOC}/protpardelle/move.py

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

EOF
)
echo "Submitted Inference Job ${INFERENCE}"
