#       Sgourakis Lab
#   Author: Ram Pantula
#   Date: April 15, 2026
#   Email: sagarg@sas.upenn.edu

# import required libraries
import csv
import pyrosetta
pyrosetta.init()
from pyrosetta import pose_from_pdb

import os
import sys
sys.path.append('../')
from constants import *
from common import *


def get_dihedrals(pdb_dict, pep_len):

    outputfile = f"{dbpath}/out/peptide_dihedrals.csv"

    with open(outputfile, "a") as dihedralsfile:
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
            pose = pose_from_pdb(pdbpath)      
            p1 = pose.pdb_info().pdb2pose(DEFAULT_PEP_CHAIN, 1)
            pO = pose.pdb_info().pdb2pose(DEFAULT_PEP_CHAIN, pep_len)

            for resi_num in range(p1, pO+1):
                phi = pose.phi(resi_num)
                psi = pose.psi(resi_num)

                row.append(str(phi))
                row.append(str(psi))

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
