"""
Layer: 5 - Runtime

Rules:
- Selection-wide skeleton solve per docs/phases/G5a_skeleton_runtime.md.
- Solve nodes are occurrence-level; cut seam sides stay split, stitched
  seam sides are unioned by shared source vertex.
- One length equation per RUN connecting its OWN endpoints.
- Island lines are the pieces of the Layer 3 rail cut by the island (its runs
  and stitched hinges): a family that crosses a cut seam splits into several
  island lines (plan Slice Q).
- Axis roles and run orientation come from the island's unfolded frame
  (stitch-tree parallel transport) when every island patch is planar;
  an island without one bipartitions its lines into axes by the right
  corners of its patch surfaces (Layer 3 RunCornerRelation), takes
  in-line run signs from its ordered island rails and one sign per line
  from the handedness of those right corners (convex turns left, reflex
  right); an unordered rail or a line the corners contradict stays
  unsigned with a diagnostic, and a signed axis line the corners do not
  tie to the island's longest line is reported. No world axes; roles and
  signs read no 3D directions (the axis solve still normalizes equations
  between the same two cross components by a 3D dot).
- A Layer 4 STRAIGHT_STRIP FeatureConstraint (the only feature channel,
  G0 DD-26) lays an island of exactly its one patch as a rectangle: the
  constraint's loop order gives axes and signs, its target lengths scale the
  runs. A constraint on a patch that shares its island is not applied and
  the island gets a diagnostic. Layer 5 recognises no strips itself.
- Island rails: Layer 3 cuts each family's ScaffoldRail by the island (its
  runs and stitched hinges) and orders the pieces; Layer 5 checks them
  against the unfolded frame and never orders a line itself.
- The per-axis solve is axis_solve.py: every equation group has its own
  gauge; a framed island anchors each group to its frame coordinates.
- Contradictions -> UNCONSTRAINED + diagnostics, never silent smearing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from math import pi
from typing import Any, Mapping

from scaffold_core.layer_2_geometry.measures import EPSILON, cross, dot, normalize
from scaffold_core.layer_3_relations.model import PatchChainEndpointRole, RunCornerKind, ScaffoldRailSegment
from scaffold_core.layer_3_relations.scaffold_rails import cut_scaffold_rail, rail_member_endpoints
from scaffold_core.layer_4_features.model import FeatureConstraintKind
from scaffold_core.layer_5_runtime.axis_solve import RESIDUAL_TOLERANCE_PER_SPAN, AxisSolve, solve_axis
from scaffold_core.layer_5_runtime.islands import (
    PLANAR_PATCH_MIN_NORMAL_DOT,
    IslandAssembly,
    SeamRigidity,
    chain_axis,
    compose,
    identity,
    is_rigid_seam,
    rotate,
    rotation_about,
    seam_rigidity,
    unfold_rotation,
)

# A run takes an axis in the rigid unfolded frame only within the planar
# tolerance angle (~5 degrees, plan Slice S); steeper runs stay OBLIQUE.
AXIS_CLASS_MIN_COS = PLANAR_PATCH_MIN_NORMAL_DOT
NODE_FRAME_TOLERANCE = 1e-6  # relative to the island extent
UNFOLDED_FRAME = "UNFOLDED"
FRAME_FREE = "FRAME_FREE"
STRIP_LAYOUT = "STRIP"  # an applied STRAIGHT_STRIP FeatureConstraint
_STRIP_AXIS_UNIT = {"AXIS_A": (1.0, 0.0, 0.0), "AXIS_B": (0.0, 1.0, 0.0)}


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
    strip_by_island, strip_notes_by_island = _strip_constraints_by_island(context, assembly)
    skeletons = []
    for island in assembly.islands:
        skeletons.append(_island_skeleton(
            island, assembly, relations, geometry, lookups,
            strip_by_island.get(island.id), strip_notes_by_island.get(island.id, ()),
        ))
    return tuple(skeletons)


def _strip_constraints_by_island(context: Any, assembly: IslandAssembly):
    """STRAIGHT_STRIP constraints that apply, and notes for those that do not.

    A constraint applies only to an island made of its one patch; otherwise
    the island gets a diagnostic naming the patch (never silently dropped).
    """

    features = getattr(context, "feature_snapshot", None)
    if features is None:
        return {}, {}
    island_by_id = {island.id: island for island in assembly.islands}
    applied: dict[str, Any] = {}
    notes: dict[str, list[str]] = {}
    for constraint in features.constraints:
        if constraint.kind is not FeatureConstraintKind.STRAIGHT_STRIP:
            continue
        patch_id = str(constraint.patch_id)
        island_id = assembly.island_by_patch_id.get(patch_id)
        if island_id is None:
            continue
        if tuple(island_by_id[island_id].patch_ids) == (patch_id,):
            applied[island_id] = constraint
        else:
            notes.setdefault(island_id, []).append(
                f"strip constraint not applied, patch shares its island: {patch_id}"
            )
    return applied, {island_id: tuple(messages) for island_id, messages in notes.items()}


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


def _island_skeleton(island, assembly, relations, geometry, lookups, strip=None, strip_notes=()):
    diagnostics: list[str] = list(strip_notes)
    patch_ids = set(island.patch_ids)
    runs = tuple(e for e in lookups.evidence_by_id.values() if str(e.patch_id) in patch_ids)
    node_by_run_end, vertex_by_run_end = _node_map(island, runs, relations, lookups)
    for run_id, role in sorted(set(node_by_run_end) - set(vertex_by_run_end)):
        diagnostics.append(
            f"run end on a seam-cut mid-chain vertex touches both seam sides: {run_id}:{role} -> unpinned"
        )
    rail_segments = _island_rail_segments(island, runs, lookups)
    line_of = _lines_from_segments(rail_segments)
    strip_layout = None if strip is None else _strip_layout(strip, runs, node_by_run_end, diagnostics)
    frame = None if strip_layout is not None else _unfolded_frame(island, assembly, geometry, lookups)
    length_of = None
    frame_coordinates = {"AXIS_A": None, "AXIS_B": None}
    if strip_layout is not None:
        roles, signs, direction_of, length_of = strip_layout
        mismatches = ()
        drift = None  # no frame: the solve measures drift along each axis
    elif frame is None:
        axis_by_line = _bipartition_families(runs, line_of, relations.run_corner_relations, diagnostics)
        roles = {
            e.id: axis_by_line.get(line_of.get(e.id), "OBLIQUE")
            for e in runs
        }
        signs = _rail_signs(rail_segments, line_of, diagnostics)
        _orient_lines_by_corners(runs, line_of, axis_by_line, signs, relations.run_corner_relations, diagnostics)
        direction_of = {e.id: e.direction for e in runs}
        mismatches: tuple[str, ...] = ()
        drift = None  # no frame: the solve measures drift along each axis
    else:
        framed = tuple(e for e in runs if str(e.patch_id) in frame.rotation_by_patch)
        direction_of = {e.id: e.direction for e in runs}
        direction_of.update({
            e.id: _rotate(frame.rotation_by_patch[str(e.patch_id)], e.direction) for e in framed
        })
        for patch_id in sorted(patch_ids - set(frame.rotation_by_patch)):
            diagnostics.append(f"patch outside the rigid island frame: {patch_id} -> OBLIQUE")
        drift = RESIDUAL_TOLERANCE_PER_SPAN * _frame_extent(frame, framed, lookups.position_of_source)
        roles, signs = _frame_roles_and_signs(
            runs, framed, line_of, direction_of, frame.normal, diagnostics, drift
        )
        mismatches = _node_frame_mismatches(frame, framed, node_by_run_end, lookups.position_of_source)
        axes = _frame_axes(framed, line_of, direction_of, frame.normal)
        if axes is not None:
            frame_coordinates = _frame_coordinates(
                frame, framed, node_by_run_end, lookups.position_of_source, axes
            )
    # A strip island takes its axes from the constraint, not from its lines:
    # the rail/line check does not apply to it.
    rail_conflicts = (
        () if strip_layout is not None
        else _island_rail_conflicts(rail_segments, line_of, roles, signs, frame is not None)
    )
    axis_a = solve_axis(
        "AXIS_A", runs, roles, signs, node_by_run_end, diagnostics, direction_of, drift, length_of,
        frame_coordinates["AXIS_A"],
    )
    axis_b = solve_axis(
        "AXIS_B", runs, roles, signs, node_by_run_end, diagnostics, direction_of, drift, length_of,
        frame_coordinates["AXIS_B"],
    )
    # A node with no equation on either axis is not on the skeleton: the
    # frame alone would pin it, so it keeps no coordinate (stays fabric).
    frame_only = axis_a.frame_only_nodes & axis_b.frame_only_nodes
    if frame_only:
        axis_a, axis_b = (
            replace(solve, coordinate_by_node={
                node: value for node, value in solve.coordinate_by_node.items() if node not in frame_only
            })
            for solve in (axis_a, axis_b)
        )
    if strip_layout is not None:
        layout = STRIP_LAYOUT
    else:
        layout = FRAME_FREE if frame is None else UNFOLDED_FRAME
    return IslandSkeleton(
        island.id, node_by_run_end, roles, axis_a, axis_b, tuple(diagnostics),
        line_by_run=line_of,
        orientation_by_run=signs,
        frame=layout,
        node_frame_mismatches=mismatches,
        vertex_by_run_end=vertex_by_run_end,
        rail_segments=rail_segments,
        rail_frame_conflicts=rail_conflicts,
    )


def _strip_layout(strip, runs, node_by_run_end, diagnostics):
    """Axis roles, signs, directions and run lengths of a STRAIGHT_STRIP island.

    The constraint lists the four uses in loop order. Uses at positions 0 and
    2 share one axis, 1 and 3 the other; the pair with the longer target is
    AXIS_A. Runs follow the loop direction, so walking the loop from the first
    AXIS_A use gives +A, +B, -A, -B and the rectangle closes unmirrored. Each
    run's length is scaled by target / use length, so opposite sides come out
    equal. Returns None, with a diagnostic, when a use has no runs or the
    uses do not close the loop in the stated order (the END node of use i is
    the START node of use i+1); the island then keeps its normal layout.
    """

    runs_by_use: dict[str, list] = {}
    for e in runs:
        runs_by_use.setdefault(str(e.patch_chain_id), []).append(e)
    uses = [str(pc_id) for pc_id in strip.patch_chain_ids]
    if len(uses) != 4 or any(sum(e.length for e in runs_by_use.get(use, ())) <= EPSILON for use in uses):
        diagnostics.append(f"strip constraint not applied, a side has no runs: {strip.patch_id}")
        return None
    if not _strip_uses_close(uses, runs_by_use, node_by_run_end):
        diagnostics.append(f"strip constraint not applied, its uses do not close the loop: {strip.patch_id}")
        return None
    first_a = 0 if strip.target_lengths[0] >= strip.target_lengths[1] else 1
    roles = {e.id: "OBLIQUE" for e in runs}
    signs: dict[str, float] = {}
    direction_of = {e.id: e.direction for e in runs}
    length_of: dict[str, float] = {}
    for position, use in enumerate(uses):
        step = (position - first_a) % 4
        role = "AXIS_A" if step % 2 == 0 else "AXIS_B"
        sign = 1.0 if step < 2 else -1.0
        use_runs = runs_by_use[use]
        scale = strip.target_lengths[position % 2] / sum(e.length for e in use_runs)
        for e in use_runs:
            roles[e.id] = role
            signs[e.id] = sign
            length_of[e.id] = e.length * scale
            direction_of[e.id] = tuple(sign * c for c in _STRIP_AXIS_UNIT[role])
    return roles, signs, direction_of, length_of


def _strip_uses_close(uses, runs_by_use, node_by_run_end) -> bool:
    """The uses, in the constraint's order, chain END -> START around the loop.

    A use's runs follow the loop direction, so its start node is the one
    run START that no run of the use ends on, and its end node vice versa.
    """

    ends_of_use = []
    for use in uses:
        starts = [node_by_run_end[(e.id, "START")] for e in runs_by_use[use]]
        ends = [node_by_run_end[(e.id, "END")] for e in runs_by_use[use]]
        open_starts = [node for node in starts if node not in ends]
        open_ends = [node for node in ends if node not in starts]
        if len(open_starts) != 1 or len(open_ends) != 1:
            return False
        ends_of_use.append((open_starts[0], open_ends[0]))
    return all(ends_of_use[i][1] == ends_of_use[(i + 1) % len(uses)][0] for i in range(len(uses)))


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


def _lines_from_segments(segments) -> dict[str, str]:
    """Island lines are the pieces of the island's rail cut (plan Slice Q).

    A line id is the family id plus the smallest member id of its piece.
    """

    line_of: dict[str, str] = {}
    for segment in segments:
        members = segment.ordered_member_directional_evidence_ids
        line_id = f"{segment.direction_family_id}@{min(members)}"
        for member in members:
            line_of[member] = line_id
    return line_of


def _rail_signs(segments, line_of, diagnostics) -> dict[str, float]:
    """In-line run signs of an island without a rigid frame (plan Slice Q).

    Every ordered island rail supplies its transported signs; Layer 5 never
    orders a line itself (G0 DD-47). A branched rail, or a loop the island
    leaves closed, stays unsigned with a diagnostic, and its runs add no
    length equations.
    """

    signs: dict[str, float] = {}
    for segment in segments:
        members = segment.ordered_member_directional_evidence_ids
        if not segment.is_ordered:
            diagnostics.append(f"unordered island rail: {line_of[members[0]]} -> unsigned")
            continue
        for member in members:
            signs[member] = float(segment.orientation_sign_by_member[member])
    return signs


def _island_rail_conflicts(segments, line_of, roles, signs, framed: bool) -> tuple[str, ...]:
    """Check the island rails against the island lines and the unfolded frame.

    Island lines are the cut segments, so every line with more than one run is
    exactly one rail segment (a guard). In a framed island an ordered
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
        for child, chain_id in sorted(tree.get(parent, ())):
            if child in rotation or not is_rigid_seam(rigidity, chain_id, parent, child):
                continue
            rotation[child] = unfold_rotation(rigidity, geometry, chain_id, parent, child, rotation[parent])
            hinge = geometry.chain_facts[chain_id].segments[0].start_position
            parent_hinge = _rotate(rotation[parent], hinge)
            child_hinge = _rotate(rotation[child], hinge)
            offset[child] = tuple(parent_hinge[i] + offset[parent][i] - child_hinge[i] for i in range(3))
            pending.append(child)
    return _IslandFrame(rotation, offset, normalize(facts[root].normal))


def _frame_axes(framed, line_of, direction_of, normal):
    """AXIS_A along the longest island line's longest run, AXIS_B = normal x AXIS_A.

    None when no framed run lies on an island line.
    """

    length_by_line: dict[str, float] = {}
    runs_by_line: dict[str, list] = {}
    for e in framed:
        line_id = line_of.get(e.id)
        if line_id is None:
            continue
        length_by_line[line_id] = length_by_line.get(line_id, 0.0) + e.length
        runs_by_line.setdefault(line_id, []).append(e)
    if not length_by_line:
        return None
    seed = sorted(length_by_line, key=lambda line_id: (-length_by_line[line_id], line_id))[0]
    seed_run = max(runs_by_line[seed], key=lambda e: (e.length, e.id))
    axis_a = normalize(direction_of[seed_run.id])
    return axis_a, normalize(cross(normal, axis_a))


def _frame_roles_and_signs(runs, framed, line_of, direction_of, normal, diagnostics, drift=None):
    """Island-line axis roles and run orientation in the unfolded frame.

    AXIS_A follows the longest island line; AXIS_B = normal x AXIS_A keeps the
    island unmirrored. A run's sign says whether it points along or against its
    axis. A line whose framed members disagree is not straight in the island
    frame and degrades to OBLIQUE with a diagnostic. Runs outside the frame
    stay OBLIQUE.
    """

    roles = {e.id: "OBLIQUE" for e in runs}
    signs = {e.id: 1.0 for e in runs}
    axes = _frame_axes(framed, line_of, direction_of, normal)
    if axes is None:
        return roles, signs
    axis_a, axis_b = axes
    runs_by_line: dict[str, list] = {}
    for e in framed:
        if line_of.get(e.id) is not None:
            runs_by_line.setdefault(line_of[e.id], []).append(e)
    for line_id in sorted(runs_by_line):
        members = runs_by_line[line_id]
        member_roles = set()
        jogs = []
        for e in members:
            direction = normalize(direction_of[e.id])
            along_a, along_b = dot(direction, axis_a), dot(direction, axis_b)
            if drift is not None and e.length * min(abs(along_a), abs(along_b)) > drift:
                jogs.append(e)  # a jog: it leaves its axis by more than drift
            elif abs(along_a) >= AXIS_CLASS_MIN_COS:
                member_roles.add("AXIS_A")
                signs[e.id] = 1.0 if along_a > 0.0 else -1.0
            elif abs(along_b) >= AXIS_CLASS_MIN_COS:
                member_roles.add("AXIS_B")
                signs[e.id] = 1.0 if along_b > 0.0 else -1.0
            else:
                member_roles.add("OBLIQUE")
        if len(member_roles) == 1:
            role = next(iter(member_roles))
        elif not member_roles:
            role = "OBLIQUE"  # every member leaves its axis: an oblique line
        else:
            role = "OBLIQUE"
            diagnostics.append(f"island line not straight in the unfolded frame: {line_id} -> OBLIQUE")
        for e in members:
            roles[e.id] = role
        for e in jogs:
            if role != "OBLIQUE":
                diagnostics.append(f"island line jogs in the unfolded frame: {e.id} -> OBLIQUE")
            roles[e.id] = "OBLIQUE"
    return roles, signs


def _frame_extent(frame, runs, position_of_source) -> float:
    """Largest coordinate range of the framed run ends in the unfolded frame."""

    points = []
    for e in runs:
        rotation = frame.rotation_by_patch[str(e.patch_id)]
        offset = frame.offset_by_patch[str(e.patch_id)]
        for source_vertex in (e.start_source_vertex_id, e.end_source_vertex_id):
            rotated = _rotate(rotation, position_of_source[str(source_vertex)])
            points.append(tuple(rotated[i] + offset[i] for i in range(3)))
    if not points:
        return 0.0
    return max(max(point[i] for point in points) - min(point[i] for point in points) for i in range(3))


def _frame_points_by_node(frame, runs, node_by_run_end, position_of_source) -> dict[str, list]:
    """Unfolded frame positions of each solve node, one per framed run end."""

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
    return points_by_node


def _frame_coordinates(frame, runs, node_by_run_end, position_of_source, axes):
    """Each framed node's mean unfolded position projected on AXIS_A and AXIS_B.

    The axis solve anchors every equation group to these coordinates, so all
    groups of a framed island share the frame's origin.
    """

    coordinates: dict[str, dict[str, float]] = {"AXIS_A": {}, "AXIS_B": {}}
    for node, points in _frame_points_by_node(frame, runs, node_by_run_end, position_of_source).items():
        mean = tuple(sum(point[i] for point in points) / len(points) for i in range(3))
        for axis_name, axis in zip(("AXIS_A", "AXIS_B"), axes):
            coordinates[axis_name][node] = dot(mean, axis)
    return coordinates


def _node_frame_mismatches(frame, runs, node_by_run_end, position_of_source) -> tuple[str, ...]:
    """Solve nodes whose occurrences sit apart in the rigid unfolded frame."""

    points_by_node = _frame_points_by_node(frame, runs, node_by_run_end, position_of_source)
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


def _bipartition_families(runs, family_of, run_corner_relations, diagnostics):
    """Axis classes via right corners on the patch surface (frame-free).

    Derivation for curved islands, which have no rigid unfolded frame. Two
    island lines are orthogonal iff two of their runs, both in this island,
    meet at a Layer 3 RunCornerRelation of kind RIGHT: a right corner of one
    patch's own surface (convex or reflex). The seed (longest) line is AXIS_A;
    lines meeting it at a right corner are AXIS_B, and so on by BFS.
    Contradictions degrade the line to OBLIQUE with a diagnostic - never
    silently forced - and an OBLIQUE line passes no axis to its neighbours.
    """

    length_by_family: dict[str, float] = {}
    for e in runs:
        family_id = family_of.get(e.id)
        if family_id is None:
            continue
        length_by_family[family_id] = length_by_family.get(family_id, 0.0) + e.length
    if not length_by_family:
        return {}
    island_run_ids = {e.id for e in runs}
    edges: dict[str, set[str]] = {}
    for corner in run_corner_relations:
        if corner.kind is not RunCornerKind.RIGHT:
            continue
        first_id, second_id = corner.first_directional_evidence_id, corner.second_directional_evidence_id
        if first_id not in island_run_ids or second_id not in island_run_ids:
            continue
        fam_a, fam_b = family_of.get(first_id), family_of.get(second_id)
        if fam_a is None or fam_b is None or fam_a == fam_b:
            continue
        edges.setdefault(fam_a, set()).add(fam_b)
        edges.setdefault(fam_b, set()).add(fam_a)
    seed = sorted(length_by_family, key=lambda fid: (-length_by_family[fid], fid))[0]
    axis_by_family: dict[str, str] = {seed: "AXIS_A"}
    pending = [seed]
    while pending:
        current = pending.pop()
        if axis_by_family[current] == "OBLIQUE":
            continue
        opposite = "AXIS_B" if axis_by_family[current] == "AXIS_A" else "AXIS_A"
        for neighbor in sorted(edges.get(current, ())):
            if neighbor not in axis_by_family:
                axis_by_family[neighbor] = opposite
                pending.append(neighbor)
            elif axis_by_family[neighbor] != opposite:
                diagnostics.append(f"axis bipartition conflict: {neighbor} -> OBLIQUE")
                axis_by_family[neighbor] = "OBLIQUE"
    return axis_by_family


def _orient_lines_by_corners(runs, line_of, axis_by_line, signs, run_corner_relations, diagnostics):
    """One sign factor per island line from the handedness of right corners.

    Frame-free islands only. The rails fix each line's in-line run signs; the
    factor of a whole line is unknown. At a Layer 3 RunCornerRelation of kind
    RIGHT the run whose role is END arrives at the corner and the run whose
    role is START leaves it, both along the patch's boundary loop, which
    follows the face winding. In an unmirrored layout a convex corner turns
    left and a reflex corner turns right, so with a sign s per run
    (coordinate(END) - coordinate(START) = s * length):
    s(arriving) * s(leaving) = +1 when (arriving is AXIS_A) == convex, else -1.
    That fixes the product of the two lines' factors. Factors propagate by
    BFS from the longest line (tie: id), each corner read once. A line
    given two different factors is a conflict: its runs lose their signs (no
    length equations) and the island gets one diagnostic per such line. A
    signed axis line that the corners do not tie to the longest line keeps
    its rail signs, with a diagnostic: its direction against the rest of the
    island is unknown. No 3D directions are read.
    """

    island_run_ids = {e.id for e in runs}
    length_by_line: dict[str, float] = {}
    for e in runs:
        line_id = line_of.get(e.id)
        if line_id is not None:
            length_by_line[line_id] = length_by_line.get(line_id, 0.0) + e.length
    links: dict[str, list[tuple[str, float, int]]] = {}
    for index, corner in enumerate(run_corner_relations):
        if corner.kind is not RunCornerKind.RIGHT:
            continue
        run_by_role = {
            corner.first_endpoint_role: corner.first_directional_evidence_id,
            corner.second_endpoint_role: corner.second_directional_evidence_id,
        }
        arriving = run_by_role.get(PatchChainEndpointRole.END)
        leaving = run_by_role.get(PatchChainEndpointRole.START)
        if arriving is None or leaving is None:
            continue
        if not {arriving, leaving} <= island_run_ids or arriving not in signs or leaving not in signs:
            continue
        arriving_line, leaving_line = line_of.get(arriving), line_of.get(leaving)
        arriving_axis = axis_by_line.get(arriving_line)
        if {arriving_axis, axis_by_line.get(leaving_line)} != {"AXIS_A", "AXIS_B"}:
            continue
        convex = corner.interior_angle_sum < pi
        wanted = 1.0 if (arriving_axis == "AXIS_A") == convex else -1.0
        relative = wanted * signs[arriving] * signs[leaving]
        links.setdefault(arriving_line, []).append((leaving_line, relative, index))
        links.setdefault(leaving_line, []).append((arriving_line, relative, index))
    factor_by_line: dict[str, float] = {}
    conflicts: set[str] = set()
    read: set[int] = set()
    longest_first = sorted(length_by_line, key=lambda line_id: (-length_by_line[line_id], line_id))
    tied: set[str] = set()  # the lines the corners tie to the longest linked line
    for seed in longest_first:
        if seed not in links or seed in factor_by_line:
            continue
        first_group = not factor_by_line
        factor_by_line[seed] = 1.0
        pending = deque([seed])
        while pending:
            current = pending.popleft()
            for neighbor, relative, index in sorted(links[current]):
                if index in read:
                    continue
                read.add(index)
                expected = factor_by_line[current] * relative
                if neighbor not in factor_by_line:
                    factor_by_line[neighbor] = expected
                    pending.append(neighbor)
                elif factor_by_line[neighbor] != expected:
                    conflicts.add(neighbor)
        if first_group:
            tied = set(factor_by_line)
    for line_id in sorted(conflicts):
        diagnostics.append(f"corner handedness conflict on island line: {line_id} -> unsigned")
    signed_axis_lines = {
        line_of[e.id] for e in runs
        if e.id in signs and axis_by_line.get(line_of.get(e.id)) in ("AXIS_A", "AXIS_B")
    }
    if not tied:  # no corner links at all: the longest signed axis line stands for itself
        tied = set(next(([line_id] for line_id in longest_first if line_id in signed_axis_lines), ()))
    for line_id in sorted(signed_axis_lines - tied):
        diagnostics.append(f"island line not tied to the longest line by right corners: {line_id}")
    for e in runs:
        line_id = line_of.get(e.id)
        if e.id not in signs or line_id is None:
            continue
        if line_id in conflicts:
            del signs[e.id]
        elif factor_by_line.get(line_id, 1.0) < 0.0:
            signs[e.id] = -signs[e.id]


_chain_axis = chain_axis
_identity = identity
_rotation = rotation_about
_compose = compose
_rotate = rotate
