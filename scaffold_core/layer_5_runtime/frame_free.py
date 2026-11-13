"""
Layer: 5 - Runtime

Rules:
- The frame-free consumer of an island without a rigid unfolded frame
  (G0 DD-47, DD-49, DD-51, DD-52): its island lines are bipartitioned into
  axes by Layer 3 right corners (plain or bridged), whole lines are oriented
  by the corner turn law, an OBLIQUE bridge run is laid by its two corner
  turns, and a line the corners never reach is reported.
- Reads Layer 3 RunCornerRelation / RunBridgedCornerRelation records and the
  island's lines and rail signs only; no 3D direction, world axis or H/V.
  Never orders a line or flips one run (G0 DD-47).
"""

from __future__ import annotations

from collections import deque
from math import cos, pi, sin

from scaffold_core.layer_3_relations.model import PatchChainEndpointRole, RunCornerKind
from scaffold_core.layer_5_runtime.axis_solve import RESIDUAL_TOLERANCE

_LAYOUT_AXIS_UNIT = {"AXIS_A": (1.0, 0.0), "AXIS_B": (0.0, 1.0)}


def bipartition_families(runs, family_of, run_corner_relations, diagnostics, bridged_corners=()):
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
    runs, line_of, axis_by_line, signs, run_corner_relations, diagnostics, bridged_corners=()
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
    length_by_line: dict[str, float] = {}
    for e in runs:
        line_id = line_of.get(e.id)
        if line_id is not None:
            length_by_line[line_id] = length_by_line.get(line_id, 0.0) + e.length
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
