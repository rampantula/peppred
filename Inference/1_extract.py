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
import re
import numpy as np
import pandas as pd

#this script basically organizes outputs from afft + protpardelle to run pca

DIHEDRAL_CSV = "out/peptide_dihedrals.csv"
MHC_CSV = "out/MHCs.csv"
SCORING_DIR = "scorings"

OUT_DECOY = "out/trial_decoy_feature_table.csv"
OUT_ENSEMBLE = "out/trial_ensemble_feature_summary.csv"

HLA_SLICE = slice(0, 180)
PEP_SLICE = slice(180, 189)


def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = (
        out.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )
    return out


def parse_sample_name(sample_name: str):
    s = str(sample_name).strip()
    m = re.match(r"^sample_(.+)_(\d+)$", s)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def load_family_map():
    mhc = pd.read_csv(MHC_CSV)
    mhc = normalize_cols(mhc)

    if "pdb" not in mhc.columns or "peptide_sequence" not in mhc.columns:
        raise ValueError("MHC CSV must contain columns 'PDB' and 'Peptide Sequence'")

    mhc["pdb"] = mhc["pdb"].astype(str).str.strip()
    mhc["peptide_sequence"] = mhc["peptide_sequence"].astype(str).str.strip()
    mhc["ensemble"] = mhc["pdb"].str.extract(r"^sample_(.+)_(\d+)$")[0]
    mhc["ensemble"] = mhc["ensemble"].astype(str).str.strip()

    return mhc.groupby("ensemble")["peptide_sequence"].first().to_dict()


def load_plddt_vector(npz_path: str):
    if not os.path.exists(npz_path):
        return None, None

    try:
        with np.load(npz_path, allow_pickle=True) as z:
            for k in z.files:
                if "plddt" in k.lower():
                    arr = np.asarray(z[k], dtype=float)
                    if arr.ndim == 1 and arr.size >= HLA_SLICE.stop:
                        return arr, k

            for k in z.files:
                arr = np.asarray(z[k])
                if arr.ndim == 1 and arr.size >= HLA_SLICE.stop and np.issubdtype(arr.dtype, np.number):
                    return arr.astype(float), k
    except Exception:
        return None, None

    return None, None


def summarize_npz(arr: np.ndarray):
    arr = np.asarray(arr, dtype=float)
    hla = arr[HLA_SLICE]
    pep = arr[PEP_SLICE] if arr.size >= PEP_SLICE.stop else np.array([], dtype=float)

    out = {
        "npz_len": int(arr.size),
        "plddt_full_mean": float(np.mean(arr)),
        "plddt_full_std": float(np.std(arr)),
        "plddt_full_min": float(np.min(arr)),
        "plddt_full_max": float(np.max(arr)),
        "plddt_hla_mean": float(np.mean(hla)),
        "plddt_hla_std": float(np.std(hla)),
        "plddt_hla_min": float(np.min(hla)),
        "plddt_hla_max": float(np.max(hla)),
    }

    if pep.size > 0:
        out.update({
            "plddt_pep_mean": float(np.mean(pep)),
            "plddt_pep_std": float(np.std(pep)),
            "plddt_pep_min": float(np.min(pep)),
            "plddt_pep_max": float(np.max(pep)),
            "plddt_hla_minus_pep_mean": float(np.mean(hla) - np.mean(pep)),
        })
    else:
        out.update({
            "plddt_pep_mean": np.nan,
            "plddt_pep_std": np.nan,
            "plddt_pep_min": np.nan,
            "plddt_pep_max": np.nan,
            "plddt_hla_minus_pep_mean": np.nan,
        })

    return out


def circ_mean_deg(x_deg):
    x_rad = np.deg2rad(np.asarray(x_deg, dtype=float))
    s = np.mean(np.sin(x_rad))
    c = np.mean(np.cos(x_rad))
    return float(np.rad2deg(np.arctan2(s, c)))


def circ_var(x_deg):
    x_rad = np.deg2rad(np.asarray(x_deg, dtype=float))
    s = np.mean(np.sin(x_rad))
    c = np.mean(np.cos(x_rad))
    R = np.sqrt(s * s + c * c)
    return float(1.0 - R)


def circ_std(x_deg):
    x_rad = np.deg2rad(np.asarray(x_deg, dtype=float))
    s = np.mean(np.sin(x_rad))
    c = np.mean(np.cos(x_rad))
    R = np.sqrt(s * s + c * c)
    R = max(R, 1e-12)
    return float(np.sqrt(-2.0 * np.log(R)))


def find_dihedral_columns(df: pd.DataFrame):
    cols = [c for c in df.columns if re.fullmatch(r"(phi|psi)_\d+", str(c))]
    def key(c):
        kind, idx = c.split("_")
        return (int(idx), 0 if kind == "phi" else 1)
    return sorted(cols, key=key)


def main():
    df = pd.read_csv(DIHEDRAL_CSV)
    df = normalize_cols(df)

    dihedral_cols = find_dihedral_columns(df)

    parsed = df["pdbid"].astype(str).str.strip().apply(parse_sample_name)
    df["ensemble"] = [x[0] for x in parsed]
    df["decoy_num"] = [x[1] for x in parsed]

    df = df.dropna(subset=["ensemble", "decoy_num"]).copy()
    df["ensemble"] = df["ensemble"].astype(str).str.strip()
    df["decoy_num"] = df["decoy_num"].astype(int)

    for c in dihedral_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=dihedral_cols).reset_index(drop=True)

    ens_to_pep = load_family_map()
    df["family"] = df["ensemble"].map(ens_to_pep)

    decoy_blocks = []
    ensemble_rows = []

    for ensemble, g in df.groupby("ensemble", sort=True):
        family = g["family"].iloc[0]
        npz_path = os.path.join(SCORING_DIR, f"{ensemble}.npz")
        arr, npz_key = load_plddt_vector(npz_path)
        if arr is None:
            continue

        npz_feats = summarize_npz(arr)

        block = g[["pdbid", "ensemble", "decoy_num"] + dihedral_cols].copy()
        block["family"] = family
        for k, v in npz_feats.items():
            block[k] = v
        block["npz_path"] = npz_path
        block["npz_key_used"] = npz_key
        decoy_blocks.append(block)

        row = {
            "ensemble": ensemble,
            "family": family,
            "n_decoys": len(g),
            "npz_path": npz_path,
            "npz_key_used": npz_key,
        }
        for c in dihedral_cols:
            vals = g[c].to_numpy(dtype=float)
            row[f"{c}_mean"] = float(np.mean(vals))
            row[f"{c}_std"] = float(np.std(vals))
            row[f"{c}_min"] = float(np.min(vals))
            row[f"{c}_max"] = float(np.max(vals))
            row[f"{c}_circmean_deg"] = circ_mean_deg(vals)
            row[f"{c}_circvar"] = circ_var(vals)
            row[f"{c}_circstd"] = circ_std(vals)

        row.update(npz_feats)
        ensemble_rows.append(row)

    decoy_df = pd.concat(decoy_blocks, ignore_index=True)
    ensemble_df = pd.DataFrame(ensemble_rows)

    decoy_df.to_csv(OUT_DECOY, index=False)
    ensemble_df.to_csv(OUT_ENSEMBLE, index=False)

    print("DONE")
    print(f"Wrote {OUT_DECOY}")
    print(f"Wrote {OUT_ENSEMBLE}")


if __name__ == "__main__":
    main()
