#!/usr/bin/env python3
# Change note (2026-06-14, wyattb/codex):
# Public-SIF release prep: keep setup.py compatible with legacy placeholders and
# allow either host-conda or SIF runtime paths through PEPPRED_* env vars.
import os
import re

#### USERS EDIT HERE: ######

# Paths
#
# Host-conda/non-SIF use:
#   Leave PEPPRED_SIF/SIF unset. Set PEPPRED_CONDA_ACTIVATE to the host conda
#   activate script, PEPPRED_NETMHCPAN_BIN to the host netMHCpan executable, and
#   PEPPRED_ROSETTA_DIR only if needed by a local Rosetta workflow. The runner
#   can still use PEPPRED_SCHEDULER=slurm or PEPPRED_SCHEDULER=local.
#
# Singularity/SIF use:
#   Set PEPPRED_SIF=/path/to/peppred.sif before running setup.py or start.py.
#   CONDA defaults to the container activate script. NMHC should be the
#   container-visible NetMHCpan path; bind the host NetMHCpan install at runtime
#   with PEPPRED_NETMHCPAN_HOST_DIR.
#   PyRosetta is not controlled by ROSETTA. It is attempted by default; set
#   PEPPRED_PYROSETTA_PATH if the package is outside the active Python env, or
#   PEPPRED_ENABLE_PYROSETTA=0 to use the Biopython fallback.
# ROOT: host code directory (bind-mounted into container at same path)
ROOT = os.environ.get("PEPPRED_ROOT", os.path.dirname(os.path.abspath(__file__)))

# ROSETTA: optional; leave unset unless using a local Rosetta/PyRosetta path.
ROSETTA = os.environ.get("PEPPRED_ROSETTA_DIR", "")

# CONDA: host conda activate script for non-SIF, container activate script for SIF.
CONDA = os.environ.get("PEPPRED_CONDA_ACTIVATE", "/opt/conda/bin/activate" if os.environ.get("PEPPRED_SIF") else "enter path to ../bin/activate")

# NMHC: netMHCpan inside container; bind PEPPRED_NETMHCPAN_HOST_DIR to this container directory.
NETMHCPAN_CONTAINER_DIR = os.environ.get("PEPPRED_NETMHCPAN_CONTAINER_DIR", "/container/software/netmhcpan")
NETMHCPAN_VERSION_DIR = os.environ.get("PEPPRED_NETMHCPAN_VERSION_DIR", "netMHCpan-4.2-linux")
NMHC = os.environ.get("PEPPRED_NETMHCPAN_BIN", f"{NETMHCPAN_CONTAINER_DIR}/{NETMHCPAN_VERSION_DIR}/netMHCpan")

# Partition names (change for your HPC cluster)
PARTITION_GPU = os.environ.get("PEPPRED_GPU_PARTITION", "gpu")
PARTITION_SHORT = os.environ.get("PEPPRED_CPU_PARTITION", "normal")

### DO NOT EDIT ###

#updated scripts
TARGET_FILES = [
    f"{ROOT}/misc/constants.py",
    f"{ROOT}/AFFT-HLA3DB/fold.sh",
    f"{ROOT}/AFFT-HLA3DB/predict_structure.sh",
    f"{ROOT}/AFFT-HLA3DB/misc/constants.py",
    f"{ROOT}/protpardelle/misc/constants.py",
    f"{ROOT}/Inference/constants.py",
    f"{ROOT}/start.py",
    f"{ROOT}/Inference/list.sh",
    f"{ROOT}/protpardelle/run.sh",
]

config_vars = {k: str(v) for k, v in globals().items() if k.isupper() and k not in ["TARGET_FILES"]}

def replace_placeholders(content):
    def repl(match):
        var_name = match.group(1)
        if var_name in config_vars:
            return config_vars[var_name]
        else:
            print(f"[!] Warning: {var_name} not defined in config section")
            return match.group(0)  # leave placeholder unchanged
    return re.sub(r"\{\{(\w+)\}\}", repl, content)

def main():
    for path in TARGET_FILES:
        if not os.path.exists(path):
            print(f"[!] Skipping {path} (not found)")
            continue

        with open(path, "r") as f:
            original = f.read()

        updated = replace_placeholders(original)
        backup_path = path + ".bak"
        if not os.path.exists(backup_path):
            with open(backup_path, "w") as f:
                f.write(original)

        with open(path, "w") as f:
            f.write(updated)

        print(f"[+] Updated {path}")

if __name__ == "__main__":
    main()
