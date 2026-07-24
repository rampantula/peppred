# PepPred SIF Maintenance

This directory is the shared, source-controlled build surface for the PepPred
runtime image. The generated SIF does not belong in Git. Development images
belong in shared lab storage; public images belong in a versioned Zenodo
record.

## What the image contains

The image contains four runtime environments:

- `alphafold`
- `compare`
- `train`
- `protpardelle`

The image intentionally does not contain:

- PepPred model and Protpardelle model assets;
- NetMHCpan;
- PyRosetta.

Model assets are distributed as the companion archive documented in the
top-level README. NetMHCpan and PyRosetta remain user-provided because they are
separately distributed. Users may explicitly select the Biopython dihedral
implementation with `PEPPRED_ENABLE_PYROSETTA=0`.

## Build prerequisites

- A clean Git checkout of the exact source revision to release.
- Apptainer or Singularity with permission to build from a definition file.
- Network access to the Debian, Anaconda, conda, and Python package sources.
- A build temporary directory with enough free space for the uncompressed
  image. For this image, budget at least 40 GB.

If the system's `/tmp` is small, point Apptainer at project or scratch storage:

```bash
export APPTAINER_TMPDIR=/path/to/large/project/tmp
```

## Build a candidate

Run the build from any directory:

```bash
export PEPPRED_SIF_OUTPUT_DIR=/path/to/shared/lab/peppred-images
./containers/build.sh v0.1.1
```

Set `PEPPRED_BUILD_FAKEROOT=1` if the local Apptainer installation requires
explicit fakeroot mode. `PEPPRED_BUILD_CPUS` limits squashfs compression
workers; inside a Slurm job it defaults to `SLURM_CPUS_PER_TASK`.

Release builds require a clean Git checkout. For an explicitly non-release
development build, set:

```bash
export PEPPRED_ALLOW_DIRTY_BUILD=1
```

The build script refuses to overwrite an existing release and produces:

```text
peppred-v0.1.1.sif
peppred-v0.1.1.sif.sha256
peppred-v0.1.1.manifest.txt
```

The checksum file contains only the portable release filename, not a personal
scratch path.

## Test an existing image

The default smoke test checks the four environments, required AlphaFold CUDA
tools/libraries, the intentional absence of bundled PyRosetta, and explicit
selection of the Biopython fallback:

```bash
./containers/test.sh /path/to/peppred-v0.1.1.sif
```

Run the full AlphaFold/JAX/TensorFlow import from a normal compute allocation:

```bash
./containers/test.sh /path/to/peppred-v0.1.1.sif --full
```

The full test requires an open-file limit of at least 1024. GPU release
validation and one end-to-end PepPred input remain separate from this cheap
container smoke test.

## Versioning rules

| Change | Release action |
| --- | --- |
| PepPred Python/shell code only | Retest against the current SIF; usually no image rebuild |
| Conda, Python, CUDA, or system dependency | Build a new SIF version |
| Code under `protpardelle/src/` | Build a new SIF because that package is installed into the image |
| Model weights or model configuration | Publish a new companion asset version |
| Scheduler or documentation only | Usually no image rebuild |

One SIF serves both the Slurm-only and unified-scheduler branches unless their
runtime dependencies diverge.

Never replace a published SIF in place. Use a new version such as `v0.1.2`.
An internal convenience symlink such as `peppred-current.sif` may point to the
current shared-lab copy, but public documentation and manifests must use the
versioned filename and SHA256.

## Three-person release workflow

1. One maintainer builds from a clean, reviewed Git revision.
2. A second maintainer runs the smoke test, the relevant GPU/end-to-end test,
   verifies the SHA256, and tests an external PyRosetta bind when that mode is
   claimed for the release.
3. In the existing PepPred Zenodo record, create a **New version**.
4. Import any unchanged files from the prior version.
5. Upload the new SIF, its `.sha256`, its manifest, and the matching companion
   asset archive/checksum.
6. Record the version-specific DOI and source commit in the release notes.
7. Publish only after the files and checksums have been independently checked.

All three lab members should be added to the Zenodo record with **Can manage**
access. That permission applies to drafts and all current and future versions.
The README should link to the concept DOI for the latest release:

<https://doi.org/10.5281/zenodo.20076766>

The SIF and current companion archive together fit within Zenodo's default
50 GB per-record quota.

## Provenance of the first portable recipe

The environment YAMLs here are the inputs used to create the validated
`peppred-v0.1.0.sif`. The Protpardelle requirements were recovered from that
image because the original build installed then-current packages rather than
the older `protpardelle/uv.lock`.

Validated image:

```text
size: 8,546,824,192 bytes
SHA256: a5b4ffe610825d8a14e1fabab70c3f26de8bad80a68e1da37a6b0d9bbeff5948
```

The base image digest and Miniconda installer/checksum are pinned in
`peppred.def`. Package repositories can still change or remove old artifacts,
so each future SIF remains a separately checksummed release artifact even when
its source inputs are pinned.
