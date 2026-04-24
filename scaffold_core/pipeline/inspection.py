"""
Layer: pipeline

Rules:
- Owns debug/inspection orchestration for G1 pipeline data.
- May import layers.
- Does not contain topology, geometry, relation, feature, or runtime logic.
- Does not import Blender directly; Blender mesh reading stays in Layer 0.
"""

from __future__ import annotations

from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import validate_topology
from scaffold_core.layer_1_topology.queries import chain_uses_for_chain


def describe_active_blender_mesh_topology(context: object) -> str:
    """Return a text report for the active Blender mesh topology snapshot."""

    source = read_source_mesh_from_blender(context)
    model = build_topology_snapshot(source)
    diagnostics = validate_topology(model)

    lines = [
        f"source faces: {len(source.faces)}",
        f"selected faces: {len(source.selected_face_ids)}",
        f"marks: {[(str(mark.kind), str(mark.target_id)) for mark in source.marks]}",
        f"shells: {len(model.shells)}",
        f"patches: {len(model.patches)}",
        f"chains: {len(model.chains)}",
        f"chain uses: {len(model.chain_uses)}",
    ]
    lines.extend(
        f"shell {shell.id}: patches {tuple(str(patch_id) for patch_id in shell.patch_ids)}"
        for shell in model.shells.values()
    )
    lines.extend(
        f"patch {patch.id}: shell {patch.shell_id} faces "
        f"{tuple(str(face_id) for face_id in patch.source_face_ids)} loops "
        f"{tuple(str(loop_id) for loop_id in patch.loop_ids)}"
        for patch in model.patches.values()
    )
    lines.extend(
        f"chain {chain.id}: uses {len(chain_uses_for_chain(model, chain.id))}"
        for chain in model.chains.values()
    )
    lines.extend(
        f"{diagnostic.severity} {diagnostic.code} "
        f"{tuple(diagnostic.entity_ids)} {dict(diagnostic.evidence)}"
        for diagnostic in diagnostics
    )
    return "\n".join(lines)
