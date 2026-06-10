#!/bin/bash
#SBATCH --job-name=gen_inputs
#SBATCH --time=00:20:00
#SBATCH -p {{PARTITION_SHORT}}
#SBATCH --mem=8G
#SBATCH -o inputgen.out
#SBATCH --error=inputgen.err

mkdir outfiles

cd {{ROOT}}/AFFT-HLA3DB
module load cuda11.8/toolkit/11.8.0

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:{{TENSOR}}
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
        --chdir={{ROOT}}/protpardelle \
        {{ROOT}}/protpardelle/run.sh)

    echo "Submitted dependent job $final_jid after AFFT jobs finish"
else
    echo "No AFFT jobs submitted, skipping dependent job."
fi
