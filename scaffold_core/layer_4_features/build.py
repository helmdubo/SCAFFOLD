"""
Layer: 4 - Features

Rules:
- Build the FeatureSnapshot from Layers 1-3 read-only; never write Layer 3
  (G0 DD-25) and never import Layer 5.
- One rule per feature kind, as plain functions: candidate rule, resolver,
  constraint. A second feature kind is a second set of functions.
- Every pattern match is a candidate (DD-15); the resolver accepts or
  suppresses with a reason, and suppressed instances are retained (DD-20).
- Structure only: no world axes, no H/V, no surface-role vocabulary.
- The bevel rule reads Layer 0 face marks and face/edge incidence, Layer 1
  patches, chains and uses, and Layer 3 quad ladders and PatchAdjacency;
  no position, length, normal, world axis, UV or island.
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
    FeatureCandidate,
    FeatureConstraint,
    FeatureConstraintKind,
    FeatureInstance,
    FeatureInstanceStatus,
    FeatureKind,
    FeatureOptions,
    FeatureSnapshot,
    FeatureSuppressionReason,
    StripSide,
)

STRIP_SIDE_COUNT = 4
# Opposite sides whose 3D lengths differ by more than this share of the
# longer one need straightening.
STRIP_LENGTH_MISMATCH = 0.01
STRIP_OPPOSITE_PAIRS = ((0, 2), (1, 3))
# A Chain is bent in 3D when its length exceeds its chord by more than this
# share; a closed Chain (chord ~0) is always bent. A vertex merely off the
# chord line (an arched chain whose length equals its chord) is not bent.
STRIP_BENT_DETOUR = 0.01


def build_feature_snapshot(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    relations: RelationSnapshot,
    options: FeatureOptions = FeatureOptions(),
    source: SourceMeshSnapshot | None = None,
) -> FeatureSnapshot:
    """Run every feature rule, then resolve and constrain its candidates.

    The bevel rule runs always (no option): it emits records only, no
    constraint, so it changes no layout. It needs the Layer 0 source faces
    (marks and incidence): without source (the default) bevels is empty.
    Pass 2 always passes it.
    """

    candidates = strip_candidates(topology, geometry, relations)
    instances = tuple(resolve_strip(candidate, options) for candidate in candidates)
    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    constraints = tuple(
        strip_constraint(instance, candidate_by_id[instance.candidate_id])
        for instance in instances
        if instance.status is FeatureInstanceStatus.ACCEPTED
    )
    bevels, bevel_diagnostics = bevel_instances(topology, relations, source)
    return FeatureSnapshot(
        options=options,
        candidates=candidates,
        instances=instances,
        constraints=constraints,
        bevels=bevels,
        diagnostics=bevel_diagnostics,
    )


# ---------------------------------------------------------------- STRIP rule


def strip_candidates(
    topology: SurfaceModel,
    geometry: GeometryFactSnapshot,
    relations: RelationSnapshot,
) -> tuple[FeatureCandidate, ...]:
    """Patches with exactly one boundary loop of exactly four PatchChain uses.

    Per use: 3D Chain length, whether the Chain is bent (chain_is_bent) and
    whether the use is exactly one SURFACE_LINE piece.
    """

    pieces_by_use: dict[str, list] = {}
    for piece in relations.patch_chain_shape_relations:
        pieces_by_use.setdefault(str(piece.patch_chain_id), []).append(piece)
    candidates = []
    for patch_id in sorted(topology.patches, key=str):
        patch = topology.patches[patch_id]
        if len(patch.loop_ids) != 1:
            continue
        loop = topology.loops[patch.loop_ids[0]]
        if len(loop.patch_chain_ids) != STRIP_SIDE_COUNT:
            continue
        uses = sorted(
            (topology.patch_chains[pc_id] for pc_id in loop.patch_chain_ids),
            key=lambda pc: pc.position_in_loop,
        )
        sides = []
        for pc in uses:
            facts = geometry.chain_facts[pc.chain_id]
            pieces = pieces_by_use.get(str(pc.id), ())
            sides.append(
                StripSide(
                    patch_chain_id=pc.id,
                    chain_id=pc.chain_id,
                    position_in_loop=pc.position_in_loop,
                    length=facts.length,
                    is_bent=chain_is_bent(facts),
                    is_surface_line=len(pieces) == 1 and pieces[0].kind is PatchChainShapeKind.SURFACE_LINE,
                )
            )
        candidates.append(
            FeatureCandidate(
                id=f"feature_candidate:strip:{patch_id}",
                kind=FeatureKind.STRIP,
                patch_id=patch_id,
                loop_id=loop.id,
                sides=tuple(sides),
            )
        )
    return tuple(candidates)


def chain_is_bent(facts) -> bool:
    """Bent in 3D: length > chord * (1 + STRIP_BENT_DETOUR), or a closed Chain."""

    if facts.chord_length <= EPSILON:
        return True
    return facts.length > facts.chord_length * (1.0 + STRIP_BENT_DETOUR)


def strip_needs_straightening(candidate: FeatureCandidate) -> bool:
    """Some side is not one surface line, or opposite sides differ in length."""

    sides = candidate.sides
    if any(not side.is_surface_line for side in sides):
        return True
    for first, second in STRIP_OPPOSITE_PAIRS:
        longer = max(sides[first].length, sides[second].length)
        if longer > 0.0 and abs(sides[first].length - sides[second].length) > STRIP_LENGTH_MISMATCH * longer:
            return True
    return False


def resolve_strip(candidate: FeatureCandidate, options: FeatureOptions) -> FeatureInstance:
    """ACCEPTED only with the option on, a strip that needs straightening and a bent opposite pair.

    The shape is graded first, so "option off" marks exactly the candidates the option would accept.
    """

    sides = candidate.sides
    if not strip_needs_straightening(candidate):
        reason = FeatureSuppressionReason.ALREADY_RECTANGLE
    elif not any(sides[first].is_bent and sides[second].is_bent for first, second in STRIP_OPPOSITE_PAIRS):
        reason = FeatureSuppressionReason.NO_BENT_OPPOSITE_PAIR
    elif not options.straighten_strips:
        reason = FeatureSuppressionReason.OPTION_OFF
    else:
        reason = None
    return FeatureInstance(
        id=f"feature_instance:strip:{candidate.patch_id}",
        candidate_id=candidate.id,
        kind=FeatureKind.STRIP,
        patch_id=candidate.patch_id,
        status=FeatureInstanceStatus.ACCEPTED if reason is None else FeatureInstanceStatus.SUPPRESSED,
        suppression_reason=reason,
    )


def strip_constraint(instance: FeatureInstance, candidate: FeatureCandidate) -> FeatureConstraint:
    """The rectangle: four uses in loop order and the mean length of each opposite pair."""

    sides = candidate.sides
    return FeatureConstraint(
        id=f"feature_constraint:straight_strip:{candidate.patch_id}",
        kind=FeatureConstraintKind.STRAIGHT_STRIP,
        instance_id=instance.id,
        patch_id=candidate.patch_id,
        patch_chain_ids=tuple(side.patch_chain_id for side in sides),
        target_lengths=tuple(
            (sides[first].length + sides[second].length) / 2.0 for first, second in STRIP_OPPOSITE_PAIRS
        ),
    )


# ---------------------------------------------------------------- BEVEL rule
#
# Rule A (by mark) decides every patch with a marked face; Rule B (by
# structure) looks only at patches none of whose faces is marked. A patch
# that is neither gets no record.

BEVEL_FACE_MARKS = frozenset((SourceFaceStrength.MEDIUM, SourceFaceStrength.WEAK))
BEVEL_UNRESOLVED_CODE = "FEATURE_BEVEL_STRIP_READING_UNRESOLVED"
UNRESOLVED_NO_LADDER = "no quad ladder relation"
UNRESOLVED_NO_READING_FITS_MARKS = "no ladder reading fits the marks"
UNRESOLVED_TWO_READINGS_FIT_MARKS = "two ladder readings fit the marks"
UNRESOLVED_TWO_READINGS_QUALIFY = "two ladder readings qualify by structure"

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
    """Rule B over unmarked patches: pure junctions, and strips with an end on one.

    A reading is end-strict when every end edge borders a patch without a
    ladder relation, the mesh border or the patch itself (a closed reading
    has no ends). A patch's strict end edges are the union of the end edges
    of all its end-strict readings. A pure junction is an unmarked patch
    without a ladder relation whose every boundary edge is a strict end edge
    of the neighbouring ladder patch or lies on the mesh border, at least
    one of them a strict end edge. A strip candidate is an unmarked ladder
    patch with an end-strict reading that has an end edge on a pure junction
    and whose every column has its two rail edges on two different other
    patches. Then, in this order:
    a. a bevel strip lies between two surfaces that are not bevel strips: a
       candidate with a strip candidate among its rail neighbours (of any
       qualifying reading) is dropped, judged against the candidate set
       before any dropping, so two candidates on each other's rails both go;
    b. a junction joins at least one strip: a pure junction gets a record
       only when one of its edges is a strict end edge of a strip kept by a.
    """

    strict_end_edges: dict[PatchId, set[SourceEdgeId]] = {}
    for patch_id, relation in mesh.ladders.items():
        edges: set[SourceEdgeId] = set()
        for reading in relation.readings:
            if mesh.end_strict(patch_id, reading):
                edges.update(reading.end_a_source_edge_ids)
                edges.update(reading.end_b_source_edge_ids)
        strict_end_edges[patch_id] = edges

    junctions: set[PatchId] = set()
    for patch_id in unmarked:
        if patch_id in mesh.ladders:
            continue
        touching = False
        pure = True
        for edge_id in mesh.boundary_edges[patch_id]:
            kind, other = mesh.across(patch_id, edge_id)
            if kind == ACROSS_BORDER:
                continue
            if kind == ACROSS_PATCH and edge_id in strict_end_edges.get(other, ()):
                touching = True
                continue
            pure = False
            break
        if pure and touching:
            junctions.add(patch_id)

    candidates: dict[PatchId, list[int]] = {}
    for patch_id in unmarked:
        relation = mesh.ladders.get(patch_id)
        if relation is None or patch_id in junctions:
            continue
        qualifying = [
            index
            for index, reading in enumerate(relation.readings)
            if mesh.end_strict(patch_id, reading)
            and any(
                mesh.across(patch_id, edge_id)[1] in junctions
                for edge_id in reading.end_a_source_edge_ids + reading.end_b_source_edge_ids
            )
            and mesh.rails_on_two_patches(patch_id, reading)
        ]
        if qualifying:
            candidates[patch_id] = qualifying

    strips = {
        patch_id: qualifying
        for patch_id, qualifying in candidates.items()
        if not any(
            neighbour in candidates
            for index in qualifying
            for neighbour in mesh.neighbour_patches(
                patch_id,
                mesh.ladders[patch_id].readings[index].rail_a_source_edge_ids
                + mesh.ladders[patch_id].readings[index].rail_b_source_edge_ids,
            )
        )
    }

    found: dict[PatchId, tuple[BevelInstance, str | None]] = {}
    for patch_id in unmarked:
        if patch_id in junctions:
            if any(
                mesh.across(patch_id, edge_id)[1] in strips
                and edge_id in strict_end_edges[mesh.across(patch_id, edge_id)[1]]
                for edge_id in mesh.boundary_edges[patch_id]
            ):
                found[patch_id] = (
                    _bevel_record(patch_id, FeatureKind.BEVEL_JUNCTION, BevelEvidenceSource.STRUCTURE),
                    None,
                )
        elif patch_id in strips:
            qualifying = strips[patch_id]
            if len(qualifying) == 1:
                found[patch_id] = (_strip_record(mesh, patch_id, BevelEvidenceSource.STRUCTURE, qualifying[0]), None)
            else:
                found[patch_id] = (
                    _bevel_record(patch_id, FeatureKind.BEVEL_STRIP, BevelEvidenceSource.STRUCTURE),
                    UNRESOLVED_TWO_READINGS_QUALIFY,
                )
    return found


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
    """The accepted bevel strips met along each boundary loop in loop order, other neighbours, border."""

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
