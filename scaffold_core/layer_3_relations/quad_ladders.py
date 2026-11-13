"""
Layer: 3 - Relations

Rules:
- Build PatchQuadLadderRelation v0 evidence: the ways an all-quad patch is
  crossed by edge-ring columns from one part of its boundary to another.
- Pure topology over Layer 0 faces and Layer 1 patches, chains and uses: no
  position, length, normal, angle or direction is read, so noise and
  curvature cannot change a reading.
- Keep every reading (zero, one or two per patch); do not choose one and do
  not read neighbours, widths or lengths.
- Evidence only: no role, feature, world direction, UV, solve, API, UI or
  runtime semantics, and no Layer 1 identity is created or changed.
"""

from __future__ import annotations

from collections import defaultdict

from scaffold_core.ids import PatchChainId, PatchId, SourceEdgeId, SourceFaceId, SourceVertexId
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.model import PatchChain, SurfaceModel
from scaffold_core.layer_3_relations.model import PatchQuadLadderReading, PatchQuadLadderRelation

QUAD_VERTEX_COUNT = 4

# Why a patch, or one colour class of its columns, gives no reading. The
# builder keeps them for callers that count reasons (inspection, probes).
REASON_NOT_ALL_QUADS = "not_all_quads"
REASON_SELF_CROSSING_COLUMN = "self_crossing_column"
REASON_NOT_TWO_WAY = "columns_not_two_way"
REASON_CLOSED_COLUMNS = "closed_columns"
REASON_FOLDED_COLUMN = "folded_column"
REASON_COLUMNS_NOT_ALIGNED = "columns_not_aligned"
REASON_NOT_ONE_PATH_OR_RING = "columns_not_one_path_or_ring"
REASON_NOT_ORIENTABLE = "ring_not_orientable"


def build_patch_quad_ladder_relations(
    topology: SurfaceModel,
    source: SourceMeshSnapshot | None,
) -> tuple[PatchQuadLadderRelation, ...]:
    """One record per patch with at least one ladder reading, in patch order."""

    relations, _reasons = patch_quad_ladder_relations_with_reasons(topology, source)
    return relations


def patch_quad_ladder_relations_with_reasons(
    topology: SurfaceModel,
    source: SourceMeshSnapshot | None,
) -> tuple[tuple[PatchQuadLadderRelation, ...], dict[PatchId, tuple[str, ...]]]:
    """The records, and for every patch without one the reasons it has none."""

    if source is None:
        return (), {}
    uses_by_patch_edge: dict[tuple[PatchId, SourceEdgeId], list[PatchChain]] = defaultdict(list)
    for use in topology.patch_chains.values():
        chain = topology.chains.get(use.chain_id)
        if chain is None:
            continue
        for edge_id in chain.source_edge_ids:
            uses_by_patch_edge[(use.patch_id, edge_id)].append(use)
    edge_rank = {edge_id: rank for rank, edge_id in enumerate(source.edges)}
    use_directions: dict[PatchChainId, frozenset] = {}

    relations: list[PatchQuadLadderRelation] = []
    reasons: dict[PatchId, tuple[str, ...]] = {}
    for patch_id, patch in topology.patches.items():
        builder = _PatchLadders(topology, source, patch_id, patch.source_face_ids, uses_by_patch_edge, edge_rank, use_directions)
        readings, closed_count, patch_reasons = builder.readings()
        if not readings:
            reasons[patch_id] = patch_reasons
            continue
        relations.append(
            PatchQuadLadderRelation(
                id=f"patch_quad_ladder:{patch_id}",
                patch_id=patch_id,
                face_count=len(patch.source_face_ids),
                readings=readings,
                closed_column_count=closed_count,
                confidence=1.0,
            )
        )
    return tuple(relations), reasons


class _PatchLadders:
    """Edge-ring columns of one patch; a short-lived working set, not a record."""

    def __init__(self, topology, source, patch_id, face_ids, uses_by_patch_edge, edge_rank, use_directions):
        self.topology = topology
        self.source = source
        self.patch_id = patch_id
        self.face_ids = tuple(face_ids)
        self.face_rank = {face_id: rank for rank, face_id in enumerate(self.face_ids)}
        self.uses_by_patch_edge = uses_by_patch_edge
        self.edge_rank = edge_rank
        self.use_directions = use_directions

    # ------------------------------------------------------------------ cells

    def _cells(self) -> bool:
        """Per face its vertex cycle and edges[i] = edge(cycle[i], cycle[i + 1]); False unless all quads."""

        self.cycle: dict[SourceFaceId, tuple[SourceVertexId, ...]] = {}
        self.edges: dict[SourceFaceId, tuple[SourceEdgeId, ...]] = {}
        self.edge_faces: dict[SourceEdgeId, list[SourceFaceId]] = defaultdict(list)
        for face_id in self.face_ids:
            face = self.source.faces.get(face_id)
            if face is None or len(face.vertex_ids) != QUAD_VERTEX_COUNT or len(set(face.vertex_ids)) != QUAD_VERTEX_COUNT:
                return False
            by_ends = {}
            for edge_id in face.edge_ids:
                edge = self.source.edges.get(edge_id)
                if edge is None:
                    return False
                by_ends[frozenset(edge.vertex_ids)] = edge_id
            cycle = tuple(face.vertex_ids)
            edges = []
            for index in range(QUAD_VERTEX_COUNT):
                edge_id = by_ends.get(frozenset((cycle[index], cycle[(index + 1) % QUAD_VERTEX_COUNT])))
                if edge_id is None:
                    return False
                edges.append(edge_id)
            self.cycle[face_id] = cycle
            self.edges[face_id] = tuple(edges)
            for edge_id in edges:
                self.edge_faces[edge_id].append(face_id)
        return True

    def _interior(self, edge_id: SourceEdgeId) -> bool:
        """Two faces of this patch meet across it and it lies on no Chain."""

        if (self.patch_id, edge_id) in self.uses_by_patch_edge:
            return False
        faces = self.edge_faces.get(edge_id, ())
        return len(faces) == 2 and faces[0] != faces[1]

    # ---------------------------------------------------------------- strands

    def _walk(self, face_id, entry):
        """Edge-ring walk entering face_id at edge position entry; ends at a boundary edge or back at the start."""

        start = (face_id, entry % 2)
        sequence = [(face_id, entry)]
        current, position = face_id, entry
        for _step in range(2 * len(self.face_ids) + 2):
            exit_edge = self.edges[current][(position + 2) % QUAD_VERTEX_COUNT]
            if not self._interior(exit_edge):
                return sequence, exit_edge, False
            first, second = self.edge_faces[exit_edge]
            following = second if first == current else first
            following_position = self.edges[following].index(exit_edge)
            if (following, following_position % 2) == start:
                return sequence, None, True
            sequence.append((following, following_position))
            current, position = following, following_position
        return sequence, None, True  # unreachable on a finite patch: the walk is reversible

    def _strands(self):
        """Every edge ring of the patch, as (face, entry position) steps with its two boundary ends."""

        strand_of: dict[tuple[SourceFaceId, int], int] = {}
        strands = []
        for face_id in self.face_ids:
            for pair in (0, 1):
                if (face_id, pair) in strand_of:
                    continue
                forward, end_edge, closed = self._walk(face_id, pair)
                if closed:
                    steps, start_edge = forward, None
                else:
                    backward, start_edge, _closed = self._walk(face_id, pair + 2)
                    steps = [
                        (step_face, (step_position + 2) % QUAD_VERTEX_COUNT)
                        for step_face, step_position in reversed(backward[1:])
                    ] + forward
                index = len(strands)
                folded = False
                for step_face, step_position in steps:
                    key = (step_face, step_position % 2)
                    if key in strand_of:
                        folded = True
                    strand_of[key] = index
                strands.append({
                    "steps": steps,
                    "start_edge": start_edge,
                    "end_edge": end_edge,
                    "closed": closed,
                    "folded": folded,
                })
        return strands, strand_of

    # --------------------------------------------------------------- readings

    def readings(self):
        if not self._cells():
            return (), 0, (REASON_NOT_ALL_QUADS,)
        strands, strand_of = self._strands()
        closed_count = sum(1 for strand in strands if strand["closed"])
        conflicts: dict[int, set[int]] = defaultdict(set)
        for face_id in self.face_ids:
            first, second = strand_of[(face_id, 0)], strand_of[(face_id, 1)]
            if first == second:
                return (), closed_count, (REASON_SELF_CROSSING_COLUMN,)
            conflicts[first].add(second)
            conflicts[second].add(first)
        colour: dict[int, int] = {}
        for seed in range(len(strands)):
            if seed in colour:
                continue
            colour[seed] = 0
            stack = [seed]
            while stack:
                index = stack.pop()
                for other in conflicts[index]:
                    if other not in colour:
                        colour[other] = 1 - colour[index]
                        stack.append(other)
                    elif colour[other] == colour[index]:
                        return (), closed_count, (REASON_NOT_TWO_WAY,)
        found = []
        reasons = []
        for wanted in (0, 1):
            members = [strands[index] for index in range(len(strands)) if colour.get(index) == wanted]
            if not members:
                continue
            reading = self._reading(members)
            if isinstance(reading, str):
                reasons.append(reading)
            else:
                found.append(reading)
        found.sort(key=lambda item: (
            -len(item.columns),
            self.face_rank[item.columns[0][0]],
            self.edge_rank.get(item.rail_a_source_edge_ids[0], -1),
        ))
        return tuple(found), closed_count, tuple(reasons)

    def _reading(self, members):
        if any(strand["closed"] for strand in members):
            return REASON_CLOSED_COLUMNS
        if any(strand["folded"] for strand in members):
            return REASON_FOLDED_COLUMN
        columns = []
        for strand in members:
            column = self._column(strand)
            if column is None:
                return REASON_COLUMNS_NOT_ALIGNED
            columns.append(column)
        links = self._links(columns)
        if links is None:
            return REASON_COLUMNS_NOT_ALIGNED
        order = self._order(columns, links)
        if order is None:
            return REASON_NOT_ONE_PATH_OR_RING
        oriented = self._orient(columns, order)
        if oriented is None:
            return REASON_NOT_ORIENTABLE
        return self._canonical(*oriented)

    def _column(self, strand):
        """Faces, rail edges and the two side lines (vertex and edge sequences, rail A to rail B)."""

        steps = strand["steps"]
        first_face, first_position = steps[0]
        cycle = self.cycle[first_face]
        lines = []
        for start_vertex in (cycle[first_position], cycle[(first_position + 1) % QUAD_VERTEX_COUNT]):
            vertices, edges = [start_vertex], []
            current = start_vertex
            for face_id, position in steps:
                face_cycle = self.cycle[face_id]
                face_edges = self.edges[face_id]
                if current == face_cycle[position]:
                    side = (position + 3) % QUAD_VERTEX_COUNT
                    following = face_cycle[(position + 3) % QUAD_VERTEX_COUNT]
                elif current == face_cycle[(position + 1) % QUAD_VERTEX_COUNT]:
                    side = (position + 1) % QUAD_VERTEX_COUNT
                    following = face_cycle[(position + 2) % QUAD_VERTEX_COUNT]
                else:
                    return None
                edges.append(face_edges[side])
                vertices.append(following)
                current = following
            lines.append((tuple(vertices), tuple(edges)))
        return {
            "faces": tuple(face_id for face_id, _position in steps),
            "rail_a": strand["start_edge"],
            "rail_b": strand["end_edge"],
            "lines": lines,
        }

    def _links(self, columns):
        """(column, side) -> the (column, side) sharing that whole profile line, or None at the boundary."""

        owners: dict[SourceEdgeId, list[tuple[int, int]]] = defaultdict(list)
        for column_index, column in enumerate(columns):
            for side, (_vertices, edges) in enumerate(column["lines"]):
                for edge_id in edges:
                    owners[edge_id].append((column_index, side))
        links: dict[tuple[int, int], tuple[int, int] | None] = {}
        for column_index, column in enumerate(columns):
            for side, (_vertices, edges) in enumerate(column["lines"]):
                me = (column_index, side)
                partners = set()
                boundary = 0
                for edge_id in edges:
                    if not self._interior(edge_id):
                        boundary += 1
                        continue
                    others = [owner for owner in owners[edge_id] if owner != me]
                    if len(others) != 1:
                        return None
                    partners.add(others[0])
                if boundary == len(edges):
                    links[me] = None
                    continue
                if boundary or len(partners) != 1:
                    return None
                partner = next(iter(partners))
                if partner[0] == column_index:
                    return None
                if len(columns[partner[0]]["lines"][partner[1]][1]) != len(edges):
                    return None
                links[me] = partner
        return links

    def _order(self, columns, links):
        """Columns in profile order with their incoming side; a path or one ring, else None."""

        boundary_slots = [slot for slot, partner in links.items() if partner is None]
        if len(boundary_slots) == 2:
            start, closed = min(boundary_slots), False
        elif not boundary_slots:
            start, closed = (0, 0), True
        else:
            return None
        order = []
        seen = set()
        column_index, incoming = start
        while True:
            if column_index in seen:
                return None
            seen.add(column_index)
            order.append((column_index, incoming))
            partner = links[(column_index, 1 - incoming)]
            if partner is None:
                break
            if closed and partner[0] == start[0]:
                if partner != start:
                    return None
                break
            column_index, incoming = partner
        if len(order) != len(columns):
            return None
        return order, closed

    def _orient(self, columns, order_and_closed):
        """Flip columns so every shared profile line runs the same way; None for a twisted ring."""

        order, closed = order_and_closed
        oriented = []
        previous_line = None
        for column_index, incoming in order:
            column = columns[column_index]
            line_in = column["lines"][incoming]
            if previous_line is None:
                flip = False
            elif line_in[0] == previous_line[0]:
                flip = False
            elif tuple(reversed(line_in[0])) == previous_line[0]:
                flip = True
            else:
                return None
            line_out = column["lines"][1 - incoming]
            if flip:
                line_in, line_out = _reversed_line(line_in), _reversed_line(line_out)
                faces, rail_a, rail_b = tuple(reversed(column["faces"])), column["rail_b"], column["rail_a"]
            else:
                faces, rail_a, rail_b = column["faces"], column["rail_a"], column["rail_b"]
            oriented.append({"faces": faces, "rail_a": rail_a, "rail_b": rail_b, "in": line_in, "out": line_out})
            previous_line = line_out
        if closed and oriented[-1]["out"][0] != oriented[0]["in"][0]:
            return None
        lines = [column["in"] for column in oriented]
        if not closed:
            lines.append(oriented[-1]["out"])
        return oriented, lines, closed

    def _canonical(self, columns, lines, closed):
        """The smallest of the equivalent orientations by patch face order, then rail A edge order."""

        count = len(columns)
        if closed:
            first = min(range(count), key=lambda index: min(self.face_rank[face] for face in columns[index]["faces"]))
            columns = columns[first:] + columns[:first]
            lines = lines[first:] + lines[:first]
            reversed_columns = [columns[(-index) % count] for index in range(count)]
            reversed_lines = [lines[(1 - index) % count] for index in range(count)]
        else:
            reversed_columns = list(reversed(columns))
            reversed_lines = list(reversed(lines))
        candidates = []
        for ordered_columns, ordered_lines in ((columns, lines), (reversed_columns, reversed_lines)):
            for flip in (False, True):
                if flip:
                    candidate_columns = [
                        {"faces": tuple(reversed(column["faces"])), "rail_a": column["rail_b"], "rail_b": column["rail_a"]}
                        for column in ordered_columns
                    ]
                    candidate_lines = [_reversed_line(line) for line in ordered_lines]
                else:
                    candidate_columns, candidate_lines = ordered_columns, ordered_lines
                key = (
                    tuple(self.face_rank[face] for column in candidate_columns for face in column["faces"]),
                    tuple(self.edge_rank.get(column["rail_a"], -1) for column in candidate_columns),
                    tuple(self.edge_rank.get(edge, -1) for line in candidate_lines for edge in line[1]),
                )
                candidates.append((key, candidate_columns, candidate_lines))
        _key, best_columns, best_lines = min(candidates, key=lambda item: item[0])
        return self._record(best_columns, best_lines, closed)

    def _record(self, columns, lines, closed) -> PatchQuadLadderReading:
        rail_a_uses = [self._use_on_face_side(column["faces"][0], column["rail_a"]) for column in columns]
        rail_b_uses = [self._use_on_face_side(column["faces"][-1], column["rail_b"]) for column in columns]
        if closed:
            end_a_edges, end_b_edges = (), ()
            end_a_uses, end_b_uses = [], []
        else:
            end_a_edges, end_b_edges = lines[0][1], lines[-1][1]
            end_a_uses = [self._use_on_face_side(face, edge) for face, edge in zip(columns[0]["faces"], end_a_edges)]
            end_b_uses = [self._use_on_face_side(face, edge) for face, edge in zip(columns[-1]["faces"], end_b_edges)]
        sides = [_ordered_unique(uses) for uses in (rail_a_uses, rail_b_uses, end_a_uses, end_b_uses)]
        side_count: dict[PatchChainId, int] = defaultdict(int)
        for side in sides:
            for use_id in side:
                side_count[use_id] += 1
        return PatchQuadLadderReading(
            columns=tuple(column["faces"] for column in columns),
            faces_per_column=len(columns[0]["faces"]),
            is_closed=closed,
            rail_a_source_edge_ids=tuple(column["rail_a"] for column in columns),
            rail_b_source_edge_ids=tuple(column["rail_b"] for column in columns),
            rail_a_patch_chain_ids=sides[0],
            rail_b_patch_chain_ids=sides[1],
            end_a_source_edge_ids=tuple(end_a_edges),
            end_b_source_edge_ids=tuple(end_b_edges),
            end_a_patch_chain_ids=sides[2],
            end_b_patch_chain_ids=sides[3],
            profile_vertex_ids=tuple(line[0] for line in lines),
            profile_edge_ids=tuple(line[1] for line in lines),
            shared_patch_chain_ids=tuple(sorted((use_id for use_id, count in side_count.items() if count > 1), key=str)),
        )

    # ------------------------------------------------------------------- uses

    def _use_on_face_side(self, face_id: SourceFaceId, edge_id: SourceEdgeId) -> PatchChainId | None:
        """The use of this patch on face_id's side of boundary edge_id (DD-51: a use walks as its faces wind)."""

        uses = self.uses_by_patch_edge.get((self.patch_id, edge_id), ())
        if len(uses) == 1:
            return uses[0].id
        if not uses:
            return None
        cycle = self.cycle[face_id]
        position = self.edges[face_id].index(edge_id)
        directed = (edge_id, cycle[position], cycle[(position + 1) % QUAD_VERTEX_COUNT])
        for use in uses:
            if directed in self._directed_edges(use):
                return use.id
        return None

    def _directed_edges(self, use: PatchChain) -> frozenset:
        """(edge, from, to) for each source edge of a use, walked from the use's start vertex."""

        if use.id in self.use_directions:
            return self.use_directions[use.id]
        chain = self.topology.chains[use.chain_id]
        edges = list(chain.source_edge_ids)
        if use.orientation_sign < 0:
            edges.reverse()
        start_vertex = self.topology.vertices.get(use.start_vertex_id) if use.start_vertex_id is not None else None
        result: frozenset = frozenset()
        if start_vertex is not None and start_vertex.source_vertex_ids:
            start = start_vertex.source_vertex_ids[0]
            for offset in range(len(edges)):  # a closed chain may start anywhere
                walked = self._walk_edges(edges[offset:] + edges[:offset], start)
                if walked is not None:
                    result = frozenset(walked)
                    break
        self.use_directions[use.id] = result
        return result

    def _walk_edges(self, edges, start):
        current = start
        walked = []
        for edge_id in edges:
            first, second = self.source.edges[edge_id].vertex_ids
            if current == first:
                walked.append((edge_id, first, second))
                current = second
            elif current == second:
                walked.append((edge_id, second, first))
                current = first
            else:
                return None
        return walked


def _reversed_line(line):
    vertices, edges = line
    return tuple(reversed(vertices)), tuple(reversed(edges))


def _ordered_unique(items) -> tuple:
    seen = set()
    out = []
    for item in items:
        if item is None or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)
