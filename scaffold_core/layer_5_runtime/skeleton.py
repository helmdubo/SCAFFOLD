"""
Layer: 5 - Runtime

Rules:
- Selection-wide skeleton solve per docs/phases/G5a_skeleton_runtime.md.
- Solve nodes are occurrence-level; cut seam sides stay split, stitched
  seam sides are unioned by shared source vertex.
- One length equation per RUN connecting its OWN endpoints; axis roles
  come from ConnectedDirectionFamily directions in the island's
  unfolded frame (stitch-tree parallel transport). No world axes.
- Contradictions -> UNCONSTRAINED + diagnostics, never silent smearing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, sin
from typing import Any, Mapping

from scaffold_core.layer_2_geometry.measures import EPSILON, dot, normalize
from scaffold_core.layer_5_runtime.islands import IslandAssembly, build_islands

AXIS_CLASS_MIN_COS = 0.92
RESIDUAL_TOLERANCE = 1e-5
GAUGE_WEIGHT = 1e6


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


def build_island_skeletons(context: Any, assembly: IslandAssembly) -> tuple[IslandSkeleton, ...]:
    relations = context.relation_snapshot
    topology = context.topology_snapshot
    geometry = context.geometry_facts
    evidence_by_id = {e.id: e for e in relations.patch_chain_directional_evidence}
    patch_chain_by_id = {str(pc.id): pc for pc in topology.patch_chains.values()}
    source_of_vertex = {
        str(vertex_id): (str(vertex.source_vertex_ids[0]) if vertex.source_vertex_ids else str(vertex_id))
        for vertex_id, vertex in topology.vertices.items()
    }
    skeletons = []
    for island in assembly.islands:
        skeletons.append(_island_skeleton(
            island, assembly, relations, topology, geometry,
            evidence_by_id, patch_chain_by_id, source_of_vertex,
        ))
    return tuple(skeletons)


def _island_skeleton(island, assembly, relations, topology, geometry,
                     evidence_by_id, patch_chain_by_id, source_of_vertex):
    diagnostics: list[str] = []
    patch_ids = set(island.patch_ids)
    runs = tuple(e for e in evidence_by_id.values() if str(e.patch_id) in patch_ids)
    node_by_run_end = _node_map(island, runs, topology, patch_chain_by_id, source_of_vertex, relations)
    family_of = _family_of(relations)
    axis_by_family = _bipartition_families(runs, family_of, node_by_run_end, diagnostics)
    roles = {
        e.id: axis_by_family.get(family_of.get(e.id), "OBLIQUE")
        for e in runs
    }
    signs = _orientation_signs(runs, family_of, node_by_run_end)
    _co_orient_axis_families(runs, family_of, axis_by_family, signs, node_by_run_end, diagnostics)
    axis_a = _solve_axis("AXIS_A", runs, roles, signs, node_by_run_end, diagnostics)
    axis_b = _solve_axis("AXIS_B", runs, roles, signs, node_by_run_end, diagnostics)
    return IslandSkeleton(island.id, node_by_run_end, roles, axis_a, axis_b, tuple(diagnostics))


def _family_of(relations) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family in relations.connected_direction_families:
        for member in family.member_directional_evidence_ids:
            mapping[member] = family.id
    return mapping


def _bipartition_families(runs, family_of, node_by_run_end, diagnostics):
    """Axis classes via local orthogonality at shared junctions (frame-free).

    The seed (longest) family is AXIS_A; families meeting it orthogonally
    at a junction are AXIS_B, and so on by BFS. Contradictions degrade the
    family to OBLIQUE with a diagnostic - never silently forced.
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


def _node_map(island, runs, topology, patch_chain_by_id, source_of_vertex, relations):
    """Occurrence-level solve nodes (DD-37 does the splitting for us).

    Chain-end nodes are the PatchChain's own occurrence vertex ids: plain
    corners naturally share one occurrence across adjacent patch chains,
    while cut/self-seam sides carry distinct occurrences and stay split -
    closed rims therefore never collapse into contradiction cycles.
    Mid-chain nodes are (source, patch_chain)-scoped; stitched chains
    union both sides by source vertex.
    """

    raw: dict[tuple[str, str], str] = {}
    for e in runs:
        chain = topology.chains[_key(topology.chains, str(e.parent_chain_id))]
        segment_count = len(chain.source_edge_ids)
        pc = patch_chain_by_id[str(e.patch_chain_id)]
        forward = e.orientation_sign == 1
        first_boundary = 0 in e.segment_indices
        last_boundary = (segment_count - 1) in e.segment_indices
        start_is_boundary = first_boundary if forward else last_boundary
        end_is_boundary = last_boundary if forward else first_boundary
        # Pick the occurrence whose SOURCE vertex matches the evidence end:
        # pc.start/end ordering is not reliably evidence-oriented. Closed
        # bands (both pc ends on one source vertex) fall back to the
        # orientation formula - any consistent side labeling works there.
        pc_start_source = source_of_vertex.get(str(pc.start_vertex_id), str(pc.start_vertex_id))
        pc_end_source = source_of_vertex.get(str(pc.end_vertex_id), str(pc.end_vertex_id))
        ambiguous = pc_start_source == pc_end_source

        def _occurrence_for(source_vertex: str, prefer_start: bool):
            if not ambiguous:
                if source_vertex == pc_start_source:
                    return pc.start_vertex_id
                if source_vertex == pc_end_source:
                    return pc.end_vertex_id
            return pc.start_vertex_id if prefer_start == forward else pc.end_vertex_id

        for role, source_vertex, boundary, occurrence in (
            ("START", str(e.start_source_vertex_id), start_is_boundary,
             _occurrence_for(str(e.start_source_vertex_id), True)),
            ("END", str(e.end_source_vertex_id), end_is_boundary,
             _occurrence_for(str(e.end_source_vertex_id), False)),
        ):
            node = (
                f"occ:{occurrence}:pc:{e.patch_chain_id}"
                if boundary
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

    return {key: find(node) for key, node in raw.items()}


def _family_of(relations) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family in relations.connected_direction_families:
        for member in family.member_directional_evidence_ids:
            mapping[member] = family.id
    return mapping


def _bipartition_families(runs, family_of, node_by_run_end, diagnostics):
    """Axis classes via local orthogonality at shared junctions (frame-free).

    The seed (longest) family is AXIS_A; families meeting it orthogonally
    at a junction are AXIS_B, and so on by BFS. Contradictions degrade the
    family to OBLIQUE with a diagnostic - never silently forced.
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


def _island_axes(relations, runs, unfolded_dir):
    lengths: dict[str, float] = {}
    direction_by_family: dict[str, tuple] = {}
    family_of = {}
    for family in relations.connected_direction_families:
        for member in family.member_directional_evidence_ids:
            family_of[member] = family.id
    for e in runs:
        family_id = family_of.get(e.id)
        if family_id is None:
            continue
        lengths[family_id] = lengths.get(family_id, 0.0) + e.length
        if family_id not in direction_by_family:
            direction_by_family[family_id] = normalize(unfolded_dir[e.id])
    if not lengths:
        return None, None
    seed_family = sorted(lengths, key=lambda fid: (-lengths[fid], fid))[0]
    axis_a = direction_by_family[seed_family]
    best_b = None
    for family_id in sorted(lengths, key=lambda fid: (-lengths[fid], fid)):
        candidate = direction_by_family[family_id]
        if abs(dot(candidate, axis_a)) <= 0.4:
            best_b = _orthogonalize(candidate, axis_a)
            break
    return axis_a, best_b


def _orthogonalize(vector, axis):
    projected = tuple(vector[i] - dot(vector, axis) * axis[i] for i in range(3))
    return normalize(projected)


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
    run_by_id = {e.id: e for e in runs}
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


def _solve_axis(axis_name, runs, roles, signs, node_by_run_end, diagnostics):
    """P7 semantics: the A coordinate lives on COLUMN components (nodes
    connected by AXIS_B runs share one A value) and is constrained by
    AXIS_A run lengths; symmetric for B on ROW components."""

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
        oriented = tuple(c * (1.0 if value >= 0.0 else -1.0) for c in e.direction)
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


def _key(mapping, wanted: str):
    for key in mapping:
        if str(key) == wanted:
            return key
    raise KeyError(wanted)
