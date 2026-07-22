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

import pickle
from collections import OrderedDict
from pathlib import Path
from timeit import default_timer
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import haiku as hk
import numpy as np
import pandas as pd
import tensorflow as tf

import train_utils
from alphafold.common import protein, residue_constants
from alphafold.data import pipeline, templates
from alphafold.model import config, data, model


CHAIN_BREAK_DISTANCE = 1.75
CHAIN_INDEX_OFFSET = 200
MODEL_METRIC_NAMES = ("plddt", "ptm", "predicted_aligned_error")
ATOM37_COUNT = residue_constants.atom_type_num


# ---------------------------------------------------------------------------
# PDB parsing and coordinate conversion
# ---------------------------------------------------------------------------


def _is_coordinate_record(line: str) -> bool:
    return line[:6] in {"ATOM  ", "HETATM"}


def _accepted_altloc(line: str) -> bool:
    return len(line) > 16 and line[16] in " A1"


def _one_letter_residue(resname: str) -> str | None:
    if resname == "MSE":
        return "M"
    return residue_constants.restype_3to1.get(resname)


def _atom_xyz(line: str) -> np.ndarray:
    return np.asarray(
        [
            float(line[30:38]),
            float(line[38:46]),
            float(line[46:54]),
        ]
    )


def _check_chain_continuity(
    pdbfile: str | Path,
    chain_order: Sequence[str],
    residues_by_chain: Mapping[str, Sequence[str]],
    coordinates: Mapping[str, Mapping[str, Mapping[str, np.ndarray]]],
    *,
    allow_chainbreaks: bool,
) -> None:
    """Check adjacent C--N distances using the original 1.75 A threshold."""
    for chain_id in chain_order:
        residue_ids = residues_by_chain[chain_id]
        for left_id, right_id in zip(residue_ids[:-1], residue_ids[1:]):
            left_atoms = coordinates[chain_id][left_id]
            right_atoms = coordinates[chain_id][right_id]
            if "C" not in left_atoms or "N" not in right_atoms:
                continue

            distance = float(np.linalg.norm(left_atoms["C"] - right_atoms["N"]))
            if distance <= CHAIN_BREAK_DISTANCE:
                continue

            print(
                "WARNING chainbreak:",
                chain_id,
                left_id,
                right_id,
                distance,
                pdbfile,
            )
            if not allow_chainbreaks:
                print("STOP: chainbreaks", pdbfile)
                print("DONE")
                raise SystemExit


def load_pdb_coords(
    pdbfile,
    allow_chainbreaks=False,
    allow_skipped_lines=False,
    verbose=False,
):
    """
    Read a simple PDB coordinate file.

    Returns
    -------
    tuple
        ``(chains, all_resids, all_coords, all_name1s)`` using the same nested
        dictionary layout as the historical implementation.
    """
    if verbose:
        print("reading:", pdbfile)

    chains: list[str] = []
    all_resids: dict[str, list[str]] = {}
    all_coords: dict[str, dict[str, dict[str, np.ndarray]]] = {}
    all_name1s: dict[str, dict[str, str]] = {}
    encountered_unsupported_residue = False

    with open(pdbfile, "r") as handle:
        for line in handle:
            if not _is_coordinate_record(line):
                continue
            if line[17:20] == "HOH" or not _accepted_altloc(line):
                continue

            residue_name = line[17:20]
            residue_letter = _one_letter_residue(residue_name)
            if residue_letter is None:
                print("skip ATOM line:", line.rstrip("\n"), pdbfile)
                encountered_unsupported_residue = True
                continue

            chain_id = line[21]
            residue_id = line[22:27]
            atom_name = line[12:16].split()[0]

            if chain_id not in all_resids:
                chains.append(chain_id)
                all_resids[chain_id] = []
                all_coords[chain_id] = {}
                all_name1s[chain_id] = {}

            if line.startswith("HETATM"):
                print("WARNING: HETATM", pdbfile, line.rstrip("\n"))

            if residue_id not in all_coords[chain_id]:
                all_resids[chain_id].append(residue_id)
                all_coords[chain_id][residue_id] = {}
                all_name1s[chain_id][residue_id] = residue_letter

            all_coords[chain_id][residue_id][atom_name] = _atom_xyz(line)

    _check_chain_continuity(
        pdbfile,
        chains,
        all_resids,
        all_coords,
        allow_chainbreaks=allow_chainbreaks,
    )

    if encountered_unsupported_residue and not allow_skipped_lines:
        print("STOP: skipped lines:", pdbfile)
        print("DONE")
        raise SystemExit

    return chains, all_resids, all_coords, all_name1s


def _ordered_residues(
    chain_order: Sequence[str],
    all_resids: Mapping[str, Sequence[str]],
) -> list[tuple[str, str]]:
    return [
        (chain_id, residue_id)
        for chain_id in chain_order
        for residue_id in all_resids[chain_id]
    ]


def _report_unknown_atom(atom_name: str, chain_id: str, residue_id: str) -> None:
    if atom_name == "NV":
        return

    stripped = atom_name
    while stripped and stripped[0] in "123":
        stripped = stripped[1:]
    if stripped and stripped[0] != "H":
        print("unrecognized atom:", atom_name, chain_id, residue_id)


def fill_afold_coords(chain_order, all_resids, all_coords):
    """Convert nested PDB coordinates to AlphaFold's atom37 arrays."""
    assert ATOM37_COUNT == 37

    residue_order = _ordered_residues(chain_order, all_resids)
    positions = np.zeros((len(residue_order), ATOM37_COUNT, 3))
    position_mask = np.zeros((len(residue_order), ATOM37_COUNT), dtype=np.int64)

    for output_index, (chain_id, residue_id) in enumerate(residue_order):
        residue_positions = np.zeros((ATOM37_COUNT, 3), dtype=np.float32)
        residue_mask = np.zeros(ATOM37_COUNT, dtype=np.float32)

        for atom_name, xyz in all_coords[chain_id][residue_id].items():
            atom_index = residue_constants.atom_order.get(atom_name)
            if atom_index is None:
                _report_unknown_atom(atom_name, chain_id, residue_id)
                continue
            residue_positions[atom_index] = xyz
            residue_mask[atom_index] = 1.0

        positions[output_index] = residue_positions
        position_mask[output_index] = residue_mask

    return positions, position_mask


# ---------------------------------------------------------------------------
# Inference features and prediction output
# ---------------------------------------------------------------------------


def _chain_lengths(chainbreak_sequence: str) -> list[int]:
    return [len(chain) for chain in chainbreak_sequence.split("/")]


def _apply_chain_break_offsets(
    residue_index: np.ndarray,
    chain_lengths: Sequence[int],
) -> np.ndarray:
    """Apply AlphaFold's multichain residue-index jump in place-compatible form."""
    adjusted = residue_index
    consumed = 0
    for chain_length in chain_lengths[:-1]:
        consumed += chain_length
        adjusted[consumed:] += CHAIN_INDEX_OFFSET
    return adjusted


def _make_prediction_features(
    query_sequence: str,
    msa: list,
    deletion_matrix: list,
    template_features: Mapping[str, Any],
) -> dict[str, Any]:
    features = pipeline.make_sequence_features(
        sequence=query_sequence,
        description="none",
        num_res=len(query_sequence),
    )
    features.update(
        pipeline.make_msa_features(
            msas=[msa],
            deletion_matrices=[deletion_matrix],
        )
    )
    features.update(template_features)
    return features


def run_alphafold_prediction(
    query_sequence: str,
    msa: list,
    deletion_matrix: list,
    chainbreak_sequence: str,
    template_features: dict,
    model_runners: dict,
    out_prefix: str,
    crop_size=None,
    dump_pdbs=True,
    dump_metrics=True,
):
    """Build inference features, mark chain boundaries, and run AlphaFold."""
    feature_dict = _make_prediction_features(
        query_sequence,
        msa,
        deletion_matrix,
        template_features,
    )
    feature_dict["residue_index"] = _apply_chain_break_offsets(
        feature_dict["residue_index"],
        _chain_lengths(chainbreak_sequence),
    )

    return predict_structure(
        out_prefix,
        feature_dict,
        model_runners,
        crop_size=crop_size,
        dump_pdbs=dump_pdbs,
        dump_metrics=dump_metrics,
    )


def _prediction_metrics(prediction_result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        metric_name: prediction_result[metric_name]
        for metric_name in MODEL_METRIC_NAMES
        if prediction_result.get(metric_name) is not None
    }


def _mean_plddt(values: Any) -> float:
    return float(np.mean(values))


def _write_ranked_prediction(
    *,
    prefix: str,
    rank: int,
    model_name: str,
    pdb_text: str,
    metric_values: Mapping[str, Any],
    dump_pdbs: bool,
    dump_metrics: bool,
) -> None:
    ranked_prefix = f"{prefix}_model_{rank}_{model_name}"

    if dump_pdbs:
        with open(f"{ranked_prefix}.pdb", "w") as handle:
            handle.write(pdb_text)

    if dump_metrics:
        for metric_name in MODEL_METRIC_NAMES:
            value = metric_values.get(metric_name)
            if value is not None:
                np.save(f"{ranked_prefix}_{metric_name}.npy", value)


def predict_structure(
    prefix,
    feature_dict,
    model_runners,
    random_seed=0,
    crop_size=None,
    dump_pdbs=True,
    dump_metrics=True,
):
    """
    Run all configured AlphaFold models and save outputs ranked by mean pLDDT.

    ``crop_size`` is retained in the signature for compatibility; model runners
    are already configured with it before this function is called.
    """
    del crop_size

    metrics_by_model: dict[str, dict[str, Any]] = {}
    model_outputs: list[dict[str, Any]] = []

    for model_name, model_runner in model_runners.items():
        started = default_timer()
        print(f"running {model_name}")

        processed_features = model_runner.process_features(
            feature_dict,
            random_seed=random_seed,
        )
        prediction_result = model_runner.predict(processed_features)

        predicted_protein = protein.from_prediction(
            processed_features,
            prediction_result,
        )
        pdb_text = protein.to_pdb(predicted_protein)
        selected_metrics = _prediction_metrics(prediction_result)
        metrics_by_model[model_name] = selected_metrics

        plddt = prediction_result["plddt"]
        mean_confidence = _mean_plddt(plddt)
        model_outputs.append(
            {
                "name": model_name,
                "pdb": pdb_text,
                "metrics": selected_metrics,
                "mean_plddt": mean_confidence,
            }
        )

        print(
            f"{model_name} pLDDT: {mean_confidence} "
            f"Time: {default_timer() - started}"
        )

    mean_plddt_values = np.asarray(
        [output["mean_plddt"] for output in model_outputs]
    )
    ranking = mean_plddt_values.argsort()[::-1]
    ranked_outputs = [model_outputs[index] for index in ranking]

    for rank, output in enumerate(ranked_outputs, start=1):
        print(f"model_{rank} {output['mean_plddt']}")
        _write_ranked_prediction(
            prefix=prefix,
            rank=rank,
            model_name=output["name"],
            pdb_text=output["pdb"],
            metric_values=output["metrics"],
            dump_pdbs=dump_pdbs,
            dump_metrics=dump_metrics,
        )

    return metrics_by_model


# ---------------------------------------------------------------------------
# Model configuration and parameter loading
# ---------------------------------------------------------------------------


def _base_alphafold_model_name(model_name: str) -> str:
    return model_name.split("_ft", maxsplit=1)[0]


def _configure_model(
    model_name: str,
    crop_size: int,
    *,
    num_recycle: int,
    num_ensemble: int,
    resample_msa_in_recycling: bool,
    small_msas: bool,
):
    model_config = config.model_config(_base_alphafold_model_name(model_name))
    model_config.data.eval.crop_size = crop_size
    model_config.data.eval.num_ensemble = num_ensemble
    model_config.data.common.num_recycle = num_recycle
    model_config.model.num_recycle = num_recycle

    if small_msas:
        print(
            "load_model_runners:: small_msas==True setting small",
            "max_extra_msa and max_msa_clusters",
        )
        model_config.data.common.max_extra_msa = 1
        model_config.data.eval.max_msa_clusters = 5

    if not resample_msa_in_recycling:
        model_config.data.common.resample_msa_in_recycling = False
        model_config.model.resample_msa_in_recycling = False

    return model_config


def _load_finetuned_parameters(model_name: str, parameter_file: str):
    print("loading", model_name, "params from file:", parameter_file)
    with open(parameter_file, "rb") as handle:
        serialized_parameters = pickle.load(handle)

    alphafold_parameters, ignored_parameters = hk.data_structures.partition(
        lambda module_name, parameter_name, value: module_name[:9] == "alphafold",
        serialized_parameters,
    )
    print("ignoring other_params:", ignored_parameters)
    return alphafold_parameters


def _load_model_parameters(
    model_name: str,
    model_params_file: str | None,
    data_dir: str | None,
):
    use_custom_parameters = (
        model_params_file is not None and model_params_file != "classic"
    )
    if use_custom_parameters:
        return _load_finetuned_parameters(model_name, model_params_file)

    assert "_ft" not in model_name
    return data.get_model_haiku_params(
        model_name=model_name,
        data_dir=data_dir,
    )


def load_model_runners(
    model_names,
    crop_size,
    data_dir,
    num_recycle=3,
    num_ensemble=1,
    model_params_files=None,
    resample_msa_in_recycling=True,
    small_msas=True,
):
    """Create ordered AlphaFold model runners for standard or custom weights."""
    if model_params_files is None:
        model_params_files = [None] * len(model_names)
    assert len(model_names) == len(model_params_files)

    runners = OrderedDict()
    for model_name, parameter_file in zip(model_names, model_params_files):
        print("config:", model_name)
        model_config = _configure_model(
            model_name,
            crop_size,
            num_recycle=num_recycle,
            num_ensemble=num_ensemble,
            resample_msa_in_recycling=resample_msa_in_recycling,
            small_msas=small_msas,
        )
        parameters = _load_model_parameters(
            model_name,
            parameter_file,
            data_dir,
        )
        runners[model_name] = model.RunModel(model_config, parameters)

    return runners


# ---------------------------------------------------------------------------
# Template feature construction
# ---------------------------------------------------------------------------


def _template_sequence_and_order(
    chain_order: Sequence[str],
    all_resids: Mapping[str, Sequence[str]],
    all_name1s: Mapping[str, Mapping[str, str]],
) -> tuple[list[tuple[str, str]], str]:
    ordered = _ordered_residues(chain_order, all_resids)
    sequence = "".join(all_name1s[chain][residue] for chain, residue in ordered)
    return ordered, sequence


def _count_alignment_identities(
    target_sequence: str,
    template_sequence: str,
    alignment: Mapping[int, int],
) -> int:
    return sum(
        target_sequence[target_index] == template_sequence[template_index]
        for target_index, template_index in alignment.items()
    )


def _project_template_onto_target(
    target_length: int,
    template_sequence: str,
    template_positions: np.ndarray,
    template_mask: np.ndarray,
    alignment: Mapping[int, int],
) -> tuple[str, np.ndarray, np.ndarray]:
    aligned_letters = ["-"] * target_length
    aligned_positions = np.zeros((target_length, ATOM37_COUNT, 3))
    aligned_mask = np.zeros((target_length, ATOM37_COUNT), dtype=np.int64)

    for target_index, template_index in alignment.items():
        aligned_letters[target_index] = template_sequence[template_index]
        aligned_positions[target_index] = template_positions[template_index]
        aligned_mask[target_index] = template_mask[template_index]

    return "".join(aligned_letters), aligned_positions, aligned_mask


def create_single_template_features(
    target_sequence,
    template_pdbfile,
    target_to_template_alignment,
    template_name,
    allow_chainbreaks=True,
    allow_skipped_lines=True,
    expected_identities=None,
    expected_template_len=None,
):
    """Construct AlphaFold template features for one target/template mapping."""
    chains, residues, coordinates, residue_letters = load_pdb_coords(
        template_pdbfile,
        allow_chainbreaks=allow_chainbreaks,
        allow_skipped_lines=allow_skipped_lines,
    )
    _, template_full_sequence = _template_sequence_and_order(
        chains,
        residues,
        residue_letters,
    )

    if expected_template_len:
        assert len(template_full_sequence) == expected_template_len

    template_positions, template_position_mask = fill_afold_coords(
        chains,
        residues,
        coordinates,
    )
    identities = _count_alignment_identities(
        target_sequence,
        template_full_sequence,
        target_to_template_alignment,
    )
    if expected_identities:
        assert identities == expected_identities

    aligned_sequence, aligned_positions, aligned_mask = _project_template_onto_target(
        len(target_sequence),
        template_full_sequence,
        template_positions,
        template_position_mask,
        target_to_template_alignment,
    )

    assert len(aligned_sequence) == len(target_sequence)
    assert identities == sum(
        target_letter == template_letter
        for target_letter, template_letter in zip(target_sequence, aligned_sequence)
    )

    return {
        "template_all_atom_positions": aligned_positions,
        "template_all_atom_masks": aligned_mask,
        "template_sequence": aligned_sequence.encode(),
        "template_aatype": residue_constants.sequence_to_onehot(
            aligned_sequence,
            residue_constants.HHBLITS_AA_TO_ID,
        ),
        "template_domain_names": template_name.encode(),
        "template_sum_probs": [identities],
    }


def compile_template_features(template_features_list):
    """Stack a list of single-template feature dictionaries by template axis."""
    return {
        feature_name: np.stack(
            [feature_set[feature_name] for feature_set in template_features_list],
            axis=0,
        ).astype(dtype)
        for feature_name, dtype in templates.TEMPLATE_FEATURES.items()
    }


# ---------------------------------------------------------------------------
# Training batch construction
# ---------------------------------------------------------------------------


def _parse_alignment_string(alignment_string: str) -> dict[int, int]:
    return {
        int(pair.split(":", maxsplit=1)[0]): int(pair.split(":", maxsplit=1)[1])
        for pair in alignment_string.split(";")
    }


def _full_residue_index(target_chainseq: str) -> np.ndarray:
    chains = target_chainseq.split("/")
    residue_index = np.arange(sum(len(chain) for chain in chains))
    consumed = 0
    for chain in chains[:-1]:
        consumed += len(chain)
        residue_index[consumed:] += CHAIN_INDEX_OFFSET
    return residue_index


def _template_batch_for_trimmed_target(
    *,
    target_full_sequence: str,
    target_sequence: str,
    target_trim_positions: Sequence[int],
    full_pos_to_trim_pos: Mapping[int, int],
    templates_alignfile: str,
    debug: bool,
) -> dict[str, np.ndarray]:
    template_feature_sets = []
    template_rows = pd.read_table(templates_alignfile)

    for row in template_rows.itertuples():
        full_alignment = _parse_alignment_string(
            row.target_to_template_alignstring
        )
        template_label = f"temp{row.Index}"

        if debug:
            create_single_template_features(
                target_full_sequence,
                row.template_pdbfile,
                full_alignment,
                template_label,
                expected_identities=row.identities,
                expected_template_len=row.template_len,
            )

        trimmed_alignment = {
            full_pos_to_trim_pos[full_target_index]: template_index
            for full_target_index, template_index in full_alignment.items()
            if full_target_index in full_pos_to_trim_pos
        }
        template_feature_sets.append(
            create_single_template_features(
                target_sequence,
                row.template_pdbfile,
                trimmed_alignment,
                template_label,
                expected_template_len=row.template_len,
            )
        )

    return compile_template_features(template_feature_sets)


def _raw_training_features(
    target_sequence: str,
    template_features: Mapping[str, Any],
) -> dict[str, Any]:
    msa = [target_sequence]
    deletions = [[0] * len(target_sequence)]
    feature_dict = pipeline.make_sequence_features(
        sequence=target_sequence,
        description="none",
        num_res=len(target_sequence),
    )
    feature_dict.update(
        pipeline.make_msa_features(
            msas=[msa],
            deletion_matrices=[deletions],
        )
    )
    feature_dict.update(template_features)
    return feature_dict


def _native_features_for_trimmed_target(
    *,
    target_full_sequence: str,
    target_sequence: str,
    target_trim_positions: Sequence[int],
    full_pos_to_trim_pos: Mapping[int, int],
    native_pdbfile: str,
    native_align: Mapping[int, int],
    native_identities: int | None,
    native_len: int | None,
    debug: bool,
) -> dict[str, Any]:
    if debug:
        create_single_template_features(
            target_full_sequence,
            native_pdbfile,
            native_align,
            "dummy",
            expected_identities=native_identities,
            expected_template_len=native_len,
        )

    trimmed_alignment = {
        full_pos_to_trim_pos[full_target_index]: native_index
        for full_target_index, native_index in native_align.items()
        if full_target_index in full_pos_to_trim_pos
    }
    return create_single_template_features(
        target_sequence,
        native_pdbfile,
        trimmed_alignment,
        "dummy",
        expected_template_len=native_len,
    )


def _pad_native_arrays(
    processed_feature_dict: Mapping[str, Any],
    native_features: Mapping[str, Any],
    trimmed_length: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    padded_length = processed_feature_dict["aatype"].shape[1]
    padding = padded_length - trimmed_length

    atom_positions = np.concatenate(
        [
            native_features["template_all_atom_positions"],
            np.zeros((padding, ATOM37_COUNT, 3)),
        ],
        axis=0,
    )
    atom_mask = np.concatenate(
        [
            native_features["template_all_atom_masks"],
            np.zeros((padding, ATOM37_COUNT)),
        ],
        axis=0,
    )
    aatype = np.concatenate(
        [
            processed_feature_dict["aatype"][0][:trimmed_length],
            20 * np.ones(padding),
        ],
        axis=0,
    ).astype(np.int32)
    return atom_positions, atom_mask, aatype


def _attach_native_training_features(
    processed_feature_dict: MutableMapping[str, Any],
    atom_positions: np.ndarray,
    atom_mask: np.ndarray,
    aatype: np.ndarray,
) -> None:
    pseudo_beta, pseudo_beta_mask = train_utils.pseudo_beta_fn_np(
        aatype,
        atom_positions,
        atom_mask,
    )

    protein_features = train_utils.make_atom14_positions(
        {
            "aatype": aatype,
            "all_atom_positions": atom_positions,
            "all_atom_mask": atom_mask,
        }
    )
    del protein_features["aatype"]
    protein_features = {
        key: np.asarray(value)[None, ...]
        for key, value in protein_features.items()
    }

    processed_feature_dict["pseudo_beta"] = np.asarray(pseudo_beta)[None, ...]
    processed_feature_dict["pseudo_beta_mask"] = np.asarray(
        pseudo_beta_mask
    )[None, ...]
    processed_feature_dict["all_atom_mask"] = np.asarray(atom_mask)[None, ...]
    processed_feature_dict["resolution"] = np.asarray(1.0)[None, ...]
    processed_feature_dict.update(protein_features)

    n_index, ca_index, c_index = [
        residue_constants.atom_order[atom_name]
        for atom_name in ("N", "CA", "C")
    ]
    rotation, translation = train_utils.make_transform_from_reference_np(
        n_xyz=processed_feature_dict["all_atom_positions"][0, :, n_index, :],
        ca_xyz=processed_feature_dict["all_atom_positions"][0, :, ca_index, :],
        c_xyz=processed_feature_dict["all_atom_positions"][0, :, c_index, :],
    )
    processed_feature_dict["backbone_translation"] = translation[None, ...]
    processed_feature_dict["backbone_rotation"] = rotation[None, ...]
    processed_feature_dict["backbone_affine_mask"] = (
        processed_feature_dict["all_atom_mask"][0, :, n_index]
        * processed_feature_dict["all_atom_mask"][0, :, ca_index]
        * processed_feature_dict["all_atom_mask"][0, :, c_index]
    )[None, ...]


def create_batch_for_training(
    target_chainseq,
    target_trim_positions,
    templates_alignfile,
    native_pdbfile,
    native_align,
    crop_size,
    model_runner,
    native_identities=None,
    native_len=None,
    debug=False,
    verbose=False,
    random_seed=None,
):
    """Create a processed AlphaFold feature batch with native training labels."""
    assert len(target_trim_positions) <= crop_size
    assert None not in target_trim_positions

    if verbose:
        print(
            "create_batch_for_training:",
            target_chainseq,
            target_trim_positions,
            templates_alignfile,
            native_pdbfile,
            native_align,
            crop_size,
            native_identities,
            native_len,
        )

    trim_positions = sorted(set(target_trim_positions))
    full_pos_to_trim_pos = {
        full_position: trimmed_position
        for trimmed_position, full_position in enumerate(trim_positions)
    }

    target_full_sequence = target_chainseq.replace("/", "")
    target_sequence = "".join(
        target_full_sequence[position] for position in trim_positions
    )
    trimmed_residue_index = _full_residue_index(target_chainseq)[trim_positions]

    all_template_features = _template_batch_for_trimmed_target(
        target_full_sequence=target_full_sequence,
        target_sequence=target_sequence,
        target_trim_positions=trim_positions,
        full_pos_to_trim_pos=full_pos_to_trim_pos,
        templates_alignfile=templates_alignfile,
        debug=debug,
    )
    feature_dict = _raw_training_features(
        target_sequence,
        all_template_features,
    )

    if verbose:
        print("features_after_creation:", " ".join(feature_dict.keys()))
    feature_dict["residue_index"] = trimmed_residue_index.astype(
        feature_dict["residue_index"].dtype
    )

    if random_seed is None:
        random_seed = np.random.randint(0, 999999)
    with tf.device("cpu:0"):
        processed_feature_dict = model_runner.process_features(
            feature_dict,
            random_seed=random_seed,
        )

    if verbose:
        print(
            "features_after_initial_processing:",
            " ".join(processed_feature_dict.keys()),
        )

    native_features = _native_features_for_trimmed_target(
        target_full_sequence=target_full_sequence,
        target_sequence=target_sequence,
        target_trim_positions=trim_positions,
        full_pos_to_trim_pos=full_pos_to_trim_pos,
        native_pdbfile=native_pdbfile,
        native_align=native_align,
        native_identities=native_identities,
        native_len=native_len,
        debug=debug,
    )

    padded_length = processed_feature_dict["aatype"].shape[1]
    assert padded_length == crop_size
    atom_positions, atom_mask, aatype = _pad_native_arrays(
        processed_feature_dict,
        native_features,
        len(trim_positions),
    )
    _attach_native_training_features(
        processed_feature_dict,
        atom_positions,
        atom_mask,
        aatype,
    )

    if verbose:
        print("features_at_end:", " ".join(processed_feature_dict.keys()))
    return processed_feature_dict