#!/usr/bin/env python3
#       Sgourakis Lab
#   Author: Ram Pantula
#   Modified: Wyatt Blackson
#   Date: July 1, 2025
#   Email: rpantula@sas.upenn.edu

"""
Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
Licensed for academic and non-commercial use only. Commercial use requires a separate license.
See LICENSE file for details.
"""

from pathlib import Path
from datetime import datetime
import shutil
import os
from constants import mainpath

#script that organizes outputs

def moveit(src: Path, dst: Path):
    if src.exists():
        target = dst / src.name
        if target.exists():
            target = dst / f"{src.name}_moved"
        shutil.move(str(src), str(target))
    else:
        print(f"WARNING: {src} not found")

def renameit(src: Path, new_name: str):
    if src.exists():
        target = src.parent / new_name

        if target.exists():
            target = src.parent / f"{new_name}_renamed"

        src.rename(target)
    else:
        print(f"WARNING: {src} not found")

def current_run_dirs(src: Path, excluded=()):
    excluded = set(excluded)
    if not src.exists():
        return []
    return sorted(
        d for d in src.iterdir()
        if d.is_dir() and d.name not in excluded and not d.name.startswith(".")
    )

def main():
    loc = Path(mainpath)
    timestamp = datetime.now().strftime("%m%d%y%H%M%S")

    nmhc_dir = loc / "NMHC"

    nmhc_run_dirs = current_run_dirs(nmhc_dir, excluded={"incomplete", "__pycache__"})
    names = [d.name for d in nmhc_run_dirs]

    joined_name = "_".join(names) if names else "NMHC_results"

    result_dir = loc / "results" / f"{joined_name}_{timestamp}"
    result_dir.mkdir(parents=True, exist_ok=True)

    for d in nmhc_run_dirs:
        moveit(d, result_dir)
        
    print(f"Result directory:\n{result_dir}")

    moveit(loc / "Inference" / "out", result_dir)
    #moveit(loc / "Inference" / "scorings", result_dir) --> redundant scorings directory (can be optionally turned on)

    afft_dir = loc / "AFFT-HLA3DB"

    moveit(afft_dir / "outfiles", result_dir)
    moveit(afft_dir / "input_seq", result_dir)

    (afft_dir / "input_seq").mkdir(parents=True, exist_ok=True)

    protpardelle_results = Path(os.environ.get("PROTPARDELLE_OUTPUT_DIR", loc / "protpardelle" / "results"))
    protpardelle_project = (
        os.environ.get("PROTPARDELLE_CONFIG_NAME")
        or os.environ.get("PROTPARDELLE_PROJECT_NAME")
        or "peppred"
    )
    protpardelle_project_dir = protpardelle_results / protpardelle_project

    if protpardelle_project_dir.exists():
        moveit(protpardelle_project_dir, result_dir)
    else:
        print(f"WARNING: Protpardelle project output not found: {protpardelle_project_dir}")
        
    results_dir = loc / "results"

    for f in results_dir.glob("*.csv"):
        moveit(f, result_dir)

    for f in results_dir.glob("*.txt"):
        moveit(f, result_dir)
    
    renameit(result_dir / "out", "Inference_Results")
    renameit(result_dir / "outfiles", "AFF2_structures")
    renameit(result_dir / protpardelle_project, "Protpardelle_out")
    renameit(result_dir / "input_seq", "AFF2_inputs")


    print("\nDone.")

if __name__ == "__main__":
    main()
