"""
Layer: 5 - Runtime

Rules:
- Assemble the pinned UV skeleton output model and validation invariants.
- Entry point run_skeleton_solve orchestrates islands -> skeleton -> pins.
- Vertices without both axis coordinates stay unpinned (conformal fabric).
- Stations: every inner source vertex of an axis run whose two ends have a
  UV is pinned on the straight UV segment between them, at its arc-length
  fraction along the run. Its identity is its occurrence on the run's own
  patch side; a run-end pin is never overridden.
- A ladder island (a STRAIGHT_LADDER constraint) pins every boundary vertex
  occurrence at the place its constraint gives it; it has no stations.
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
    vertex_id: str  # own topology occurrence (DD-37): seam sides differ


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
    node_frame_mismatches: tuple[str, ...] = ()
    vertex_by_face_corner: Mapping[tuple[str, str], str] = field(default_factory=dict)
    rail_frame_conflicts: tuple[str, ...] = ()


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
    # (face, source vertex) -> the corner's own occurrence, from the Layer 2
    # patch-side face fans: each seam side has its own fan.
    vertex_by_face_corner = {
        (str(face_id), str(fan.source_vertex_id)): str(fan.vertex_id)
        for fan in context.geometry_facts.local_face_fan_facts.values()
        for face_id in fan.source_face_ids
    }
    for skeleton in skeletons:
        residual_max = max(residual_max, skeleton.axis_a.residual_max, skeleton.axis_b.residual_max)
        diagnostics.extend(skeleton.diagnostics)
        island_vertices, island_violations, width = _island_vertices(
            skeleton, evidence_by_id, offset_u, context.geometry_facts, vertex_by_face_corner, diagnostics
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
        node_frame_mismatches=tuple(
            f"{skeleton.island_id}:{node}"
            for skeleton in skeletons
            for node in skeleton.node_frame_mismatches
        ),
        vertex_by_face_corner=vertex_by_face_corner,
        rail_frame_conflicts=tuple(
            f"{skeleton.island_id}:{conflict}"
            for skeleton in skeletons
            for conflict in skeleton.rail_frame_conflicts
        ),
    )


def _island_vertices(skeleton, evidence_by_id, offset_u, geometry, vertex_by_face_corner, diagnostics):
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
        vertex_id = skeleton.vertex_by_run_end.get((evidence_id, role))
        if uv is None or vertex_id is None:
            continue
        evidence = evidence_by_id[evidence_id]
        source_vertex = str(evidence.start_source_vertex_id if role == "START" else evidence.end_source_vertex_id)
        shifted = (uv[0] - min_u + offset_u, uv[1])
        # Keyed per vertex occurrence so both sides of a seam keep their own UV.
        vertices[(vertex_id, str(evidence.patch_id))] = PinnedVertex(
            source_vertex_id=source_vertex,
            island_id=skeleton.island_id,
            patch_id=str(evidence.patch_id),
            uv=shifted,
            pinned=True,
            vertex_id=vertex_id,
        )
    # A ladder island pins every boundary vertex where its constraint places
    # it, so no station is derived from arc length there.
    for (vertex_id, patch_id), (source_vertex, uv) in skeleton.ladder_pins.items():
        vertices[(vertex_id, patch_id)] = PinnedVertex(
            source_vertex_id=source_vertex,
            island_id=skeleton.island_id,
            patch_id=patch_id,
            uv=(uv[0] - min_u + offset_u, uv[1]),
            pinned=True,
            vertex_id=vertex_id,
        )
    skipped = _station_pins(
        skeleton, evidence_by_id, uv_by_node, geometry, vertex_by_face_corner, vertices, min_u - offset_u
    )
    if skipped:
        diagnostics.append(
            f"{skeleton.island_id}: {skipped} station vertices without one occurrence on their side -> unpinned"
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


def _station_pins(skeleton, evidence_by_id, uv_by_node, geometry, vertex_by_face_corner, vertices, shift_u):
    """Pin the inner source vertices of axis runs whose two ends have a UV.

    A station divides the straight UV segment between the run's end nodes in
    proportion to arc length along the run (its segment lengths). Its pin is
    the station vertex's occurrence on this run's patch side, read through
    the Layer 2 side faces of its two run segments; a vertex without exactly
    one such occurrence is skipped and counted. Existing pins (run ends, or a
    station placed before) are never overridden. Returns the skipped count.
    """

    skipped = 0
    for evidence_id in sorted(skeleton.axis_role_by_run):
        if skeleton.axis_role_by_run[evidence_id] not in ("AXIS_A", "AXIS_B"):
            continue
        start_node = skeleton.node_by_run_end[(evidence_id, "START")]
        end_node = skeleton.node_by_run_end[(evidence_id, "END")]
        if start_node == end_node:
            continue  # a ring: every station would collapse onto its one node
        start_uv = uv_by_node.get(start_node)
        end_uv = uv_by_node.get(end_node)
        if start_uv is None or end_uv is None:
            continue
        e = evidence_by_id[evidence_id]
        path = _run_path(e, geometry)
        if path is None:
            skipped += max(len(e.segment_indices) - 1, 0)
            continue
        side_faces = geometry.patch_chain_facts[e.patch_chain_id].segment_side_face_ids
        total = sum(segment_length for segment_length, _position, _vertex in path)
        walked = 0.0
        for (segment_length, position, vertex), (_length, next_position, _next) in zip(path, path[1:]):
            walked += segment_length
            occurrences = {
                vertex_by_face_corner.get((str(side_faces[index]), vertex))
                for index in (position, next_position)
                if index < len(side_faces) and side_faces[index] is not None
            } - {None}
            if len(occurrences) != 1 or total <= 0.0:
                skipped += 1
                continue
            key = (next(iter(occurrences)), str(e.patch_id))
            if key in vertices:
                continue
            t = walked / total
            vertices[key] = PinnedVertex(
                source_vertex_id=vertex,
                island_id=skeleton.island_id,
                patch_id=str(e.patch_id),
                uv=(
                    start_uv[0] + t * (end_uv[0] - start_uv[0]) - shift_u,
                    start_uv[1] + t * (end_uv[1] - start_uv[1]),
                ),
                pinned=True,
                vertex_id=key[0],
            )
    return skipped


def _run_path(e, geometry):
    """The run's segments walked from its START vertex to its END vertex.

    Each step is (segment length, segment position in the Chain's segment
    order, source vertex reached). None when the segments are not one path.
    """

    chain_facts = geometry.chain_facts.get(e.parent_chain_id)
    if chain_facts is None:
        return None
    position_by_index = {segment.segment_index: i for i, segment in enumerate(chain_facts.segments)}
    if not e.segment_indices or any(index not in position_by_index for index in e.segment_indices):
        return None
    segments = [chain_facts.segments[position_by_index[index]] for index in e.segment_indices]
    current = str(e.start_source_vertex_id)
    if current not in (str(segments[0].start_source_vertex_id), str(segments[0].end_source_vertex_id)):
        segments.reverse()
    path = []
    for segment in segments:
        ends = (str(segment.start_source_vertex_id), str(segment.end_source_vertex_id))
        if current not in ends:
            return None
        current = ends[1] if current == ends[0] else ends[0]
        path.append((segment.length, position_by_index[segment.segment_index], current))
    if current != str(e.end_source_vertex_id):
        return None
    return path


def _seam_length_mismatches(context, assembly, evidence_by_id):
    relations = context.relation_snapshot
    topology = context.topology_snapshot
    mismatches: list[str] = []
    self_seams = {
        str(junction.matched_chain_id)
        for junction in relations.scaffold_junctions
        if junction.kind.value == "SELF_SEAM" and junction.matched_chain_id is not None
    }
    length_by_patch_chain: dict[str, float] = {}
    for evidence in evidence_by_id.values():
        key = str(evidence.patch_chain_id)
        length_by_patch_chain[key] = length_by_patch_chain.get(key, 0.0) + evidence.length
    patch_chain_ids_by_chain: dict[str, list[str]] = {}
    for pc in topology.patch_chains.values():
        patch_chain_ids_by_chain.setdefault(str(pc.chain_id), []).append(str(pc.id))
    for chain_id in sorted(self_seams):
        lengths = [
            length_by_patch_chain.get(patch_chain_id, 0.0)
            for patch_chain_id in patch_chain_ids_by_chain.get(chain_id, ())
        ]
        if len(lengths) == 2 and abs(lengths[0] - lengths[1]) > AXIS_PARALLEL_TOLERANCE:
            mismatches.append(f"{chain_id}:{lengths[0]:.6f}!={lengths[1]:.6f}")
    return mismatches
