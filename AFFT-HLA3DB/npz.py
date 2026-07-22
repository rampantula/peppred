#!/usr/bin/env python3
#       Sgourakis Lab
#   Author: Ram Pantula
#   Date: July 1, 2025
#   Email: rpantula@sas.upenn.edu

"""
Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
Licensed for academic and non-commercial use only. Commercial use requires a separate license.
See LICENSE file for details.
"""

import os
import numpy as np
from misc.constants import *

INPUT_ROOT   = f"{mainpath}/AFFT-HLA3DB/outfiles"
STORAGE_ROOT = f"{mainpath}/AFFT-HLA3DB/scorings"


def combine_npy_to_npz(dirpath, npy_files, out_path):
    arrays = {}
    for fname in npy_files:
        key = os.path.splitext(fname)[0]
        fpath = os.path.join(dirpath, fname)
        try:
            arrays[key] = np.load(fpath)
        except Exception as e:
            print(f"  [!] failed to load {fpath!r}: {e}")
    if arrays:
        np.savez_compressed(out_path, **arrays)
        print(f"  [+] wrote {out_path}")
    else:
        print(f"  [!] no valid arrays to save in {dirpath!r}")

def main():
    input_root   = os.path.abspath(INPUT_ROOT)
    storage_root = os.path.abspath(STORAGE_ROOT)
    os.makedirs(storage_root, exist_ok=True)

    print(f"Scanning for .npy files under {input_root!r} …")
    for dirpath, _, files in os.walk(input_root):
        # find any .npy files in this folder
        npy_files = [f for f in files if f.lower().endswith(".npy")]
        if not npy_files:
            continue

        folder_name = os.path.basename(dirpath)
        out_filename = f"{folder_name}.npz"
        out_path = os.path.join(storage_root, out_filename)

        print(f"Combining {len(npy_files)} .npy files in {dirpath!r} → {out_path!r}")
        combine_npy_to_npz(dirpath, npy_files, out_path)

if __name__ == "__main__":
    main()

