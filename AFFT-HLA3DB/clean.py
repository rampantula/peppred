#!/usr/bin/env python3
import re
from pathlib import Path

# Allowed amino acids (20 standard + B/Z for ambiguous)
ALLOWED = set("ACDEFGHIKLMNPQRSTVWYBZ")

def has_issue(seq: str):
    seq = re.sub(r"\s+", "", seq).upper()
    return any(c not in ALLOWED for c in seq)

def main(folder="input_seq"):
    folder = Path(folder)
    if not folder.exists():
        print(f"[WARN] Directory not found: {folder}")
        return
    
    bad_files = []
    for txt_file in folder.glob("*.txt"):
        lines = [ln.strip() for ln in txt_file.read_text().splitlines() if ln.strip()]
        if any(has_issue(line) for line in lines):
            bad_files.append(txt_file.name)
    
    if bad_files:
        print("Files with sequence issues:")
        for fname in bad_files:
            print(fname)
    else:
        print("No issues found.")

if __name__ == "__main__":
    main()

