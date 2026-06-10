#!/bin/bash
#SBATCH --job-name=afft_hla3db
#SBATCH --time=0:30:00
#SBATCH -p {{PARTITION_GPU}}
#SBATCH --gres=gpu:1
#SBATCH -o inputgen.out
#SBATCH --error=inputgen.err

targname=$1
params=$2
module load cuda11.8/toolkit/11.8.0
# Derive alphafold env lib path from CONDA (no TENSOR config needed)
ALPHAFOLD_ENV=$(dirname $(dirname {{CONDA}}))/envs/alphafold
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$ALPHAFOLD_ENV/lib
source {{CONDA}}

conda activate alphafold

if ! test -f ${params}; then
  echo "Model parameters file is missing."
fi

python run_prediction.py --targets ${targname}/inputs/target.tsv --outfile_prefix ${targname}/outfile --model_names model_2_ptm_ft --model_params_files ${params} --ignore_identities

