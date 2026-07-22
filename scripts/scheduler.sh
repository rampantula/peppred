#!/usr/bin/env bash
#Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
#Licensed for academic and non-commercial use only. Commercial use requires a separate license.
#See LICENSE file for details.

peppred_scheduler_mode() {
    local mode="${PEPPRED_SCHEDULER:-slurm}"
    mode="${mode,,}"
    case "${mode}" in
        serial|single-node|single_node|noslurm|no-slurm)
            mode="local"
            ;;
    esac

    if [[ "${mode}" != "slurm" && "${mode}" != "local" ]]; then
        echo "PEPPRED_SCHEDULER must be 'slurm' or 'local'." >&2
        return 2
    fi

    printf '%s\n' "${mode}"
}

peppred_is_local() {
    [[ "${SCHEDULER:-$(peppred_scheduler_mode)}" == "local" ]]
}

peppred_is_slurm() {
    [[ "${SCHEDULER:-$(peppred_scheduler_mode)}" == "slurm" ]]
}

peppred_run_step() {
    local label="$1"
    shift
    echo "Running ${label}"
    "$@"
}

peppred_submit_job() {
    sbatch --parsable "$@"
}
