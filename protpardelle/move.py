import shutil
import os
from pathlib import Path

from misc.constants import *

# Change note (2026-06-14, wyattb/codex):
# SIF compatibility: collect Protpardelle outputs from the configured
# project/output directory, avoiding assumptions about a fixed local results tree.

# Root directory containing model/config output folders for this run.
OUTPUT_ROOT = Path(os.environ.get("PROTPARDELLE_OUTPUT_DIR", Path(mainpath) / "protpardelle" / "results"))
PROJECT_NAME = (
    os.environ.get("PROTPARDELLE_CONFIG_NAME")
    or os.environ.get("PROTPARDELLE_PROJECT_NAME")
    or "peppred"
)
ROOT_DIR = OUTPUT_ROOT / PROJECT_NAME
OUT_DIR = Path("structures")

OUT_DIR.mkdir(exist_ok=True)

if not ROOT_DIR.exists():
    raise FileNotFoundError(f"Protpardelle output root not found: {ROOT_DIR}")

config_dirs = sorted(p for p in ROOT_DIR.iterdir() if p.is_dir())
if not config_dirs:
    raise RuntimeError(f"No Protpardelle config output directories found in {ROOT_DIR}")

for config_dir in config_dirs:
    for folder_path in sorted(p for p in config_dir.iterdir() if p.is_dir()):
        for src in sorted(folder_path.glob("*.pdb")):
            # case 1: already a sample file
            if src.name.startswith("sample_"):
                new_name = src.name
            # case 2: base structure like 1K5N.pdb
            else:
                new_name = f"sample_{src.stem}_50.pdb"

            dst = OUT_DIR / new_name
            if dst.exists():
                dst = OUT_DIR / f"{config_dir.name}_{new_name}"

            shutil.copy2(src, dst)

print("Done collecting PDBs.")
