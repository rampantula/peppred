import os
import csv
import re
from coverage import *

#calculate coverage for alleles after nmhc pan step

def extract_alleles(path):
    alleles = []
    pattern = re.compile(r"HLA-[A-Z]\*\d{2}:\d{2}")

    with open(path, "r") as f:
        for line in f:
            hits = pattern.findall(line)
            for h in hits:
                fixed = h.replace("HLA-", "")
                alleles.append(fixed)
    return list(dict.fromkeys(alleles))

def load_allele_freqs(csv_path="HLA_population_coverage.csv"):
    freq_map = {}
    if not os.path.exists(csv_path):
        print(f"[WARN] Allele frequency file not found: {csv_path}")
        return freq_map
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            allele = row.get("Allele", "").replace("HLA-", "").strip()
            freq_str = row.get("Frequency", "").strip()  # or whatever your column is
            if not allele or not freq_str:
                continue
            try:
                freq = float(freq_str)
            except ValueError:
                continue
            freq_map[allele] = freq

    return freq_map


#### Final Text Summary #####
def write_text_summary(
        pepID,
        sequence,
        alleles,
        coverage,
        freq_map,   # <-- pass in the freq_map built once in main()
        out_path="results/netmhcpan_text_summary.txt",
    ):
 
                
    lines = []
    lines.append(f"######### {pepID} NETMHCPAN #########")
    lines.append(f"{sequence} | {len(alleles)} Binders | Coverage {coverage:.2f} %")
    lines.append(f"Binding Alleles and Allele Frequencies")
    
    # Each allele printed one per line
    for a in alleles:
        freq = freq_map.get(a)
        if freq is None or freq == "":
            freq_str = "N/A"
        else:
            try:
                # freq should already be a float from load_allele_freqs,
                # but this is safe even if it's a string
                freq_val = float(freq)
                freq_str = f"{freq_val:.6f}"
            except ValueError:
                freq_str = str(freq)

        lines.append(f"{a} - {freq_str}")

    lines.append("")  # blank line after each peptide block

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "a") as out:
        out.write("\n".join(lines) + "\n")


def main():
    nmhc_dir = "NMHC"
    out_csv = "results/netMHCpan_coverage.csv"

    if not os.path.isdir(nmhc_dir):
        print("[ERROR] NMHC/ folder not found.")
        return
        
    freq_map = load_allele_freqs("HLA_population_coverage.csv")
    
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
            coverage = run_coverage_from_list(alleles, csv_file_path='HLA_population_coverage.csv')
     
        write_text_summary(
            pepID=pepID,
            sequence=sequence,
            alleles=alleles,
            coverage=coverage,
            freq_map=freq_map,
            out_path="results/netmhcpan_text_summary.txt"
            )
        print(f"[+] {pepID} ({sequence}) → {num_binders} binders, coverage {coverage:.2f}%")

if __name__ == "__main__":
    main()

