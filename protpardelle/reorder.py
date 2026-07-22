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
import re
from Bio.PDB import PDBParser, PDBIO, StructureBuilder

def split_and_rewrite_pdb(pdb_path, output_path, tail_count=9):
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("structure", pdb_path)
    model = structure[0]

    residues = [res for chain in model for res in chain if res.id[0] == ' ']
    tail_res = residues[-tail_count:]

    builder = StructureBuilder.StructureBuilder()
    builder.init_structure("structure")
    builder.init_model(0)

    # Chain A
    builder.init_chain('A')
    for res in residues[:-tail_count]:
        builder.structure[0]['A'].add(res.copy())

    # Chain B (renumber starting from 1)
    builder.init_chain('B')
    for i, res in enumerate(tail_res, start=1):
        new_res = res.copy()
        new_res.id = (' ', i, ' ')  # standard residue ID format: (' ', resseq, ' ')
        builder.structure[0]['B'].add(new_res)

    io = PDBIO()
    io.set_structure(builder.structure)
    io.save(output_path)

def process_all_pdbs(folder_path="MHC_pdbs/"):
    for filename in os.listdir(folder_path):
        pdb_id = os.path.splitext(filename)[0]
        output_filename = f"{pdb_id}_reordered.pdb"
        input_path = os.path.join(folder_path, filename)
        output_path = os.path.join(folder_path, output_filename)

        try:
            split_and_rewrite_pdb(input_path, output_path)
            os.remove(input_path)
            print(f"Processed: {filename} → {output_filename}")
        except Exception as e:
            print(f"Failed to process {filename}: {e}")

# Run the batch job
FOLDER = "MHC_pdbs"
process_all_pdbs(FOLDER)
import os
for root, dirs, files in os.walk(FOLDER):
    for fname in files:
        if "_reordered" in fname:
            old_path = os.path.join(root, fname)
            new_name = fname.replace("_reordered", "")
            new_path = os.path.join(root, new_name)

            if os.path.exists(new_path):
                print(f"Skipping (exists): {new_path}")
                continue

            os.rename(old_path, new_path)
            print(f"Renamed: {old_path} -> {new_path}")

