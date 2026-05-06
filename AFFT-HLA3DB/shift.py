#       Sgourakis Lab
#   Author: Ram Pantula
#   Date: July 1, 2025
#   Email: rpantula@sas.upenn.edu
import os
import sys
import shutil

def main():
    if len(sys.argv) < 2:
        print("Usage: python shift.py <root_directory>")
        sys.exit(1)

    root = os.path.abspath(sys.argv[1])

    input_seq_dir = os.path.join(root, "AFFT-HLA3DB", "input_seq")
    outfiles_dir = os.path.join(root, "AFFT-HLA3DB", "outfiles")
    afft_dir = os.path.join(root, "AFFT-HLA3DB")

    # Ensure outfiles directory exists
    os.makedirs(outfiles_dir, exist_ok=True)

    # Check all *_seq.txt files in input_seq
    for fname in os.listdir(input_seq_dir):
        if not fname.endswith("_seq.txt"):
            continue

        # Extract the target folder name
        targetfolder = fname.replace("_seq.txt", "")
        src = os.path.join(afft_dir, targetfolder)
        dst = os.path.join(outfiles_dir, targetfolder)

        if os.path.isdir(src):
            print(f"[INFO] Moving folder {src} → {dst}")
            # Move folder (replace if exists)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.move(src, dst)
        else:
            print(f"[WARN] Folder {src} not found, skipping.")

if __name__ == "__main__":
    main()

