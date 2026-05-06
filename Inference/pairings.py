import itertools
import pandas as pd

INPUT_CSV = "out/trial_ensemble_feature_summary.csv"
OUTPUT_CSV = "out/pairs.csv"


def main():
    df = pd.read_csv(INPUT_CSV)

    required = {"ensemble", "family"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["ensemble"] = df["ensemble"].astype(str).str.strip()
    df["family"] = df["family"].astype(str).str.strip()

    df = df.dropna(subset=["ensemble", "family"]).copy()
    df = df[(df["ensemble"] != "") & (df["family"] != "")].copy()

    df = df.drop_duplicates(subset=["ensemble"])

    pair_rows = []

    # all-by-all pairing within each family only
    for family, subdf in df.groupby("family"):
        ensembles = sorted(subdf["ensemble"].tolist())

        for pdb1, pdb2 in itertools.combinations(ensembles, 2):
            pair_rows.append({
                "PDB1": pdb1,
                "PDB2": pdb2,
            })

    out = pd.DataFrame(pair_rows, columns=["PDB1", "PDB2"])
    out.to_csv(OUTPUT_CSV, index=False)

    print("DONE")
    print(f"Saved: {OUTPUT_CSV}")
    print(f"Total pairs: {len(out)}")

    fam_counts = (
        df.groupby("family")["ensemble"]
        .nunique()
        .reset_index(name="n_ensembles")
    )
    fam_counts["expected_pairs"] = fam_counts["n_ensembles"].apply(
        lambda n: n * (n - 1) // 2
    )

    print("\nPer-family pairing summary:")
    print(fam_counts.to_string(index=False))


if __name__ == "__main__":
    main()
