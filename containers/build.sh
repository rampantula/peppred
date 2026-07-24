#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./containers/build.sh vMAJOR.MINOR.PATCH

Builds, smoke-tests, and checksums a versioned PepPred SIF.

Optional environment variables:
  PEPPRED_SIF_OUTPUT_DIR     Output directory (default: <repo>/dist)
  PEPPRED_BUILD_FAKEROOT    Set to 1 to pass --fakeroot
  PEPPRED_BUILD_CPUS        Limit squashfs compression workers
                            (default under Slurm: SLURM_CPUS_PER_TASK)
  PEPPRED_ALLOW_DIRTY_BUILD Set to 1 for an explicitly non-release build
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "$#" -ne 1 ]]; then
    usage >&2
    exit 2
fi

version="${1:-}"
if [[ ! "${version}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
    usage >&2
    echo "ERROR: version must look like v0.1.1 or v0.2.0-rc1." >&2
    exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "${script_dir}/.." && pwd -P)"
definition="${script_dir}/peppred.def"
output_dir="${PEPPRED_SIF_OUTPUT_DIR:-${repo_root}/dist}"
image_name="peppred-${version}.sif"
image_path="${output_dir}/${image_name}"
checksum_path="${image_path}.sha256"
manifest_path="${output_dir}/peppred-${version}.manifest.txt"

if ! git -C "${repo_root}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: build from a Git checkout so the source revision is recorded." >&2
    exit 1
fi

required_inputs=(
    "${definition}"
    "${script_dir}/envs/alphafold.yml"
    "${script_dir}/envs/compare.yml"
    "${script_dir}/envs/train.yml"
    "${script_dir}/envs/protpardelle-validated-pip.txt"
    "${repo_root}/protpardelle/pyproject.toml"
    "${repo_root}/protpardelle/README.md"
    "${repo_root}/protpardelle/LICENSE"
    "${repo_root}/protpardelle/src"
)
for required_input in "${required_inputs[@]}"; do
    if [[ ! -e "${required_input}" ]]; then
        echo "ERROR: required build input is missing: ${required_input}" >&2
        exit 1
    fi
done

dirty_state="$(git -C "${repo_root}" status --porcelain --untracked-files=normal)"
if [[ -n "${dirty_state}" && "${PEPPRED_ALLOW_DIRTY_BUILD:-0}" != "1" ]]; then
    echo "ERROR: release builds require a clean Git checkout." >&2
    echo "Commit or stash changes, or set PEPPRED_ALLOW_DIRTY_BUILD=1 for a development build." >&2
    exit 1
fi

source_commit="$(git -C "${repo_root}" rev-parse HEAD)"
if [[ -n "${dirty_state}" ]]; then
    source_commit="${source_commit}-dirty"
fi

if command -v apptainer >/dev/null 2>&1; then
    container_runtime="$(command -v apptainer)"
elif command -v singularity >/dev/null 2>&1; then
    container_runtime="$(command -v singularity)"
else
    echo "ERROR: Apptainer or Singularity is required to build the SIF." >&2
    exit 1
fi

mkdir -p "${output_dir}"
for artifact in "${image_path}" "${checksum_path}" "${manifest_path}"; do
    if [[ -e "${artifact}" ]]; then
        echo "ERROR: refusing to overwrite existing release artifact: ${artifact}" >&2
        exit 1
    fi
done

build_args=(
    build
    --build-arg "PEPPRED_VERSION=${version}"
    --build-arg "PEPPRED_GIT_COMMIT=${source_commit}"
)
build_help="$("${container_runtime}" build --help 2>&1)"
if grep -q -- "--reproducible" <<<"${build_help}"; then
    build_args+=(--reproducible)
fi
if [[ "${PEPPRED_BUILD_FAKEROOT:-0}" == "1" ]]; then
    build_args+=(--fakeroot)
fi
build_cpus="${PEPPRED_BUILD_CPUS:-${SLURM_CPUS_PER_TASK:-}}"
if [[ -n "${build_cpus}" ]]; then
    if [[ ! "${build_cpus}" =~ ^[1-9][0-9]*$ ]]; then
        echo "ERROR: PEPPRED_BUILD_CPUS must be a positive integer." >&2
        exit 2
    fi
    if grep -q -- "--mksquashfs-args" <<<"${build_help}"; then
        build_args+=(--mksquashfs-args "-processors ${build_cpus}")
    else
        echo "WARNING: the container runtime cannot limit squashfs workers." >&2
    fi
fi

echo "Building ${image_path}"
echo "Source revision: ${source_commit}"
(
    cd "${repo_root}"
    "${container_runtime}" "${build_args[@]}" "${image_path}" "${definition}"
)

"${script_dir}/test.sh" "${image_path}"

(
    cd "${output_dir}"
    sha256sum "${image_name}" > "${image_name}.sha256"
)

image_sha256="$(cut -d ' ' -f 1 "${checksum_path}")"
runtime_version="$("${container_runtime}" version)"
definition_sha256="$(sha256sum "${definition}" | cut -d ' ' -f 1)"
alphafold_sha256="$(sha256sum "${script_dir}/envs/alphafold.yml" | cut -d ' ' -f 1)"
compare_sha256="$(sha256sum "${script_dir}/envs/compare.yml" | cut -d ' ' -f 1)"
train_sha256="$(sha256sum "${script_dir}/envs/train.yml" | cut -d ' ' -f 1)"
protpardelle_sha256="$(sha256sum "${script_dir}/envs/protpardelle-validated-pip.txt" | cut -d ' ' -f 1)"

{
    printf 'peppred_version=%s\n' "${version}"
    printf 'source_commit=%s\n' "${source_commit}"
    printf 'image_file=%s\n' "${image_name}"
    printf 'image_sha256=%s\n' "${image_sha256}"
    printf 'container_runtime=%s\n' "${runtime_version}"
    printf 'definition_sha256=%s\n' "${definition_sha256}"
    printf 'alphafold_spec_sha256=%s\n' "${alphafold_sha256}"
    printf 'compare_spec_sha256=%s\n' "${compare_sha256}"
    printf 'train_spec_sha256=%s\n' "${train_sha256}"
    printf 'protpardelle_spec_sha256=%s\n' "${protpardelle_sha256}"
    printf 'built_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${manifest_path}"

echo "Build complete:"
echo "  ${image_path}"
echo "  ${checksum_path}"
echo "  ${manifest_path}"
