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

from typing import Dict, List, MutableMapping, Optional, Tuple, Union

import jax
import jax.numpy as jnp
import numpy as np
from alphafold.common import residue_constants


# Feature groups retained as lists for backward compatibility with code that
# imports or modifies them directly.
pdb_key_list = [
    "atom14_atom_exists",
    "residx_atom14_to_atom37",
    "residx_atom37_to_atom14",
    "atom37_atom_exists",
    "pseudo_beta",
    "pseudo_beta_mask",
    "all_atom_mask",
    "chi_mask",
    "chi_angles",
    "all_atom_positions",
    "atom14_gt_exists",
    "atom14_gt_positions",
    "atom14_alt_gt_positions",
    "atom14_alt_gt_exists",
    "atom14_atom_is_ambiguous",
    "rigidgroups_gt_frames",
    "rigidgroups_gt_exists",
    "rigidgroups_group_exists",
    "rigidgroups_group_is_ambiguous",
    "rigidgroups_alt_gt_frames",
    "backbone_translation",
    "backbone_rotation",
    "backbone_affine_mask",
]

pdb_key_list_int = [
    "residx_atom14_to_atom37",
    "residx_atom37_to_atom14",
]

list_a = [
    "atom14_atom_exists",
    "residx_atom14_to_atom37",
    "residx_atom37_to_atom14",
    "atom37_atom_exists",
    "pseudo_beta",
    "pseudo_beta_mask",
    "all_atom_mask",
    "resolution",
    "all_atom_positions",
    "atom14_gt_exists",
    "atom14_gt_positions",
    "atom14_alt_gt_positions",
    "atom14_alt_gt_exists",
    "atom14_atom_is_ambiguous",
    "backbone_translation",
    "backbone_rotation",
    "backbone_affine_mask",
]

list_a_templates = [
    "template_aatype",
    "template_all_atom_masks",
    "template_all_atom_positions",
    "template_pseudo_beta",
    "template_pseudo_beta_mask",
    "template_sum_probs",
]

list_b_templates = ["template_mask"]

list_b = [
    "aatype",
    "residue_index",
    "seq_length",
    "is_distillation",
    "seq_mask",
    "msa_mask",
    "msa_row_mask",
    "random_crop_to_size_seed",
    "extra_msa",
    "extra_msa_mask",
    "extra_msa_row_mask",
    "bert_mask",
    "true_msa",
    "extra_has_deletion",
    "extra_deletion_value",
    "msa_feat",
    "target_feat",
]

list_c = [
    "chi_mask",
    "chi_angles",
    "rigidgroups_gt_frames",
    "rigidgroups_gt_exists",
    "rigidgroups_group_exists",
    "rigidgroups_group_is_ambiguous",
    "rigidgroups_alt_gt_frames",
]


def pseudo_beta_fn_np(
    aatype: np.ndarray,
    all_atom_positions: np.ndarray,
    all_atom_masks: Optional[np.ndarray],
) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
    """Return pseudo-beta coordinates and, when supplied, their validity mask.

    Glycine uses its CA coordinate; every other residue uses CB.
    """
    glycine_mask = np.equal(aatype, residue_constants.restype_order["G"])
    ca_index = residue_constants.atom_order["CA"]
    cb_index = residue_constants.atom_order["CB"]

    choose_ca = np.expand_dims(glycine_mask, axis=-1)
    pseudo_beta = np.where(
        choose_ca,
        all_atom_positions[..., ca_index, :],
        all_atom_positions[..., cb_index, :],
    )

    if all_atom_masks is None:
        return pseudo_beta

    pseudo_beta_mask = np.where(
        glycine_mask,
        all_atom_masks[..., ca_index],
        all_atom_masks[..., cb_index],
    ).astype(np.float32)
    return pseudo_beta, pseudo_beta_mask


def apply_rot_to_vec(rot, vec, unstack: bool = False):
    """Apply a 3-by-3 rotation to a vector and return its three components."""
    if unstack:
        components = tuple(vec[:, axis] for axis in range(3))
    else:
        components = tuple(vec)

    return [
        sum(rot[row][col] * components[col] for col in range(3))
        for row in range(3)
    ]


def _multiply(a, b):
    """Multiply two 3-by-3 matrices whose entries may be batched arrays."""
    rows = []
    for row in range(3):
        rows.append(
            np.array(
                [
                    sum(a[row][inner] * b[inner][column] for inner in range(3))
                    for column in range(3)
                ]
            )
        )
    return np.stack(rows)


def _check_backbone_coordinate_shapes(
    n_xyz: np.ndarray,
    ca_xyz: np.ndarray,
    c_xyz: np.ndarray,
) -> None:
    assert n_xyz.ndim == 2, n_xyz.shape
    assert n_xyz.shape[-1] == 3, n_xyz.shape
    assert n_xyz.shape == ca_xyz.shape == c_xyz.shape, (
        n_xyz.shape,
        ca_xyz.shape,
        c_xyz.shape,
    )


def _rotation_about_z(sine: np.ndarray, cosine: np.ndarray) -> np.ndarray:
    zeros = np.zeros_like(sine)
    ones = np.ones_like(sine)
    return np.stack(
        [
            np.array([cosine, -sine, zeros]),
            np.array([sine, cosine, zeros]),
            np.array([zeros, zeros, ones]),
        ]
    )


def _rotation_about_y(sine: np.ndarray, cosine: np.ndarray) -> np.ndarray:
    zeros = np.zeros_like(sine)
    ones = np.ones_like(sine)
    return np.stack(
        [
            np.array([cosine, zeros, sine]),
            np.array([zeros, ones, zeros]),
            np.array([-sine, zeros, cosine]),
        ]
    )


def _rotation_about_x(sine: np.ndarray, cosine: np.ndarray) -> np.ndarray:
    zeros = np.zeros_like(sine)
    ones = np.ones_like(sine)
    return np.stack(
        [
            np.array([ones, zeros, zeros]),
            np.array([zeros, cosine, -sine]),
            np.array([zeros, sine, cosine]),
        ]
    )


def make_canonical_transform(
    n_xyz: np.ndarray,
    ca_xyz: np.ndarray,
    c_xyz: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build transforms that place each residue backbone in canonical space.

    CA is translated to the origin, C is rotated onto the positive x-axis, and
    N is rotated into the xy-plane. The returned tuple is ``(translation,
    rotation)`` and matches the legacy function's shapes and conventions.
    """
    _check_backbone_coordinate_shapes(n_xyz, ca_xyz, c_xyz)

    translation = -ca_xyz
    shifted_n = n_xyz + translation
    shifted_c = c_xyz + translation

    c_x, c_y, c_z = (shifted_c[:, axis] for axis in range(3))
    xy_norm = np.sqrt(1e-20 + c_x**2 + c_y**2)
    xyz_norm = np.sqrt(1e-20 + c_x**2 + c_y**2 + c_z**2)

    rotate_xy = _rotation_about_z(-c_y / xy_norm, c_x / xy_norm)
    rotate_xz = _rotation_about_y(c_z / xyz_norm, xy_norm / xyz_norm)
    carbon_rotation = _multiply(rotate_xz, rotate_xy)

    rotated_n = np.stack(
        apply_rot_to_vec(carbon_rotation, shifted_n, unstack=True)
    ).T
    n_y = rotated_n[:, 1]
    n_z = rotated_n[:, 2]
    yz_norm = np.sqrt(1e-20 + n_y**2 + n_z**2)

    nitrogen_rotation = _rotation_about_x(-n_z / yz_norm, n_y / yz_norm)
    canonical_rotation = np.transpose(
        _multiply(nitrogen_rotation, carbon_rotation),
        (2, 0, 1),
    )
    return translation, canonical_rotation


def make_transform_from_reference_np(
    n_xyz: np.ndarray,
    ca_xyz: np.ndarray,
    c_xyz: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return rotation and translation that map canonical backbones to input."""
    translation, canonical_rotation = make_canonical_transform(
        n_xyz,
        ca_xyz,
        c_xyz,
    )
    return np.transpose(canonical_rotation, (0, 2, 1)), -translation


def _build_atom14_lookup_tables() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create residue-type lookup tables between atom14 and atom37 layouts."""
    atom14_to_atom37: List[List[int]] = []
    atom37_to_atom14: List[List[int]] = []
    atom14_exists: List[List[float]] = []

    for residue_letter in residue_constants.restypes:
        residue_name = residue_constants.restype_1to3[residue_letter]
        atom14_names = residue_constants.restype_name_to_atom14_names[residue_name]

        atom14_to_atom37.append(
            [residue_constants.atom_order[name] if name else 0 for name in atom14_names]
        )
        name_to_atom14 = {name: index for index, name in enumerate(atom14_names)}
        atom37_to_atom14.append(
            [name_to_atom14.get(name, 0) for name in residue_constants.atom_types]
        )
        atom14_exists.append([1.0 if name else 0.0 for name in atom14_names])

    # Unknown residue row.
    atom14_to_atom37.append([0] * 14)
    atom37_to_atom14.append([0] * 37)
    atom14_exists.append([0.0] * 14)

    return (
        np.asarray(atom14_to_atom37, dtype=np.int32),
        np.asarray(atom37_to_atom14, dtype=np.int32),
        np.asarray(atom14_exists, dtype=np.float32),
    )


def _build_atom37_exists_table() -> np.ndarray:
    table = np.zeros((21, 37), dtype=np.float32)
    for residue_index, residue_letter in enumerate(residue_constants.restypes):
        residue_name = residue_constants.restype_1to3[residue_letter]
        for atom_name in residue_constants.residue_atoms[residue_name]:
            table[residue_index, residue_constants.atom_order[atom_name]] = 1.0
    return table


def _restype_names_with_unknown() -> List[str]:
    return [
        residue_constants.restype_1to3[letter]
        for letter in residue_constants.restypes
    ] + ["UNK"]


def _build_atom14_renaming_matrices() -> np.ndarray:
    residue_names = _restype_names_with_unknown()
    matrices = {
        residue_name: np.eye(14, dtype=np.float32)
        for residue_name in residue_names
    }

    for residue_name, swaps in residue_constants.residue_atom_renaming_swaps.items():
        atom14_names = residue_constants.restype_name_to_atom14_names[residue_name]
        correspondence = np.arange(14)
        for first_name, second_name in swaps.items():
            first_index = atom14_names.index(first_name)
            second_index = atom14_names.index(second_name)
            correspondence[first_index] = second_index
            correspondence[second_index] = first_index
        matrices[residue_name] = np.eye(14, dtype=np.float32)[correspondence]

    return np.stack([matrices[name] for name in residue_names])


def _build_atom14_ambiguity_table() -> np.ndarray:
    table = np.zeros((21, 14), dtype=np.float32)
    for residue_name, swaps in residue_constants.residue_atom_renaming_swaps.items():
        residue_index = residue_constants.restype_order[
            residue_constants.restype_3to1[residue_name]
        ]
        atom14_names = residue_constants.restype_name_to_atom14_names[residue_name]
        for first_name, second_name in swaps.items():
            table[residue_index, atom14_names.index(first_name)] = 1.0
            table[residue_index, atom14_names.index(second_name)] = 1.0
    return table


def make_atom14_positions(
    prot: MutableMapping[str, np.ndarray],
) -> MutableMapping[str, np.ndarray]:
    """Add AlphaFold atom14 ground-truth fields to ``prot`` in place."""
    atom14_to_atom37_table, atom37_to_atom14_table, atom14_exists_table = (
        _build_atom14_lookup_tables()
    )

    aatype = prot["aatype"]
    residx_atom14_to_atom37 = atom14_to_atom37_table[aatype]
    atom14_exists = atom14_exists_table[aatype]

    atom14_gt_exists = atom14_exists * np.take_along_axis(
        prot["all_atom_mask"],
        residx_atom14_to_atom37,
        axis=1,
    ).astype(np.float32)

    atom14_gt_positions = atom14_gt_exists[:, :, None] * np.take_along_axis(
        prot["all_atom_positions"],
        residx_atom14_to_atom37[..., None],
        axis=1,
    )

    prot["atom14_atom_exists"] = atom14_exists
    prot["atom14_gt_exists"] = atom14_gt_exists
    prot["atom14_gt_positions"] = atom14_gt_positions
    prot["residx_atom14_to_atom37"] = residx_atom14_to_atom37
    prot["residx_atom37_to_atom14"] = atom37_to_atom14_table[aatype]
    prot["atom37_atom_exists"] = _build_atom37_exists_table()[aatype]

    renaming_transform = _build_atom14_renaming_matrices()[aatype]
    prot["atom14_alt_gt_positions"] = np.einsum(
        "rac,rab->rbc",
        atom14_gt_positions,
        renaming_transform,
    )
    prot["atom14_alt_gt_exists"] = np.einsum(
        "ra,rab->rb",
        atom14_gt_exists,
        renaming_transform,
    )
    prot["atom14_atom_is_ambiguous"] = _build_atom14_ambiguity_table()[aatype]

    return prot


def compute_plddt_jax(logits: jnp.ndarray) -> jnp.ndarray:
    """Convert predicted-LDDT logits to per-residue pLDDT values."""
    number_of_bins = logits.shape[-1]
    bin_width = 1.0 / number_of_bins
    bin_centers = jnp.arange(
        start=0.5 * bin_width,
        stop=1.0,
        step=bin_width,
    )
    probabilities = jax.nn.softmax(logits, axis=-1)
    return jnp.sum(probabilities * bin_centers[None, :], axis=-1) * 100


def _calculate_bin_centers_jax(breaks: jnp.ndarray) -> jnp.ndarray:
    """Convert PAE bin edges into centers, including the final overflow bin."""
    step = breaks[1] - breaks[0]
    ordinary_centers = breaks + step / 2
    final_center = jnp.asarray([ordinary_centers[-1] + step])
    return jnp.concatenate((ordinary_centers, final_center), axis=0)


def _calculate_expected_aligned_error_jax(
    alignment_confidence_breaks: jnp.ndarray,
    aligned_distance_error_probs: jnp.ndarray,
) -> Tuple[jnp.ndarray, jnp.ndarray]:
    """Return expected pairwise aligned error and its largest represented value."""
    centers = _calculate_bin_centers_jax(alignment_confidence_breaks)
    expected_error = jnp.sum(
        aligned_distance_error_probs * centers,
        axis=-1,
    )
    return expected_error, jnp.asarray(centers[-1])


def compute_predicted_aligned_error_jax(
    logits: jnp.ndarray,
    breaks: jnp.ndarray,
) -> Dict[str, jnp.ndarray]:
    """Convert PAE logits into probabilities and expected aligned errors."""
    probabilities = jax.nn.softmax(logits, axis=-1)
    expected_error, maximum_error = _calculate_expected_aligned_error_jax(
        alignment_confidence_breaks=breaks,
        aligned_distance_error_probs=probabilities,
    )
    return {
        "aligned_confidence_probs": probabilities,
        "predicted_aligned_error": expected_error,
        "max_predicted_aligned_error": maximum_error,
    }