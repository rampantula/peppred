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

import os
import numpy as np
import pandas as pd
import joblib

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

#runs the pca

INPUT_CSV = "out/trial_decoy_feature_table.csv"
OUTDIR = "out/trial_family_pca_out"
MODEL_PATH = os.path.join(OUTDIR, "trial_family_pca_models.pkl")
MAX_PCS = 5

os.makedirs(OUTDIR, exist_ok=True)


def sincos_embed(X_deg):
    X_rad = np.deg2rad(X_deg)
    return np.hstack([np.sin(X_rad), np.cos(X_rad)])


def main():
    df = pd.read_csv(INPUT_CSV)

    dih_cols = [c for c in df.columns if c.startswith("phi_") or c.startswith("psi_")]
    dih_cols = sorted(dih_cols, key=lambda x: (int(x.split("_")[1]), x.startswith("psi")))

    decoy_rows = []
    ensemble_rows = []
    family_rows = []
    family_models = {}

    for family, fam_df in df.groupby("family", dropna=True):
        if fam_df["ensemble"].nunique() < 2:
            continue

        X_deg = fam_df[dih_cols].values
        X = sincos_embed(X_deg)

        imp = SimpleImputer(strategy="median")
        X_imp = imp.fit_transform(X)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_imp)

        n_components = min(MAX_PCS, X_scaled.shape[1], X_scaled.shape[0] - 1)
        if n_components < 2:
            continue

        pca = PCA(n_components=n_components, whiten=True, random_state=42)
        Z = pca.fit_transform(X_scaled)

        fam_df = fam_df.copy().reset_index(drop=True)
        for i in range(n_components):
            fam_df[f"PC{i+1}"] = Z[:, i]

        decoy_rows.append(
            fam_df[["pdbid", "ensemble", "family"] + [f"PC{i+1}" for i in range(n_components)]].copy()
        )

        for ens, g in fam_df.groupby("ensemble"):
            Zg = g[[f"PC{i+1}" for i in range(n_components)]].values
            centroid = np.mean(Zg, axis=0)
            std = np.std(Zg, axis=0)
            minv = np.min(Zg, axis=0)
            maxv = np.max(Zg, axis=0)

            row = {
                "ensemble": ens,
                "family": family,
                "n_members": len(Zg),
                "spread_mean": float(np.mean(np.linalg.norm(Zg - centroid, axis=1))),
                "spread_trace": float(np.sum(np.var(Zg, axis=0))),
            }

            for i in range(n_components):
                row[f"pc{i+1}_centroid"] = centroid[i]
                row[f"pc{i+1}_std"] = std[i]
                row[f"pc{i+1}_min"] = minv[i]
                row[f"pc{i+1}_max"] = maxv[i]

            ensemble_rows.append(row)

        eig = pca.explained_variance_
        var_ratio = pca.explained_variance_ratio_

        fam_row = {
            "family": family,
            "n_decoys": len(fam_df),
            "n_ensembles": fam_df["ensemble"].nunique(),
        }
        for i in range(len(eig)):
            fam_row[f"eig_{i+1}"] = eig[i]
            fam_row[f"var_ratio_{i+1}"] = var_ratio[i]
        family_rows.append(fam_row)

        family_models[family] = {
            "imputer": imp,
            "scaler": scaler,
            "pca": pca,
            "columns": dih_cols,
        }

    pd.concat(decoy_rows, ignore_index=True).to_csv(f"{OUTDIR}/decoy_pca_scores.csv", index=False)
    pd.DataFrame(ensemble_rows).to_csv(f"{OUTDIR}/ensemble_pca_summary.csv", index=False)
    pd.DataFrame(family_rows).to_csv(f"{OUTDIR}/family_pca_summary.csv", index=False)
    joblib.dump(family_models, MODEL_PATH)

    print("DONE")
    print(f"Outputs saved in: {OUTDIR}")


if __name__ == "__main__":
    main()
