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
from __future__ import annotations

import argparse
import itertools
import socket
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

import predict_utils


DEFAULT_MODEL_NAMES = ["model_2_ptm"]
ALIGNMENT_COLUMNS = {
    "template_pdbfile",
    "target_to_template_alignstring",
    "identities",
    "target_len",
    "template_len",
}


def build_argument_parser() -> argparse.ArgumentParser:
    """Construct the command-line parser without executing the program."""
    parser = argparse.ArgumentParser(
        description="Run template-based AlphaFold inference.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python3 run_prediction_refactored.py \\
      --targets targets.tsv \\
      --data_dir /path/to/alphafold/data \\
      --outfile_prefix prediction \\
      --model_names model_2_ptm \\
      --ignore_identities
""",
    )

    parser.add_argument(
        "--outfile_prefix",
        help="Prefix prepended to generated prediction files.",
    )
    parser.add_argument(
        "--final_outfile_prefix",
        help="Prefix prepended to the final summary TSV filename.",
    )
    parser.add_argument(
        "--targets",
        required=True,
        help="Tab-separated file listing the targets to model.",
    )
    parser.add_argument(
        "--data_dir",
        help="Directory containing AlphaFold's params/ directory.",
    )
    parser.add_argument(
        "--model_names",
        type=str,
        nargs="*",
        default=DEFAULT_MODEL_NAMES,
    )
    parser.add_argument(
        "--model_params_files",
        type=str,
        nargs="*",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--ignore_identities",
        action="store_true",
        help=(
            "Do not validate the identities column in template alignment files. "
            "This is useful when an alignment file is reused for different peptides."
        ),
    )
    parser.add_argument(
        "--no_pdbs",
        action="store_true",
        help="Do not write predicted PDB files.",
    )
    parser.add_argument(
        "--terse",
        action="store_true",
        help="Do not write predicted PDBs or confidence-matrix .npy files.",
    )
    parser.add_argument(
        "--no_resample_msa",
        action="store_true",
        help="Disable random MSA resampling during recycling.",
    )
    return parser


def read_targets(targets_file: str | Path) -> pd.DataFrame:
    """Read and minimally validate the target table."""
    targets = pd.read_table(targets_file)
    if "target_chainseq" not in targets.columns:
        raise ValueError("Targets TSV is missing required column 'target_chainseq'.")
    if targets.empty:
        raise ValueError("Targets TSV contains no target rows.")
    return targets


def sequence_without_chain_separators(chain_sequence: str) -> str:
    return chain_sequence.replace("/", "")


def determine_crop_size(targets: pd.DataFrame) -> int:
    """Use the longest concatenated target sequence as AlphaFold's crop size."""
    return max(
        len(sequence_without_chain_separators(chainseq))
        for chainseq in targets["target_chainseq"]
    )


def print_runtime_details(targets: pd.DataFrame, crop_size: int) -> None:
    """Print the same class of verbose runtime information as the old driver."""
    import jax

    devices = jax.local_devices()
    platform = devices[0].platform if devices else "unavailable"
    print("cmd:", " ".join(sys.argv))
    print(
        "local_device:",
        platform,
        "hostname:",
        socket.gethostname(),
        "num_targets:",
        targets.shape[0],
        "max_len=",
        crop_size,
    )


def parse_alignment_string(value: str) -> dict[int, int]:
    """Convert 'target:template;...' into a zero-indexed mapping dictionary."""
    mapping: dict[int, int] = {}
    for pair in value.split(";"):
        target_position, template_position = pair.split(":", maxsplit=1)
        mapping[int(target_position)] = int(template_position)
    return mapping


def validate_alignment_table(table: pd.DataFrame, alignment_file: Path) -> None:
    missing = ALIGNMENT_COLUMNS.difference(table.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(
            f"Alignment file {alignment_file} is missing required columns: "
            f"{missing_text}"
        )


def build_template_feature_batch(
    *,
    query_sequence: str,
    alignment_file: str | Path,
    ignore_identities: bool,
) -> dict[str, np.ndarray]:
    """Load all templates for one target and combine their AlphaFold features."""
    alignment_path = Path(alignment_file)
    print("ALIGNFILE name:", alignment_path)
    if not alignment_path.exists():
        raise FileNotFoundError(f"Template alignment file not found: {alignment_path}")

    alignments = pd.read_table(alignment_path)
    validate_alignment_table(alignments, alignment_path)

    feature_sets = []
    for template_number, row in alignments.iterrows():
        if row.target_len != len(query_sequence):
            raise ValueError(
                f"Target length mismatch in {alignment_path}: TSV reports "
                f"{row.target_len}, but sequence length is {len(query_sequence)}."
            )

        alignment = parse_alignment_string(
            row.target_to_template_alignstring
        )
        expected_identities = None if ignore_identities else row.identities

        features = predict_utils.create_single_template_features(
            query_sequence,
            row.template_pdbfile,
            alignment,
            f"T{template_number:03d}",
            allow_chainbreaks=True,
            allow_skipped_lines=True,
            expected_identities=expected_identities,
            expected_template_len=row.template_len,
        )
        feature_sets.append(features)

    return predict_utils.compile_template_features(feature_sets)


def resolve_target_output_prefix(
    target_row: pd.Series,
    row_number: Any,
    command_prefix: str | None,
) -> Any:
    """Preserve the original output-prefix precedence for each target row."""
    if "outfile_prefix" in target_row.index:
        return target_row["outfile_prefix"]

    if command_prefix is None:
        raise ValueError(
            "--outfile_prefix is required when the targets TSV has no "
            "'outfile_prefix' column."
        )

    if "targetid" in target_row.index:
        return f"{command_prefix}_{target_row['targetid']}"
    return f"{command_prefix}_T{row_number}"


def chain_ranges(chain_sequence: str) -> list[tuple[int, int]]:
    """Return half-open residue ranges for slash-delimited target chains."""
    lengths = [len(chain) for chain in chain_sequence.split("/")]
    stops = list(itertools.accumulate(lengths))
    starts = [0, *stops[:-1]]
    return list(zip(starts, stops))


def add_confidence_summaries(
    output_row: pd.Series,
    *,
    model_name: str,
    metrics: Mapping[str, Any],
    query_chainseq: str,
    query_length: int,
) -> None:
    """Add overall, per-chain, and inter-chain confidence summaries in place."""
    plddt = metrics["plddt"]
    pae = metrics.get("predicted_aligned_error")
    ranges = chain_ranges(query_chainseq)

    if not ranges or ranges[-1][1] != query_length:
        raise ValueError(
            "The slash-delimited chain lengths do not match the full query length."
        )

    output_row[f"{model_name}_plddt"] = np.mean(plddt[:query_length])
    if pae is not None:
        output_row[f"{model_name}_pae"] = np.mean(
            pae[:query_length, :query_length]
        )

    for chain_1, (start_1, stop_1) in enumerate(ranges):
        output_row[f"{model_name}_plddt_{chain_1}"] = np.mean(
            plddt[start_1:stop_1]
        )

        if pae is None:
            continue

        for chain_2, (start_2, stop_2) in enumerate(ranges):
            output_row[f"{model_name}_pae_{chain_1}_{chain_2}"] = np.mean(
                pae[start_1:stop_1, start_2:stop_2]
            )


def predict_target(
    *,
    target_row: pd.Series,
    row_number: Any,
    model_runners: Mapping[str, Any],
    crop_size: int,
    args: argparse.Namespace,
) -> pd.Series:
    """Prepare templates, run AlphaFold, and summarize one target."""
    query_chainseq = target_row["target_chainseq"]
    query_sequence = sequence_without_chain_separators(query_chainseq)
    output_prefix = resolve_target_output_prefix(
        target_row,
        row_number,
        args.outfile_prefix,
    )

    template_features = build_template_feature_batch(
        query_sequence=query_sequence,
        alignment_file=target_row["templates_alignfile"],
        ignore_identities=args.ignore_identities,
    )

    msa = [query_sequence]
    deletion_matrix = [[0] * len(query_sequence)]

    all_metrics = predict_utils.run_alphafold_prediction(
        query_sequence=query_sequence,
        msa=msa,
        deletion_matrix=deletion_matrix,
        chainbreak_sequence=query_chainseq,
        template_features=template_features,
        model_runners=model_runners,
        out_prefix=output_prefix,
        crop_size=crop_size,
        dump_pdbs=not (args.no_pdbs or args.terse),
        dump_metrics=not args.terse,
    )

    output_row = target_row.copy()
    for model_name, metrics in all_metrics.items():
        add_confidence_summaries(
            output_row,
            model_name=model_name,
            metrics=metrics,
            query_chainseq=query_chainseq,
            query_length=len(query_sequence),
        )
    return output_row


def resolve_final_output_prefix(
    args: argparse.Namespace,
    targets: pd.DataFrame,
) -> Any | None:
    """Preserve the original final-summary prefix precedence."""
    if args.final_outfile_prefix:
        return args.final_outfile_prefix
    if args.outfile_prefix:
        return args.outfile_prefix
    if "outfile_prefix" in targets.columns:
        return targets.iloc[0]["outfile_prefix"]
    return None


def run(args: argparse.Namespace) -> None:
    targets = read_targets(args.targets)
    crop_size = determine_crop_size(targets)

    if args.verbose:
        print_runtime_details(targets, crop_size)
    sys.stdout.flush()

    model_runners = predict_utils.load_model_runners(
        args.model_names,
        crop_size,
        args.data_dir,
        model_params_files=args.model_params_files,
        resample_msa_in_recycling=not args.no_resample_msa,
    )

    completed_rows: list[pd.Series] = []
    for ordinal, (row_number, target_row) in enumerate(targets.iterrows()):
        print("START:", row_number, "of", targets.shape[0])
        completed_rows.append(
            predict_target(
                target_row=target_row,
                row_number=row_number,
                model_runners=model_runners,
                crop_size=crop_size,
                args=args,
            )
        )

    final_prefix = resolve_final_output_prefix(args, targets)
    if final_prefix:
        output_file = f"{final_prefix}_final.tsv"
        pd.DataFrame(completed_rows).to_csv(output_file, sep="\t", index=False)
        print("made:", output_file)


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()