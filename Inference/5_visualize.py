import re
from pathlib import Path

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from matplotlib.colors import LinearSegmentedColormap
from scipy.cluster.hierarchy import linkage, leaves_list, dendrogram
from scipy.spatial.distance import squareform

INPUT_CSV = Path("out/trial_predictions.csv")
OUTPUT_DIR = Path("out/heatmaps")

THR_DISSIMILAR = 0.23434466004165883
THR_BALANCED = 0.6039940514483328
THR_SIMILAR = 0.879809519504887

DEFAULT_MISSING_VALUE = 0.5
DIAGONAL_VALUE = 1.0

def parse_trial_and_allele(pdb_name):
    pdb_name = str(pdb_name)

    m = re.match(r"^([A-Za-z0-9]+?)([A-Z])(\d{2})(\d{2})$", pdb_name)
    if m:
        trial, locus, a1, a2 = m.groups()
        return trial, f"{locus}*{a1}:{a2}"

    m = re.match(r"^(.*?)([A-Z])(\d{2})(\d{2})$", pdb_name)
    if m:
        trial, locus, a1, a2 = m.groups()
        return trial, f"{locus}*{a1}:{a2}"

    return "UNKNOWN", pdb_name


def make_symmetric_matrix(alleles, edge_df, value_col="p_meta"):
    mat = pd.DataFrame(
        DEFAULT_MISSING_VALUE,
        index=alleles,
        columns=alleles,
        dtype=float,
    )

    np.fill_diagonal(mat.values, DIAGONAL_VALUE)

    grouped = (
        edge_df
        .groupby(["allele1", "allele2"], as_index=False)[value_col]
        .mean()
    )

    for _, row in grouped.iterrows():
        a = row["allele1"]
        b = row["allele2"]
        v = float(row[value_col])

        if a in mat.index and b in mat.columns:
            mat.loc[a, b] = v
            mat.loc[b, a] = v

    return mat


def cluster_matrix(matrix_df):
    sim = matrix_df.copy().astype(float)

    sim = (sim + sim.T) / 2.0
    np.fill_diagonal(sim.values, DIAGONAL_VALUE)

    dist = 1.0 - sim
    np.fill_diagonal(dist.values, 0.0)

    dist_values = np.clip(dist.values, 0.0, 1.0)
    condensed = squareform(dist_values, checks=False)

    Z = linkage(condensed, method="average")
    order_idx = leaves_list(Z)

    ordered_labels = [sim.index[i] for i in order_idx]
    ordered = sim.loc[ordered_labels, ordered_labels]

    return ordered, Z


def make_blue_cmap():
    return LinearSegmentedColormap.from_list(
        "thresholded_blue",
        [
            (0.00, "#ffffff"),
            (THR_DISSIMILAR, "#ffffff"),
            (THR_DISSIMILAR + 1e-6, "#f7fbff"),
            (THR_BALANCED, "#9ecae1"),
            (THR_SIMILAR - 1e-6, "#2171b5"),
            (THR_SIMILAR, "#08306b"),
            (1.00, "#08306b"),
        ],
        N=256,
    )


def draw_clustered_heatmap(matrix_df, linkage_Z, outpath, title):
    sns.set_theme(style="white", context="paper")

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })

    cmap = make_blue_cmap()

    n = len(matrix_df)
    fig_w = max(7.0, 0.22 * n + 2.0)
    fig_h = max(6.5, 0.22 * n + 1.5)

    fig = plt.figure(figsize=(fig_w, fig_h))

    grid = fig.add_gridspec(
        nrows=2,
        ncols=3,
        width_ratios=[0.9, 6.0, 0.25],
        height_ratios=[0.05, 6.0],
        wspace=0.02,
        hspace=0.02,
    )

    ax_blank = fig.add_subplot(grid[0, 0])
    ax_blank.axis("off")

    ax_heat = fig.add_subplot(grid[1, 1])
    ax_tree = fig.add_subplot(grid[1, 0])
    ax_cbar = fig.add_subplot(grid[1, 2])

    dendrogram(
        linkage_Z,
        orientation="left",
        no_labels=True,
        color_threshold=0,
        above_threshold_color="#bdbdbd",
        ax=ax_tree,
    )

    ax_tree.invert_yaxis()
    ax_tree.axis("off")

    sns.heatmap(
        matrix_df,
        ax=ax_heat,
        cmap=cmap,
        vmin=0.0,
        vmax=1.0,
        square=True,
        linewidths=0.12,
        linecolor=(1, 1, 1, 0.25),
        cbar=True,
        cbar_ax=ax_cbar,
    )

    ax_heat.set_title(title, fontsize=12, pad=10)
    ax_heat.set_xlabel("")
    ax_heat.set_ylabel("")
    ax_heat.tick_params(axis="x", labelrotation=90, labelsize=5, length=0, pad=1)
    ax_heat.tick_params(axis="y", labelrotation=0, labelsize=5, length=0, pad=1)

    for spine in ax_heat.spines.values():
        spine.set_visible(False)

    ax_cbar.set_ylabel("similarity confidence", rotation=90, labelpad=8, fontsize=8)
    ax_cbar.tick_params(labelsize=7, length=2)
    ax_cbar.set_yticks([THR_DISSIMILAR, THR_BALANCED, THR_SIMILAR])
    ax_cbar.set_yticklabels([
        f"{THR_DISSIMILAR:.2f}",
        f"{THR_BALANCED:.2f}",
        f"{THR_SIMILAR:.2f}",
    ])

    fig.patch.set_facecolor("white")
    fig.savefig(outpath, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)

    needed = {"PDB1", "PDB2", "p_meta"}
    missing = needed.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    parsed1 = df["PDB1"].map(parse_trial_and_allele)
    parsed2 = df["PDB2"].map(parse_trial_and_allele)

    df[["trial1", "allele1"]] = pd.DataFrame(parsed1.tolist(), index=df.index)
    df[["trial2", "allele2"]] = pd.DataFrame(parsed2.tolist(), index=df.index)

    same_trial = df["trial1"] == df["trial2"]
    if not same_trial.all():
        print(f"Dropping {(~same_trial).sum()} cross-trial rows.")

    df = df.loc[same_trial].copy()

    df["p_meta"] = pd.to_numeric(df["p_meta"], errors="coerce")
    df = df.dropna(subset=["p_meta"])

    order_rows = []

    for trial in sorted(df["trial1"].unique()):
        sub = df.loc[df["trial1"] == trial].copy()

        alleles = sorted(set(sub["allele1"]).union(set(sub["allele2"])))

        if len(alleles) < 2:
            print(f"Skipping {trial}: not enough alleles.")
            continue

        pmat = make_symmetric_matrix(
            alleles=alleles,
            edge_df=sub,
            value_col="p_meta",
        )

        ordered_pmat, Z = cluster_matrix(pmat)

        trial_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", trial)
        outpath = OUTPUT_DIR / f"{trial_slug}_heatmap.png"

        draw_clustered_heatmap(
            matrix_df=ordered_pmat,
            linkage_Z=Z,
            outpath=outpath,
            title=f"{trial} Allele Similarity Heatmap",
        )

        for rank, allele in enumerate(ordered_pmat.index, start=1):
            order_rows.append({
                "trial": trial,
                "cluster_rank": rank,
                "allele": allele,
            })

        print(f"Saved heatmap for {trial}: {outpath}")

    if order_rows:
        pd.DataFrame(order_rows).to_csv(
            OUTPUT_DIR / "clustered_allele_order.csv",
            index=False,
        )

    print(f"\nDone. Output folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
