import os
import numpy as np
import pandas as pd


ENSEMBLE_PCA_SUMMARY = "out/trial_family_pca_out/ensemble_pca_summary.csv"
FAMILY_PCA_SUMMARY = "out/trial_family_pca_out/family_pca_summary.csv"
ENSEMBLE_SUMMARY = "out/trial_ensemble_feature_summary.csv"

TRIAL_PAIRS_CSV = "out/pairs.csv"
OUTFILE = "out/trial_pair_features.csv"

MAX_PC_FEATURES = 5


def circular_diff_deg(a_deg, b_deg):
    return (a_deg - b_deg + 180.0) % 360.0 - 180.0


def build_lookup(df, key_col):
    return {str(r[key_col]): r for _, r in df.iterrows()}


def safe_absdiff(a, b):
    if pd.isna(a) or pd.isna(b):
        return np.nan
    return abs(a - b)


def safe_mean2(a, b):
    if pd.isna(a) and pd.isna(b):
        return np.nan
    return np.nanmean([a, b])


def main():
    pairs = pd.read_csv(TRIAL_PAIRS_CSV)[["PDB1", "PDB2"]].copy()
    pairs["PDB1"] = pairs["PDB1"].astype(str).str.strip()
    pairs["PDB2"] = pairs["PDB2"].astype(str).str.strip()

    ens_pca = pd.read_csv(ENSEMBLE_PCA_SUMMARY)
    fam_pca = pd.read_csv(FAMILY_PCA_SUMMARY)
    ens_sum = pd.read_csv(ENSEMBLE_SUMMARY)

    ens_pca["ensemble"] = ens_pca["ensemble"].astype(str).str.strip()
    ens_sum["ensemble"] = ens_sum["ensemble"].astype(str).str.strip()
    fam_pca["family"] = fam_pca["family"].astype(str).str.strip()

    pca_lookup = build_lookup(ens_pca, "ensemble")
    sum_lookup = build_lookup(ens_sum, "ensemble")
    fam_lookup = build_lookup(fam_pca, "family")

    pc_idx = []
    for i in range(1, MAX_PC_FEATURES + 1):
        needed = [f"pc{i}_centroid", f"pc{i}_std", f"pc{i}_min", f"pc{i}_max"]
        if all(c in ens_pca.columns for c in needed):
            pc_idx.append(i)

    exclude_cols = {"ensemble", "family", "n_decoys", "npz_path", "npz_key_used"}
    circmean_cols = [c for c in ens_sum.columns if c.endswith("_circmean_deg")]
    anchor_scalar_cols = []
    for c in ens_sum.columns:
        if c in exclude_cols or c in circmean_cols:
            continue
        if pd.api.types.is_numeric_dtype(ens_sum[c]):
            anchor_scalar_cols.append(c)
    anchor_scalar_cols = [c for c in anchor_scalar_cols if c not in {"n_decoys"}]

    rows = []

    for _, r in pairs.iterrows():
        A = str(r["PDB1"]).strip()
        B = str(r["PDB2"]).strip()

        if A not in pca_lookup or B not in pca_lookup:
            continue
        if A not in sum_lookup or B not in sum_lookup:
            continue

        pA = pca_lookup[A]
        pB = pca_lookup[B]
        sA = sum_lookup[A]
        sB = sum_lookup[B]

        famA = str(pA["family"]).strip()
        famB = str(pB["family"]).strip()
        if famA != famB:
            continue

        family = famA
        fam_row = fam_lookup.get(family, None)

        feat = {
            "PDB1": A,
            "PDB2": B,
            "family": family,
        }

        deltas = []
        abs_deltas = []

        for i in pc_idx:
            d = float(pA[f"pc{i}_centroid"] - pB[f"pc{i}_centroid"])
            ad = abs(d)

            deltas.append(d)
            abs_deltas.append(ad)

            feat[f"pc{i}_delta_signed"] = d
            feat[f"pc{i}_delta_abs"] = ad

            stdA = float(pA[f"pc{i}_std"])
            stdB = float(pB[f"pc{i}_std"])
            feat[f"pc{i}_std_A"] = stdA
            feat[f"pc{i}_std_B"] = stdB
            feat[f"pc{i}_std_absdiff"] = abs(stdA - stdB)
            feat[f"pc{i}_std_mean"] = 0.5 * (stdA + stdB)

            minA, maxA = float(pA[f"pc{i}_min"]), float(pA[f"pc{i}_max"])
            minB, maxB = float(pB[f"pc{i}_min"]), float(pB[f"pc{i}_max"])

            overlap_low = max(minA, minB)
            overlap_high = min(maxA, maxB)
            overlap = max(0.0, overlap_high - overlap_low)

            widthA = max(1e-8, maxA - minA)
            widthB = max(1e-8, maxB - minB)

            feat[f"pc{i}_range_overlap"] = overlap
            feat[f"pc{i}_overlap_frac_A"] = overlap / widthA
            feat[f"pc{i}_overlap_frac_B"] = overlap / widthB

        deltas = np.asarray(deltas, dtype=float)
        abs_deltas = np.asarray(abs_deltas, dtype=float)

        feat["pc_dist"] = float(np.linalg.norm(deltas))
        feat["pc_manhattan"] = float(np.sum(abs_deltas))
        feat["pc_max_abs_delta"] = float(np.max(abs_deltas))
        feat["pc_mean_abs_delta"] = float(np.mean(abs_deltas))

        feat["n_members_A"] = float(pA["n_members"])
        feat["n_members_B"] = float(pB["n_members"])
        feat["n_members_min"] = float(min(pA["n_members"], pB["n_members"]))
        feat["n_members_mean"] = 0.5 * float(pA["n_members"] + pB["n_members"])

        feat["spread_mean_A"] = float(pA["spread_mean"])
        feat["spread_mean_B"] = float(pB["spread_mean"])
        feat["spread_mean_absdiff"] = abs(float(pA["spread_mean"]) - float(pB["spread_mean"]))
        feat["spread_mean_mean"] = 0.5 * float(pA["spread_mean"] + pB["spread_mean"])

        feat["spread_trace_A"] = float(pA["spread_trace"])
        feat["spread_trace_B"] = float(pB["spread_trace"])
        feat["spread_trace_absdiff"] = abs(float(pA["spread_trace"]) - float(pB["spread_trace"]))
        feat["spread_trace_mean"] = 0.5 * float(pA["spread_trace"] + pB["spread_trace"])

        if fam_row is not None:
            for i in range(1, MAX_PC_FEATURES + 1):
                eig_col = f"eig_{i}"
                vr_col = f"var_ratio_{i}"
                if eig_col in fam_row.index:
                    feat[f"family_{eig_col}"] = float(fam_row[eig_col])
                if vr_col in fam_row.index:
                    feat[f"family_{vr_col}"] = float(fam_row[vr_col])

            if "n_decoys" in fam_row.index:
                feat["family_n_decoys"] = float(fam_row["n_decoys"])
            if "n_ensembles" in fam_row.index:
                feat["family_n_ensembles"] = float(fam_row["n_ensembles"])

        for c in anchor_scalar_cols:
            a = pd.to_numeric(sA[c], errors="coerce")
            b = pd.to_numeric(sB[c], errors="coerce")

            feat[f"{c}_A"] = a
            feat[f"{c}_B"] = b
            feat[f"{c}_absdiff"] = safe_absdiff(a, b)
            feat[f"{c}_mean"] = safe_mean2(a, b)

        for c in circmean_cols:
            a = pd.to_numeric(sA[c], errors="coerce")
            b = pd.to_numeric(sB[c], errors="coerce")

            base = c.replace("_circmean_deg", "")
            if pd.isna(a) or pd.isna(b):
                feat[f"{base}_circ_delta_signed"] = np.nan
                feat[f"{base}_circ_delta_abs"] = np.nan
            else:
                d = circular_diff_deg(a, b)
                feat[f"{base}_circ_delta_signed"] = d
                feat[f"{base}_circ_delta_abs"] = abs(d)

        rows.append(feat)

    out = pd.DataFrame(rows)
    out.to_csv(OUTFILE, index=False)

    print("DONE")
    print(f"Saved: {OUTFILE}")
    print(f"Pairs: {len(out)}")


if __name__ == "__main__":
    main()
