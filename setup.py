#!/usr/bin/env python3
import os
import re

#### USERS EDIT HERE: ######

# Paths
ROOT = "enter path ../peppred"
ROSETTA = "enter path to ../.../main"
CONDA = "enter path to ../bin/activate"
TENSOR = "example: ../anaconda3/envs/../lib:/../../lib/python3.9/site-packages/tensorrt"
NMHC = "enter path to netMHCpan-4.1/netMHCpan"
# Partition names (change for your HPC cluster)
# Sherlock: gpu / normal | Original lab: gpuq / shortq
PARTITION_GPU = "gpu"
PARTITION_SHORT = "normal"

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

