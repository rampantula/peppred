#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./containers/test.sh /path/to/peppred-vX.Y.Z.sif [--full]

The default smoke test avoids importing the largest TensorFlow stack and can
run on a login node. --full performs the AlphaFold/JAX/TensorFlow import and
should run in a normal compute allocation with an open-file limit of at least
1024.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
    usage >&2
    exit 2
fi

image_path="${1:-}"
mode="${2:-}"
if [[ -z "${image_path}" || ( -n "${mode}" && "${mode}" != "--full" ) ]]; then
    usage >&2
    exit 2
fi
if [[ ! -f "${image_path}" ]]; then
    echo "ERROR: SIF not found: ${image_path}" >&2
    exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "${script_dir}/.." && pwd -P)"
image_dir="$(cd "$(dirname "${image_path}")" && pwd -P)"
image_path="${image_dir}/$(basename "${image_path}")"

if command -v apptainer >/dev/null 2>&1; then
    container_runtime="$(command -v apptainer)"
elif command -v singularity >/dev/null 2>&1; then
    container_runtime="$(command -v singularity)"
else
    echo "ERROR: Apptainer or Singularity is required to test the SIF." >&2
    exit 1
fi

"${container_runtime}" inspect "${image_path}" >/dev/null

"${container_runtime}" exec --cleanenv "${image_path}" /bin/bash -c '
    set -eu
    test -x /opt/conda/envs/alphafold/bin/python
    test -x /opt/conda/envs/alphafold/bin/ptxas
    test -e /opt/conda/envs/alphafold/lib/libcusolver.so.11
    test -x /opt/conda/envs/compare/bin/python
    test -x /opt/conda/envs/train/bin/python
    test -x /opt/conda/envs/protpardelle/bin/python
'

"${container_runtime}" exec --cleanenv "${image_path}" \
    /opt/conda/envs/alphafold/bin/python -c \
    "import importlib.util; assert importlib.util.find_spec('jax'); assert importlib.util.find_spec('tensorflow'); assert importlib.util.find_spec('openmm'); print('alphafold package probe: ok')"

"${container_runtime}" exec --cleanenv "${image_path}" \
    /opt/conda/envs/compare/bin/python -c \
    "import Bio, importlib.util, pymol; assert importlib.util.find_spec('pyrosetta') is None; print('compare environment: ok; PyRosetta not bundled')"

"${container_runtime}" exec --cleanenv "${image_path}" \
    /opt/conda/envs/train/bin/python -c \
    "import lightgbm, pandas, sklearn; print('train environment: ok')"

"${container_runtime}" exec --cleanenv "${image_path}" \
    /opt/conda/envs/protpardelle/bin/python -c \
    "import Bio, protpardelle, torch, transformers; print('protpardelle environment: ok; torch=' + torch.__version__)"

"${container_runtime}" exec \
    --cleanenv \
    --bind "${repo_root}:/opt/peppred-source:ro" \
    --pwd /opt/peppred-source/Inference \
    --env PEPPRED_ENABLE_PYROSETTA=0 \
    "${image_path}" \
    /opt/conda/envs/compare/bin/python -c \
    "import dihedrals; assert not dihedrals.HAS_PYROSETTA; print('Biopython fallback selection: ok')"

if [[ "${mode}" == "--full" ]]; then
    open_file_limit="$(ulimit -Sn)"
    if [[ "${open_file_limit}" != "unlimited" && "${open_file_limit}" -lt 1024 ]]; then
        echo "ERROR: --full requires an open-file limit of at least 1024; found ${open_file_limit}." >&2
        exit 1
    fi
    "${container_runtime}" exec --cleanenv "${image_path}" \
        /opt/conda/envs/alphafold/bin/python -c \
        "import jax, openmm, tensorflow; print('full AlphaFold import: ok')"
fi

echo "PepPred SIF smoke test: PASS"
