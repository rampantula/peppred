#!/usr/bin/env python3
import os
import sys
import csv
import subprocess
from supertypes import supertypes
from coverage import run_coverage_from_list 
import re
import os
import shutil
from datetime import datetime

def moveAFFT():
    src = "AFFT-HLA3DB"
    dst_root = "AFFT-HLA3DB/incomplete"
    untouchable = {
        "alphafold",
        "__pycache__",
        "completed",
        "figures",
        "input_seq",
        "misc",
        "params",
        "runlogs",
        "template_pdbs",
        "template_seq",
        "incomplete",
        ".DS_Store"
    }


    movable = []
    for name in os.listdir(src):
        path = os.path.join(src, name)
        if os.path.isdir(path) and name not in untouchable:
            movable.append(name)
    if not movable:
        print("No folders to move. Skipping creation of new directory.")
        return
    os.makedirs(dst_root, exist_ok=True)
    timestamp = datetime.now().strftime("%m%d%y%H%M%S")
    dst = os.path.join(dst_root, f"input_{timestamp}")
    os.makedirs(dst, exist_ok=True)

    print(f"Moving {len(movable)} folders into: {dst}")
    for name in movable:
        src_path = os.path.join(src, name)
        shutil.move(src_path, dst)
        print(f"Moved: {name} -> {dst}")

    print("Done.")

def moveNMHC():
    src = "NMHC"
    dst_root = "NMHC/incomplete"
    untouchable = {
        "incomplete",
        ".DS_Store"
    }
    movable = []
    for name in os.listdir(src):
        path = os.path.join(src, name)
        if os.path.isdir(path) and name not in untouchable:
            movable.append(name)
    if not movable:
        print("No folders to move. Skipping creation of new directory.")
        return


    os.makedirs(dst_root, exist_ok=True)
    timestamp = datetime.now().strftime("%m%d%y%H%M%S")
    dst = os.path.join(dst_root, f"input_{timestamp}")
    os.makedirs(dst, exist_ok=True)

    print(f"Moving {len(movable)} folders into: {dst}")
    for name in movable:
        src_path = os.path.join(src, name)
        shutil.move(src_path, dst)
        print(f"Moved: {name} -> {dst}")

    print("Done.")

def extract_alleles(result_file):
    alleles = []
    pattern = re.compile(r"(A\*\d{2}:\d{2}|B\*\d{2}:\d{2}|C\*\d{2}:\d{2})")

    with open(result_file, "r") as f:
        for line in f:
            m = pattern.search(line)
            if m:
                alleles.append(m.group(1))

    return list(dict.fromkeys(alleles))


def process_csv(input_csv):
    peptides = []  

    with open(input_csv, "r") as f:
        reader = csv.reader(f)

        for row_num, row in enumerate(reader, start=1):
            if not row or all(not c.strip() for c in row):
                print(f"[Warning] Skipping blank row {row_num}")
                continue
            if row[0].lower().startswith("pep"):
                print(f"[Info] Detected header row at {row_num}, skipping.")
                continue
            if len(row) < 2:
                print(f"[Error] Row {row_num} has fewer than 2 columns: {row}")
                continue

            raw_id = row[0].strip()
            clean_id = re.sub(r"[^A-Za-z0-9\-]", "_", raw_id)

            original_id = clean_id
            counter = 1
            while any(p[0] == clean_id for p in peptides):
                clean_id = f"{original_id}{counter}"  
                counter += 1

            pepID = clean_id

            sequence = row[1].strip()
            allele_list = []
            for a in row[2:]:
                a = a.strip()
                if not a:
                    continue
                if re.match(r"^[ABC]\d{2}:\d{2}", a):
                    a = a[0] + "*" + a[1:]

                allele_list.append(a)

            peptides.append((pepID, sequence, allele_list))

    if not peptides:
        print("[ERROR] No valid peptide rows found in input CSV.")
        sys.exit(1)

    return peptides

def write_alleles_file(pepID, allele_list):
    nmhc_dir = os.path.join("NMHC", pepID)
    os.makedirs(nmhc_dir, exist_ok=True)

    outfile = os.path.join(nmhc_dir, "alleles.txt")
    written = set()

    with open(outfile, "w") as out:
        for allele in allele_list:
            found = False
            query = f"HLA-{allele}"

            for stype, members in supertypes.items():
                if query in members:
                    found = True
                    for m in members:
                        formatted = m.replace("*", "")

                        if formatted not in written:
                            out.write(formatted + "\n")
                            written.add(formatted)

                    break

            if not found:
                print(f"[Warning] Allele {allele} not found in any supertype.")

def generate_netmhc_script(pepID, sequence):
    # Read configured netMHCpan path from constants (populated by setup.py)
    from protpardelle.misc import constants as prot_constants
    netmhc_path = prot_constants.netloc

    nmhc_dir = os.path.join("NMHC", pepID)
    script_path = os.path.join(nmhc_dir, f"run_{pepID}.sh")

    with open(script_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"touch NMHC/{pepID}/{sequence}.xls\n")
        f.write(
            f"cat NMHC/{pepID}/alleles.txt | while read line; do "
            f"{netmhc_path} -a $line -p NMHC/{pepID}/{sequence}.pep -l 9 -BA "
            f"-xlsfile NMHC/{pepID}/{sequence}.xls "
            f">> NMHC/{pepID}/{sequence}.xls; "
            f"done\n"
        )

        f.write(
            f"awk '/{sequence}/&&/*/&&/:/ {{print $2, $15, $16, $18}}' "
            f"NMHC/{pepID}/{sequence}.xls > NMHC/{pepID}/results_{sequence}.txt\n"
        )

        f.write(
            f"awk '/{sequence}/&&/*/&&/:/&&/SB|WB/ {{print $2, $15, $16, $18}}' "
            f"NMHC/{pepID}/{sequence}.xls > NMHC/{pepID}/results_{sequence}_SB_WB_only.txt\n"
        )

        f.write(
            f"python geninput.py NMHC/{pepID}/results_{sequence}_SB_WB_only.txt "
            f"NMDP.fasta {sequence} {pepID}\n"
        )

    os.chmod(script_path, 0o755)
    return script_path


def main():
    if len(sys.argv) != 2:
        print("Usage: python start.py input.csv")
        sys.exit(1)
    
    print("Resetting Inputs")
    moveAFFT()
    moveNMHC()
    
    input_csv = sys.argv[1]
    peptides = process_csv(input_csv)
    subprocess.run(["bash", "NMHC/archive.sh"], check=True)
    
    job_ids = []
    for pepID, sequence, allele_list in peptides:
        nmhc_dir = os.path.join("NMHC", pepID)
        os.makedirs(nmhc_dir, exist_ok=True)

        with open(os.path.join(nmhc_dir, f"{sequence}.pep"), "w") as f:
            f.write(sequence + "\n")
            
        write_alleles_file(pepID, allele_list)
        script = generate_netmhc_script(pepID, sequence)

        out = subprocess.check_output([
            "sbatch",
            f"--output=slurm_logs/run_{pepID}.out",
            f"--error=slurm_logs/run_{pepID}.err",
            script
        ]).decode().strip()

        job_id = out.split()[-1]
        job_ids.append(job_id)
    print(f"[+] Submitted {len(job_ids)} NetMHC jobs.")


    netmhc_dependency = ":".join(job_ids)

    cover_job_info = subprocess.check_output([
        "sbatch",
        f"--dependency=afterok:{netmhc_dependency}",
        "--output=slurm_logs/cover.out",
        "--error=slurm_logs/cover.err",
        "--wrap=python3 cover.py"
    ]).decode().strip()

    cover_job = cover_job_info.split()[-1]
    print(f"[+] Submitted coverage job with ID {cover_job}")

    fold_job_info = subprocess.check_output([
        "sbatch",
        f"--dependency=afterok:{cover_job}",
        "-p",
        "{{PARTITION_GPU}}",
        "--gres=gpu:1",
        "--output=slurm_logs/fold.out",
        "--error=slurm_logs/fold.err",
        "AFFT-HLA3DB/fold.sh"
    ]).decode().strip()

    fold_job = fold_job_info.split()[-1]
    print(f"[+] Submitted fold job with ID {fold_job}")

if __name__ == "__main__":
    main()

