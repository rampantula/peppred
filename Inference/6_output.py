from pathlib import Path
from datetime import datetime
import shutil

from constants import mainpath

#script that organizes outputs

def safe_move(src: Path, dst: Path):
    if src.exists():
        target = dst / src.name
        if target.exists():
            target = dst / f"{src.name}_moved"
        shutil.move(str(src), str(target))
    else:
        print(f"WARNING: {src} not found")


def main():
    loc = Path(mainpath)
    timestamp = datetime.now().strftime("%m%d%y%H%M%S")

    nmhc_dir = loc / "NMHC"

    names = []
    if nmhc_dir.exists():
        for d in nmhc_dir.iterdir():
            if d.is_dir() and d.name != "incomplete":
                names.append(d.name)

    joined_name = "_".join(names) if names else "NMHC_results"

    result_dir = loc / "results" / f"{joined_name}_{timestamp}"
    result_dir.mkdir(parents=True, exist_ok=True)

    if nmhc_dir.exists():
        for d in nmhc_dir.iterdir():
        	safe_move(d, result_dir)
        
    print(f"Result directory:\n{result_dir}")

    safe_move(loc / "Inference" / "out", result_dir)
    safe_move(loc / "Inference" / "scorings", result_dir)

    afft_dir = loc / "AFFT-HLA3DB"

    safe_move(afft_dir / "outfiles", result_dir)
    safe_move(afft_dir / "input_seq", result_dir)

    # recreate input_seq
    (afft_dir / "input_seq").mkdir(parents=True, exist_ok=True)

    protpardelle_results = loc / "protpardelle" / "results"

    if nmhc_dir.exists():
        for d in nmhc_dir.iterdir():
            if d.is_dir() and d.name != "incomplete":
        	safe_move(d, result_dir)
    else:
        print("WARNING: protpardelle/results not found")
        
        
   # move all .txt and .csv from loc/results
    results_dir = loc / "results"

    for f in results_dir.glob("*.csv"):
        safe_move(f, result_dir)

    for f in results_dir.glob("*.txt"):
        safe_move(f, result_dir)

        print("\nDone.")

if __name__ == "__main__":
    main()
