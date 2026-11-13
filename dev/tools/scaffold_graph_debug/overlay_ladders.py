"""Ladders and Bevels layers of the Scaffold structure-debugger payload, without Blender.

Layer 3 quad ladders (the reading Layer 4 chose for a bevel strip, else the
first one), the Layer 0 source face mark and the Layer 4 bevel records: a
record by the Face Strength mark is drawn as the truth, a record by
structure on its own lighter layers as a candidate. Called by overlay_v2's
build_debug_payload and format_report; uses its drawing helpers and defines
no Scaffold relation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .overlay_v2 import (
    UsePieceView,
    _add,
    _fill_strokes,
    _offset,
    _scale,
    _source_position,
    _stroke,
    _vertex_normal,
)
from .rail_offsets import RAIL_NORMAL_HOVER_FACTOR

LADDER_RAIL_COLORS = {"A": (0.95, 0.25, 0.6, 1.0), "B": (0.5, 0.95, 0.15, 1.0)}
LADDER_END_COLOR = (0.6, 0.3, 1.0, 1.0)
LADDER_COLUMN_COLOR = (0.8, 0.8, 0.8, 0.9)
LADDER_RAIL_WIDTH = 6
LADDER_COLUMN_WIDTH = 2
FACE_STRENGTH_KINDS = ("WEAK", "MEDIUM", "STRONG")
FACE_STRENGTH_COLORS = {
    "WEAK": (0.95, 0.3, 0.3, 1.0),
    "MEDIUM": (0.3, 0.7, 1.0, 1.0),
    "STRONG": (0.55, 0.55, 0.55, 1.0),
}
# A bevel record by mark is the truth; by structure it is a candidate the
# mesh topology suggests, drawn on its own layers in lighter colours.
BEVEL_LAYERS = {
    "BEVEL_STRIP": "Scaffold_Bevel_Strip",
    "BEVEL_JUNCTION": "Scaffold_Bevel_Junction",
    "BEVEL_STRIP_STRUCTURE": "Scaffold_Bevel_Strip_Structure",
    "BEVEL_JUNCTION_STRUCTURE": "Scaffold_Bevel_Junction_Structure",
    "SUPPRESSED": "Scaffold_Bevel_Not_Isolated",
}
BEVEL_COLORS = {
    "BEVEL_STRIP": (1.0, 0.6, 0.1, 1.0),
    "BEVEL_JUNCTION": (0.6, 0.25, 0.95, 1.0),
    "BEVEL_STRIP_STRUCTURE": (1.0, 0.85, 0.6, 1.0),
    "BEVEL_JUNCTION_STRUCTURE": (0.82, 0.72, 1.0, 1.0),
    "SUPPRESSED": (1.0, 0.1, 0.1, 1.0),
}


def bevel_group(record) -> str:
    """The layer group of a bevel record: kind (and _STRUCTURE by structure) when accepted, else SUPPRESSED."""

    if record.status.value != "ACCEPTED":
        return "SUPPRESSED"
    return record.kind.value + ("_STRUCTURE" if record.source.value == "STRUCTURE" else "")


def ladder_items(look, relations, chosen: dict[str, int]):
    """Rails, ends and column lines of one reading per PatchQuadLadderRelation.

    The reading Layer 4 chose for a bevel strip (chosen: patch id -> index),
    else the first reading.
    """

    rails, ends, columns = [], [], []
    for relation in sorted(getattr(relations, "patch_quad_ladder_relations", ()), key=lambda item: item.id):
        patch_id = str(relation.patch_id)
        reading_index = chosen.get(patch_id, 0)
        reading = relation.readings[reading_index]
        profile = [[str(vertex) for vertex in line] for line in reading.profile_vertex_ids]
        first_column, last_column = reading.columns[0], reading.columns[-1]
        rail_paths = {"A": [line[0] for line in profile], "B": [line[-1] for line in profile]}
        for rail, vertices in rail_paths.items():
            if reading.is_closed:
                vertices = vertices + vertices[:1]
            face_id = first_column[0] if rail == "A" else first_column[-1]
            view = _ladder_view(look, f"{relation.id}:rail_{rail}", patch_id, vertices, face_id)
            offset = _offset(look, view) if view is not None else None
            rails.append({
                "relation_id": relation.id,
                "patch_id": patch_id,
                "reading_index": reading_index,
                "rail": rail,
                "source_edge_ids": [
                    str(edge) for edge in (reading.rail_a_source_edge_ids if rail == "A" else reading.rail_b_source_edge_ids)
                ],
                "strokes": [_stroke(offset["polyline"], f"ladder_rail_{rail}", LADDER_RAIL_COLORS[rail], LADDER_RAIL_WIDTH)]
                if offset else [],
            })
        if not reading.is_closed:
            for end, vertices, column, edges in (
                ("A", profile[0], first_column, reading.end_a_source_edge_ids),
                ("B", profile[-1], last_column, reading.end_b_source_edge_ids),
            ):
                view = _ladder_view(look, f"{relation.id}:end_{end}", patch_id, vertices, column[0])
                offset = _offset(look, view) if view is not None else None
                ends.append({
                    "relation_id": relation.id,
                    "patch_id": patch_id,
                    "reading_index": reading_index,
                    "end": end,
                    "source_edge_ids": [str(edge) for edge in edges],
                    "strokes": [_stroke(offset["polyline"], "ladder_end", LADDER_END_COLOR, LADDER_RAIL_WIDTH)]
                    if offset else [],
                })
        inner = profile if reading.is_closed else profile[1:-1]
        strokes = []
        for vertices in inner:
            points = [_source_position(look, vertex) for vertex in vertices]
            if any(point is None for point in points) or len(points) < 2:
                continue
            lifted = [
                _add(point, _scale(_vertex_normal(look, patch_id, vertex), RAIL_NORMAL_HOVER_FACTOR * look.unit))
                for point, vertex in zip(points, vertices)
            ]
            strokes.append(_stroke(lifted, "ladder_column", LADDER_COLUMN_COLOR, LADDER_COLUMN_WIDTH))
        columns.append({
            "relation_id": relation.id,
            "patch_id": patch_id,
            "reading_index": reading_index,
            "column_count": len(reading.columns),
            "faces_per_column": reading.faces_per_column,
            "is_closed": reading.is_closed,
            "reading_count": len(relation.readings),
            "strokes": strokes,
        })
    return rails, ends, columns


def _ladder_view(look, view_id: str, patch_id: str, vertices: list[str], face_id) -> UsePieceView | None:
    """A rail or end walked the way face_id winds along its first edge, so the offset lands on that face."""

    if len(vertices) < 2:
        return None
    face = look.source.faces.get(face_id)
    if face is not None:
        cycle = [str(vertex) for vertex in face.vertex_ids]
        a, b = vertices[0], vertices[1]
        if a in cycle and cycle[(cycle.index(a) + 1) % len(cycle)] != b:
            vertices = list(reversed(vertices))
    points = [_source_position(look, vertex) for vertex in vertices]
    if any(point is None for point in points):
        return None
    return UsePieceView(
        id=view_id,
        patch_id=patch_id,
        patch_chain_id="",
        parent_chain_id="",
        vertex_ids=tuple(vertices),
        polyline=tuple(points),
    )


def face_strength_items(look) -> list[dict[str, Any]]:
    """One fill item per Blender Face Strength class present; unmarked faces are not drawn."""

    faces_by_kind: dict[str, list[Any]] = defaultdict(list)
    for patch_id in sorted(look.patch_rank, key=look.patch_rank.get):
        for face_id in look.patch_by_id[patch_id].source_face_ids:
            face = look.source.faces.get(face_id)
            mark = getattr(face, "face_strength", None) if face is not None else None
            if mark is not None:
                faces_by_kind[mark.value].append(face_id)
    return [
        {
            "face_strength": kind,
            "face_ids": [str(face_id) for face_id in faces_by_kind[kind]],
            "strokes": _fill_strokes(look, faces_by_kind[kind], f"face_strength_{kind}", FACE_STRENGTH_COLORS[kind]),
        }
        for kind in FACE_STRENGTH_KINDS
        if faces_by_kind.get(kind)
    ]


def chosen_readings(bevels) -> dict[str, int]:
    """Patch id -> the reading Layer 4 chose, for accepted bevel strips with a resolved direction."""

    return {
        str(record.patch_id): record.reading_index
        for record in bevels
        if record.kind.value == "BEVEL_STRIP" and record.status.value == "ACCEPTED" and record.reading_index is not None
    }


def bevel_items(look, bevels) -> dict[str, list[dict[str, Any]]]:
    """Fill per accepted bevel strip / junction, and per suppressed (bevel-marked, not a clean patch) record."""

    items: dict[str, list[dict[str, Any]]] = {layer: [] for layer in BEVEL_LAYERS.values()}
    for record in sorted(bevels, key=lambda item: look.patch_rank.get(str(item.patch_id), 0)):
        patch = look.patch_by_id.get(str(record.patch_id))
        if patch is None:
            continue
        group = bevel_group(record)
        items[BEVEL_LAYERS[group]].append({
            "id": record.id,
            "patch_id": str(record.patch_id),
            "kind": record.kind.value,
            "source": record.source.value,
            "status": record.status.value,
            "reason": record.suppression_reason.value if record.suppression_reason is not None else None,
            "reading_index": record.reading_index,
            "corner_kind": record.corner_kind.value,
            "strokes": _fill_strokes(look, patch.source_face_ids, f"bevel_{group.lower()}", BEVEL_COLORS[group]),
        })
    return items


def bevel_counts(bevels) -> dict[str, Any]:
    accepted = [record for record in bevels if record.status.value == "ACCEPTED"]
    strips = [record for record in accepted if record.kind.value == "BEVEL_STRIP"]
    return {
        "strips_by_source": dict(sorted(Counter(record.source.value for record in strips).items())),
        "junctions_by_source": dict(sorted(Counter(
            record.source.value for record in accepted if record.kind.value == "BEVEL_JUNCTION"
        ).items())),
        "unresolved": sum(1 for record in strips if record.reading_index is None),
        "suppressed_by_reason": dict(sorted(Counter(
            record.suppression_reason.value for record in bevels if record.suppression_reason is not None
        ).items())),
        "strip_corner_kinds": dict(sorted(Counter(record.corner_kind.value for record in strips).items())),
    }


def ladder_counts(relations) -> dict[str, int]:
    records = getattr(relations, "patch_quad_ladder_relations", ())
    return {
        "ladder_patches": len(records),
        "closed": sum(1 for record in records if any(reading.is_closed for reading in record.readings)),
        "two_readings": sum(1 for record in records if len(record.readings) == 2),
    }


def report_lines(payload: dict[str, Any]) -> list[str]:
    """Report lines: ladder patches, faces by source face mark, bevel records by source."""

    out = []
    ladders = payload.get("ladder_counts", {})
    out.append(
        f"ladder patches: {ladders.get('ladder_patches', 0)} "
        f"(closed {ladders.get('closed', 0)}, with two readings {ladders.get('two_readings', 0)})"
    )
    face_strength = payload.get("face_strength_counts", {})
    if face_strength:
        out.append("faces by source face mark: " + ", ".join(
            f"{kind.lower()}={face_strength.get(kind, 0)}" for kind in FACE_STRENGTH_KINDS
        ))
    bevel = payload.get("bevel_counts", {})
    if any(bevel.get(key) for key in ("strips_by_source", "junctions_by_source", "suppressed_by_reason")):
        out.append(
            "bevel strips: " + _count_text(bevel.get("strips_by_source", {}))
            + f"; unresolved {bevel.get('unresolved', 0)}"
            + "; corners " + _count_text(bevel.get("strip_corner_kinds", {}))
        )
        out.append("bevel junctions: " + _count_text(bevel.get("junctions_by_source", {})))
        out.append("bevel-marked, not isolated: " + _count_text(bevel.get("suppressed_by_reason", {})))
    laid = payload.get("bevel_ladders", {})
    if laid.get("constraints") or laid.get("not_laid"):
        out.append(
            f"bevel strips laid from their ladder: {laid.get('islands', 0)} of {laid.get('constraints', 0)} constraints"
        )
        for patch_id, reason in laid.get("not_laid", ()):
            out.append(f"  not laid: {patch_id}: {reason}")
    return out


def ladder_layout_counts(context, solve) -> dict[str, Any]:
    """STRAIGHT_LADDER constraints, islands laid by them, and the bevel strips without one and why."""

    features = getattr(context, "feature_snapshot", None)
    constraints = [
        constraint for constraint in getattr(features, "constraints", ()) or ()
        if constraint.kind.value == "STRAIGHT_LADDER"
    ]
    not_laid = [
        (str(diagnostic.entity_ids[0]) if diagnostic.entity_ids else "?", str(diagnostic.evidence.get("reason", "")))
        for diagnostic in getattr(features, "diagnostics", ()) or ()
        if diagnostic.code == "FEATURE_BEVEL_STRIP_NOT_LAID"
    ]
    return {
        "constraints": len(constraints),
        "islands": sum(1 for skeleton in solve.skeletons if skeleton.frame == "LADDER"),
        "not_laid": not_laid,
    }


def _count_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{key.lower()}={value}" for key, value in counts.items()) or "none"
