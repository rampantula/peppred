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

import re
import os
import sys
import shutil

def extract_alleles(results_file):
    alleles = []
    with open(results_file, "r") as f:
        for line in f:
            match = re.search(r"HLA-([A-Z]\*\d{2}:\d{2})", line)
            if match:
                alleles.append(match.group(1))
    return list(dict.fromkeys(alleles))  


def load_fasta(fasta_path):
    fasta_dict = {}
    current_header = None
    current_seq = []
    with open(fasta_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if current_header and current_seq:
                    fasta_dict[current_header] = "".join(current_seq)
                current_header = line[1:].split()[0]  
                current_seq = []
            else:
                current_seq.append(line)
        if current_header and current_seq:
            fasta_dict[current_header] = "".join(current_seq)
    return fasta_dict


def write_input_seq_files(alleles, fasta_dict, pep_id, peptide, base_dir):
    input_dir = os.path.join(base_dir, "AFFT-HLA3DB", "input_seq")
    os.makedirs(input_dir, exist_ok=True)

    for allele in alleles:
        if allele not in fasta_dict:
            print(f"[WARNING] No FASTA found for {allele}")
            continue

        outfile = os.path.join(input_dir, f"{pep_id.replace('_','')}{allele.replace('*', '').replace(':', '')}_seq.txt")
        with open(outfile, "w") as out:
            out.write(f"{fasta_dict[allele]}\n{peptide}\n")
        print(f"Wrote {outfile}")


def main():
    if len(sys.argv) != 5:
        print("Usage: python geninput.py <results_file> <NMDP_fasta> <pep_id> <peptide_sequence>")
        sys.exit(1)
    
    results_file, fasta_file, peptide, pep_id = sys.argv[1:5]

    alleles = extract_alleles(results_file)
    print(f"Found {len(alleles)} alleles in {results_file}")

    fasta_dict = load_fasta(fasta_file)
    write_input_seq_files(alleles, fasta_dict, pep_id, peptide, os.getcwd())


if __name__ == "__main__":
    main()

