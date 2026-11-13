"""
Layer: 4 - Features

Rules:
- The bevel kinds BEVEL_STRIP / BEVEL_JUNCTION (G0 DD-54) and the
  STRAIGHT_LADDER constraint of a marked bevel strip, as plain functions;
  build.py assembles them into the FeatureSnapshot.
- Read Layers 0-3 read-only; never write Layer 3 (G0 DD-25) and never import
  Layer 5.
- The bevel rule reads Layer 0 face marks and face/edge incidence, Layer 1
  patches, chains and uses, and Layer 3 quad ladders and PatchAdjacency;
  no position, length, normal, world axis, UV or island.
- The ladder constraint reads the chosen ladder reading, the Layer 3 shape
  of its rail uses (PatchChainShapeRelation), the Layer 2 edge lengths and
  face fans; no Layer 0 position. It carries every number Layer 5 needs
  (DD-26).
"""

from __future__ import annotations

from collections import defaultdict

from scaffold_core.core.diagnostics import Diagnostic, DiagnosticSeverity
from scaffold_core.ids import PatchId, SourceEdgeId, SourceFaceId
from scaffold_core.layer_0_source.marks import SourceFaceStrength
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.model import SurfaceModel
from scaffold_core.layer_2_geometry.facts import GeometryFactSnapshot
from scaffold_core.layer_2_geometry.measures import EPSILON
from scaffold_core.layer_3_relations.model import (
    DihedralKind,
    PatchChainShapeKind,
    PatchQuadLadderReading,
    RelationSnapshot,
)
from scaffold_core.layer_4_features.model import (
    BevelCornerKind,
    BevelEvidenceSource,
    BevelInstance,
    BevelJunctionContact,
    BevelStripEnd,
    FeatureConstraint,
    FeatureConstraintKind,
    FeatureInstanceStatus,
    FeatureKind,
    FeatureOptions,
    FeatureSuppressionReason,
    LadderProfileLine,
    LadderVertex,
    StraightLadder,
)


# ---------------------------------------------------------------- LADDER constraint
#
# A bevel strip confirmed by the mark is laid from its chosen ladder reading
# (Layer 3) as a straight strip of its own: rails straight and parallel,
# profile lines across, true width. The constraint carries every number the
# layout needs (DD-26): Layer 5 opens neither the ladder nor the bevel record.
# A strip whose two rails are straight on its surface develops as it is and
# is not straightened (plan Slice AI): it is laid like any other patch.

LADDER_NOT_LAID_CODE = "FEATURE_BEVEL_STRIP_NOT_LAID"
NOT_LAID_NO_READING = "no chosen ladder reading"
NOT_LAID_CLOSED = "the reading is a closed ring"
NOT_LAID_SHARED_USE = "a use lies on more than one side"
NOT_LAID_DEGENERATE = "a profile line has no length"
NOT_LAID_DEVELOPS = "both rails are straight on its surface: it develops as it is"


def ladder_constraints(
    bevels: tuple[BevelInstance, ...],
    relations: RelationSnapshot,
    geometry: GeometryFactSnapshot,
    options: FeatureOptions,
) -> tuple[tuple[FeatureConstraint, ...], tuple[Diagnostic, ...]]:
    """One STRAIGHT_LADDER per accepted bevel strip by mark with an open reading and no shared use.

    Only with the option straighten_bevel_strips. A strip by structure
    (a candidate) never emits one. A strip by mark that cannot be laid gets
    a diagnostic naming the patch and the reason (a WARNING).

    A strip that already develops without distortion is not straightened
    (the principle of DD-50, plan Slice AI): when each of its two rails is
    one use whose shape on the strip's own side (DD-48) is exactly one
    SURFACE_LINE, it emits no constraint and gets an INFO diagnostic with
    the same code and the reason NOT_LAID_DEVELOPS. A planar mitred strip
    and a strip that is a piece of a cylinder are such strips. With one rail
    straight and the other not, the strip still emits its constraint.
    """

    if not options.straighten_bevel_strips:
        return (), ()
    ladders = {relation.patch_id: relation for relation in relations.patch_quad_ladder_relations}
    shapes_by_use: dict = defaultdict(list)
    for shape in relations.patch_chain_shape_relations:
        shapes_by_use[shape.patch_chain_id].append(shape.kind)
    occurrence = {
        (face_id, fan.source_vertex_id): fan.vertex_id
        for fan in geometry.local_face_fan_facts.values()
        for face_id in fan.source_face_ids
    }
    constraints = []
    diagnostics = []
    for record in bevels:
        if (
            record.kind is not FeatureKind.BEVEL_STRIP
            or record.status is not FeatureInstanceStatus.ACCEPTED
            or record.source is not BevelEvidenceSource.SOURCE_MARK
        ):
            continue
        if record.reading_index is None:
            ladder, note = None, NOT_LAID_NO_READING
        else:
            reading = ladders[record.patch_id].readings[record.reading_index]
            if reading.is_closed:
                ladder, note = None, NOT_LAID_CLOSED
            elif reading.shared_patch_chain_ids:
                ladder, note = None, NOT_LAID_SHARED_USE
            elif all(
                len(uses) == 1 and shapes_by_use.get(uses[0]) == [PatchChainShapeKind.SURFACE_LINE]
                for uses in (reading.rail_a_patch_chain_ids, reading.rail_b_patch_chain_ids)
            ):
                ladder, note = None, NOT_LAID_DEVELOPS
            else:
                ladder, note = straight_ladder(reading, occurrence, geometry.edge_length_by_source_edge)
        if ladder is None:
            diagnostics.append(
                Diagnostic(
                    code=LADDER_NOT_LAID_CODE,
                    severity=DiagnosticSeverity.INFO if note == NOT_LAID_DEVELOPS else DiagnosticSeverity.WARNING,
                    message=f"Bevel strip {record.patch_id}: not laid from its ladder ({note}).",
                    source="layer_4_features.ladder_constraints",
                    entity_ids=(str(record.patch_id),),
                    evidence={"reason": note},
                )
            )
            continue
        constraints.append(
            FeatureConstraint(
                id=f"feature_constraint:straight_ladder:{record.patch_id}",
                kind=FeatureConstraintKind.STRAIGHT_LADDER,
                instance_id=record.id,
                patch_id=record.patch_id,
                patch_chain_ids=(
                    ladder.rail_a_patch_chain_ids + ladder.rail_b_patch_chain_ids
                    + ladder.end_a_patch_chain_ids + ladder.end_b_patch_chain_ids
                ),
                target_lengths=(ladder.length, ladder.width),
                ladder=ladder,
            )
        )
    return tuple(constraints), tuple(diagnostics)


def straight_ladder(
    reading: PatchQuadLadderReading,
    occurrence: dict,
    edge_length_by_source_edge: dict,
) -> tuple[StraightLadder | None, str | None]:
    """The straight layout of an open reading, or None and the reason.

    u of profile line i is the mean of the two rails' cumulative 3D arc
    lengths from end A to line i, so the strip's length is the mean of its
    rails' lengths. The width is the mean 3D length of the profile lines
    (each a polyline across). An end line's vertices between the rails sit
    at their cumulative fraction of that line's length. A vertex is named by
    its occurrence on the strip's side: the face fan (Layer 2) holding a
    column face at that vertex. Every edge length, on a Chain or inside the
    patch, is the Layer 2 fact edge_length_by_source_edge.

    Every place has an occurrence and no occurrence has two places: the face
    named for a place is a column face with that vertex as a corner, Layer 2
    builds a fan for every corner of every patch face, and a fan joins faces
    only across patch-interior edges, which in an open reading join grid
    neighbours that name the vertex at the same place.
    """

    columns = reading.columns
    lines = reading.profile_vertex_ids
    last_column, last_face = len(columns) - 1, reading.faces_per_column - 1

    def vertex(line_index: int, step: int) -> LadderVertex:
        face_id = columns[min(line_index, last_column)][min(step, last_face)]
        source_vertex = lines[line_index][step]
        return LadderVertex(occurrence[(face_id, source_vertex)], source_vertex)

    def cumulative(edge_ids) -> list[float]:
        walked = [0.0]
        for edge_id in edge_ids:
            walked.append(walked[-1] + edge_length_by_source_edge[edge_id])
        return walked

    rail_a, rail_b = cumulative(reading.rail_a_source_edge_ids), cumulative(reading.rail_b_source_edge_ids)
    across_by_line = [cumulative(edge_ids) for edge_ids in reading.profile_edge_ids]
    if any(walked[-1] <= EPSILON for walked in across_by_line):
        return None, NOT_LAID_DEGENERATE
    width = sum(walked[-1] for walked in across_by_line) / len(across_by_line)
    profile_lines = []
    for index, line in enumerate(lines):
        u = (rail_a[index] + rail_b[index]) / 2.0
        across = []
        if index in (0, len(lines) - 1):
            walked = across_by_line[index]
            for step in range(1, len(line) - 1):
                across.append((vertex(index, step), walked[step] / walked[-1]))
        profile_lines.append(LadderProfileLine(u, vertex(index, 0), vertex(index, len(line) - 1), tuple(across)))
    return (
        StraightLadder(
            width=width,
            length=profile_lines[-1].u,
            profile_lines=tuple(profile_lines),
            rail_a_patch_chain_ids=reading.rail_a_patch_chain_ids,
            rail_b_patch_chain_ids=reading.rail_b_patch_chain_ids,
            end_a_patch_chain_ids=reading.end_a_patch_chain_ids,
            end_b_patch_chain_ids=reading.end_b_patch_chain_ids,
        ),
        None,
    )


# ---------------------------------------------------------------- BEVEL rule
#
# Rule A (by mark) decides every patch with a marked face; Rule B (by
# structure) looks only at patches none of whose faces is marked. A patch
# that is neither gets no record. A record by mark is the truth; a record by
# structure is a candidate the mesh topology suggests.
#
# Known limit of Rule A (behaviour by design): a marked strip whose end lies
# on an unbevelled face (a partial bevel, e.g. only the vertical edges of a
# pillar chamfered, its caps STRONG or unmarked) fits no reading, and so do
# marked strips whose junction faces are unmarked: such a strip is kept as a
# bevel strip with no direction (reading None) and a diagnostic.

BEVEL_FACE_MARKS = frozenset((SourceFaceStrength.MEDIUM, SourceFaceStrength.WEAK))
BEVEL_UNRESOLVED_CODE = "FEATURE_BEVEL_STRIP_READING_UNRESOLVED"
UNRESOLVED_NO_LADDER = "no quad ladder relation"
UNRESOLVED_NO_READING_FITS_MARKS = "no ladder reading fits the marks"
UNRESOLVED_TWO_READINGS_FIT_MARKS = "two ladder readings fit the marks"

# What lies across a boundary edge of a patch (_BevelMesh.across).
ACROSS_BORDER = "border"  # no other face: the mesh border
ACROSS_SELF = "self"  # the patch's own face, across a seam
ACROSS_PATCH = "patch"  # exactly one face, of one other patch
ACROSS_SEVERAL = "several"  # a non-manifold edge


def bevel_instances(
    topology: SurfaceModel,
    relations: RelationSnapshot,
    source: SourceMeshSnapshot | None,
) -> tuple[tuple[BevelInstance, ...], tuple[Diagnostic, ...]]:
    """Bevel strips and junctions by mark (Rule A) or by structure (Rule B), in patch order."""

    if source is None:
        return (), ()
    mesh = _BevelMesh(topology, relations, source)
    found: dict[PatchId, tuple[BevelInstance, str | None]] = {}
    unmarked: list[PatchId] = []
    for patch_id in mesh.patch_ids:
        marks = {mesh.mark(face_id) for face_id in topology.patches[patch_id].source_face_ids}
        if marks == {None}:
            unmarked.append(patch_id)
            continue
        by_mark = _bevel_by_mark(mesh, patch_id, marks)
        if by_mark is not None:
            found[patch_id] = by_mark
    found.update(_bevels_by_structure(mesh, unmarked))

    accepted_strips = {
        patch_id: record
        for patch_id, (record, _note) in found.items()
        if record.kind is FeatureKind.BEVEL_STRIP and record.status is FeatureInstanceStatus.ACCEPTED
    }
    records = []
    diagnostics = []
    for patch_id in mesh.patch_ids:
        if patch_id not in found:
            continue
        record, note = found[patch_id]
        if record.kind is FeatureKind.BEVEL_JUNCTION and record.status is FeatureInstanceStatus.ACCEPTED:
            record = _with_junction_contacts(mesh, record, accepted_strips)
        records.append(record)
        if note is not None:
            diagnostics.append(
                Diagnostic(
                    code=BEVEL_UNRESOLVED_CODE,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Bevel strip {patch_id}: ladder direction unresolved ({note}).",
                    source="layer_4_features.bevel_instances",
                    entity_ids=(str(patch_id),),
                    evidence={"reason": note, "source": record.source.value},
                )
            )
    return tuple(records), tuple(diagnostics)


def _bevel_by_mark(mesh, patch_id: PatchId, marks: set) -> tuple[BevelInstance, str | None] | None:
    """Rule A: all MEDIUM is a strip, all WEAK a junction; mixed bevel marks are suppressed."""

    bevel_marks = marks & BEVEL_FACE_MARKS
    if not bevel_marks:
        return None  # STRONG only (or STRONG and unmarked): not a bevel, and Rule B does not apply
    kind = FeatureKind.BEVEL_STRIP if SourceFaceStrength.MEDIUM in bevel_marks else FeatureKind.BEVEL_JUNCTION
    reason = None
    if marks - BEVEL_FACE_MARKS:
        reason = FeatureSuppressionReason.BEVEL_NOT_ISOLATED
    elif len(bevel_marks) == 2:
        reason = FeatureSuppressionReason.BEVEL_STRIP_AND_JUNCTION_FACES
    if reason is not None:
        return _bevel_record(patch_id, kind, BevelEvidenceSource.SOURCE_MARK, reason=reason), None
    if kind is FeatureKind.BEVEL_JUNCTION:
        return _bevel_record(patch_id, kind, BevelEvidenceSource.SOURCE_MARK), None
    relation = mesh.ladders.get(patch_id)
    if relation is None:
        return _bevel_record(patch_id, kind, BevelEvidenceSource.SOURCE_MARK), UNRESOLVED_NO_LADDER
    fitting = [index for index, reading in enumerate(relation.readings) if mesh.fits_marks(reading)]
    if len(fitting) != 1:
        note = UNRESOLVED_NO_READING_FITS_MARKS if not fitting else UNRESOLVED_TWO_READINGS_FIT_MARKS
        return _bevel_record(patch_id, kind, BevelEvidenceSource.SOURCE_MARK), note
    return _strip_record(mesh, patch_id, BevelEvidenceSource.SOURCE_MARK, fitting[0]), None


def _bevels_by_structure(mesh, unmarked: list[PatchId]) -> dict[PatchId, tuple[BevelInstance, str | None]]:
    """Rule B over unmarked patches: a fixpoint over decided ladder readings.

    Rule B decides only unmarked patches; marked ladder patches take part in
    its state as ladders (step 1 reads every ladder patch, marked or not, so
    a marked strip can make its unmarked neighbours junctions).

    Across a boundary edge lies the mesh border (no face on the other side
    within the model; faces outside the selection count as border, as in
    G1), the patch itself, one other patch, or several faces.

    1. A reading is end-strict when every end edge borders a patch without
       a ladder relation, the mesh border or the patch itself (a closed
       reading has no ends). A ladder patch with exactly one end-strict
       reading is DECIDED with that reading; with two it is UNDECIDED; with
       none it takes no part.
    2. An unmarked patch without a ladder relation is a JUNCTION when at
       least one of its boundary edges is an end edge of a neighbour's
       decided reading, and every one of them lies on the mesh border, is an
       end edge of a neighbour's decided reading, or borders an undecided
       ladder patch. Any other edge (a rail edge of a decided reading, an
       edge on any other patch, on the patch itself or non-manifold) breaks it.
    3. An undecided patch whose edges on junctions are end edges in exactly
       one of its readings becomes decided with that reading; when they
       point to both readings it is BLOCKED: it stays undecided for good (it
       still counts as undecided in step 2) and is never decided.
    Steps 2 and 3 run in rounds, each over the whole state at once, until a
    round decides or blocks nothing. Decided and blocked only grow, so this
    ends; a round does not depend on the order of patches or ids. The
    junctions are those of step 2 on the final state, so a junction of an
    earlier round that no longer qualifies (one of its edges became a rail
    edge) is gone; a decision is never taken back.
    4. A strip candidate is an unmarked decided patch whose decided reading
       has an end edge on a junction and whose every column has its two rail
       edges on two different other patches. A candidate with a candidate
       among its rail neighbours is dropped (judged against the candidate
       set before dropping): a bevel strip lies between surfaces that are
       not strips. A junction gets a record only when one of its edges is an
       end edge of the decided reading of a kept strip.
    """

    decided, _undecided, _blocked, junctions = rule_b_fixpoint(mesh, unmarked)
    unmarked_set = set(unmarked)
    candidates = {
        patch_id
        for patch_id, index in decided.items()
        if patch_id in unmarked_set
        and any(mesh.across(patch_id, edge_id)[1] in junctions for edge_id in mesh.end_edges(patch_id, index))
        and mesh.rails_on_two_patches(patch_id, mesh.ladders[patch_id].readings[index])
    }
    strips = {
        patch_id
        for patch_id in candidates
        if not any(
            neighbour in candidates
            for neighbour in mesh.neighbour_patches(patch_id, mesh.rail_edges(patch_id, decided[patch_id]))
        )
    }

    found: dict[PatchId, tuple[BevelInstance, str | None]] = {}
    for patch_id in unmarked:
        if patch_id in strips:
            found[patch_id] = (_strip_record(mesh, patch_id, BevelEvidenceSource.STRUCTURE, decided[patch_id]), None)
        elif patch_id in junctions and any(
            mesh.across(patch_id, edge_id)[1] in strips
            and edge_id in mesh.end_edges(mesh.across(patch_id, edge_id)[1], decided[mesh.across(patch_id, edge_id)[1]])
            for edge_id in mesh.boundary_edges[patch_id]
        ):
            found[patch_id] = (_bevel_record(patch_id, FeatureKind.BEVEL_JUNCTION, BevelEvidenceSource.STRUCTURE), None)
    return found


def rule_b_fixpoint(mesh, unmarked: list[PatchId]) -> tuple[dict[PatchId, int], set[PatchId], set[PatchId], set[PatchId]]:
    """Rule B steps 1-3: decided readings (patch -> reading index), undecided, blocked and junctions."""

    end_strict = {
        patch_id: tuple(index for index, reading in enumerate(relation.readings) if mesh.end_strict(patch_id, reading))
        for patch_id, relation in mesh.ladders.items()
    }
    decided = {patch_id: indices[0] for patch_id, indices in end_strict.items() if len(indices) == 1}
    undecided = {patch_id for patch_id, indices in end_strict.items() if len(indices) == 2}
    blocked: set[PatchId] = set()
    open_patches = [patch_id for patch_id in unmarked if patch_id not in mesh.ladders]
    while True:
        junctions = {patch_id for patch_id in open_patches if mesh.is_junction(patch_id, decided, undecided)}
        newly_decided: dict[PatchId, int] = {}
        newly_blocked: set[PatchId] = set()
        for patch_id in undecided - blocked:
            pointed = {
                index
                for edge_id in mesh.boundary_edges[patch_id]
                if mesh.across(patch_id, edge_id)[1] in junctions
                for index in end_strict[patch_id]
                if edge_id in mesh.end_edges(patch_id, index)
            }
            if len(pointed) == 1:
                newly_decided[patch_id] = pointed.pop()
            elif len(pointed) == 2:
                newly_blocked.add(patch_id)
        if not newly_decided and not newly_blocked:
            break
        decided.update(newly_decided)
        undecided -= set(newly_decided)
        blocked |= newly_blocked
    return decided, undecided, blocked, junctions


def _bevel_record(patch_id, kind, source, *, reason=None) -> BevelInstance:
    name = "bevel_strip" if kind is FeatureKind.BEVEL_STRIP else "bevel_junction"
    return BevelInstance(
        id=f"feature_instance:{name}:{patch_id}",
        kind=kind,
        patch_id=patch_id,
        status=FeatureInstanceStatus.ACCEPTED if reason is None else FeatureInstanceStatus.SUPPRESSED,
        source=source,
        suppression_reason=reason,
    )


def _strip_record(mesh, patch_id: PatchId, source: BevelEvidenceSource, reading_index: int) -> BevelInstance:
    """An accepted bevel strip with copies of its chosen reading, rail neighbours and corner kind."""

    reading = mesh.ladders[patch_id].readings[reading_index]
    rail_a = mesh.neighbour_patches(patch_id, reading.rail_a_source_edge_ids)
    rail_b = mesh.neighbour_patches(patch_id, reading.rail_b_source_edge_ids)
    base = _bevel_record(patch_id, FeatureKind.BEVEL_STRIP, source)
    return BevelInstance(
        id=base.id,
        kind=base.kind,
        patch_id=patch_id,
        status=base.status,
        source=source,
        reading_index=reading_index,
        faces_per_column=reading.faces_per_column,
        column_count=len(reading.columns),
        is_closed=reading.is_closed,
        rail_a_patch_chain_ids=reading.rail_a_patch_chain_ids,
        rail_b_patch_chain_ids=reading.rail_b_patch_chain_ids,
        end_a_patch_chain_ids=reading.end_a_patch_chain_ids,
        end_b_patch_chain_ids=reading.end_b_patch_chain_ids,
        rail_a_neighbour_patch_ids=rail_a,
        rail_b_neighbour_patch_ids=rail_b,
        corner_kind=mesh.corner_kind(
            reading.rail_a_patch_chain_ids + reading.rail_b_patch_chain_ids,
            set(rail_a) | set(rail_b),
        ),
    )


def _with_junction_contacts(mesh, record: BevelInstance, accepted_strips: dict) -> BevelInstance:
    """The accepted bevel strips met along each boundary loop in loop order, other neighbours, border.

    A junction never lies across a rail edge of a strip's chosen reading: by
    mark a rail has no bevel-marked face across, by structure a rail edge
    breaks a junction. So a contact is on an end of the strip's reading, and
    strip_end is None only when the strip has no chosen reading (by mark).
    """

    contacts: list[BevelJunctionContact] = []
    others: list[PatchId] = []
    border = False
    for loop_edges in mesh.loop_edges(record.patch_id):
        loop_contacts: list[BevelJunctionContact] = []
        for edge_id in loop_edges:
            kind, other = mesh.across(record.patch_id, edge_id)
            if kind == ACROSS_BORDER:
                border = True
            elif kind == ACROSS_PATCH and other in accepted_strips:
                contact = BevelJunctionContact(other, _strip_end(mesh, accepted_strips[other], edge_id))
                if not loop_contacts or loop_contacts[-1] != contact:
                    loop_contacts.append(contact)
            elif kind == ACROSS_PATCH and other not in others:
                others.append(other)
        if len(loop_contacts) > 1 and loop_contacts[0] == loop_contacts[-1]:
            loop_contacts.pop()
        contacts.extend(loop_contacts)
    return BevelInstance(
        id=record.id,
        kind=record.kind,
        patch_id=record.patch_id,
        status=record.status,
        source=record.source,
        joined_strips=tuple(contacts),
        other_neighbour_patch_ids=tuple(others),
        touches_mesh_border=border,
    )


def _strip_end(mesh, strip: BevelInstance, edge_id: SourceEdgeId) -> BevelStripEnd | None:
    if strip.reading_index is None:
        return None
    reading = mesh.ladders[strip.patch_id].readings[strip.reading_index]
    if edge_id in reading.end_a_source_edge_ids:
        return BevelStripEnd.A
    if edge_id in reading.end_b_source_edge_ids:
        return BevelStripEnd.B
    return None


class _BevelMesh:
    """Face/edge incidence of the model's faces for the bevel rule; a short-lived working set, not a record."""

    def __init__(self, topology: SurfaceModel, relations: RelationSnapshot, source: SourceMeshSnapshot):
        self.topology = topology
        self.source = source
        self.patch_ids = tuple(sorted(topology.patches, key=str))
        self.ladders = {relation.patch_id: relation for relation in relations.patch_quad_ladder_relations}
        self._end_edges: dict[tuple[PatchId, int], frozenset] = {}
        self.patch_of_face: dict[SourceFaceId, PatchId] = {}
        self.faces_of_edge: dict[SourceEdgeId, list[SourceFaceId]] = defaultdict(list)
        for patch_id in self.patch_ids:
            for face_id in topology.patches[patch_id].source_face_ids:
                self.patch_of_face[face_id] = patch_id
                face = source.faces.get(face_id)
                for edge_id in face.edge_ids if face is not None else ():
                    self.faces_of_edge[edge_id].append(face_id)
        self.boundary_edges: dict[PatchId, tuple[SourceEdgeId, ...]] = {}
        for patch_id in self.patch_ids:
            seen: dict[SourceEdgeId, None] = {}
            for loop_edges in self.loop_edges(patch_id):
                for edge_id in loop_edges:
                    seen.setdefault(edge_id, None)
            self.boundary_edges[patch_id] = tuple(seen)
        self.adjacencies_by_use = defaultdict(list)
        for adjacency in relations.patch_adjacencies.values():
            self.adjacencies_by_use[adjacency.first_patch_chain_id].append((adjacency, adjacency.second_patch_id))
            self.adjacencies_by_use[adjacency.second_patch_chain_id].append((adjacency, adjacency.first_patch_id))

    def mark(self, face_id: SourceFaceId) -> SourceFaceStrength | None:
        face = self.source.faces.get(face_id)
        return face.face_strength if face is not None else None

    def loop_edges(self, patch_id: PatchId) -> list[list[SourceEdgeId]]:
        """Per boundary loop, its source edges in loop order (each use walked in its direction)."""

        out = []
        for loop_id in self.topology.patches[patch_id].loop_ids:
            uses = sorted(
                (self.topology.patch_chains[use_id] for use_id in self.topology.loops[loop_id].patch_chain_ids),
                key=lambda use: use.position_in_loop,
            )
            edges: list[SourceEdgeId] = []
            for use in uses:
                chain_edges = list(self.topology.chains[use.chain_id].source_edge_ids)
                edges.extend(reversed(chain_edges) if use.orientation_sign < 0 else chain_edges)
            out.append(edges)
        return out

    def across(self, patch_id: PatchId, edge_id: SourceEdgeId) -> tuple[str, PatchId | None]:
        """What lies across boundary edge edge_id of the patch."""

        faces = self.faces_of_edge.get(edge_id, ())
        own = [face_id for face_id in faces if self.patch_of_face[face_id] == patch_id]
        other = [face_id for face_id in faces if self.patch_of_face[face_id] != patch_id]
        if not other:
            return (ACROSS_SELF, None) if len(own) >= 2 else (ACROSS_BORDER, None)
        if len(other) == 1 and len(own) == 1:
            return ACROSS_PATCH, self.patch_of_face[other[0]]
        return ACROSS_SEVERAL, None

    def neighbour_patches(self, patch_id: PatchId, edge_ids) -> tuple[PatchId, ...]:
        seen: dict[PatchId, None] = {}
        for edge_id in edge_ids:
            kind, other = self.across(patch_id, edge_id)
            if kind == ACROSS_PATCH:
                seen.setdefault(other, None)
        return tuple(seen)

    def end_edges(self, patch_id: PatchId, reading_index: int) -> frozenset:
        """The end edges (end A and end B) of one reading of a ladder patch."""

        key = (patch_id, reading_index)
        if key not in self._end_edges:
            reading = self.ladders[patch_id].readings[reading_index]
            self._end_edges[key] = frozenset(reading.end_a_source_edge_ids + reading.end_b_source_edge_ids)
        return self._end_edges[key]

    def rail_edges(self, patch_id: PatchId, reading_index: int) -> tuple[SourceEdgeId, ...]:
        reading = self.ladders[patch_id].readings[reading_index]
        return reading.rail_a_source_edge_ids + reading.rail_b_source_edge_ids

    def is_junction(self, patch_id: PatchId, decided: dict, undecided: set) -> bool:
        """Rule B step 2 for a patch without a ladder relation, on the given decided / undecided state."""

        touches = False
        for edge_id in self.boundary_edges[patch_id]:
            kind, other = self.across(patch_id, edge_id)
            if kind == ACROSS_BORDER:
                continue
            if kind != ACROSS_PATCH:
                return False
            if other in decided:
                if edge_id not in self.end_edges(other, decided[other]):
                    return False
                touches = True
            elif other not in undecided:
                return False
        return touches

    def end_strict(self, patch_id: PatchId, reading: PatchQuadLadderReading) -> bool:
        """Every end edge borders a patch without a ladder relation, the mesh border or the patch itself."""

        for edge_id in reading.end_a_source_edge_ids + reading.end_b_source_edge_ids:
            kind, other = self.across(patch_id, edge_id)
            if kind == ACROSS_SEVERAL or (kind == ACROSS_PATCH and other in self.ladders):
                return False
        return True

    def rails_on_two_patches(self, patch_id: PatchId, reading: PatchQuadLadderReading) -> bool:
        """Every column's two rail edges border two different other patches."""

        for rail_a, rail_b in zip(reading.rail_a_source_edge_ids, reading.rail_b_source_edge_ids):
            kind_a, other_a = self.across(patch_id, rail_a)
            kind_b, other_b = self.across(patch_id, rail_b)
            if kind_a != ACROSS_PATCH or kind_b != ACROSS_PATCH or other_a == other_b:
                return False
        return True

    def fits_marks(self, reading: PatchQuadLadderReading) -> bool:
        """No rail edge has a bevel-marked face across; every end edge has one, or no face (mesh border)."""

        for column, rail_a, rail_b in zip(reading.columns, reading.rail_a_source_edge_ids, reading.rail_b_source_edge_ids):
            for face_id, edge_id in ((column[0], rail_a), (column[-1], rail_b)):
                if any(self.mark(other) in BEVEL_FACE_MARKS for other in self._faces_across(face_id, edge_id)):
                    return False
        if reading.is_closed:
            return True
        first, last = reading.columns[0], reading.columns[-1]
        for faces, edges in ((first, reading.end_a_source_edge_ids), (last, reading.end_b_source_edge_ids)):
            for face_id, edge_id in zip(faces, edges):
                across = self._faces_across(face_id, edge_id)
                if across and not any(self.mark(other) in BEVEL_FACE_MARKS for other in across):
                    return False
        return True

    def _faces_across(self, face_id: SourceFaceId, edge_id: SourceEdgeId) -> list[SourceFaceId]:
        faces = list(self.faces_of_edge.get(edge_id, ()))
        if face_id in faces:
            faces.remove(face_id)
        return faces

    def corner_kind(self, rail_use_ids, rail_neighbours: set) -> BevelCornerKind:
        """CONVEX / CONCAVE from the rail seams' PatchAdjacency.dihedral_kind; COPLANAR and UNDEFINED ignored."""

        kinds = set()
        for use_id in rail_use_ids:
            for adjacency, other in self.adjacencies_by_use.get(use_id, ()):
                if other in rail_neighbours and adjacency.dihedral_kind in (DihedralKind.CONVEX, DihedralKind.CONCAVE):
                    kinds.add(adjacency.dihedral_kind)
        if len(kinds) == 2:
            return BevelCornerKind.MIXED
        if kinds == {DihedralKind.CONVEX}:
            return BevelCornerKind.CONVEX
        if kinds == {DihedralKind.CONCAVE}:
            return BevelCornerKind.CONCAVE
        return BevelCornerKind.UNDEFINED
