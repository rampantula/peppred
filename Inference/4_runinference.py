#!/usr/bin/env python3

import numpy as np
import pandas as pd
import joblib


TRIAL_PAIR_FEATURES = "out/trial_pair_features.csv"
MODEL_BUNDLE = "peppred.pkl"
OUTFILE = "out/trial_predictions.csv"


def main():
    bundle = joblib.load(MODEL_BUNDLE)
    df = pd.read_csv(TRIAL_PAIR_FEATURES)

    all_feature_cols = bundle["all_feature_cols"]
    selected_features = bundle["selected_features"]
    
    for c in all_feature_cols:
        if c not in df.columns:
            df[c] = np.nan

    X_all = df[all_feature_cols].copy()
    X_sel = df[selected_features].copy()

    # Elastic Net
    enet = bundle["elastic_net"]
    X_enet_imp = enet["imputer"].transform(X_all)
    X_enet_scaled = enet["scaler"].transform(X_enet_imp)
    p_enet = enet["model"].predict_proba(X_enet_scaled)[:, 1]

    # GBDT
    gbdt = bundle["gbdt"]
    X_gbdt_imp = gbdt["imputer"].transform(X_sel)
    p_gbdt = gbdt["model"].predict_proba(X_gbdt_imp)[:, 1]

    # GP
    gp = bundle["gaussian_process"]
    X_gp_imp = gp["imputer"].transform(X_sel)
    X_gp_scaled = gp["scaler"].transform(X_gp_imp)
    p_gp = gp["model"].predict_proba(X_gp_scaled)[:, 1]

    # Meta
    meta_X = np.column_stack([p_enet, p_gbdt, p_gp])
    p_meta = np.clip(bundle["meta_model"].predict(meta_X), 0.0, 1.0)

    thr_dissimilar = float(bundle["thr_dissimilar"])
    thr_similar = float(bundle["thr_similar"])
    thr_balanced = float(bundle["thr_balanced"])

    final_bucket = np.where(
        p_meta >= thr_similar, "Similar",
        np.where(p_meta <= thr_dissimilar, "Dissimilar", "Uncertain")
    )
    final_binary_conservative = (p_meta >= thr_similar).astype(int)
    final_binary_balanced = (p_meta >= thr_balanced).astype(int)

    out_cols = ["PDB1", "PDB2", "family"]
    out = df[[c for c in out_cols if c in df.columns]].copy()
    out["p_elastic_net"] = p_enet
    out["p_gbdt"] = p_gbdt
    out["p_gaussian_process"] = p_gp
    out["p_meta"] = p_meta
    out["final_bucket"] = final_bucket
    out["final_binary_conservative"] = final_binary_conservative
    out["final_binary_balanced"] = final_binary_balanced

    out.to_csv(OUTFILE, index=False)

    print("DONE")
    print(f"Wrote {OUTFILE}")


if __name__ == "__main__":
    main()
