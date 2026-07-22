#!/usr/bin/env bash
#Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
#Licensed for academic and non-commercial use only. Commercial use requires a separate license.
#See LICENSE file for details.

set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  run_peppred.sh --input INPUT.csv [options]

Options:
  --env FILE             Source runtime exports from FILE.
                         Default: ./peppred-public.env if present.
  --scheduler MODE       slurm or local. Default: existing env value or slurm.
  --sif PATH             Set PEPPRED_SIF for Singularity/SIF runs.
  --netmhcpan PATH       Set PEPPRED_NETMHCPAN_HOST_DIR.
  --run-id ID            Set PEPPRED_RUN_ID.
  --project-name NAME    Set PROJECT_NAME.
  --samples N            Set NUM_SAMPLES.
  --mpnn N               Set NUM_MPNN_SEQS.
  --setup                Run python3 setup.py after loading env values.
  --dry-run              Print resolved configuration without submitting jobs.
  -h, --help             Show this help.

Examples:
  ./run_peppred.sh --env peppred-public.env --input input.csv --scheduler slurm
  ./run_peppred.sh --env peppred-public.env --input input.csv --scheduler local --run-id smoke_001
USAGE
}

die() {
    echo "[ERROR] $*" >&2
    exit 1
}

abspath() {
    local path="$1"
    if [[ "$path" = /* ]]; then
        printf '%s\n' "$path"
    else
        printf '%s/%s\n' "$PWD" "$path"
    fi
}

require_file() {
    local label="$1"
    local path="$2"
    [[ -f "$path" ]] || die "${label} not found: ${path}"
}

require_dir() {
    local label="$1"
    local path="$2"
    [[ -d "$path" ]] || die "${label} not found: ${path}"
}

normalize_scheduler() {
    local mode
    mode="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
    case "$mode" in
        slurm)
            printf 'slurm\n'
            ;;
        local|serial|single-node|single_node|noslurm|no-slurm)
            printf 'local\n'
            ;;
        *)
            die "--scheduler must be slurm or local"
            ;;
    esac
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_CSV=""
ENV_FILE=""
SCHEDULER_OPTION=""
RUN_SETUP=0
DRY_RUN=0
SIF_OPTION=""
NETMHCPAN_OPTION=""
RUN_ID_OPTION=""
PROJECT_NAME_OPTION=""
NUM_SAMPLES_OPTION=""
NUM_MPNN_OPTION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input)
            INPUT_CSV="${2:?--input requires a path}"
            shift 2
            ;;
        --env)
            ENV_FILE="${2:?--env requires a path}"
            shift 2
            ;;
        --scheduler)
            SCHEDULER_OPTION="${2:?--scheduler requires slurm or local}"
            shift 2
            ;;
        --sif)
            SIF_OPTION="${2:?--sif requires a path}"
            shift 2
            ;;
        --netmhcpan)
            NETMHCPAN_OPTION="${2:?--netmhcpan requires a path}"
            shift 2
            ;;
        --run-id)
            RUN_ID_OPTION="${2:?--run-id requires a value}"
            shift 2
            ;;
        --project-name)
            PROJECT_NAME_OPTION="${2:?--project-name requires a value}"
            shift 2
            ;;
        --samples)
            NUM_SAMPLES_OPTION="${2:?--samples requires a value}"
            shift 2
            ;;
        --mpnn)
            NUM_MPNN_OPTION="${2:?--mpnn requires a value}"
            shift 2
            ;;
        --setup)
            RUN_SETUP=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

[[ -n "$INPUT_CSV" ]] || { usage >&2; die "--input is required"; }

if [[ -z "$ENV_FILE" && -f "${SCRIPT_DIR}/peppred-public.env" ]]; then
    ENV_FILE="${SCRIPT_DIR}/peppred-public.env"
fi

if [[ -n "$ENV_FILE" ]]; then
    ENV_FILE="$(abspath "$ENV_FILE")"
    require_file "env file" "$ENV_FILE"
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

[[ -n "$SIF_OPTION" ]] && export PEPPRED_SIF="$SIF_OPTION"
[[ -n "$NETMHCPAN_OPTION" ]] && export PEPPRED_NETMHCPAN_HOST_DIR="$NETMHCPAN_OPTION"
[[ -n "$RUN_ID_OPTION" ]] && export PEPPRED_RUN_ID="$RUN_ID_OPTION"
[[ -n "$PROJECT_NAME_OPTION" ]] && export PROJECT_NAME="$PROJECT_NAME_OPTION"
[[ -n "$NUM_SAMPLES_OPTION" ]] && export NUM_SAMPLES="$NUM_SAMPLES_OPTION"
[[ -n "$NUM_MPNN_OPTION" ]] && export NUM_MPNN_SEQS="$NUM_MPNN_OPTION"

INPUT_CSV="$(abspath "$INPUT_CSV")"
require_file "input CSV" "$INPUT_CSV"

export PEPPRED_ROOT="${PEPPRED_ROOT:-$SCRIPT_DIR}"
PEPPRED_ROOT="$(abspath "$PEPPRED_ROOT")"
require_dir "repo root" "$PEPPRED_ROOT"
export PEPPRED_ROOT

if [[ -n "$SCHEDULER_OPTION" ]]; then
    export PEPPRED_SCHEDULER="$(normalize_scheduler "$SCHEDULER_OPTION")"
else
    export PEPPRED_SCHEDULER="$(normalize_scheduler "${PEPPRED_SCHEDULER:-slurm}")"
fi

SIF_PATH="${PEPPRED_SIF:-${SIF:-}}"
if [[ -n "$SIF_PATH" ]]; then
    SIF_PATH="$(abspath "$SIF_PATH")"
    require_file "SIF" "$SIF_PATH"
    export PEPPRED_SIF="$SIF_PATH"
    export SIF="$SIF_PATH"
    [[ -n "${PEPPRED_NETMHCPAN_HOST_DIR:-}" ]] || die "set PEPPRED_NETMHCPAN_HOST_DIR or pass --netmhcpan for SIF runs"
    PEPPRED_NETMHCPAN_HOST_DIR="$(abspath "$PEPPRED_NETMHCPAN_HOST_DIR")"
    require_dir "NetMHCpan host directory" "$PEPPRED_NETMHCPAN_HOST_DIR"
    export PEPPRED_NETMHCPAN_HOST_DIR
else
    unset PEPPRED_SIF SIF
fi

if [[ "$RUN_SETUP" -eq 1 ]]; then
    (cd "$PEPPRED_ROOT" && python3 setup.py)
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "PEPPRED_ROOT=${PEPPRED_ROOT}"
    echo "PEPPRED_SCHEDULER=${PEPPRED_SCHEDULER}"
    echo "PEPPRED_SIF=${PEPPRED_SIF:-}"
    echo "PEPPRED_NETMHCPAN_HOST_DIR=${PEPPRED_NETMHCPAN_HOST_DIR:-}"
    echo "PEPPRED_RUN_ID=${PEPPRED_RUN_ID:-}"
    echo "PROJECT_NAME=${PROJECT_NAME:-}"
    echo "NUM_SAMPLES=${NUM_SAMPLES:-}"
    echo "NUM_MPNN_SEQS=${NUM_MPNN_SEQS:-}"
    echo "PEPPRED_ENABLE_PYROSETTA=${PEPPRED_ENABLE_PYROSETTA:-1}"
    echo "PEPPRED_PYROSETTA_PATH=${PEPPRED_PYROSETTA_PATH:-}"
    printf 'Command: cd %q && python3 start.py %q\n' "$PEPPRED_ROOT" "$INPUT_CSV"
    exit 0
fi

cd "$PEPPRED_ROOT"
exec python3 start.py "$INPUT_CSV"
