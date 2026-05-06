#!/usr/bin/env python3

import os
import re
import csv
import math
from pathlib import Path

from Bio.PDB import PDBParser, is_aa
from Bio.SeqUtils import seq1
from Bio import SeqIO


# =========================
# HARD-CODED PATHS / SETTINGS
# =========================
PDB_DIR = "structures"
FASTA_FILE = "NMDP.fasta"
OUT_DIR = "out"

CHAIN_A = "A"
CHAIN_B = "B"

# Exactly 5 array chunks
N_CHUNKS = 5

FINAL_CSV = os.path.join(OUT_DIR, "MHCs.csv")
PARTIAL_DIR = os.path.join(OUT_DIR, "partials")

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(PARTIAL_DIR, exist_ok=True)


def clean_pdb_name(filename):
    """
    Example:
      sample_1JGE_00__reordered.pdb -> sample_1JGE_00
      sample_1K5N_05_reordered.pdb  -> sample_1K5N_05
    """
    stem = Path(filename).stem
    stem = re.sub(r"_+reordered$", "", stem)
    return stem


def extract_allele_from_header(header):
    """
    Tries to pull something like B*27:05 from the FASTA header.
    Falls back to the first whitespace-delimited token.
    """
    m = re.search(r'([A-Z]\*\d{2}:\d{2,3})', header)
    if m:
        return m.group(1)

    m = re.search(r'(HLA-[A-Z]\*\d{2}:\d{2,3})', header)
    if m:
        return m.group(1).replace("HLA-", "")

    return header.split()[0]


def load_fasta_records(fasta_file):
    """
    Load FASTA as:
      [
        {"header": "...", "allele": "...", "seq": "..."},
        ...
      ]
    """
    records = []
    for rec in SeqIO.parse(fasta_file, "fasta"):
        header = rec.description.strip()
        seq = str(rec.seq).strip().upper()
        allele = extract_allele_from_header(header)

        records.append({
            "header": header,
            "allele": allele,
            "seq": seq
        })
    return records


def extract_chain_sequence(structure, chain_id):
    """
    Extract amino-acid sequence from a chain in a PDB structure.
    Only standard amino acids are kept.
    """
    model = next(structure.get_models())

    if chain_id not in model:
        raise ValueError(f"Chain {chain_id} not found")

    chain = model[chain_id]
    seq = []

    for residue in chain:
        if not is_aa(residue, standard=True):
            continue

        resname = residue.get_resname().strip()
        try:
            aa = seq1(resname)
        except Exception:
            aa = "X"
        seq.append(aa)

    return "".join(seq)


def build_exact_index(fasta_records):
    exact = {}
    for rec in fasta_records:
        exact[rec["seq"]] = rec["allele"]
    return exact


def match_chain_a_to_fasta(chain_a_seq, fasta_records, exact_index):
    """
    Matching priority:
      1. exact match
      2. chain A sequence is substring of FASTA record
      3. FASTA record is substring of chain A sequence
      4. NO_MATCH
    """
    chain_a_seq = chain_a_seq.upper()

    if chain_a_seq in exact_index:
        return exact_index[chain_a_seq]

    for rec in fasta_records:
        if chain_a_seq in rec["seq"]:
            return rec["allele"]

    for rec in fasta_records:
        if rec["seq"] in chain_a_seq:
            return rec["allele"]

    return "NO_MATCH"


def get_all_pdb_files(pdb_dir):
    return sorted([p for p in Path(pdb_dir).iterdir() if p.suffix.lower() == ".pdb"])


def get_chunk_bounds(n_files, n_chunks, task_id):
    """
    Split n_files into n_chunks as evenly as possible.
    """
    chunk_size = math.ceil(n_files / n_chunks)
    start = task_id * chunk_size
    end = min(start + chunk_size, n_files)
    return start, end


def process_files(pdb_files, fasta_records, exact_index, output_csv):
    parser = PDBParser(QUIET=True)
    rows = []

    for pdb_file in pdb_files:
        pdb_name = clean_pdb_name(pdb_file.name)

        try:
            structure = parser.get_structure(pdb_name, str(pdb_file))

            a_seq = extract_chain_sequence(structure, CHAIN_A)
            b_seq = extract_chain_sequence(structure, CHAIN_B)

            allele = match_chain_a_to_fasta(a_seq, fasta_records, exact_index)

            rows.append({
                "PDB": pdb_name,
                "Allele": allele,
                "Peptide_length": len(b_seq),
                "Peptide Sequence": b_seq
            })

        except Exception as e:
            print(f"Skipping {pdb_file.name}: {e}")

    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["PDB", "Allele", "Peptide_length", "Peptide Sequence"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_csv}")


def merge_partials(partial_dir, final_csv):
    partial_files = sorted(Path(partial_dir).glob("part_*.csv"))

    if not partial_files:
        raise RuntimeError(f"No partial CSV files found in {partial_dir}")

    all_rows = []
    seen = set()

    for pf in partial_files:
        with open(pf, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row["PDB"]
                if key in seen:
                    continue
                seen.add(key)
                all_rows.append(row)

    all_rows.sort(key=lambda r: r["PDB"])

    with open(final_csv, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["PDB", "Allele", "Peptide_length", "Peptide Sequence"]
        )
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Merged {len(partial_files)} partial files into {final_csv}")
    print(f"Total unique rows: {len(all_rows)}")


def main():
    fasta_records = load_fasta_records(FASTA_FILE)
    exact_index = build_exact_index(fasta_records)
    pdb_files = get_all_pdb_files(PDB_DIR)

    if not pdb_files:
        raise RuntimeError(f"No PDB files found in {PDB_DIR}")

    merge_flag = os.environ.get("MERGE_PARTIALS", "0")
    if merge_flag == "1":
        merge_partials(PARTIAL_DIR, FINAL_CSV)
        return

    slurm_task_id = os.environ.get("SLURM_ARRAY_TASK_ID")

    if slurm_task_id is not None:
        task_id = int(slurm_task_id)
        start, end = get_chunk_bounds(len(pdb_files), N_CHUNKS, task_id)

        if start >= len(pdb_files):
            print(f"Task {task_id}: no files to process")
            return

        chunk_files = pdb_files[start:end]
        output_csv = os.path.join(PARTIAL_DIR, f"part_{task_id:04d}.csv")

        print(f"Task {task_id}: processing files {start} to {end - 1}")
        process_files(chunk_files, fasta_records, exact_index, output_csv)
    else:
        process_files(pdb_files, fasta_records, exact_index, FINAL_CSV)


if __name__ == "__main__":
    main()