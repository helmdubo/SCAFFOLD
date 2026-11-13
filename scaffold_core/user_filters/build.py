"""
Layer: user filters - build

Rules:
- The over filter (plan Slice AH): with a user world vertical, a patch is
  HORIZONTAL when its Layer 2 patch normal lies within the user angle of +up
  or -up, else VERTICAL. A bevel patch confirmed by the mark (Layer 4
  BevelInstance, ACCEPTED, SOURCE_MARK) takes its class by rule: a strip is
  HORIZONTAL when a rail neighbour that is not a bevel patch is HORIZONTAL;
  a junction takes the majority class of the strips it joins (a tie is
  HORIZONTAL, like a strip beside a horizontal surface).
- Output: one SeamDirective per Chain shared by two different patches where
  the filter has something to say: SPLIT when their classes differ, JOIN
  when they agree and one of them is a bevel patch by mark. Every other seam
  is left to the structure.
- Reads Layers 0-4 read-only and never imports Layer 5. The class depends
  only on the angle between a normal and the up line, so rotating the mesh
  and the up vector together changes nothing.
"""

from __future__ import annotations

from math import acos, degrees

from scaffold_core.core.diagnostics import Diagnostic, DiagnosticSeverity
from scaffold_core.layer_2_geometry.measures import EPSILON, dot, length, normalize
from scaffold_core.layer_4_features.model import (
    BevelEvidenceSource,
    FeatureInstanceStatus,
    FeatureKind,
)
from scaffold_core.user_filters.model import (
    RULE_BEVEL_WITH_ITS_SURFACES,
    RULE_VERTICAL_APART_FROM_HORIZONTAL,
    FilterOptions,
    FilterSnapshot,
    PatchClass,
    PatchClassRecord,
    PatchClassRule,
    SeamDirective,
    SeamDirectiveKind,
)


def build_filter_snapshot(topology, geometry, relations, features, options: FilterOptions) -> FilterSnapshot:
    """Patch classes and seam directives; an empty snapshot when options.world_up is None."""

    if options.world_up is None:
        return FilterSnapshot(options=options)
    up = normalize(tuple(float(value) for value in options.world_up))
    if length(up) <= EPSILON:
        raise ValueError("FilterOptions.world_up must not be the zero vector")
    diagnostics: list[Diagnostic] = []
    strips, junctions = _bevels_by_mark(features)
    bevel_ids = set(strips) | set(junctions)
    angle_by_patch = {str(patch_id): _angle_to_up(geometry, patch_id, up) for patch_id in topology.patches}

    def by_normal(patch_id: str) -> PatchClass:
        angle = angle_by_patch[patch_id]
        if angle is None:
            diagnostics.append(_diagnostic(
                "FILTER_PATCH_NORMAL_DEGENERATE",
                f"patch normal is degenerate, classed VERTICAL: {patch_id}",
                patch_id,
            ))
            return PatchClass.VERTICAL
        return PatchClass.HORIZONTAL if angle <= options.horizontal_angle_degrees else PatchClass.VERTICAL

    records: dict[str, PatchClassRecord] = {}
    for patch_id in sorted(angle_by_patch):
        if patch_id not in bevel_ids:
            records[patch_id] = PatchClassRecord(
                patch_id=patch_id,
                patch_class=by_normal(patch_id),
                rule=PatchClassRule.BY_NORMAL,
                angle_degrees=angle_by_patch[patch_id],
            )
    for patch_id in sorted(strips):
        bevel = strips[patch_id]
        surfaces = {
            str(neighbour)
            for neighbour in bevel.rail_a_neighbour_patch_ids + bevel.rail_b_neighbour_patch_ids
            if str(neighbour) in records
        }
        if surfaces:
            horizontal = any(records[s].patch_class is PatchClass.HORIZONTAL for s in surfaces)
            records[patch_id] = PatchClassRecord(
                patch_id=bevel.patch_id,
                patch_class=PatchClass.HORIZONTAL if horizontal else PatchClass.VERTICAL,
                rule=PatchClassRule.BEVEL_STRIP_BY_RAIL_NEIGHBOURS,
                angle_degrees=angle_by_patch.get(patch_id),
                is_bevel=True,
            )
        else:
            diagnostics.append(_diagnostic(
                "FILTER_BEVEL_STRIP_WITHOUT_SURFACE",
                f"bevel strip has no rail neighbour that is not a bevel, classed by its normal: {patch_id}",
                patch_id,
            ))
            records[patch_id] = PatchClassRecord(
                bevel.patch_id, by_normal(patch_id), PatchClassRule.BY_NORMAL, angle_by_patch.get(patch_id), True
            )
    for patch_id in sorted(junctions):
        bevel = junctions[patch_id]
        joined = {str(contact.strip_patch_id) for contact in bevel.joined_strips} & set(strips)
        horizontal = sum(1 for s in joined if records[s].patch_class is PatchClass.HORIZONTAL)
        vertical = len(joined) - horizontal
        if joined:
            records[patch_id] = PatchClassRecord(
                patch_id=bevel.patch_id,
                patch_class=PatchClass.HORIZONTAL if horizontal >= vertical else PatchClass.VERTICAL,
                rule=PatchClassRule.BEVEL_JUNCTION_BY_STRIPS,
                angle_degrees=angle_by_patch.get(patch_id),
                is_bevel=True,
            )
            if horizontal == vertical:
                diagnostics.append(_diagnostic(
                    "FILTER_BEVEL_JUNCTION_TIE",
                    f"bevel junction joins as many horizontal as vertical strips, classed HORIZONTAL: {patch_id}",
                    patch_id,
                    severity=DiagnosticSeverity.INFO,
                ))
        else:
            diagnostics.append(_diagnostic(
                "FILTER_BEVEL_JUNCTION_WITHOUT_STRIP",
                f"bevel junction joins no bevel strip, classed by its normal: {patch_id}",
                patch_id,
            ))
            records[patch_id] = PatchClassRecord(
                bevel.patch_id, by_normal(patch_id), PatchClassRule.BY_NORMAL, angle_by_patch.get(patch_id), True
            )

    directives: list[SeamDirective] = []
    for adjacency in sorted(relations.patch_adjacencies.values(), key=lambda item: str(item.id)):
        first, second = str(adjacency.first_patch_id), str(adjacency.second_patch_id)
        if first == second or first not in records or second not in records:
            continue
        if records[first].patch_class is not records[second].patch_class:
            kind, rule = SeamDirectiveKind.SPLIT, RULE_VERTICAL_APART_FROM_HORIZONTAL
        elif first in bevel_ids or second in bevel_ids:
            kind, rule = SeamDirectiveKind.JOIN, RULE_BEVEL_WITH_ITS_SURFACES
        else:
            continue
        directives.append(SeamDirective(
            chain_id=adjacency.chain_id,
            first_patch_id=adjacency.first_patch_id,
            second_patch_id=adjacency.second_patch_id,
            kind=kind,
            rule=rule,
        ))
    return FilterSnapshot(
        options=options,
        patch_classes=tuple(records[patch_id] for patch_id in sorted(records)),
        directives=tuple(directives),
        diagnostics=tuple(diagnostics),
    )


def _bevels_by_mark(features):
    """Accepted bevel strips and junctions set by the Face Strength mark; structural records are ordinary patches."""

    strips: dict = {}
    junctions: dict = {}
    if features is None:
        return strips, junctions
    for bevel in features.bevels:
        if bevel.status is not FeatureInstanceStatus.ACCEPTED or bevel.source is not BevelEvidenceSource.SOURCE_MARK:
            continue
        if bevel.kind is FeatureKind.BEVEL_STRIP:
            strips[str(bevel.patch_id)] = bevel
        elif bevel.kind is FeatureKind.BEVEL_JUNCTION:
            junctions[str(bevel.patch_id)] = bevel
    return strips, junctions


def _angle_to_up(geometry, patch_id, up) -> float | None:
    """Degrees between the Layer 2 patch normal and the up line (0 = facing up or down)."""

    facts = geometry.patch_facts.get(patch_id)
    if facts is None or length(facts.normal) <= EPSILON:
        return None
    cosine = min(1.0, abs(dot(normalize(facts.normal), up)))
    return degrees(acos(cosine))


def _diagnostic(code: str, message: str, patch_id: str, severity=DiagnosticSeverity.WARNING) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=severity,
        message=message,
        source="user_filters.build_filter_snapshot",
        entity_ids=(patch_id,),
    )
