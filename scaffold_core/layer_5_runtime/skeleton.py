"""
Layer: 5 - Runtime

Rules:
- Selection-wide skeleton solve per docs/phases/G5a_skeleton_runtime.md.
- Solve nodes are occurrence-level; cut seam sides stay split, stitched
  seam sides are unioned by shared source vertex.
- One length equation per RUN connecting its OWN endpoints.
- Island lines: a ConnectedDirectionFamily keeps only crossings that stay in
  one patch or pass a hinge stitched in the island; a family that crosses a
  cut seam splits into several island lines.
- Axis roles and run orientation come from the island's unfolded frame
  (stitch-tree parallel transport) when every island patch is planar;
  curved islands keep the provisional frame-free derivation. No world axes.
- Island rails: Layer 3 cuts each family's ScaffoldRail by the island (its
  runs and stitched hinges) and orders the pieces; Layer 5 only checks them
  against the island lines and the unfolded frame, never orders a line.
- Contradictions -> UNCONSTRAINED + diagnostics, never silent smearing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, sin
from typing import Any, Mapping

from scaffold_core.layer_2_geometry.measures import EPSILON, cross, dot, normalize
from scaffold_core.layer_3_relations.model import ScaffoldRailSegment
from scaffold_core.layer_3_relations.scaffold_rails import cut_scaffold_rail, rail_member_endpoints
from scaffold_core.layer_5_runtime.islands import IslandAssembly, SeamRigidity, is_rigid_seam, seam_rigidity

AXIS_CLASS_MIN_COS = 0.92
NODE_FRAME_TOLERANCE = 1e-6  # relative to the island extent
RESIDUAL_TOLERANCE = 1e-5
GAUGE_WEIGHT = 1e6
UNFOLDED_FRAME = "UNFOLDED"
FRAME_FREE = "FRAME_FREE"


@dataclass(frozen=True)
class AxisSolve:
    axis: str
    coordinate_by_node: Mapping[str, float]
    residual_max: float
    unconstrained_components: tuple[int, ...]
    equation_count: int


@dataclass(frozen=True)
class IslandSkeleton:
    island_id: str
    node_by_run_end: Mapping[tuple[str, str], str]
    axis_role_by_run: Mapping[str, str]
    axis_a: AxisSolve
    axis_b: AxisSolve
    diagnostics: tuple[str, ...]
    line_by_run: Mapping[str, str] = field(default_factory=dict)
    orientation_by_run: Mapping[str, float] = field(default_factory=dict)
    frame: str = FRAME_FREE
    node_frame_mismatches: tuple[str, ...] = ()
    vertex_by_run_end: Mapping[tuple[str, str], str] = field(default_factory=dict)
    rail_segments: tuple[ScaffoldRailSegment, ...] = ()
    rail_frame_conflicts: tuple[str, ...] = ()


@dataclass(frozen=True)
class _IslandFrame:
    """Rigid unfolding of a planar island into its root patch plane."""

    rotation_by_patch: Mapping[str, tuple]
    offset_by_patch: Mapping[str, tuple]
    normal: tuple


@dataclass(frozen=True)
class _SelectionLookups:
    """Read-only lookups over the selection, shared by every island solve."""

    evidence_by_id: Mapping[str, Any]
    patch_chain_by_id: Mapping[str, Any]
    source_of_vertex: Mapping[str, str]
    position_of_source: Mapping[str, tuple]
    vertices_of_edge: Mapping[str, frozenset]
    faces_of_edge: Mapping[str, frozenset]
    fan_faces: Mapping[tuple[str, str], frozenset]
    fan_vertices: Mapping[tuple[str, str], frozenset]
    rigidity: SeamRigidity
    family_by_member: Mapping[str, Any] = field(default_factory=dict)
    rail_endpoints: Mapping[str, Any] = field(default_factory=dict)


def build_island_skeletons(context: Any, assembly: IslandAssembly) -> tuple[IslandSkeleton, ...]:
    relations = context.relation_snapshot
    geometry = context.geometry_facts
    lookups = _selection_lookups(context)
    skeletons = []
    for island in assembly.islands:
        skeletons.append(_island_skeleton(island, assembly, relations, geometry, lookups))
    return tuple(skeletons)


def _selection_lookups(context: Any) -> _SelectionLookups:
    relations = context.relation_snapshot
    topology = context.topology_snapshot
    geometry = context.geometry_facts
    source = context.source_snapshot
    evidence = relations.patch_chain_directional_evidence
    faces_of_edge: dict[str, set[str]] = {}
    for face_id, face in source.faces.items():
        for edge_id in face.edge_ids:
            faces_of_edge.setdefault(str(edge_id), set()).add(str(face_id))
    fan_faces: dict[tuple[str, str], set[str]] = {}
    fan_vertices: dict[tuple[str, str], set[str]] = {}
    for fan in geometry.local_face_fan_facts.values():
        fan_faces.setdefault((str(fan.patch_id), str(fan.vertex_id)), set()).update(
            str(face_id) for face_id in fan.source_face_ids
        )
        fan_vertices.setdefault((str(fan.patch_id), str(fan.source_vertex_id)), set()).add(str(fan.vertex_id))
    return _SelectionLookups(
        evidence_by_id={e.id: e for e in evidence},
        patch_chain_by_id={str(pc.id): pc for pc in topology.patch_chains.values()},
        source_of_vertex={
            str(vertex_id): (str(vertex.source_vertex_ids[0]) if vertex.source_vertex_ids else str(vertex_id))
            for vertex_id, vertex in topology.vertices.items()
        },
        position_of_source={str(vertex_id): vertex.position for vertex_id, vertex in source.vertices.items()},
        vertices_of_edge={
            str(edge_id): frozenset(str(vertex_id) for vertex_id in edge.vertex_ids)
            for edge_id, edge in source.edges.items()
        },
        faces_of_edge={edge_id: frozenset(faces) for edge_id, faces in faces_of_edge.items()},
        fan_faces={key: frozenset(faces) for key, faces in fan_faces.items()},
        fan_vertices={key: frozenset(vertices) for key, vertices in fan_vertices.items()},
        rigidity=seam_rigidity(context),
        family_by_member={
            member: family
            for family in relations.connected_direction_families
            for member in family.member_directional_evidence_ids
        },
        rail_endpoints=rail_member_endpoints(relations.run_endpoint_junctions),
    )


def _island_skeleton(island, assembly, relations, geometry, lookups):
    diagnostics: list[str] = []
    patch_ids = set(island.patch_ids)
    runs = tuple(e for e in lookups.evidence_by_id.values() if str(e.patch_id) in patch_ids)
    node_by_run_end, vertex_by_run_end = _node_map(island, runs, relations, lookups)
    for run_id, role in sorted(set(node_by_run_end) - set(vertex_by_run_end)):
        diagnostics.append(
            f"run end on a seam-cut mid-chain vertex touches both seam sides: {run_id}:{role} -> unpinned"
        )
    line_of = _island_lines(island, runs, relations)
    frame = _unfolded_frame(island, assembly, geometry, lookups)
    if frame is None:
        axis_by_line = _bipartition_families(runs, line_of, node_by_run_end, diagnostics)
        roles = {
            e.id: axis_by_line.get(line_of.get(e.id), "OBLIQUE")
            for e in runs
        }
        signs = _orientation_signs(runs, line_of, node_by_run_end)
        _co_orient_axis_families(runs, line_of, axis_by_line, signs, node_by_run_end, diagnostics)
        direction_of = {e.id: e.direction for e in runs}
        mismatches: tuple[str, ...] = ()
    else:
        framed = tuple(e for e in runs if str(e.patch_id) in frame.rotation_by_patch)
        direction_of = {e.id: e.direction for e in runs}
        direction_of.update({
            e.id: _rotate(frame.rotation_by_patch[str(e.patch_id)], e.direction) for e in framed
        })
        for patch_id in sorted(patch_ids - set(frame.rotation_by_patch)):
            diagnostics.append(f"patch outside the rigid island frame: {patch_id} -> OBLIQUE")
        roles, signs = _frame_roles_and_signs(runs, framed, line_of, direction_of, frame.normal, diagnostics)
        mismatches = _node_frame_mismatches(frame, framed, node_by_run_end, lookups.position_of_source)
    rail_segments = _island_rail_segments(island, runs, lookups)
    rail_conflicts = _island_rail_conflicts(rail_segments, line_of, roles, signs, frame is not None)
    axis_a = _solve_axis("AXIS_A", runs, roles, signs, node_by_run_end, diagnostics, direction_of)
    axis_b = _solve_axis("AXIS_B", runs, roles, signs, node_by_run_end, diagnostics, direction_of)
    return IslandSkeleton(
        island.id, node_by_run_end, roles, axis_a, axis_b, tuple(diagnostics),
        line_by_run=line_of,
        orientation_by_run=signs,
        frame=FRAME_FREE if frame is None else UNFOLDED_FRAME,
        node_frame_mismatches=mismatches,
        vertex_by_run_end=vertex_by_run_end,
        rail_segments=rail_segments,
        rail_frame_conflicts=rail_conflicts,
    )


def _island_rail_segments(island, runs, lookups) -> tuple[ScaffoldRailSegment, ...]:
    """Cut every family's ScaffoldRail by this island (DD-47 draft loop policy).

    Layer 3 orders the pieces; the island only supplies the cut: its runs and
    the hinges it stitches. A loop opens exactly where the island cuts it.
    """

    family_by_id: dict[str, Any] = {}
    run_ids_by_family: dict[str, set[str]] = {}
    for e in runs:
        family = lookups.family_by_member.get(e.id)
        if family is None:
            continue
        family_by_id[family.id] = family
        run_ids_by_family.setdefault(family.id, set()).add(e.id)
    segments = []
    for family_id in sorted(run_ids_by_family):
        segments.extend(cut_scaffold_rail(
            family_by_id[family_id],
            lookups.rail_endpoints,
            run_ids_by_family[family_id],
            island.stitched_chain_ids,
        ))
    return tuple(segments)


def _island_rail_conflicts(segments, line_of, roles, signs, framed: bool) -> tuple[str, ...]:
    """Check the island rails against the island lines and the unfolded frame.

    Both views cut the same family by the same island, so every line with more
    than one run is exactly one rail segment. In a framed island an ordered
    rail runs one way along its axis: the rail sign times the frame sign is the
    same for every axis run of the line.
    """

    segment_index_by_member: dict[str, int] = {}
    for index, segment in enumerate(segments):
        for member in segment.ordered_member_directional_evidence_ids:
            segment_index_by_member[member] = index
    members_by_line: dict[str, set[str]] = {}
    for run_id, line_id in line_of.items():
        members_by_line.setdefault(line_id, set()).add(run_id)
    conflicts: list[str] = []
    for line_id, members in sorted(members_by_line.items()):
        if len(members) < 2:
            continue
        indexes = {segment_index_by_member.get(member) for member in members}
        if (
            len(indexes) != 1
            or None in indexes
            or set(segments[next(iter(indexes))].ordered_member_directional_evidence_ids) != members
        ):
            conflicts.append(f"island rail and island line disagree: {line_id}")
            continue
        segment = segments[next(iter(indexes))]
        if not framed or not segment.is_ordered:
            continue
        products = {
            1 if segment.orientation_sign_by_member[member] * signs.get(member, 0) > 0 else -1
            for member in members
            if roles.get(member) in ("AXIS_A", "AXIS_B") and signs.get(member, 0) != 0
        }
        if len(products) > 1:
            conflicts.append(f"island rail runs against the unfolded frame: {line_id}")
    return tuple(conflicts)


def _island_lines(island, runs, relations) -> dict[str, str]:
    """Split ConnectedDirectionFamilies into island lines.

    A family is one transported line on the surface. Inside an island only
    crossings that stay in one patch or pass a hinge stitched in this island
    keep it one straight line of the island layout, so a family that crosses a
    cut seam splits. A line id is the family id plus the smallest member id of
    its piece.
    """

    run_ids = {e.id for e in runs}
    stitched = set(island.stitched_chain_ids)
    family_of: dict[str, str] = {}
    parents: dict[str, str] = {}

    def find(item: str) -> str:
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    for family in relations.connected_direction_families:
        for member in family.member_directional_evidence_ids:
            if member in run_ids:
                family_of[member] = family.id
                parents[member] = member
        for crossing in family.crossing_records:
            first = crossing.first_directional_evidence_id
            second = crossing.second_directional_evidence_id
            if first not in run_ids or second not in run_ids:
                continue
            same_patch = crossing.first_patch_id == crossing.second_patch_id
            if not same_patch and str(crossing.shared_chain_id) not in stitched:
                continue
            first_root, second_root = find(first), find(second)
            if first_root != second_root:
                parents[max(first_root, second_root)] = min(first_root, second_root)
    return {run_id: f"{family_id}@{find(run_id)}" for run_id, family_id in family_of.items()}


def _unfolded_frame(island, assembly, geometry, lookups) -> _IslandFrame | None:
    """Rigid stitch-tree unfolding of an island without curved patches.

    Each stitched hinge rotates the child patch about the hinge Chain by the
    angle between the patch normals, so the child lands in its parent's plane
    (parallel transport along the island's spanning tree). The frame crosses
    only rigid seams (islands.is_rigid_seam, shared with the island tree):
    a straight Chain (the Layer 3 straight-hinge rule), or a join of coplanar
    patches, which needs no rotation. A warped n-gon or a bent hinge between
    non-coplanar patches has no rotation axis; patches behind it stay outside
    the frame. An island with a curved patch has no rigid frame and keeps the
    frame-free derivation.
    """

    patch_ids = tuple(island.patch_ids)
    rigidity = lookups.rigidity
    if not all(patch_id in rigidity.planar_patch_ids for patch_id in patch_ids):
        return None
    rigid_patch_ids = tuple(patch_id for patch_id in patch_ids if patch_id not in rigidity.warped_patch_ids)
    if not rigid_patch_ids:
        return None
    stitched = set(island.stitched_chain_ids)
    tree: dict[str, list[tuple[str, str]]] = {}
    for decision in assembly.decisions:
        if decision.accepted and decision.chain_id in stitched:
            tree.setdefault(decision.first_patch_id, []).append((decision.second_patch_id, decision.chain_id))
            tree.setdefault(decision.second_patch_id, []).append((decision.first_patch_id, decision.chain_id))
    facts = {patch_id: geometry.patch_facts[patch_id] for patch_id in patch_ids}
    root = max(rigid_patch_ids, key=lambda patch_id: (facts[patch_id].area, patch_id))
    rotation = {root: _identity()}
    offset = {root: (0.0, 0.0, 0.0)}
    pending = [root]
    while pending:
        parent = pending.pop(0)
        parent_normal = normalize(facts[parent].normal)
        for child, chain_id in sorted(tree.get(parent, ())):
            if child in rotation or not is_rigid_seam(rigidity, chain_id, parent, child):
                continue
            if chain_id in rigidity.straight_chain_ids:
                child_normal = normalize(facts[child].normal)
                axis = _chain_axis(geometry, chain_id)
                angle = atan2(dot(axis, cross(child_normal, parent_normal)), dot(child_normal, parent_normal))
                rotation[child] = _compose(rotation[parent], _rotation(axis, angle))
            else:
                rotation[child] = rotation[parent]  # coplanar join over a bent Chain
            hinge = geometry.chain_facts[chain_id].segments[0].start_position
            parent_hinge = _rotate(rotation[parent], hinge)
            child_hinge = _rotate(rotation[child], hinge)
            offset[child] = tuple(parent_hinge[i] + offset[parent][i] - child_hinge[i] for i in range(3))
            pending.append(child)
    return _IslandFrame(rotation, offset, normalize(facts[root].normal))


def _frame_roles_and_signs(runs, framed, line_of, direction_of, normal, diagnostics):
    """Island-line axis roles and run orientation in the unfolded frame.

    AXIS_A follows the longest island line; AXIS_B = normal x AXIS_A keeps the
    island unmirrored. A run's sign says whether it points along or against its
    axis. A line whose framed members disagree is not straight in the island
    frame and degrades to OBLIQUE with a diagnostic. Runs outside the frame
    stay OBLIQUE.
    """

    roles = {e.id: "OBLIQUE" for e in runs}
    signs = {e.id: 1.0 for e in runs}
    length_by_line: dict[str, float] = {}
    runs_by_line: dict[str, list] = {}
    for e in framed:
        line_id = line_of.get(e.id)
        if line_id is None:
            continue
        length_by_line[line_id] = length_by_line.get(line_id, 0.0) + e.length
        runs_by_line.setdefault(line_id, []).append(e)
    if not length_by_line:
        return roles, signs
    seed = sorted(length_by_line, key=lambda line_id: (-length_by_line[line_id], line_id))[0]
    seed_run = max(runs_by_line[seed], key=lambda e: (e.length, e.id))
    axis_a = normalize(direction_of[seed_run.id])
    axis_b = normalize(cross(normal, axis_a))
    for line_id in sorted(runs_by_line):
        members = runs_by_line[line_id]
        member_roles = set()
        for e in members:
            direction = normalize(direction_of[e.id])
            along_a, along_b = dot(direction, axis_a), dot(direction, axis_b)
            if abs(along_a) >= AXIS_CLASS_MIN_COS:
                member_roles.add("AXIS_A")
                signs[e.id] = 1.0 if along_a > 0.0 else -1.0
            elif abs(along_b) >= AXIS_CLASS_MIN_COS:
                member_roles.add("AXIS_B")
                signs[e.id] = 1.0 if along_b > 0.0 else -1.0
            else:
                member_roles.add("OBLIQUE")
        if len(member_roles) == 1:
            role = next(iter(member_roles))
        else:
            role = "OBLIQUE"
            diagnostics.append(f"island line not straight in the unfolded frame: {line_id} -> OBLIQUE")
        for e in members:
            roles[e.id] = role
    return roles, signs


def _node_frame_mismatches(frame, runs, node_by_run_end, position_of_source) -> tuple[str, ...]:
    """Solve nodes whose occurrences sit apart in the rigid unfolded frame."""

    run_by_id = {e.id: e for e in runs}
    points_by_node: dict[str, list] = {}
    for (run_id, role), node in node_by_run_end.items():
        e = run_by_id.get(run_id)
        if e is None:
            continue
        source_vertex = e.start_source_vertex_id if role == "START" else e.end_source_vertex_id
        rotated = _rotate(frame.rotation_by_patch[str(e.patch_id)], position_of_source[str(source_vertex)])
        offset = frame.offset_by_patch[str(e.patch_id)]
        points_by_node.setdefault(node, []).append(tuple(rotated[i] + offset[i] for i in range(3)))
    points = [point for node_points in points_by_node.values() for point in node_points]
    if not points:
        return ()
    extent = max(
        max(point[i] for point in points) - min(point[i] for point in points)
        for i in range(3)
    )
    tolerance = NODE_FRAME_TOLERANCE * max(extent, 1.0)
    mismatched = []
    for node, node_points in sorted(points_by_node.items()):
        spread = max(
            max(point[i] for point in node_points) - min(point[i] for point in node_points)
            for i in range(3)
        )
        if spread > tolerance:
            mismatched.append(node)
    return tuple(mismatched)


def _node_map(island, runs, relations, lookups):
    """Occurrence-level solve nodes (DD-37 does the splitting for us).

    Chain-end nodes are the PatchChain's own occurrence vertex ids: plain
    corners naturally share one occurrence across adjacent patch chains,
    while cut/self-seam sides carry distinct occurrences and stay split -
    closed rims therefore never collapse into contradiction cycles.
    Mid-chain nodes are (source, patch_chain)-scoped; stitched chains
    union both sides by source vertex.
    Also returns each run end's own vertex occurrence, the pin identity.
    """

    patch_chain_by_id = lookups.patch_chain_by_id
    source_of_vertex = lookups.source_of_vertex
    raw: dict[tuple[str, str], str] = {}
    vertex_by_run_end: dict[tuple[str, str], str] = {}
    for e in runs:
        pc = patch_chain_by_id[str(e.patch_chain_id)]
        forward = e.orientation_sign == 1
        # Pick the occurrence whose SOURCE vertex matches the evidence end:
        # pc.start/end ordering is not reliably evidence-oriented.
        pc_start_source = source_of_vertex.get(str(pc.start_vertex_id), str(pc.start_vertex_id))
        pc_end_source = source_of_vertex.get(str(pc.end_vertex_id), str(pc.end_vertex_id))
        ambiguous = pc_start_source == pc_end_source
        # A run end is a chain end when it sits on a PatchChain end vertex. The
        # Chain's segment order can start elsewhere: a closed rim cut by a
        # SEAM_SELF starts its segments at an arbitrary ring vertex.
        chain_end_sources = (pc_start_source, pc_end_source)

        def _occurrence_for(source_vertex: str, prefer_start: bool):
            if not ambiguous:
                if source_vertex == pc_start_source:
                    return pc.start_vertex_id
                if source_vertex == pc_end_source:
                    return pc.end_vertex_id
            # Both PatchChain ends sit on one source vertex (a closed rim cut
            # by a SEAM_SELF): the seam side whose face fan holds the face on
            # the run's end edge is the run's own occurrence.
            touching = _faces_at_run_end(e, source_vertex, lookups)
            sides = {
                occurrence
                for occurrence in (pc.start_vertex_id, pc.end_vertex_id)
                if lookups.fan_faces.get((str(e.patch_id), str(occurrence)), frozenset()) & touching
            }
            if len(sides) == 1:
                return next(iter(sides))
            return pc.start_vertex_id if prefer_start == forward else pc.end_vertex_id

        for role, source_vertex, prefer_start in (
            ("START", str(e.start_source_vertex_id), True),
            ("END", str(e.end_source_vertex_id), False),
        ):
            # A chain end sits on the occurrence picked above. At a mid-chain
            # vertex it is the occurrence whose face fan holds the faces on the
            # run's own edges; a seam cutting the vertex puts both sides there.
            if source_vertex in chain_end_sources:
                occurrences = {_occurrence_for(source_vertex, prefer_start)}
            else:
                touching = _faces_at_run_end(e, source_vertex, lookups)
                occurrences = {
                    occurrence
                    for occurrence in lookups.fan_vertices.get((str(e.patch_id), source_vertex), ())
                    if lookups.fan_faces.get((str(e.patch_id), occurrence), frozenset()) & touching
                }
            if len(occurrences) == 1:
                vertex_by_run_end[(e.id, role)] = str(next(iter(occurrences)))
            node = (
                f"occ:{vertex_by_run_end[(e.id, role)]}:pc:{e.patch_chain_id}"
                if source_vertex in chain_end_sources
                else f"mid:{source_vertex}:pc:{e.patch_chain_id}"
            )
            raw[(e.id, role)] = node

    parents: dict[str, str] = {}

    def find(item: str) -> str:
        parents.setdefault(item, item)
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parents[max(ra, rb)] = min(ra, rb)

    for node in raw.values():
        parents.setdefault(node, node)

    island_patch_set = set(island.patch_ids)
    # Within a loop, adjacent patch chains share their corner occurrence.
    for corner in relations.loop_corners:
        if str(corner.patch_id) not in island_patch_set:
            continue
        union(
            f"occ:{corner.vertex_id}:pc:{corner.previous_patch_chain_id}",
            f"occ:{corner.vertex_id}:pc:{corner.next_patch_chain_id}",
        )

    stitched = set(island.stitched_chain_ids)
    island_patches = set(island.patch_ids)
    uses_by_chain: dict[str, list] = {}
    for pc in patch_chain_by_id.values():
        if str(pc.chain_id) in stitched and str(pc.patch_id) in island_patches:
            uses_by_chain.setdefault(str(pc.chain_id), []).append(pc)
    for chain_id, uses in uses_by_chain.items():
        if len(uses) != 2:
            continue
        first, second = uses
        for end_a in (first.start_vertex_id, first.end_vertex_id):
            source_a = source_of_vertex.get(str(end_a), str(end_a))
            for end_b in (second.start_vertex_id, second.end_vertex_id):
                if source_of_vertex.get(str(end_b), str(end_b)) == source_a:
                    union(f"occ:{end_a}:pc:{first.id}", f"occ:{end_b}:pc:{second.id}")
        mids_by_source: dict[str, list[str]] = {}
        for node in raw.values():
            if node.startswith("mid:") and (node.endswith(f"pc:{first.id}") or node.endswith(f"pc:{second.id}")):
                mids_by_source.setdefault(node.split(":")[1], []).append(node)
        for nodes in mids_by_source.values():
            for node in nodes[1:]:
                union(nodes[0], node)

    return {key: find(node) for key, node in raw.items()}, vertex_by_run_end


def _faces_at_run_end(e, source_vertex: str, lookups) -> frozenset:
    """Source faces on the run's own edges at one of its end vertices."""

    faces: set[str] = set()
    for edge_id in e.source_edge_ids:
        if source_vertex in lookups.vertices_of_edge.get(str(edge_id), frozenset()):
            faces.update(lookups.faces_of_edge.get(str(edge_id), frozenset()))
    return frozenset(faces)


def _bipartition_families(runs, family_of, node_by_run_end, diagnostics):
    """Axis classes via local orthogonality at shared junctions (frame-free).

    Provisional derivation for curved islands, which have no rigid unfolded
    frame. The seed (longest) family is AXIS_A; families meeting it
    orthogonally at a junction are AXIS_B, and so on by BFS. Contradictions
    degrade the family to OBLIQUE with a diagnostic - never silently forced.
    """

    length_by_family: dict[str, float] = {}
    runs_by_node: dict[str, list] = {}
    for e in runs:
        family_id = family_of.get(e.id)
        if family_id is None:
            continue
        length_by_family[family_id] = length_by_family.get(family_id, 0.0) + e.length
        for role in ("START", "END"):
            runs_by_node.setdefault(node_by_run_end[(e.id, role)], []).append(e)
    if not length_by_family:
        return {}
    edges: dict[str, set[str]] = {}
    for node_runs in runs_by_node.values():
        for i, first in enumerate(node_runs):
            for second in node_runs[i + 1:]:
                fam_a, fam_b = family_of.get(first.id), family_of.get(second.id)
                if fam_a is None or fam_b is None or fam_a == fam_b:
                    continue
                if abs(dot(normalize(first.direction), normalize(second.direction))) <= 0.4:
                    edges.setdefault(fam_a, set()).add(fam_b)
                    edges.setdefault(fam_b, set()).add(fam_a)
    seed = sorted(length_by_family, key=lambda fid: (-length_by_family[fid], fid))[0]
    axis_by_family: dict[str, str] = {seed: "AXIS_A"}
    pending = [seed]
    while pending:
        current = pending.pop()
        opposite = "AXIS_B" if axis_by_family[current] == "AXIS_A" else "AXIS_A"
        for neighbor in sorted(edges.get(current, ())):
            if neighbor not in axis_by_family:
                axis_by_family[neighbor] = opposite
                pending.append(neighbor)
            elif axis_by_family[neighbor] != opposite:
                diagnostics.append(f"axis bipartition conflict: {neighbor} -> OBLIQUE")
                axis_by_family[neighbor] = "OBLIQUE"
    return axis_by_family


def _orientation_signs(runs, family_of, node_by_run_end):
    """Head-to-tail orientation along each family rail (frame-free)."""

    signs: dict[str, float] = {}
    runs_by_family: dict[str, list] = {}
    for e in runs:
        family_id = family_of.get(e.id)
        if family_id is not None:
            runs_by_family.setdefault(family_id, []).append(e)
    for family_id, members in runs_by_family.items():
        node_index: dict[str, list] = {}
        for e in members:
            for role in ("START", "END"):
                node_index.setdefault(node_by_run_end[(e.id, role)], []).append((e, role))
        for e in sorted(members, key=lambda item: item.id):
            if e.id in signs:
                continue
            signs[e.id] = 1.0
            queue = [e]
            while queue:
                current = queue.pop()
                for role in ("START", "END"):
                    node = node_by_run_end[(current.id, role)]
                    for other, other_role in node_index.get(node, ()):
                        if other.id in signs:
                            continue
                        same = role != other_role  # END meets START -> same direction
                        signs[other.id] = signs[current.id] * (1.0 if same else -1.0)
                        queue.append(other)
    return signs


def _components(runs, roles, role_name, node_by_run_end):
    parents: dict[str, str] = {}

    def find(item: str) -> str:
        parents.setdefault(item, item)
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    for e in runs:
        start = node_by_run_end[(e.id, "START")]
        end = node_by_run_end[(e.id, "END")]
        parents.setdefault(start, start)
        parents.setdefault(end, end)
        if roles.get(e.id) == role_name:
            ra, rb = find(start), find(end)
            if ra != rb:
                parents[max(ra, rb)] = min(ra, rb)
    return {node: find(node) for node in parents}


def _co_orient_axis_families(runs, family_of, axis_by_family, signs, node_by_run_end, diagnostics):
    """Co-orient parallel rails of one axis through their linking cross runs.

    At a cross (other-axis) run's two end nodes the incident rail
    directions are locally parallel on a developable band, so their dot
    fixes the relative sign between the two rail families.
    """

    runs_by_node: dict[str, list] = {}
    for e in runs:
        for role in ("START", "END"):
            runs_by_node.setdefault(node_by_run_end[(e.id, role)], []).append(e)
    for axis in ("AXIS_A", "AXIS_B"):
        cross_axis = "AXIS_B" if axis == "AXIS_A" else "AXIS_A"
        links: dict[str, dict[str, float]] = {}
        for e in runs:
            family_id = family_of.get(e.id)
            if axis_by_family.get(family_id) != cross_axis:
                continue
            ends = [node_by_run_end[(e.id, "START")], node_by_run_end[(e.id, "END")]]
            rail_hits = []
            for node in ends:
                for other in runs_by_node.get(node, ()):
                    other_family = family_of.get(other.id)
                    if axis_by_family.get(other_family) == axis:
                        rail_hits.append((other_family, other))
                        break
            if len(rail_hits) == 2 and rail_hits[0][0] != rail_hits[1][0]:
                (fam_a, run_a), (fam_b, run_b) = rail_hits
                oriented_a = tuple(c * signs.get(run_a.id, 1.0) for c in run_a.direction)
                oriented_b = tuple(c * signs.get(run_b.id, 1.0) for c in run_b.direction)
                rel = 1.0 if dot(normalize(oriented_a), normalize(oriented_b)) >= 0.0 else -1.0
                links.setdefault(fam_a, {})[fam_b] = rel
                links.setdefault(fam_b, {})[fam_a] = rel
        flip: dict[str, float] = {}
        for family_id in sorted(links):
            if family_id in flip:
                continue
            flip[family_id] = 1.0
            queue = [family_id]
            while queue:
                current = queue.pop()
                for neighbor, rel in links.get(current, {}).items():
                    expected = flip[current] * rel
                    if neighbor not in flip:
                        flip[neighbor] = expected
                        queue.append(neighbor)
                    elif flip[neighbor] != expected:
                        diagnostics.append(f"rail co-orientation conflict at {neighbor}")
        for e in runs:
            family_id = family_of.get(e.id)
            factor = flip.get(family_id)
            if factor is not None and factor < 0.0:
                signs[e.id] = -signs.get(e.id, 1.0)


def _solve_axis(axis_name, runs, roles, signs, node_by_run_end, diagnostics, direction_of=None):
    """P7 semantics: the A coordinate lives on COLUMN components (nodes
    connected by AXIS_B runs share one A value) and is constrained by
    AXIS_A run lengths; symmetric for B on ROW components.

    direction_of supplies run directions in the island frame when one exists.
    """

    own_role = "AXIS_A" if axis_name == "AXIS_A" else "AXIS_B"
    cross_role = "AXIS_B" if axis_name == "AXIS_A" else "AXIS_A"
    component_of = _components(runs, roles, cross_role, node_by_run_end)
    equations = []
    for e in runs:
        if roles.get(e.id) != own_role:
            continue
        start = component_of.get(node_by_run_end[(e.id, "START")])
        end = component_of.get(node_by_run_end[(e.id, "END")])
        if start is None or end is None or start == end:
            continue
        equations.append([start, end, signs.get(e.id, 1.0) * e.length, e.id, e])
    # Runs connecting the same two cross-components are mutually parallel
    # on a developable region: normalize their signs to the group's first
    # run so parallel columns/rails cannot contradict each other.
    reference_by_pair = {}
    for equation in equations:
        start, end, value, _eid, e = equation
        pair = (min(start, end), max(start, end))
        direction = e.direction if direction_of is None else direction_of[e.id]
        oriented = tuple(c * (1.0 if value >= 0.0 else -1.0) for c in direction)
        if pair not in reference_by_pair:
            reference_by_pair[pair] = (oriented, start, end)
            continue
        ref_dir, _ref_start, _ref_end = reference_by_pair[pair]
        # On a developable region runs between the same two rails are
        # parallel: the coordinate grows along the reference direction,
        # so the equation sign follows the dot sign alone.
        if dot(normalize(oriented), normalize(ref_dir)) < 0.0:
            equation[2] = -value
    equations = [(eq[0], eq[1], eq[2], eq[3]) for eq in equations]
    if not equations:
        return AxisSolve(axis_name, {}, 0.0, (), 0)
    coords, residuals = _lstsq(equations)
    bad = [i for i, r in enumerate(residuals) if abs(r) > RESIDUAL_TOLERANCE]
    unconstrained: tuple[int, ...] = ()
    if bad:
        bad_components = {equations[i][0] for i in bad} | {equations[i][1] for i in bad}
        diagnostics.append(
            f"{axis_name}: {len(bad)} contradictory equations -> UNCONSTRAINED components"
        )
        for component in bad_components:
            coords.pop(component, None)
        kept = [
            eq for index, eq in enumerate(equations)
            if index not in set(bad) and eq[0] not in bad_components and eq[1] not in bad_components
        ]
        if kept:
            coords, residuals = _lstsq(kept)
        else:
            residuals = []
        unconstrained = tuple(sorted({index for index in bad}))
    residual_max = max((abs(r) for r in residuals), default=0.0)
    coordinate_by_node = {
        node: coords[component]
        for node, component in component_of.items()
        if component in coords
    }
    return AxisSolve(axis_name, coordinate_by_node, residual_max, unconstrained, len(equations))


def _lstsq(equations):
    nodes = sorted({eq[0] for eq in equations} | {eq[1] for eq in equations})
    index = {node: i for i, node in enumerate(nodes)}
    n = len(nodes)
    ata = [[0.0] * n for _ in range(n)]
    atb = [0.0] * n
    rows = []
    for start, end, value, _eid in equations:
        row = {index[end]: 1.0, index[start]: index[end] != index[start] and -1.0 or 0.0}
        rows.append((index[start], index[end], value))
    for i_start, i_end, value in rows:
        for (a, ca) in ((i_end, 1.0), (i_start, -1.0)):
            atb[a] += ca * value
            for (b, cb) in ((i_end, 1.0), (i_start, -1.0)):
                ata[a][b] += ca * cb
    # gauge: pin first node to zero
    ata[0][0] += GAUGE_WEIGHT
    solution = _solve_dense(ata, atb)
    coords = {node: solution[index[node]] for node in nodes}
    residuals = [coords[end] - coords[start] - value for start, end, value, _eid in equations]
    return coords, residuals


def _solve_dense(matrix, vector):
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            continue
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        a[col] = [v / factor for v in a[col]]
        for row in range(n):
            if row != col and abs(a[row][col]) > 0.0:
                scale = a[row][col]
                a[row] = [rv - scale * cv for rv, cv in zip(a[row], a[col])]
    return [a[i][n] for i in range(n)]


def _chain_axis(geometry, chain_id):
    facts = geometry.chain_facts.get(chain_id)
    if facts is None:
        return (0.0, 0.0, 1.0)
    if facts.chord_length > EPSILON:
        return normalize(facts.chord_direction)
    for segment in facts.segments:
        if segment.length > EPSILON:
            return normalize(segment.direction)
    return (0.0, 0.0, 1.0)


def _identity():
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _rotation(axis, angle):
    x, y, z = normalize(axis)
    c, s, t = cos(angle), sin(angle), 1.0 - cos(angle)
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )


def _compose(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def _rotate(matrix, vector):
    if matrix is None:
        return vector
    return tuple(sum(matrix[i][k] * vector[k] for k in range(3)) for i in range(3))
