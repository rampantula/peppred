import os
import shutil
from misc.constants import *

# root directory containing the ensemble folders

ROOT_DIR = f"{mainpath}/protpardelle/results/peppred/cc89pmhc-epoch8800-sampling_partial_diffusion_allatom-ss1.0-schurn0-ccstart0.0-dx0.0-dy0.0-dz0.0-rewind80"

# output directory where all pdbs will go
OUT_DIR = "structures"

os.makedirs(OUT_DIR, exist_ok=True)

for folder in os.listdir(ROOT_DIR):

    folder_path = os.path.join(ROOT_DIR, folder)

    if not os.path.isdir(folder_path):
        continue

    for file in os.listdir(folder_path):

        if not file.endswith(".pdb"):
            continue

        src = os.path.join(folder_path, file)

        # case 1: already a sample file
        if file.startswith("sample_"):
            new_name = file

        # case 2: base structure like 1K5N.pdb
        else:
            base = file.replace(".pdb", "")
            new_name = f"sample_{base}_50.pdb"

        dst = os.path.join(OUT_DIR, new_name)

        shutil.copy2(src, dst)

print("Done collecting PDBs.")
