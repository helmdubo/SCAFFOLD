"""
Layer: 5 - Runtime

Rules:
- The frame-free consumer of an island without a rigid unfolded frame
  (G0 DD-47, DD-49, DD-51, DD-52): the island lines of the two sides of a
  stitched Chain (runs over the same Chain segments) are joined into one line,
  its island lines are bipartitioned into
  axes by Layer 3 right corners (plain or bridged), whole lines are oriented
  by the corner turn law, an OBLIQUE bridge run is laid by its two corner
  turns, and a line the corners never reach is reported. The longest line
  seeds both; a joined line counts its stitched Chain once and keeps the id
  and orientation of its longest part.
- The stitched rail of a marked ladder strip in the quilt (the uses
  quilt_ladders.stitched_rail_uses names) is one island line between the
  right corners, plain or bridged, that Layer 3 records between runs of the
  rail's Chain on any use of it, and never across a use's own ends (plan
  Slice AL). The runs of the rail's Chain on a line that join made from
  several lines keep their length equations unless letting them go
  removes the contradiction or leaves fewer contradictory equations among
  the other runs (plan Slice AM; skeleton.py tries such lines alone
  shortest first by 3D rail length, ties together, then the shortest k of
  them together for k = 2 .. n); a line that yields
  gives no length equation, and its run-end nodes are stations, by 3D
  length, between its nodes the solve lays. The joins are made
  together or not at all: skeleton.py keeps the lines as they were when
  the bipartition of the joined lines meets a conflict (whether or not
  the lines without the joins have one too), and the seed of
  the bipartition and orientation is chosen by the lengths before the
  joins.
- Reads Layer 3 RunCornerRelation / RunBridgedCornerRelation records, run
  fields, the island's lines, rail signs and stitched Chains, and the rail
  uses named by quilt_ladders.py only; no 3D direction, world axis or H/V.
  Never orders a line or flips one run (G0 DD-47): run order along a use is
  its Layer 3 segment order.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import cos, pi, sin

from scaffold_core.layer_3_relations.model import PatchChainEndpointRole, RunCornerKind
from scaffold_core.layer_5_runtime.axis_solve import RESIDUAL_TOLERANCE

_LAYOUT_AXIS_UNIT = {"AXIS_A": (1.0, 0.0), "AXIS_B": (0.0, 1.0)}
MARKED_RAIL_PREFIX = "ladder strip in a quilt, stitched rail made one line"
MARKED_RAILS_KEPT_PREFIX = (
    "ladder strips in a quilt, stitched rails not made one line: with the rails joined the quilt's right corners"
    " hold a line on both axes, the lines are kept as they were"
)


def join_stitched_lines(runs, line_of, signs, stitched_chain_ids, diagnostics):
    """The two sides of a stitched Chain are one UV line (identity, not evidence).

    Inside one quilt a stitched Chain has one UV per vertex. Two signed runs
    of two different uses of a stitched Chain that cover exactly the same
    Chain segments run between the same two vertices of the Chain, so they
    share their solve nodes and are one straight UV segment: their island
    lines are one line. Runs whose segment sets differ are not joined, even
    when they overlap: one side may turn a corner where the other runs
    straight (a chord shortcut on one use, several runs on the other), and
    the two sides then are not one line. Both runs follow their uses
    (G0 DD-51): their orientation signs say whether they walk the Chain the
    same way, and with their rail signs they fix the relative factor of the
    two lines (o_a * o_b * s_a * s_b). Lines are joined by a union-find with
    that parity. A pair already on one line whose parity contradicts it is
    reported; the line keeps the orientation it had, and the pair's own
    signs are not changed. Unsigned runs take no part. Reads only the Layer
    3 run fields (parent Chain, use, segment indices, orientation sign) and
    the island's stitched Chains. Returns the joined line map, the signs
    relative to it and the length of each line; the inputs are not changed.
    A joined line keeps the id and the orientation of its longest part (tie:
    the smallest id), so the longest line that seeds the bipartition and the
    line orientation is the line it was before the join. A joined line is as
    long as its parts without the second side of each joined pair: the
    stitched Chain is laid once, not twice.
    """

    stitched = {str(chain_id) for chain_id in stitched_chain_ids}
    runs_by_chain: dict[str, list] = {}
    for e in runs:
        if str(e.parent_chain_id) in stitched and e.id in signs and e.id in line_of:
            runs_by_chain.setdefault(str(e.parent_chain_id), []).append(e)
    part_length = line_lengths(runs, line_of)
    pairs: list = []
    second_sides: list = []  # per pair joined across two lines: its second side, laid on the first
    for chain_id in sorted(runs_by_chain):
        members = sorted(runs_by_chain[chain_id], key=lambda e: e.id)
        for index, first in enumerate(members):
            for second in members[index + 1:]:
                if str(first.patch_chain_id) == str(second.patch_chain_id):
                    continue
                if sorted(first.segment_indices) != sorted(second.segment_indices):
                    continue
                if line_of[first.id] != line_of[second.id]:
                    second_sides.append(second)  # two lines made one: the Chain is laid once
                pairs.append((first, second))
    joined = _join_lines(pairs, line_of, signs, part_length, "stitched Chain sides", diagnostics)
    if joined is None:
        return line_of, signs, part_length
    joined_line_of, joined_signs, length_by_line = joined
    for e in second_sides:
        length_by_line[joined_line_of[e.id]] -= e.length
    return joined_line_of, joined_signs, length_by_line


def _join_lines(pairs, line_of, signs, part_length, what, diagnostics):
    """Join the island lines of each pair of signed runs into one line: a union-find with parity.

    The relative factor of the two runs' lines is o_a * o_b * s_a * s_b
    (orientation signs of their uses and run signs, G0 DD-51). A pair whose
    lines are already one and whose parity contradicts it is reported (what
    names the pair's kind); the line keeps the orientation it had. A joined
    line keeps the id and orientation of its longest part (part_length; tie:
    the smallest id). Returns None when nothing is joined, else the joined
    line map, the signs relative to it and the summed part lengths per line.
    """

    parent: dict[str, tuple[str, float]] = {}

    def find(line_id):
        root, parity = parent.get(line_id, (line_id, 1.0))
        if root == line_id:
            return line_id, 1.0
        top, above = find(root)
        parent[line_id] = (top, parity * above)
        return top, parity * above

    for first, second in pairs:
        relative = first.orientation_sign * second.orientation_sign * signs[first.id] * signs[second.id]
        (first_root, first_parity), (second_root, second_parity) = find(line_of[first.id]), find(line_of[second.id])
        if first_root == second_root:
            if first_parity * second_parity != relative:
                diagnostics.append(
                    f"{what} disagree on their line orientation: {first.id} / {second.id}"
                    " -> one line, it keeps the orientation it had"
                )
            continue
        kept, joined = sorted((first_root, second_root), key=lambda line_id: (-part_length.get(line_id, 0.0), line_id))
        parent[joined] = (kept, first_parity * second_parity * relative)
    if not parent:
        return None
    joined_line_of, joined_signs = dict(line_of), dict(signs)
    for run_id, line_id in line_of.items():
        root, parity = find(line_id)
        joined_line_of[run_id] = root
        if run_id in joined_signs:
            joined_signs[run_id] = parity * joined_signs[run_id]
    length_by_line: dict[str, float] = {}
    for line_id, length in part_length.items():
        root = find(line_id)[0]
        length_by_line[root] = length_by_line.get(root, 0.0) + length
    return joined_line_of, joined_signs, length_by_line


@dataclass(frozen=True)
class MarkedRail:
    """A stretch of a marked ladder strip's stitched rail laid as one island line (plan Slice AL).

    run_ids: the signed runs of one stitched use of the rail, in the use's
    order from its start, between two right corners on the rail's Chain or
    the use's own ends (a closed use is never joined across its own ends).
    name: the patch and the stretch's first and last source vertex.
    line_count: how many island lines the join made one; 1 when the
    stretch already was one line.
    """

    patch_id: str
    chain_id: str
    line_id: str
    run_ids: tuple[str, ...]
    line_count: int
    name: str


def join_marked_rails(runs, line_of, signs, length_by_line, rail_uses_by_patch, use_end_sources,
                      run_corner_relations, bridged_corners, diagnostics):
    """The stitched rail of a marked ladder strip is one island line between right corners on its Chain.

    rail_uses_by_patch names, per strip, the stitched uses of its stitched
    rail (quilt_ladders.stitched_rail_uses): the mark (Layer 4
    STRAIGHT_LADDER) says that rail is straight, where Layer 3 may have cut
    it into several lines because its arc is coarse. use_end_sources gives
    each use's two end source vertices (Layer 1 PatchChain start and end
    vertex). The signed runs of each such use are ordered by their first
    Chain segment (Layer 3 segment indices), rotated so that the run that
    starts at one of the use's ends comes first (a closed use cut by a
    SEAM_SELF opens where its cut is, G0 DD-47). A run is joined to the next
    when the next starts where it ends walking the Chain forward
    (orientation signs), that vertex is not one of the use's ends, and no
    right corner Layer 3 records between runs of the rail's Chain, on any
    use of it in the island, lies there: a RIGHT RunCornerRelation, or a
    RunBridgedCornerRelation (its bridge's two ends). Parity and the kept id
    are those of join_stitched_lines (_join_lines, with length_by_line, the
    lengths join_stitched_lines returns; None: the sums of the runs); runs
    without a sign take no part. A joined line keeps the id of its longest
    part. Returns the joined line map, the signs relative to it and one
    MarkedRail per stretch; the inputs are not changed.
    """

    if length_by_line is None:
        length_by_line = line_lengths(runs, line_of)
    run_by_id = {e.id: e for e in runs}
    runs_by_use: dict[str, list] = {}
    for e in runs:
        if e.id in signs and e.id in line_of:
            runs_by_use.setdefault(str(e.patch_chain_id), []).append(e)
    pairs: list = []
    stretches: list[tuple[str, list]] = []
    for patch_id in sorted(rail_uses_by_patch):
        for use in rail_uses_by_patch[patch_id]:
            members = sorted(runs_by_use.get(use, ()), key=lambda e: (e.segment_indices[0], e.id))
            if not members:
                continue
            ends = use_end_sources[use]
            first_index = next((i for i, e in enumerate(members) if _forward_start(e) in ends), 0)
            members = members[first_index:] + members[:first_index]
            cut = _corner_vertices(str(members[0].parent_chain_id), run_by_id, run_corner_relations, bridged_corners)
            stretch = [members[0]]
            for first, second in zip(members, members[1:]):
                vertex = _forward_end(first)
                # The end check guards a use none of whose runs starts at a use end (its first run unsigned and
                # so left out, or its Chain passing its own end vertex mid-way): the rotation then cannot help.
                if vertex == _forward_start(second) and vertex not in cut and vertex not in ends:
                    pairs.append((first, second))
                    stretch.append(second)
                else:
                    stretches.append((patch_id, stretch))
                    stretch = [second]
            stretches.append((patch_id, stretch))
    joined = _join_lines(pairs, line_of, signs, length_by_line, "ladder rail runs", diagnostics)
    joined_line_of, joined_signs = (line_of, signs) if joined is None else joined[:2]
    parts: dict[str, set[str]] = {}
    for run_id, line_id in line_of.items():
        parts.setdefault(joined_line_of[run_id], set()).add(line_id)
    rails = tuple(
        MarkedRail(
            patch_id, str(stretch[0].parent_chain_id), joined_line_of[stretch[0].id], tuple(e.id for e in stretch),
            len(parts[joined_line_of[stretch[0].id]]),
            f"{patch_id} ({_forward_start(stretch[0])}..{_forward_end(stretch[-1])})",
        )
        for patch_id, stretch in stretches
    )
    return joined_line_of, joined_signs, rails


def _forward_start(e) -> str:
    """The run's end vertex first along its Chain's segment order (a run follows its use, G0 DD-51)."""

    return str(e.start_source_vertex_id if e.orientation_sign != -1 else e.end_source_vertex_id)


def _forward_end(e) -> str:
    return str(e.end_source_vertex_id if e.orientation_sign != -1 else e.start_source_vertex_id)


def _corner_vertices(chain_id, run_by_id, run_corner_relations, bridged_corners) -> set[str]:
    """Source vertices of a Chain where a right corner turns it: a RIGHT or a bridged corner of its runs."""

    def on_chain(run_id):
        return run_id in run_by_id and str(run_by_id[run_id].parent_chain_id) == chain_id

    def ends(run_id):
        e = run_by_id[run_id]
        return {str(e.start_source_vertex_id), str(e.end_source_vertex_id)}

    cut: set[str] = set()
    for corner in run_corner_relations:
        first, second = corner.first_directional_evidence_id, corner.second_directional_evidence_id
        if corner.kind is RunCornerKind.RIGHT and on_chain(first) and on_chain(second):
            cut |= ends(first) & ends(second)
    for corner in bridged_corners:
        bridge = corner.bridge_directional_evidence_id
        if all(on_chain(run_id) for run_id in (corner.arriving_directional_evidence_id, bridge,
                                                corner.leaving_directional_evidence_id)):
            cut |= ends(bridge)
    return cut


MARKED_LINE_TIE = 1e-9  # relative: marked lines this close in 3D rail length yield together


@dataclass(frozen=True)
class MarkedLine:
    """The rail's Chain on a line the mark made from several lines (plan Slices AL, AM).

    chain_id, line_id: the rail's Chain and the joined island line.
    run_ids: every run of that Chain on that line, on every use of the
    Chain in the island (both sides of the stitched rail), in id order:
    the soft runs. They give length equations until the line yields.
    length: the 3D rail length of the line: for each use that holds a
    MarkedRail stretch of this Chain and line (a stitched use of the
    strip's rail), the summed 3D length of the runs of those stretches;
    the largest such sum. It is read from the strip's own rail use, never
    from the other side of the Chain, so it depends neither on ids nor on
    which use is read first.
    """

    chain_id: str
    line_id: str
    run_ids: tuple[str, ...]
    length: float


@dataclass(frozen=True)
class MarkedYield:
    """The effect of the yield a marked line was part of, at that step (plan Slice AM; skeleton._solve_axis_yielding).

    fewer: how many fewer contradictory equations the other runs (not the
    yielding lines' own soft runs) have without the yielding lines' length
    equations; left: how many remain at that step (0: none); others: how
    many other lines the mark made yielded together with this one. Taken
    when the line yields and never refreshed by a later yield on the axis.
    """

    fewer: int
    left: int
    others: int


def marked_lines(rails, runs, line_of) -> tuple[MarkedLine, ...]:
    """The lines the mark made from several lines, per rail Chain, with their soft runs and 3D rail length.

    Every use of the rail's Chain in the island counts for the soft runs
    (the two sides of the stitched rail); other runs that share the joined
    line are not soft: the mark says nothing about them.
    """

    run_by_id = {e.id: e for e in runs}
    length_by_use: dict[tuple[str, str, str], float] = {}
    for rail in rails:
        if rail.line_count < 2:
            continue
        for run_id in rail.run_ids:
            e = run_by_id[run_id]
            use = (rail.chain_id, rail.line_id, str(e.patch_chain_id))
            length_by_use[use] = length_by_use.get(use, 0.0) + e.length
    length_by_key: dict[tuple[str, str], float] = {}
    for (chain_id, line_id, _use), length in length_by_use.items():
        length_by_key[(chain_id, line_id)] = max(length_by_key.get((chain_id, line_id), 0.0), length)
    soft: dict[tuple[str, str], list[str]] = {}
    for e in runs:
        key = (str(e.parent_chain_id), line_of.get(e.id))
        if key in length_by_key:
            soft.setdefault(key, []).append(e.id)
    return tuple(
        MarkedLine(chain_id, line_id, tuple(sorted(soft.get((chain_id, line_id), ()))), length_by_key[(chain_id, line_id)])
        for chain_id, line_id in sorted(length_by_key)
    )


def marked_line_groups(lines) -> list[tuple[MarkedLine, ...]]:
    """The marked lines in the order they are tried as yielding (plan Slice AM): shortest first.

    Lines are sorted by their 3D rail length; a line whose length ties with
    the first line of the current group (relative MARKED_LINE_TIE) joins
    that group, so tied lines are tried, and yield, together: ids never
    choose. Within a group the order is that of the lines given.
    """

    groups: list[list[MarkedLine]] = []
    for line in sorted(lines, key=lambda item: item.length):
        if groups and line.length - groups[-1][0].length <= MARKED_LINE_TIE * max(line.length, groups[-1][0].length):
            groups[-1].append(line)
        else:
            groups.append([line])
    return [tuple(group) for group in groups]


def station_marked_rails(rails, yielded, runs, roles, signs, node_by_run_end, coordinates, diagnostics):
    """One diagnostic per rail the mark made one line; stations for those that yielded (plan Slices AL, AM).

    Only rails with line_count > 1 are read. yielded maps the (chain_id,
    line_id) of each line that yielded its length to the MarkedYield of
    that yield (skeleton._solve_axis_yielding). A rail whose line kept its length takes no
    stations: its runs gave their length equations. A rail whose line
    yielded gave none; coordinates maps AXIS_A / AXIS_B to the solved
    coordinate per node, and the rail's along axis is its line's role.
    Walking its runs in the order of the stretch, a node without an along
    coordinate between two nodes that have one takes the value between
    them in proportion to the 3D length along the rail (the runs' lengths).
    A node with such a node on one side only keeps no coordinate (no
    extrapolation). Its across coordinate is its line's, as on any line.
    Each diagnostic names the stretch by its patch and its first and last
    source vertex, with its line count and 3D length, and says that it
    keeps its length, or that its line has no signed run on an axis (no
    length equation at all), or that it yielded, with the effect of the
    yield at its step (the other runs of its axis have no contradictory
    equation, or how many fewer and how many left at that step; a later
    yield on the axis does not refresh it) and how many other lines
    the mark made yielded with it, and where it is laid: the length its ends
    are laid at and its difference to the 3D length, its ends not both
    laid, or no stations because fewer than two of its nodes are laid.
    Returns new coordinate maps; the inputs are not changed.
    """

    run_by_id = {e.id: e for e in runs}
    result = {axis: dict(values) for axis, values in coordinates.items()}
    for rail in rails:
        if rail.line_count < 2:
            continue
        stretch = [run_by_id[run_id] for run_id in rail.run_ids]
        length = sum(e.length for e in stretch)
        head = f"{MARKED_RAIL_PREFIX} from {rail.line_count} lines, {length:.4f} m in 3D"
        note = yielded.get((rail.chain_id, rail.line_id))
        if note is None:
            if any(e.id in signs and roles.get(e.id) in ("AXIS_A", "AXIS_B") for e in stretch):
                diagnostics.append(f"{head}, keeps its length: {rail.name}")
            else:
                diagnostics.append(f"{head}, gives no length equation, its line has no signed run on an axis: {rail.name}")
            continue
        if note.others:
            plural = "line" if note.others == 1 else "lines"
            head = f"{head}, yields its length together with {note.others} other {plural} the mark made: without their"
        else:
            head = f"{head}, yields its length: without its"
        if note.left:
            effect = f"{note.fewer} fewer contradictory equations ({note.left} left at that step)"
        else:
            effect = "no contradictory equation"
        head = f"{head} length equations the other runs of its axis have {effect}"
        axis = roles.get(stretch[0].id)
        along = result.get(axis)
        nodes = [_node_at(stretch[0], _forward_start(stretch[0]), node_by_run_end)]
        nodes.extend(_node_at(e, _forward_end(e), node_by_run_end) for e in stretch)
        walked = [0.0]
        for e in stretch:
            walked.append(walked[-1] + e.length)
        fixed = [] if along is None else [index for index, node in enumerate(nodes) if node in along]
        if len(fixed) < 2:
            diagnostics.append(f"{head}, no stations: fewer than two of its nodes are laid: {rail.name}")
            continue
        for low, high in zip(fixed, fixed[1:]):
            span = walked[high] - walked[low]
            for index in range(low + 1, high):
                t = (walked[index] - walked[low]) / span if span > 0.0 else 0.0
                along[nodes[index]] = along[nodes[low]] + t * (along[nodes[high]] - along[nodes[low]])
        if fixed[0] == 0 and fixed[-1] == len(nodes) - 1:
            laid = abs(along[nodes[-1]] - along[nodes[0]])
            diagnostics.append(f"{head}, laid at {laid:.4f} m ({laid - length:+.4f} m): {rail.name}")
        else:
            diagnostics.append(f"{head}, its ends not both laid: {rail.name}")
    return result


def _node_at(e, source_vertex, node_by_run_end) -> str:
    role = "START" if str(e.start_source_vertex_id) == source_vertex else "END"
    return node_by_run_end[(e.id, role)]


def line_lengths(runs, line_of) -> dict[str, float]:
    """The length of each island line: the sum of its runs' lengths."""

    length_by_line: dict[str, float] = {}
    for e in runs:
        line_id = line_of.get(e.id)
        if line_id is not None:
            length_by_line[line_id] = length_by_line.get(line_id, 0.0) + e.length
    return length_by_line


def bipartition_families(runs, family_of, run_corner_relations, diagnostics, bridged_corners=(), length_by_line=None):
    """Axis classes via right corners on the patch surface (frame-free).

    Derivation for curved islands, which have no rigid unfolded frame. Two
    island lines are orthogonal iff two of their runs, both in this island,
    meet at a Layer 3 RunCornerRelation of kind RIGHT: a right corner of one
    patch's own surface (convex or reflex), or are the arriving and leaving
    runs of a RunBridgedCornerRelation (a right corner turned over one bridge
    run; the bridge takes no part). The seed (longest) line is AXIS_A;
    lines meeting it at a right corner are AXIS_B, and so on by BFS.
    Contradictions degrade the line to OBLIQUE with a diagnostic - never
    silently forced - and an OBLIQUE line passes no axis to its neighbours.
    Line lengths are those join_stitched_lines returns, else the sum of the
    runs.
    """

    length_by_family = line_lengths(runs, family_of) if length_by_line is None else length_by_line
    if not length_by_family:
        return {}
    island_run_ids = {e.id for e in runs}
    edges: dict[str, set[str]] = {}
    pairs = [
        (corner.first_directional_evidence_id, corner.second_directional_evidence_id)
        for corner in run_corner_relations
        if corner.kind is RunCornerKind.RIGHT
    ]
    pairs.extend(
        (corner.arriving_directional_evidence_id, corner.leaving_directional_evidence_id)
        for corner in bridged_corners
    )
    for first_id, second_id in pairs:
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


def orient_lines_by_corners(
    runs, line_of, axis_by_line, signs, run_corner_relations, diagnostics, bridged_corners=(), length_by_line=None
):
    """One sign factor per island line from the handedness of right corners.

    Frame-free islands only. The rails fix each line's in-line run signs; the
    factor of a whole line is unknown. At a Layer 3 RunCornerRelation of kind
    RIGHT the run whose role is END arrives at the corner and the run whose
    role is START leaves it, both along the patch's boundary loop, which
    follows the face winding. In an unmirrored layout a convex corner turns
    left and a reflex corner turns right, so with a sign s per run
    (coordinate(END) - coordinate(START) = s * length):
    s(arriving) * s(leaving) = +1 when (arriving is AXIS_A) == convex, else -1.
    That fixes the product of the two lines' factors. A RunBridgedCornerRelation
    is read the same way: its arriving run arrives, its leaving run leaves,
    and its combined angle says convex or reflex. Factors propagate by
    BFS from the longest line (tie: id), each corner read once. A line
    given two different factors is a conflict: its runs lose their signs (no
    length equations) and the island gets one diagnostic per such line. A
    signed axis line that the corners do not tie to the longest line keeps
    its rail signs, with a diagnostic: its direction against the rest of the
    island is unknown. No 3D directions are read.
    """

    island_run_ids = {e.id for e in runs}
    if length_by_line is None:
        length_by_line = line_lengths(runs, line_of)
    turns: list[tuple[int, str | None, str | None, float]] = []  # (index, arriving, leaving, angle)
    for index, corner in enumerate(run_corner_relations):
        if corner.kind is not RunCornerKind.RIGHT:
            continue
        run_by_role = {
            corner.first_endpoint_role: corner.first_directional_evidence_id,
            corner.second_endpoint_role: corner.second_directional_evidence_id,
        }
        turns.append((
            index, run_by_role.get(PatchChainEndpointRole.END), run_by_role.get(PatchChainEndpointRole.START),
            corner.interior_angle_sum,
        ))
    turns.extend(
        (len(run_corner_relations) + index, corner.arriving_directional_evidence_id,
         corner.leaving_directional_evidence_id, corner.interior_angle_sum)
        for index, corner in enumerate(bridged_corners)
    )
    links: dict[str, list[tuple[str, float, int]]] = {}
    for index, arriving, leaving, angle in turns:
        if arriving is None or leaving is None:
            continue
        if not {arriving, leaving} <= island_run_ids or arriving not in signs or leaving not in signs:
            continue
        arriving_line, leaving_line = line_of.get(arriving), line_of.get(leaving)
        arriving_axis = axis_by_line.get(arriving_line)
        if {arriving_axis, axis_by_line.get(leaving_line)} != {"AXIS_A", "AXIS_B"}:
            continue
        convex = angle < pi
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


def bridge_vectors(runs, roles, signs, bridged_corners, diagnostics) -> dict[str, tuple[float, float]]:
    """The (AXIS_A, AXIS_B) layout vector of each bridge run (frame-free).

    Read once roles and signs are final. A bridged corner whose arriving run A
    and leaving run B lie on different axes with signs, and whose bridge C is
    OBLIQUE, lays C: walking the loop, A points along sign(A) times its axis
    (AXIS_A, AXIS_B right-handed, a left turn positive), the boundary turns by
    pi - angle at each of the two corners, and the two turns are corrected
    evenly so that they add up to exactly the right angle the record names
    (+pi/2 convex, -pi/2 reflex). C's vector is its length along A's direction
    turned by the first corrected turn. A corner whose B does not point where
    the right angle says is reported and lays nothing; a bridge that two
    corners lay differently is reported and gets no vector.
    """

    run_by_id = {e.id: e for e in runs}
    vectors_by_bridge: dict[str, list[tuple[float, float]]] = {}
    for corner in bridged_corners:
        arriving = corner.arriving_directional_evidence_id
        bridge = corner.bridge_directional_evidence_id
        leaving = corner.leaving_directional_evidence_id
        if not {arriving, bridge, leaving} <= set(run_by_id) or roles.get(bridge) != "OBLIQUE":
            continue
        arriving_role, leaving_role = roles.get(arriving), roles.get(leaving)
        if {arriving_role, leaving_role} != {"AXIS_A", "AXIS_B"} or arriving not in signs or leaving not in signs:
            continue
        total = 0.5 * pi if corner.interior_angle_sum < pi else -0.5 * pi
        first_turn = pi - corner.arriving_interior_angle_sum
        second_turn = pi - corner.leaving_interior_angle_sum
        first_turn -= 0.5 * (first_turn + second_turn - total)
        along = tuple(signs[arriving] * c for c in _LAYOUT_AXIS_UNIT[arriving_role])
        leaving_direction = tuple(signs[leaving] * c for c in _LAYOUT_AXIS_UNIT[leaving_role])
        if max(abs(a - b) for a, b in zip(_turn_2d(along, total), leaving_direction)) > 0.5:
            diagnostics.append(f"bridged corner against its line orientation: {corner.id}")
            continue
        length = run_by_id[bridge].length
        direction = _turn_2d(along, first_turn)
        vectors_by_bridge.setdefault(bridge, []).append((length * direction[0], length * direction[1]))
    vectors: dict[str, tuple[float, float]] = {}
    for bridge in sorted(vectors_by_bridge):
        laid = vectors_by_bridge[bridge]
        if any(max(abs(a - b) for a, b in zip(vector, laid[0])) > RESIDUAL_TOLERANCE for vector in laid):
            diagnostics.append(f"bridge run laid two ways by bridged corners: {bridge}")
            continue
        vectors[bridge] = laid[0]
    return vectors


def _turn_2d(vector, angle):
    c, s = cos(angle), sin(angle)
    return (c * vector[0] - s * vector[1], s * vector[0] + c * vector[1])


def report_unreached_lines(runs, line_of, axis_by_line, bridge_vectors, diagnostics) -> None:
    """One diagnostic per island line the right corners never reach (frame-free).

    Such a line is OBLIQUE. A line made only of bridge runs that have a
    layout vector is laid by its bridged corners and is not reported.
    """

    runs_by_line: dict[str, list[str]] = {}
    for e in runs:
        line_id = line_of.get(e.id)
        if line_id is not None:
            runs_by_line.setdefault(line_id, []).append(e.id)
    for line_id in sorted(runs_by_line):
        if line_id in axis_by_line or all(run_id in bridge_vectors for run_id in runs_by_line[line_id]):
            continue
        diagnostics.append(f"island line not reached by right corners: {line_id} -> OBLIQUE")
