"""
Layer: 5 - Runtime

Rules:
- Island assembly: spanning tree of Level A stitch decisions.
- Would-be-interior vertices use raw Layer 2 angle sums; chain endpoints
  with remaining cut incidence are excluded (T-junction rule, G5a).
- SEAM_SELF never stitches; non-tree seams stay cut.
- Rigid seams enter the tree first (plan Slice P): a straight hinge or a
  coplanar join between planar, unwarped patches, so the rigid island
  frame reaches every patch it can; longest seam first in each group.
- Overlap gate (plan Slice U): a rigid stitch stays cut when the unfolded
  part would lie over the island; a non-rigid seam between two rigid parts
  stays cut, because the frame cannot cross it.
- A straightened strip leaves its island (G0 DD-50): a patch with a
  STRAIGHT_STRIP constraint whose stitch candidates are all straight hinges
  stitches to nothing, because straightening keeps a straight side straight
  but would deform a neighbour stitched along a bent side. A strip with a
  bent stitch candidate stays stitched. Layer 4 is read only through
  FeatureConstraint.
- Read-only over lower layers; no UV or semantic roles here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, pi, sin
from typing import Any, Mapping

from scaffold_core.layer_2_geometry.measures import EPSILON, cross, dot, length, normalize
from scaffold_core.layer_3_relations.direction_families import SHARED_CHAIN_HINGE_MAX_RUNS
from scaffold_core.layer_4_features.model import FeatureConstraintKind

STITCH_LEAVING_STRIP_REASON = "a straightened strip leaves its island"
STITCH_DEFECT_TOLERANCE = 1e-3
PLANAR_PATCH_MIN_NORMAL_DOT = 0.996  # every face-fan normal within ~5 degrees of the patch normal
OVERLAP_TOLERANCE = 1e-6  # relative to the selection extent; shared edges only touch


@dataclass(frozen=True)
class StitchDecision:
    chain_id: str
    first_patch_id: str
    second_patch_id: str
    accepted: bool
    reason: str
    vertex_defects: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Island:
    id: str
    patch_ids: tuple[str, ...]
    stitched_chain_ids: tuple[str, ...]


@dataclass(frozen=True)
class IslandAssembly:
    islands: tuple[Island, ...]
    decisions: tuple[StitchDecision, ...]
    island_by_patch_id: Mapping[str, str]


@dataclass(frozen=True)
class SeamRigidity:
    """Which seams a rigid unfolding can cross (plan Slices N and P)."""

    planar_patch_ids: frozenset[str]
    warped_patch_ids: frozenset[str]
    straight_chain_ids: frozenset[str]
    normal_by_patch: Mapping[str, tuple[float, float, float]]


def seam_rigidity(context: Any) -> SeamRigidity:
    """Patch planarity, warp and straight hinges, shared by the island tree and frame."""

    geometry = context.geometry_facts
    evidence = context.relation_snapshot.patch_chain_directional_evidence
    run_count_by_patch_chain: dict[str, int] = {}
    for e in evidence:
        run_count_by_patch_chain[str(e.patch_chain_id)] = run_count_by_patch_chain.get(str(e.patch_chain_id), 0) + 1
    uses_by_chain: dict[str, list[str]] = {}
    for pc in context.topology_snapshot.patch_chains.values():
        uses_by_chain.setdefault(str(pc.chain_id), []).append(str(pc.id))
    return SeamRigidity(
        planar_patch_ids=frozenset(_planar_patch_ids(geometry)),
        warped_patch_ids=frozenset(_warped_patch_ids(geometry, evidence)),
        # The Layer 3 straight-hinge rule (plan Slice L1): every use of the
        # Chain carries at most one directional run.
        straight_chain_ids=frozenset(
            chain_id
            for chain_id, uses in uses_by_chain.items()
            if all(run_count_by_patch_chain.get(use, 0) <= SHARED_CHAIN_HINGE_MAX_RUNS for use in uses)
        ),
        normal_by_patch={str(patch_id): facts.normal for patch_id, facts in geometry.patch_facts.items()},
    )


def is_rigid_seam(rigidity: SeamRigidity, chain_id: str, first_patch_id: str, second_patch_id: str) -> bool:
    """A straight hinge, or a coplanar join, between two planar unwarped patches.

    The rigid island frame crosses exactly these seams; a warped n-gon or a
    bent hinge between non-coplanar patches has no rotation axis.
    """

    for patch_id in (first_patch_id, second_patch_id):
        if patch_id in rigidity.warped_patch_ids or patch_id not in rigidity.planar_patch_ids:
            return False
    if chain_id in rigidity.straight_chain_ids:
        return True
    first_normal = normalize(rigidity.normal_by_patch[first_patch_id])
    second_normal = normalize(rigidity.normal_by_patch[second_patch_id])
    return dot(first_normal, second_normal) >= PLANAR_PATCH_MIN_NORMAL_DOT


def unfold_rotation(rigidity: SeamRigidity, geometry, chain_id: str, parent_id: str, child_id: str, parent_rotation):
    """Rotation that lays the child patch into its parent's unfolded plane.

    A straight hinge rotates the child about the hinge Chain by the angle
    between the patch normals; a coplanar join needs no rotation. Shared by
    the overlap gate and the rigid island frame, so both see one layout.
    """

    if chain_id not in rigidity.straight_chain_ids:
        return parent_rotation
    child_normal = normalize(rigidity.normal_by_patch[child_id])
    parent_normal = normalize(rigidity.normal_by_patch[parent_id])
    axis = chain_axis(geometry, chain_id)
    angle = atan2(dot(axis, cross(child_normal, parent_normal)), dot(child_normal, parent_normal))
    return compose(parent_rotation, rotation_about(axis, angle))


def build_islands(context: Any) -> IslandAssembly:
    """Assemble islands via a spanning tree of accepted stitches."""

    topology = context.topology_snapshot
    relations = context.relation_snapshot
    source = context.source_snapshot
    angle_by_source_vertex = _angle_by_source_vertex(context)
    cut_chains_by_vertex = _chain_ids_by_source_vertex(source, topology)
    border_vertices = _border_source_vertices(source)
    self_seam_chain_ids = {
        str(junction.matched_chain_id)
        for junction in relations.scaffold_junctions
        if junction.kind.value == "SELF_SEAM" and junction.matched_chain_id is not None
    }

    parents = {str(patch_id): str(patch_id) for patch_id in topology.patches}

    def find(item: str) -> str:
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    decisions: list[StitchDecision] = []
    rigidity = seam_rigidity(context)
    placements = _initial_placements(context, rigidity)
    overlap_tolerance = OVERLAP_TOLERANCE * _selection_extent(source)
    # Tree-edge priority: rigid seams first (plan Slice P), so a planar patch
    # joins through a hinge the rigid frame can cross whenever it has one,
    # and warped n-gons or bent hinges only fill in what is left; longest
    # seam first inside each group. LEVEL_B_PLACEHOLDER: semantic stitch
    # preferences belong to the future Layer 4 grammar.
    adjacencies = sorted(
        relations.patch_adjacencies.values(),
        key=lambda item: _tree_edge_priority(item, rigidity, topology),
    )
    gate_by_adjacency = {
        str(adjacency.id): _gate(
            source,
            topology,
            str(adjacency.chain_id),
            angle_by_source_vertex,
            cut_chains_by_vertex,
            border_vertices,
        )
        for adjacency in adjacencies
        if str(adjacency.chain_id) not in self_seam_chain_ids
        and adjacency.first_patch_id != adjacency.second_patch_id
    }
    leaving_patch_ids = _leaving_strip_patch_ids(context, adjacencies, gate_by_adjacency, rigidity)
    for adjacency in adjacencies:
        chain_id = str(adjacency.chain_id)
        first = str(adjacency.first_patch_id)
        second = str(adjacency.second_patch_id)
        if chain_id in self_seam_chain_ids or first == second:
            decisions.append(StitchDecision(chain_id, first, second, False, "SEAM_SELF always splits"))
            continue
        accepted, reason, defects = gate_by_adjacency[str(adjacency.id)]
        if accepted and (first in leaving_patch_ids or second in leaving_patch_ids):
            decisions.append(StitchDecision(chain_id, first, second, False, STITCH_LEAVING_STRIP_REASON, defects))
        elif accepted and find(first) != find(second):
            joined, placement, refusal = _join_placements(
                placements[find(first)], placements[find(second)],
                chain_id, first, second, rigidity, context.geometry_facts, overlap_tolerance,
            )
            if not joined:
                decisions.append(StitchDecision(chain_id, first, second, False, refusal, defects))
                continue
            root = min(find(first), find(second))
            parents[max(find(first), find(second))] = root
            placements[root] = placement
            decisions.append(StitchDecision(chain_id, first, second, True, reason, defects))
        elif accepted:
            decisions.append(StitchDecision(chain_id, first, second, False, "non-tree seam stays cut", defects))
        else:
            decisions.append(StitchDecision(chain_id, first, second, False, reason, defects))

    members: dict[str, list[str]] = {}
    for patch_id in sorted(parents, key=str):
        members.setdefault(find(patch_id), []).append(patch_id)
    stitched_by_root: dict[str, list[str]] = {}
    for decision in decisions:
        if decision.accepted:
            stitched_by_root.setdefault(find(decision.first_patch_id), []).append(decision.chain_id)
    islands: list[Island] = []
    island_by_patch: dict[str, str] = {}
    for index, root in enumerate(sorted(members)):
        island_id = f"island:{index}"
        islands.append(Island(
            id=island_id,
            patch_ids=tuple(members[root]),
            stitched_chain_ids=tuple(sorted(stitched_by_root.get(root, ()))),
        ))
        for patch_id in members[root]:
            island_by_patch[patch_id] = island_id
    return IslandAssembly(tuple(islands), tuple(decisions), island_by_patch)


def _leaving_strip_patch_ids(context, adjacencies, gate_by_adjacency, rigidity: SeamRigidity) -> set[str]:
    """STRAIGHT_STRIP patches whose stitch candidates are all straight hinges.

    A stitch candidate is a non-SEAM_SELF adjacency of the patch that the
    angle gate accepts; a patch without candidates is an island anyway.
    """

    features = getattr(context, "feature_snapshot", None)
    if features is None:
        return set()
    strip_patch_ids = {
        str(constraint.patch_id)
        for constraint in features.constraints
        if constraint.kind is FeatureConstraintKind.STRAIGHT_STRIP
    }
    candidates: dict[str, list[str]] = {}
    for adjacency in adjacencies:
        gate = gate_by_adjacency.get(str(adjacency.id))
        if gate is None or not gate[0]:
            continue
        for patch_id in {str(adjacency.first_patch_id), str(adjacency.second_patch_id)} & strip_patch_ids:
            candidates.setdefault(patch_id, []).append(str(adjacency.chain_id))
    return {
        patch_id
        for patch_id, chain_ids in candidates.items()
        if all(chain_id in rigidity.straight_chain_ids for chain_id in chain_ids)
    }


def _tree_edge_priority(adjacency, rigidity: SeamRigidity, topology) -> tuple[bool, int, str]:
    """Rigid seams first (plan Slice P), longest seam first inside each group, then by id."""

    rigid = is_rigid_seam(
        rigidity, str(adjacency.chain_id), str(adjacency.first_patch_id), str(adjacency.second_patch_id)
    )
    return (not rigid, -_chain_edge_count(topology, adjacency.chain_id), str(adjacency.id))


def _gate(source, topology, chain_id, angle_by_source_vertex, cut_chains_by_vertex, border_vertices):
    chain = topology.chains[_key(topology.chains, chain_id)]
    interior, endpoints = _chain_vertex_split(source, chain)
    candidates = set(interior)
    for endpoint in endpoints:
        other_cuts = cut_chains_by_vertex.get(endpoint, set()) - {chain_id}
        if not other_cuts and endpoint not in border_vertices:
            candidates.add(endpoint)
    defects: dict[str, float] = {}
    for source_vertex_id in sorted(candidates):
        angle = angle_by_source_vertex.get(source_vertex_id)
        if angle is None:
            return False, f"missing angle data at {source_vertex_id}", {}
        defects[source_vertex_id] = 2.0 * pi - angle
    failing = {key: value for key, value in defects.items() if abs(value) > STITCH_DEFECT_TOLERANCE}
    if failing:
        return False, "angle defect exceeds stitch limit", failing
    return True, "all would-be interior vertices have near-zero defect", defects


def _planar_patch_ids(geometry) -> set[str]:
    """Patches without curvature: every face-fan normal stays close to the patch normal."""

    worst: dict[str, float] = {}
    for fan in geometry.local_face_fan_facts.values():
        patch_id = str(fan.patch_id)
        facts = geometry.patch_facts.get(fan.patch_id)
        if facts is None or length(facts.normal) <= EPSILON or length(fan.normal) <= EPSILON:
            worst[patch_id] = -1.0
            continue
        agreement = dot(normalize(fan.normal), normalize(facts.normal))
        worst[patch_id] = min(worst.get(patch_id, 1.0), agreement)
    return {patch_id for patch_id, agreement in worst.items() if agreement >= PLANAR_PATCH_MIN_NORMAL_DOT}


def _warped_patch_ids(geometry, directional_evidence) -> set[str]:
    """Patches with a boundary run outside the patch plane.

    A single warped n-gon has only its own average normal as face-fan normal,
    so the fan test cannot see the warp; its runs can. A run leaves the plane
    when it climbs out of it by more than the planar tolerance at the patch
    scale (square root of the area), so a centimetre-long edge with a tilted
    direction does not warp a metre-wide face.
    """

    max_out_of_plane = (1.0 - PLANAR_PATCH_MIN_NORMAL_DOT ** 2) ** 0.5
    warped: set[str] = set()
    for e in directional_evidence:
        facts = geometry.patch_facts.get(e.patch_id)
        if facts is None or length(facts.normal) <= EPSILON:
            continue
        climb = abs(dot(normalize(e.direction), normalize(facts.normal))) * e.length
        if climb > max_out_of_plane * facts.area ** 0.5:
            warped.add(str(e.patch_id))
    return warped


def _chain_vertex_split(source, chain) -> tuple[tuple[str, ...], tuple[str, ...]]:
    counts: dict[str, int] = {}
    for edge_id in chain.source_edge_ids:
        for vertex_id in source.edges[_key(source.edges, str(edge_id))].vertex_ids:
            counts[str(vertex_id)] = counts.get(str(vertex_id), 0) + 1
    interior = tuple(sorted(v for v, count in counts.items() if count >= 2))
    endpoints = tuple(sorted(v for v, count in counts.items() if count == 1))
    return interior, endpoints


def _chain_ids_by_source_vertex(source, topology) -> dict[str, set[str]]:
    incident: dict[str, set[str]] = {}
    for chain in topology.chains.values():
        for edge_id in chain.source_edge_ids:
            for vertex_id in source.edges[_key(source.edges, str(edge_id))].vertex_ids:
                incident.setdefault(str(vertex_id), set()).add(str(chain.id))
    return incident


def _chain_edge_count(topology, chain_id) -> int:
    return len(topology.chains[_key(topology.chains, str(chain_id))].source_edge_ids)


def _angle_by_source_vertex(context) -> dict[str, float]:
    angles: dict[str, float] = {}
    topology = context.topology_snapshot
    for vertex_id, facts in context.geometry_facts.vertex_facts.items():
        vertex = topology.vertices.get(vertex_id)
        if vertex is None:
            continue
        for source_vertex_id in vertex.source_vertex_ids:
            angles[str(source_vertex_id)] = facts.interior_angle_sum
    return angles


def _border_source_vertices(source) -> set[str]:
    selected = {str(face_id) for face_id in source.selected_face_ids} or {
        str(face_id) for face_id in source.faces
    }
    face_count_by_edge: dict[str, int] = {}
    for face_id, face in source.faces.items():
        if str(face_id) not in selected:
            continue
        for edge_id in face.edge_ids:
            face_count_by_edge[str(edge_id)] = face_count_by_edge.get(str(edge_id), 0) + 1
    border: set[str] = set()
    for edge_id, count in face_count_by_edge.items():
        if count != 2:
            for vertex_id in source.edges[_key(source.edges, edge_id)].vertex_ids:
                border.add(str(vertex_id))
    return border


def _key(mapping, wanted: str):
    for key in mapping:
        if str(key) == wanted:
            return key
    raise KeyError(wanted)


# Overlap gate (plan Slice U). Each island part with a rigid frame keeps its
# patches' placement (world -> part frame) and its face triangles in that
# frame. A part without rigid patches has no placement.


@dataclass
class _Placement:
    rotation_by_patch: dict
    offset_by_patch: dict
    normal: tuple
    triangles: list


def _initial_placements(context, rigidity: SeamRigidity) -> dict:
    source = context.source_snapshot
    position = {str(vertex_id): vertex.position for vertex_id, vertex in source.vertices.items()}
    placements: dict = {}
    for patch_id, patch in context.topology_snapshot.patches.items():
        key = str(patch_id)
        if key not in rigidity.planar_patch_ids or key in rigidity.warped_patch_ids:
            placements[key] = None
            continue
        normal = normalize(rigidity.normal_by_patch[key])
        u, v = _plane_basis(normal)
        triangles = []
        for face_id in patch.source_face_ids:
            points = [position[str(vertex_id)] for vertex_id in source.faces[face_id].vertex_ids]
            for i0, i1, i2 in _ear_clip([(dot(point, u), dot(point, v)) for point in points]):
                triangles.append((points[i0], points[i1], points[i2]))
        placements[key] = _Placement({key: identity()}, {key: (0.0, 0.0, 0.0)}, normal, triangles)
    return placements


def _join_placements(first_part, second_part, chain_id, first, second, rigidity, geometry, tolerance):
    """(joined, placement of the joined part, refusal reason).

    A part without rigid patches joins freely and the joined part keeps the
    other side's placement. Two rigid parts join only over a rigid seam, and
    only when the smaller part, unfolded about the seam, does not lie over
    the larger one.
    """

    if first_part is None or second_part is None:
        return True, first_part if second_part is None else second_part, ""
    if not is_rigid_seam(rigidity, chain_id, first, second):
        return False, None, "frame cannot cross between rigid parts"
    if len(second_part.triangles) > len(first_part.triangles):
        first_part, second_part, first, second = second_part, first_part, second, first
    child_rotation = unfold_rotation(
        rigidity, geometry, chain_id, first, second, first_part.rotation_by_patch[first]
    )
    turn = compose(child_rotation, _transpose(second_part.rotation_by_patch[second]))
    hinge = geometry.chain_facts[chain_id].segments[0].start_position
    target = _place(first_part.rotation_by_patch[first], first_part.offset_by_patch[first], hinge)
    moved = rotate(turn, _place(second_part.rotation_by_patch[second], second_part.offset_by_patch[second], hinge))
    shift = tuple(target[i] - moved[i] for i in range(3))
    moved_triangles = [
        tuple(_place(turn, shift, point) for point in triangle) for triangle in second_part.triangles
    ]
    if _overlaps(first_part, moved_triangles, tolerance):
        return False, None, "would overlap the island"
    for patch_id, patch_rotation in second_part.rotation_by_patch.items():
        first_part.rotation_by_patch[patch_id] = compose(turn, patch_rotation)
        first_part.offset_by_patch[patch_id] = _place(turn, shift, second_part.offset_by_patch[patch_id])
    first_part.triangles.extend(moved_triangles)
    return True, first_part, ""


def _overlaps(part: _Placement, moved_triangles, tolerance) -> bool:
    u, v = _plane_basis(part.normal)

    def flat(triangle):
        return tuple((dot(point, u), dot(point, v)) for point in triangle)

    moved = [flat(triangle) for triangle in moved_triangles]
    if not moved:
        return False
    low = tuple(min(point[i] for triangle in moved for point in triangle) - tolerance for i in range(2))
    high = tuple(max(point[i] for triangle in moved for point in triangle) + tolerance for i in range(2))
    placed = []
    for triangle in part.triangles:
        flat_triangle = flat(triangle)
        if all(
            max(point[i] for point in flat_triangle) >= low[i] and min(point[i] for point in flat_triangle) <= high[i]
            for i in range(2)
        ):
            placed.append(flat_triangle)
    if not placed:
        return False
    cell = max(high[0] - low[0], high[1] - low[1]) / 32.0 or 1.0

    def cells(triangle):
        xs = [int((point[0] - low[0]) // cell) for point in triangle]
        ys = [int((point[1] - low[1]) // cell) for point in triangle]
        return [(x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys), max(ys) + 1)]

    grid: dict = {}
    for index, triangle in enumerate(placed):
        for key in cells(triangle):
            grid.setdefault(key, []).append(index)
    for triangle in moved:
        seen: set = set()
        for key in cells(triangle):
            for index in grid.get(key, ()):
                if index not in seen:
                    seen.add(index)
                    if _triangles_overlap(placed[index], triangle, tolerance):
                        return True
    return False


def _triangles_overlap(first, second, tolerance) -> bool:
    """Separating-axis test; triangles that only touch do not overlap."""

    for triangle, other in ((first, second), (second, first)):
        for i in range(3):
            start, end = triangle[i], triangle[(i + 1) % 3]
            nx, ny = end[1] - start[1], start[0] - end[0]
            size = (nx * nx + ny * ny) ** 0.5
            if size <= EPSILON:
                return False
            own = [(nx * x + ny * y) / size for x, y in triangle]
            theirs = [(nx * x + ny * y) / size for x, y in other]
            if max(own) <= min(theirs) + tolerance or max(theirs) <= min(own) + tolerance:
                return False
    return True


def _ear_clip(points) -> list[tuple[int, int, int]]:
    """Triangles of a simple polygon (a concave n-gon keeps its notch empty)."""

    count = len(points)
    if count < 3:
        return []
    signed_area = sum(
        points[i][0] * points[(i + 1) % count][1] - points[(i + 1) % count][0] * points[i][1]
        for i in range(count)
    )
    remaining = list(range(count)) if signed_area > 0.0 else list(range(count))[::-1]

    def turn(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    triangles = []
    while len(remaining) > 3:
        for k in range(len(remaining)):
            i0, i1, i2 = remaining[k - 1], remaining[k], remaining[(k + 1) % len(remaining)]
            a, b, c = points[i0], points[i1], points[i2]
            if turn(a, b, c) <= EPSILON * EPSILON:
                continue
            if any(
                turn(a, b, points[j]) > 0.0 and turn(b, c, points[j]) > 0.0 and turn(c, a, points[j]) > 0.0
                for j in remaining
                if j not in (i0, i1, i2)
            ):
                continue
            triangles.append((i0, i1, i2))
            remaining.pop(k)
            break
        else:  # degenerate rest: close it as a fan
            break
    triangles.extend((remaining[0], remaining[i], remaining[i + 1]) for i in range(1, len(remaining) - 1))
    return triangles


def _selection_extent(source) -> float:
    points = [vertex.position for vertex in source.vertices.values()]
    if not points:
        return 1.0
    return max(max(point[i] for point in points) - min(point[i] for point in points) for i in range(3)) or 1.0


def _plane_basis(normal):
    u = normalize(cross(normal, (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)))
    return u, cross(normal, u)


def _place(matrix, offset, point):
    rotated = rotate(matrix, point)
    return (rotated[0] + offset[0], rotated[1] + offset[1], rotated[2] + offset[2])


def _transpose(matrix):
    return tuple(tuple(matrix[j][i] for j in range(3)) for i in range(3))


# Rigid rotations, shared with the skeleton's unfolded frame.


def chain_axis(geometry, chain_id):
    facts = geometry.chain_facts.get(chain_id)
    if facts is None:
        return (0.0, 0.0, 1.0)
    if facts.chord_length > EPSILON:
        return normalize(facts.chord_direction)
    for segment in facts.segments:
        if segment.length > EPSILON:
            return normalize(segment.direction)
    return (0.0, 0.0, 1.0)


def identity():
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def rotation_about(axis, angle):
    x, y, z = normalize(axis)
    c, s, t = cos(angle), sin(angle), 1.0 - cos(angle)
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )


def compose(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def rotate(matrix, vector):
    if matrix is None:
        return vector
    return tuple(sum(matrix[i][k] * vector[k] for k in range(3)) for i in range(3))
