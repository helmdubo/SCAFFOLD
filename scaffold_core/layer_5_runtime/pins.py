"""
Layer: 5 - Runtime

Rules:
- Assemble the pinned UV skeleton output model and validation invariants.
- Entry point run_skeleton_solve orchestrates islands -> skeleton -> pins.
- Vertices without both axis coordinates stay unpinned (conformal fabric).
- Invariants are validation outputs, never silently relaxed (G5a).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from scaffold_core.layer_5_runtime.islands import IslandAssembly, build_islands
from scaffold_core.layer_5_runtime.skeleton import IslandSkeleton, build_island_skeletons

ISLAND_MARGIN = 0.25  # LEVEL_B_PLACEHOLDER: naive island offsets; packing is Layer 4/5 policy.
AXIS_PARALLEL_TOLERANCE = 1e-5


@dataclass(frozen=True)
class PinnedVertex:
    source_vertex_id: str
    island_id: str
    patch_id: str
    uv: tuple[float, float]
    pinned: bool


@dataclass(frozen=True)
class SolveResult:
    assembly: IslandAssembly
    skeletons: tuple[IslandSkeleton, ...]
    vertices: tuple[PinnedVertex, ...]
    residual_max: float
    axis_parallel_violations: tuple[str, ...]
    seam_length_mismatches: tuple[str, ...]
    diagnostics: tuple[str, ...]
    patch_by_source_face: Mapping[str, str] = field(default_factory=dict)


def run_skeleton_solve(context: Any) -> SolveResult:
    """G5a entry point: islands -> selection-wide skeleton -> pinned UVs."""

    assembly = build_islands(context)
    skeletons = build_island_skeletons(context, assembly)
    relations = context.relation_snapshot
    evidence_by_id = {e.id: e for e in relations.patch_chain_directional_evidence}
    vertices: list[PinnedVertex] = []
    violations: list[str] = []
    diagnostics: list[str] = []
    residual_max = 0.0
    offset_u = 0.0
    for skeleton in skeletons:
        residual_max = max(residual_max, skeleton.axis_a.residual_max, skeleton.axis_b.residual_max)
        diagnostics.extend(skeleton.diagnostics)
        island_vertices, island_violations, width = _island_vertices(
            skeleton, evidence_by_id, offset_u
        )
        vertices.extend(island_vertices)
        violations.extend(island_violations)
        offset_u += width + ISLAND_MARGIN
    seam_mismatches = _seam_length_mismatches(context, assembly, evidence_by_id)
    patch_by_source_face = {
        str(face_id): str(patch_id)
        for patch_id, patch in context.topology_snapshot.patches.items()
        for face_id in patch.source_face_ids
    }
    return SolveResult(
        assembly=assembly,
        patch_by_source_face=patch_by_source_face,
        skeletons=tuple(skeletons),
        vertices=tuple(vertices),
        residual_max=residual_max,
        axis_parallel_violations=tuple(violations),
        seam_length_mismatches=tuple(seam_mismatches),
        diagnostics=tuple(diagnostics),
    )


def _island_vertices(skeleton, evidence_by_id, offset_u):
    a_coords = skeleton.axis_a.coordinate_by_node
    b_coords = skeleton.axis_b.coordinate_by_node
    uv_by_node: dict[str, tuple[float, float]] = {}
    for node in set(a_coords) | set(b_coords):
        a = a_coords.get(node)
        b = b_coords.get(node)
        if a is not None and b is not None:
            uv_by_node[node] = (a, b)
    violations: list[str] = []
    vertices: dict[str, PinnedVertex] = {}
    min_u = min((uv[0] for uv in uv_by_node.values()), default=0.0)
    for (evidence_id, role), node in skeleton.node_by_run_end.items():
        uv = uv_by_node.get(node)
        if uv is None:
            continue
        evidence = evidence_by_id[evidence_id]
        source_vertex = str(evidence.start_source_vertex_id if role == "START" else evidence.end_source_vertex_id)
        shifted = (uv[0] - min_u + offset_u, uv[1])
        # Keyed per patch view so seam-duplicated occurrences keep both UVs.
        vertices[(source_vertex, str(evidence.patch_id))] = PinnedVertex(
            source_vertex_id=source_vertex,
            island_id=skeleton.island_id,
            patch_id=str(evidence.patch_id),
            uv=shifted,
            pinned=True,
        )
    for evidence_id, role_name in skeleton.axis_role_by_run.items():
        if role_name not in ("AXIS_A", "AXIS_B"):
            continue
        start = uv_by_node.get(skeleton.node_by_run_end[(evidence_id, "START")])
        end = uv_by_node.get(skeleton.node_by_run_end[(evidence_id, "END")])
        if start is None or end is None:
            continue
        cross_delta = abs(end[1] - start[1]) if role_name == "AXIS_A" else abs(end[0] - start[0])
        if cross_delta > AXIS_PARALLEL_TOLERANCE:
            violations.append(f"{evidence_id}:{role_name}:{cross_delta:.6f}")
    width = max((uv[0] for uv in uv_by_node.values()), default=0.0) - min_u
    return tuple(vertices.values()), violations, width


def _seam_length_mismatches(context, assembly, evidence_by_id):
    relations = context.relation_snapshot
    topology = context.topology_snapshot
    mismatches: list[str] = []
    self_seams = {
        str(junction.matched_chain_id)
        for junction in relations.scaffold_junctions
        if junction.kind.value == "SELF_SEAM" and junction.matched_chain_id is not None
    }
    for chain_id in sorted(self_seams):
        lengths = []
        for pc in topology.patch_chains.values():
            if str(pc.chain_id) != chain_id:
                continue
            total = sum(
                e.length for e in evidence_by_id.values() if str(e.patch_chain_id) == str(pc.id)
            )
            lengths.append(total)
        if len(lengths) == 2 and abs(lengths[0] - lengths[1]) > AXIS_PARALLEL_TOLERANCE:
            mismatches.append(f"{chain_id}:{lengths[0]:.6f}!={lengths[1]:.6f}")
    return mismatches
