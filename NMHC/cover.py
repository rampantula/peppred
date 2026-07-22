#       Sgourakis Lab
#   Author: Ram Pantula
#   Date: July 1, 2025
#   Email: rpantula@sas.upenn.edu
#

"""
Copyright (c) 2026 The Children's Hospital of Philadelphia and Stanford University
Licensed for academic and non-commercial use only. Commercial use requires a separate license.
See LICENSE file for details.
"""
import os
import csv
import re
from coverage import run_coverage_from_list

def extract_alleles(path):
    alleles = []
    pattern = re.compile(r"HLA-[A-Z]\*\d{2}:\d{2}")

    with open(path, "r") as f:
        for line in f:
            hits = pattern.findall(line)
            for h in hits:
                fixed = h.replace("*", "")
                alleles.append(fixed)
    return list(dict.fromkeys(alleles))

def main():
    nmhc_dir = "NMHC"
    out_csv = "ALL_PEPTIDES_COVERAGE.csv"

    if not os.path.isdir(nmhc_dir):
        print("[ERROR] NMHC/ folder not found.")
        return

    peptide_rows = []

    for pepID in sorted(os.listdir(nmhc_dir)):
        pep_folder = os.path.join(nmhc_dir, pepID)
        if not os.path.isdir(pep_folder):
            continue

        sbwb_file = None
        for f in os.listdir(pep_folder):
            if f.endswith("_SB_WB_only.txt"):
                sbwb_file = os.path.join(pep_folder, f)
                break

        if sbwb_file is None:
            print(f"[WARN] No SB/WB file found for {pepID}")
            continue
        sequence = f.split("_SB_WB_only.txt")[0].split("results_")[-1]

        alleles = extract_alleles(sbwb_file)
        num_binders = len(alleles)

        if num_binders == 0:
            coverage = 0.0
        else:
            coverage = run_coverage_from_list(alleles)

        peptide_rows.append([
            pepID,
            sequence,
            num_binders,
            f"{coverage:.2f}",
            ";".join(alleles)
        ])

        print(f"[+] {pepID} ({sequence}) → {num_binders} binders, coverage {coverage:.2f}%")

    with open(out_csv, "w") as out:
        writer = csv.writer(out)
        writer.writerow(["pepID", "sequence", "num_binders", "coverage", "alleles"])
        writer.writerows(peptide_rows)

    print(f"\n[+] Wrote coverage summary → {out_csv}\n")


if __name__ == "__main__":
    main()

