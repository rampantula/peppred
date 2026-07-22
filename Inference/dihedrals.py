#       Sgourakis Lab
#   Author: Ram Pantula
#   Modified: Wyatt Blackson
#   Date: April 15, 2026
#   Email: sagarg@sas.upenn.edu
#
"""
Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
Licensed for academic and non-commercial use only. Commercial use requires a separate license.
See LICENSE file for details.
"""

# import required libraries
import csv
import math
import os
import sys

def _env_enabled_by_default(name):
    value = os.environ.get(name, "").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _add_pyrosetta_paths():
    path_value = os.environ.get("PEPPRED_PYROSETTA_PATH", "").strip()
    if not path_value:
        return
    for path in reversed(path_value.split(os.pathsep)):
        if path and path not in sys.path:
            sys.path.insert(0, path)


pyrosetta = None
pose_from_pdb = None
HAS_PYROSETTA = False

if _env_enabled_by_default("PEPPRED_ENABLE_PYROSETTA"):
    _add_pyrosetta_paths()
    try:
        import pyrosetta
        pyrosetta.init()
        from pyrosetta import pose_from_pdb
        HAS_PYROSETTA = True
    except Exception as exc:
        raise RuntimeError(
            "PyRosetta is enabled by default, but could not be imported. "
            "Set PEPPRED_PYROSETTA_PATH to a Python-version-compatible PyRosetta "
            "package path, or set PEPPRED_ENABLE_PYROSETTA=0 to use the Biopython "
            "dihedral fallback."
        ) from exc
else:
    print("PEPPRED_ENABLE_PYROSETTA=0; using Biopython dihedral fallback.")

sys.path.append('../')
from constants import *
from common import *


def _biopython_peptide_dihedrals(pdbpath, pep_chain, pep_len):
    from Bio.PDB import PDBParser
    from Bio.PDB.vectors import calc_dihedral

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("peptide", pdbpath)
    model = next(structure.get_models())
    chain = model[pep_chain]

    residues_by_index = {
        residue.id[1]: residue
        for residue in chain.get_residues()
        if residue.id[0] == " "
    }
    residues = [residues_by_index[i] for i in range(1, pep_len + 1)]

    angles = []
    for idx, residue in enumerate(residues):
        if idx == 0:
            phi = 0.0
        else:
            phi = math.degrees(calc_dihedral(
                residues[idx - 1]["C"].get_vector(),
                residue["N"].get_vector(),
                residue["CA"].get_vector(),
                residue["C"].get_vector(),
            ))

        if idx == len(residues) - 1:
            psi = 0.0
        else:
            psi = math.degrees(calc_dihedral(
                residue["N"].get_vector(),
                residue["CA"].get_vector(),
                residue["C"].get_vector(),
                residues[idx + 1]["N"].get_vector(),
            ))

        angles.extend([phi, psi])

    return angles


def get_dihedrals(pdb_dict, pep_len):

    outputfile = f"{dbpath}/out/peptide_dihedrals.csv"

    with open(outputfile, "w") as dihedralsfile:
        writer = csv.writer(dihedralsfile)

        header = ["pdbid"]
        for i in range(1, pep_len+1):
            header.append(f"phi_{i}")
            header.append(f"psi_{i}")

        writer.writerow(header)

        for pdbid in pdb_dict.keys():
            row = [pdbid]
            pdbpath = f"{dbpath}/structures/{pdbid}_reordered.pdb"
            if not os.path.exists(pdbpath):
                 print(f"Skipping file: {pdbid}")
                 continue
            if HAS_PYROSETTA:
                pose = pose_from_pdb(pdbpath)
                p1 = pose.pdb_info().pdb2pose(DEFAULT_PEP_CHAIN, 1)
                pO = pose.pdb_info().pdb2pose(DEFAULT_PEP_CHAIN, pep_len)

                for resi_num in range(p1, pO+1):
                    phi = pose.phi(resi_num)
                    psi = pose.psi(resi_num)

                    row.append(str(phi))
                    row.append(str(psi))
            else:
                row.extend(str(x) for x in _biopython_peptide_dihedrals(
                    pdbpath, DEFAULT_PEP_CHAIN, pep_len
                ))

            writer.writerow(row)

def main():
    import pandas as pd

    mhcs = pd.read_csv(f"{dbpath}/out/MHCs.csv")

    pdb_dict = {}
    for _, row in mhcs.iterrows():
        pdbid = row["PDB"]
        peptide = row["Peptide Sequence"]
        allele = row["Allele"]
        key = pdbid  # or pdbid + "-" + chain if needed
        pdb_dict[key] = f"{peptide}_{allele}"

    for x in [9]:
        pep_len = x  # for example
        filtered_dict = {k: v for k, v in pdb_dict.items() if len(v.split('_')[0]) == pep_len}
        get_dihedrals(filtered_dict, pep_len)

if __name__ == "__main__":
    main()
