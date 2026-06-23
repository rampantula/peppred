#!/bin/bash
#SBATCH --output=sample-%x.%j.out
#SBATCH --error=sample-%x.%j.err
#SBATCH --partition=gpu
#SBATCH --gpu_cmode=shared
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=1-16:00:00

set -euo pipefail

# Change note (2026-06-14, wyattb/codex):
# Public-SIF release prep: remove user-specific activation paths and allow the
# caller/container wrapper to provide the Protpardelle Python executable.
: "${PROTPARDELLE_PYTHON:=python}"

run_yaml=$1
motif_dir=$2
num_samples=$3
num_mpnn_seqs=$4

"${PROTPARDELLE_PYTHON}" -m protpardelle.sample \
    "${run_yaml}" \
    --motif-dir "${motif_dir}" \
    --num-samples "${num_samples}" \
    --num-mpnn-seqs "${num_mpnn_seqs}"
