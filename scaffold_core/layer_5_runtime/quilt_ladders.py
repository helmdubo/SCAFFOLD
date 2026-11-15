"""
Layer: 5 - Runtime

Rules:
- A Layer 4 STRAIGHT_LADDER FeatureConstraint whose strip lies in a quilt
  of other patches (a user filter joined one of its seams, G0 DD-55) keeps
  the strip's two rails together (plan Slice AI). An island of the strip
  alone is laid from the constraint by skeleton.py (frame LADDER).
- Only a frame-free quilt reads it. A quilt with a rigid unfolded frame
  holds only planar patches, and each patch in the frame is unfolded
  exactly: the strip there needs nothing. A strip outside that frame (behind
  a warped patch or a bent hinge) is not laid and says so.
- The ladder chooses no axis and no sign, but its mark says its stitched
  rail is straight (plan Slice AL): before the bipartition, the stitched
  uses of the stitched rail of a strip that could be read (every run end
  on the ladder, exactly one rail stitched; stitched_rail_uses) are made
  one island line between right corners, plain or bridged, that Layer 3
  records between runs of the rail's Chain, on any use of it, and never
  across a use's own ends (frame_free.join_marked_rails). The runs of the
  rail's Chain on a line that join made from several lines give no length
  equation (the mark says straight, not how long); its nodes are stations
  between its laid nodes. The free rail is never joined. The joins of a
  quilt are made together or not at all: if they bring the bipartition a
  conflict, the lines stay as they were and one diagnostic says so. The
  bipartition and line orientation then run on those lines as on any,
  seeded by the lengths before the joins. After orientation a strip is read only
  when exactly one of its rails is stitched in the quilt and the quilt lays
  that rail in at least one piece (plan Slice AK): the stitched rail is cut
  into pieces where the axis its signed runs lie on changes (a profile
  line held by runs of one axis is in a piece, a corner line held by both
  axes or a line held by none is in no piece; two neighbouring lines share
  a piece when one run holds both). In each piece its axis is the rail
  axis and the other is the across axis; no free-rail run that lies within
  a piece may lie on that piece's across axis.
- A strip that is read, piece by piece: the free rail's runs that lie within
  a piece and on its rail axis lose their signs, so they give no length
  equation (an unsigned run); each free-rail vertex of a line in a piece
  takes the along-rail coordinate of its profile-line partner on the
  stitched rail once the pins are known (pins.py), and lies across on the
  straight line between the free-rail vertices of the piece's first and
  last line. A free-rail run that spans two pieces (a mitre) keeps its
  sign and role; lines on no piece get no tie, counted in one diagnostic.
  Across, a stitched end keeps its own length and a free end follows it, each
  on the across axis of the piece that holds its line; with no end stitched
  the ends take the constraint's width; a run of an end that is not on that
  axis is left alone.
- Reads Layer 4 only through the FeatureConstraint, the island's stitched
  Chains and Layer 1 uses (which Chain a use lies on). Nothing of the user
  filter but the island it made, no world axis, no 3D direction, no ladder
  relation or bevel record.
- Every strip in a quilt gets an outcome; each "not read" outcome but the
  expected ones (both rails stitched, a rigid frame) is also a diagnostic.
  A strip read whose quilt pins none of its run ends gets its own outcome
  after the solve (QUILT_LADDER_NOTHING_PINNED), not "kept together".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scaffold_core.layer_4_features.model import FeatureConstraintKind

QUILT_LADDER_READ = "kept together"
QUILT_LADDER_BOTH_STITCHED = "both rails stitched"
QUILT_LADDER_RIGID_FRAME = "its quilt has a rigid frame"
QUILT_LADDER_NO_RAIL_STITCHED = "no rail stitched"
QUILT_LADDER_RAIL_NOT_LAID = "its stitched rail is not laid on an axis"
QUILT_LADDER_FREE_RAIL_ACROSS = "its free rail has a run on the across axis"
QUILT_LADDER_OFF_LADDER = "a run end is not on the ladder"
QUILT_LADDER_NOTHING_PINNED = "it meets the conditions but its quilt pins none of its vertices"
QUILT_LADDER_OUTSIDE_FRAME = "its patch is outside the quilt's rigid frame, not laid"
# Outcomes that are expected and stay out of the diagnostics.
QUIET_OUTCOMES = frozenset((QUILT_LADDER_READ, QUILT_LADDER_BOTH_STITCHED, QUILT_LADDER_RIGID_FRAME))
NOT_READ_PREFIX = "ladder strip in a quilt not read"
PIECES_PREFIX = "ladder strip in a quilt read in pieces"
_AXES = ("AXIS_A", "AXIS_B")
_ACROSS = {"AXIS_A": "AXIS_B", "AXIS_B": "AXIS_A"}


@dataclass(frozen=True)
class LadderTie:
    """A free-rail vertex of a strip read in its quilt, placed after the pins are known.

    Keys are (vertex occurrence, patch) pin keys. Along the rail axis of its
    piece (along_index 0 = u from AXIS_A, 1 = v from AXIS_B) the vertex takes
    the coordinate of partner, its profile-line partner on the stitched rail.
    Across it lies on the straight line between the free-rail vertices of
    its piece's first and last line (corners), at t, its profile line's u
    from the first line over the piece's length; with one corner pinned, on
    that corner's row.
    """

    key: tuple[str, str]
    source_vertex_id: str
    partner: tuple[str, str]
    corners: tuple[tuple[str, str], tuple[str, str]]
    t: float
    along_index: int


def quilt_ladders_by_island(context: Any, assembly: Any) -> dict[str, list]:
    """STRAIGHT_LADDER constraints whose patch shares its island with other patches."""

    features = getattr(context, "feature_snapshot", None)
    if features is None:
        return {}
    size = {island.id: len(island.patch_ids) for island in assembly.islands}
    result: dict[str, list] = {}
    for constraint in features.constraints:
        if constraint.kind is not FeatureConstraintKind.STRAIGHT_LADDER or constraint.ladder is None:
            continue
        island_id = assembly.island_by_patch_id.get(str(constraint.patch_id))
        if island_id is not None and size[island_id] > 1:
            result.setdefault(island_id, []).append(constraint)
    return result


def stitched_rail_uses(constraints, island, runs, vertex_by_run_end, patch_chain_by_id) -> dict[str, tuple[str, ...]]:
    """The uses of each strip's stitched rail whose Chain the quilt stitches (plan Slice AL).

    Only a strip that read_quilt_ladders could read gets an entry: every run
    end of its patch is on the ladder and exactly one of its rails is
    stitched. The mark says that rail is straight; the frame-free consumer
    makes it one island line (frame_free.join_marked_rails). Returns patch ->
    the stitched uses of that rail, in id order; the free rail is never named.
    """

    stitched = set(island.stitched_chain_ids)
    uses_by_patch: dict[str, tuple[str, ...]] = {}
    for constraint in sorted(constraints, key=lambda item: str(item.patch_id)):
        patch_id = str(constraint.patch_id)
        ladder = constraint.ladder
        if not _on_ladder(ladder, [e for e in runs if str(e.patch_id) == patch_id], vertex_by_run_end):
            continue
        rails = (ladder.rail_a_patch_chain_ids, ladder.rail_b_patch_chain_ids)
        stitched_rails = [uses for uses in rails if _is_stitched(uses, stitched, patch_chain_by_id)]
        if len(stitched_rails) != 1:
            continue
        uses_by_patch[patch_id] = tuple(sorted(
            str(use) for use in stitched_rails[0] if str(patch_chain_by_id[str(use)].chain_id) in stitched
        ))
    return uses_by_patch


def read_quilt_ladders(constraints, island, runs, roles, signs, vertex_by_run_end, patch_chain_by_id, diagnostics):
    """Read each ladder strip of a frame-free quilt once its lines are oriented (see the module rules).

    Removes the signs of the free rail's runs on the rail axis (signs is
    changed in place). Returns the run lengths to solve with (None when no
    length changes), the ties of the free-rail vertices and the outcome per
    strip patch.
    """

    stitched = set(island.stitched_chain_ids)
    length_of = {e.id: e.length for e in runs}
    changed = False
    ties: list[LadderTie] = []
    outcomes: dict[str, str] = {}
    for constraint in sorted(constraints, key=lambda item: str(item.patch_id)):
        patch_id = str(constraint.patch_id)
        ladder = constraint.ladder
        patch_runs = sorted((e for e in runs if str(e.patch_id) == patch_id), key=lambda e: e.id)
        fraction = _fractions(ladder)
        if not _on_ladder(ladder, patch_runs, vertex_by_run_end):
            outcome = QUILT_LADDER_OFF_LADDER
        else:
            outcome, read = _read_strip(ladder, patch_runs, roles, signs, stitched, patch_chain_by_id, vertex_by_run_end)
        outcomes[patch_id] = outcome
        if outcome not in QUIET_OUTCOMES:
            diagnostics.append(f"{NOT_READ_PREFIX}, {outcome}: {patch_id}")
        if outcome != QUILT_LADDER_READ:
            continue
        free, pieces, groups = read
        line_index = _line_index(ladder)
        for e in groups[free]:
            piece = _piece_holding(_line_span(e, line_index, vertex_by_run_end), pieces)
            if piece is not None and roles.get(e.id) == piece[2]:
                signs.pop(e.id, None)  # an unsigned run: no length equation
        end_axes = []
        for line in (0, len(ladder.profile_lines) - 1):
            piece = _piece_holding((line, line), pieces)
            end_axes.append(None if piece is None else _ACROSS[piece[2]])
        changed |= _follow_width(ladder, groups[2:], fraction, vertex_by_run_end, roles, end_axes, length_of, stitched,
                                 patch_chain_by_id)
        for first, last, axis in pieces:
            ties.extend(_ties(ladder, patch_id, free, 0 if axis == "AXIS_A" else 1, first, last))
        outside = len(ladder.profile_lines) - sum(last - first + 1 for first, last, _axis in pieces)
        if outside:
            diagnostics.append(f"{PIECES_PREFIX}, {outside} profile lines on no piece -> not tied: {patch_id}")
    return (length_of if changed else None), tuple(ties), outcomes


def rigid_frame_outcomes(constraints, framed_patch_ids, diagnostics) -> dict[str, str]:
    """Outcomes in a quilt with a rigid unfolded frame: a strip in the frame is unfolded exactly.

    A strip whose patch the frame does not reach (behind a warped patch or a
    bent hinge) is laid by no axis: it gets its own outcome and a diagnostic.
    """

    outcomes = {}
    for constraint in sorted(constraints, key=lambda item: str(item.patch_id)):
        patch_id = str(constraint.patch_id)
        if patch_id in framed_patch_ids:
            outcomes[patch_id] = QUILT_LADDER_RIGID_FRAME
        else:
            outcomes[patch_id] = QUILT_LADDER_OUTSIDE_FRAME
            diagnostics.append(f"{NOT_READ_PREFIX}, {QUILT_LADDER_OUTSIDE_FRAME}: {patch_id}")
    return outcomes


def drop_strips_without_pins(outcomes, ties, runs, node_by_run_end, uv_nodes, diagnostics):
    """A strip read whose quilt gives none of its run ends both coordinates keeps nothing together.

    uv_nodes holds the solve nodes with both coordinates. Such a strip gets
    the outcome QUILT_LADDER_NOTHING_PINNED with a diagnostic and loses its
    ties and its "read in pieces" diagnostic (diagnostics is changed in
    place): it is not read. Returns the outcomes and the ties.
    """

    empty = {
        patch_id for patch_id, outcome in outcomes.items()
        if outcome == QUILT_LADDER_READ and not any(
            node_by_run_end[(e.id, role)] in uv_nodes
            for e in runs if str(e.patch_id) == patch_id for role in ("START", "END")
        )
    }
    unread = tuple(f"-> not tied: {patch_id}" for patch_id in empty)
    diagnostics[:] = [
        message for message in diagnostics
        if not (message.startswith(PIECES_PREFIX) and message.endswith(unread))
    ]
    for patch_id in sorted(empty):
        diagnostics.append(f"{NOT_READ_PREFIX}, {QUILT_LADDER_NOTHING_PINNED}: {patch_id}")
    if not empty:
        return outcomes, ties
    return (
        {patch_id: QUILT_LADDER_NOTHING_PINNED if patch_id in empty else outcome for patch_id, outcome in outcomes.items()},
        tuple(tie for tie in ties if tie.key[1] not in empty),
    )


def _read_strip(ladder, patch_runs, roles, signs, stitched, patch_chain_by_id, vertex_by_run_end):
    """The outcome for one strip, and when it is read (free rail index, pieces, run groups)."""

    groups = tuple(
        [e for e in patch_runs if str(e.patch_chain_id) in {str(use) for use in uses}]
        for uses in (
            ladder.rail_a_patch_chain_ids, ladder.rail_b_patch_chain_ids,
            ladder.end_a_patch_chain_ids, ladder.end_b_patch_chain_ids,
        )
    )
    stitched_rails = [_is_stitched(uses, stitched, patch_chain_by_id)
                      for uses in (ladder.rail_a_patch_chain_ids, ladder.rail_b_patch_chain_ids)]
    if all(stitched_rails):
        return QUILT_LADDER_BOTH_STITCHED, None
    if not any(stitched_rails):
        return QUILT_LADDER_NO_RAIL_STITCHED, None
    lead = 0 if stitched_rails[0] else 1
    free = 1 - lead
    line_index = _line_index(ladder)
    pieces = _pieces(len(ladder.profile_lines), groups[lead], roles, signs, line_index, vertex_by_run_end)
    if not pieces:
        return QUILT_LADDER_RAIL_NOT_LAID, None
    for e in groups[free]:
        piece = _piece_holding(_line_span(e, line_index, vertex_by_run_end), pieces)
        if piece is not None and roles.get(e.id) == _ACROSS[piece[2]]:
            return QUILT_LADDER_FREE_RAIL_ACROSS, None
    return QUILT_LADDER_READ, (free, pieces, groups)


def _line_index(ladder) -> dict[str, int]:
    """Rail vertex occurrence -> the index of its profile line (both rails)."""

    index: dict[str, int] = {}
    for i, line in enumerate(ladder.profile_lines):
        index[str(line.rail_a.vertex_id)] = i
        index[str(line.rail_b.vertex_id)] = i
    return index


def _line_span(e, line_index, vertex_by_run_end) -> tuple[int, int] | None:
    """The first and last profile line a rail run holds (the lines of its two ends), or None."""

    ends = [line_index.get(vertex_by_run_end.get((e.id, role))) for role in ("START", "END")]
    if None in ends:
        return None
    return min(ends), max(ends)


def _pieces(line_count, stitched_runs, roles, signs, line_index, vertex_by_run_end) -> tuple[tuple[int, int, str], ...]:
    """The stitched rail cut where the axis the quilt lays it on changes: (first line, last line, axis).

    A signed run of the stitched rail on an axis holds the profile lines
    from one of its ends to the other. A line held on exactly one axis is in
    a piece; a line held on both axes (a corner where two runs meet) or on
    none is in no piece. Two neighbouring lines are in one piece when one run
    holds both. The axes are the quilt's roles (Layer 3 lines through the
    solve's bipartition); no vertex or run is walked.
    """

    axes: dict[int, set[str]] = {}
    spans: dict[str, list[tuple[int, int]]] = {axis: [] for axis in _AXES}
    for e in stitched_runs:
        span = _line_span(e, line_index, vertex_by_run_end)
        if roles.get(e.id) not in _AXES or e.id not in signs or span is None:
            continue
        spans[roles[e.id]].append(span)
        for line in range(span[0], span[1] + 1):
            axes.setdefault(line, set()).add(roles[e.id])
    pieces: list[list] = []
    for line in range(line_count):
        held = axes.get(line, set())
        if len(held) != 1:
            continue
        (axis,) = held
        previous = pieces[-1] if pieces else None
        if (
            previous is not None and previous[1] == line - 1 and previous[2] == axis
            and any(first <= line - 1 and line <= last for first, last in spans[axis])
        ):
            previous[1] = line
        else:
            pieces.append([line, line, axis])
    return tuple((first, last, axis) for first, last, axis in pieces)


def _piece_holding(span, pieces):
    """The piece whose lines hold the whole span, or None."""

    if span is None:
        return None
    return next((piece for piece in pieces if piece[0] <= span[0] and span[1] <= piece[1]), None)


def _follow_width(ladder, end_groups, fraction, vertex_by_run_end, roles, end_axes, length_of, stitched,
                  patch_chain_by_id) -> bool:
    """Lengths of the free ends' runs on the across axis: a stitched end leads, else the constraint's width.

    end_axes gives each end's across axis: the across axis of the piece
    that holds the end's profile line, None when no piece holds it. A run of
    a free end on its across axis takes its share of the width (the
    constraint's fractions across the end line) times the width to follow.
    With both ends stitched, or with the stitched end not wholly on its
    across axis, nothing changes. Returns whether a length changed.
    """

    end_uses = (ladder.end_a_patch_chain_ids, ladder.end_b_patch_chain_ids)
    stitched_ends = [index for index, uses in enumerate(end_uses) if _is_stitched(uses, stitched, patch_chain_by_id)]
    if len(stitched_ends) == 2:
        return False
    if stitched_ends:
        leading = end_groups[stitched_ends[0]]
        across_axis = end_axes[stitched_ends[0]]
        if not leading or across_axis is None or any(roles.get(e.id) != across_axis for e in leading):
            return False
        width = sum(e.length for e in leading)
    else:
        width = ladder.width
    changed = False
    for index, group in enumerate(end_groups):
        if index in stitched_ends:
            continue
        for e in group:
            share = abs(fraction[vertex_by_run_end[(e.id, "END")]] - fraction[vertex_by_run_end[(e.id, "START")]])
            if end_axes[index] is not None and roles.get(e.id) == end_axes[index] and share > 0.0:
                length_of[e.id] = share * width
                changed = True
    return changed


def _ties(ladder, patch_id: str, free: int, along_index: int, first: int, last: int) -> list[LadderTie]:
    """One tie per profile line of one piece (lines first..last): its free-rail vertex to its stitched-rail partner.

    The piece's corners are the free-rail vertices of its first and last
    line; t is the line's u measured from the first line over the piece's
    length along the strip.
    """

    def ends(line):
        return (line.rail_a, line.rail_b) if free == 1 else (line.rail_b, line.rail_a)

    lines = ladder.profile_lines[first:last + 1]
    corners = tuple((str(ends(line)[1].vertex_id), patch_id) for line in (lines[0], lines[-1]))
    span = lines[-1].u - lines[0].u
    ties = []
    for line in lines:
        partner, vertex = ends(line)
        ties.append(LadderTie(
            key=(str(vertex.vertex_id), patch_id),
            source_vertex_id=str(vertex.source_vertex_id),
            partner=(str(partner.vertex_id), patch_id),
            corners=corners,
            t=(line.u - lines[0].u) / span if span > 0.0 else 0.0,
            along_index=along_index,
        ))
    return ties


def tie_free_rails(ties, uv_by_key: Mapping, fixed_keys) -> tuple[dict, set, int]:
    """Places of the tied free-rail vertices from the island's pins.

    uv_by_key holds the island's pins by key; a key in fixed_keys (a
    run-end pin of the solve) is never moved. A tie whose partner has no
    pin, or whose rail has no pinned corner, leaves its vertex unpinned (any
    station pin it had is dropped) and is counted. Returns the places
    (key -> (source vertex, uv)), the keys to unpin and that count.
    """

    placed: dict = {}
    cleared: set = set()
    untied = 0
    for tie in ties:
        if tie.key in fixed_keys:
            continue
        partner = uv_by_key.get(tie.partner)
        first, last = (uv_by_key.get(key) for key in tie.corners)
        if partner is None or (first is None and last is None):
            cleared.add(tie.key)
            untied += 1
            continue
        across_index = 1 - tie.along_index
        if first is None or last is None:
            across = (first or last)[across_index]
        else:
            across = first[across_index] + tie.t * (last[across_index] - first[across_index])
        along = partner[tie.along_index]
        placed[tie.key] = (tie.source_vertex_id, (along, across) if tie.along_index == 0 else (across, along))
    return placed, cleared, untied


def _fractions(ladder) -> dict[str, float]:
    """Vertex occurrence -> its fraction of the width across the strip (rail A 0, rail B 1)."""

    fraction: dict[str, float] = {}
    for line in ladder.profile_lines:
        fraction[str(line.rail_a.vertex_id)] = 0.0
        fraction[str(line.rail_b.vertex_id)] = 1.0
        for vertex, share in line.across:
            fraction[str(vertex.vertex_id)] = share
    return fraction


def _on_ladder(ladder, patch_runs, vertex_by_run_end) -> bool:
    """Every run end of the strip's patch is a vertex of the ladder."""

    fraction = _fractions(ladder)
    return all(vertex_by_run_end.get((e.id, role)) in fraction for e in patch_runs for role in ("START", "END"))


def _is_stitched(uses, stitched: set, patch_chain_by_id) -> bool:
    return any(str(patch_chain_by_id[str(use)].chain_id) in stitched for use in uses)
