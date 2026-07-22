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
from Bio.PDB import PDBParser, PDBIO
from misc.constants import *

INPUT_ROOT  = f"{mainpath}/AFFT-HLA3DB/outfiles"
OUTPUT_ROOT = f"{mainpath}/AFFT-HLA3DB/MHC_pdbs"

def process_structure(pdb_path, npy_path, out_path):
    parser    = PDBParser(QUIET=True)
    structure = parser.get_structure(os.path.basename(pdb_path), pdb_path)
    scores    = np.load(npy_path)

    for model in structure:
        for chain in model:
            for i, residue in enumerate(chain):
                try:
                    for atom in residue:
                        atom.bfactor = float(scores[i])
                except IndexError:
                    print(f"  [!] missing score for residue {i+1} in {pdb_path}")
                    break

    io = PDBIO()
    io.set_structure(structure)
    io.save(out_path)
    print(f"  [+] wrote {out_path}")

def old():
    input_root  = os.path(INPUT_ROOT)
    output_root = os.path(OUTPUT_ROOT)
    os.makedirs(output_root, exist_ok=True)

    print(f"Scanning {input_root!r} …")
    for dirpath, _, files in os.walk(input_root):
        # find any pLDDT numpy file
        npy_files = [f for f in files if f.lower().endswith("plddt.npy")]
        if not npy_files:
            # nothing to do in this folder
            continue
        if len(npy_files) > 1:
            print(f"[!] multiple plddt files in {dirpath!r}, using first: {npy_files}")
        npy_path = os.path.join(dirpath, npy_files[0])

        # find all PDBs here
        pdbs = [f for f in files if f.lower().endswith(".pdb")]
        if not pdbs:
            print(f"[!] no PDBs found in {dirpath!r}, skipping")
            continue

        folder_name = os.path.basename(dirpath)
        for pdb_fn in pdbs:
            pdb_path = os.path.join(dirpath, pdb_fn)
            out_pdb_fn   = f"{folder_name}.pdb"
            out_pdb_path = os.path.join(output_root, out_pdb_fn)

            print(f"Processing {pdb_path!r} with scores {npy_path!r} → {out_pdb_path!r}")
            process_structure(pdb_path, npy_path, out_pdb_path)
            
import shutil
def main():
    input_root = os.path.abspath(INPUT_ROOT)
    output_dir = os.path.abspath(OUTPUT_ROOT)
    os.makedirs(output_dir, exist_ok=True)

    for entry in os.listdir(input_root):
        subdir = os.path.join(input_root, entry)
        if not os.path.isdir(subdir):
            continue

        # find any .pdb file in this subdirectory
        pdbs = [f for f in os.listdir(subdir) if f.lower().endswith('.pdb')]
        if not pdbs:
            print(f"[!] no PDB found in {subdir!r}, skipping.")
            continue

        # take the first PDB found
        src_pdb = os.path.join(subdir, pdbs[0])
        dst_pdb = os.path.join(output_dir, f"{entry}.pdb")

        try:
            shutil.copy2(src_pdb, dst_pdb)
            print(f"[+] copied {src_pdb!r} → {dst_pdb!r}")
        except Exception as e:
            print(f"[!] failed to copy {src_pdb!r}: {e}")

if __name__ == "__main__":
    main()
