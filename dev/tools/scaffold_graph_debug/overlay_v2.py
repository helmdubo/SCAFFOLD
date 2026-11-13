"""Build the Scaffold structure-debugger payload without Blender.

Every stroke comes from a pipeline record: Layer 1 patches, loops and uses,
Layer 2 chain segments and face fans, Layer 3 runs, corners, shapes, families
and junctions, Layer 4 instances and the Layer 5 solve (islands, stitch
decisions, skeleton lines, nodes, axis roles and pins). The add-on computes
display offsets and marker shapes, and nothing else.

The payload always holds every layer. Which layers show is a Grease Pencil
layer flag set by the panel; it is not an input here, so a toggle never needs
a rebuild.
"""

from __future__ import annotations

import colorsys
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from .colors import (
    BRANCH_COLOR,
    CHAIN_SHAPE_COLORS,
    NEUTRAL_GRAY,
    RUN_ENDPOINT_JUNCTION_COLOR,
    SCAFFOLD_NODE_COLOR,
    stable_color,
)
from .rail_offsets import RAIL_NORMAL_HOVER_FACTOR, build_side_index, offset_use_polyline

PAYLOAD_VERSION = 3
GOLDEN_RATIO = 0.618034
CHAIN_SHAPE_KINDS = ("SURFACE_LINE", "SURFACE_CURVE", "UNRESOLVED")

GROUP_STRUCTURE = "Structure"
GROUP_SKELETON = "Skeleton"
GROUP_PATCHES = "Patches: sides and types"
GROUP_LAYER3 = "Layer 3 (detail)"
GROUP_LADDERS = "Ladders"
GROUP_BEVELS = "Bevels"
GROUPS = (GROUP_STRUCTURE, GROUP_SKELETON, GROUP_PATCHES, GROUP_LAYER3, GROUP_LADDERS, GROUP_BEVELS)


@dataclass(frozen=True)
class LayerSpec:
    """One toggleable Grease Pencil layer of the debugger."""

    prop: str
    layer: str
    label: str
    group: str
    default: bool


LAYER_SPECS = (
    LayerSpec("show_patches", "Scaffold_Patches", "Patches", GROUP_STRUCTURE, True),
    LayerSpec("show_boundary", "Scaffold_Loops_Boundary", "Boundary", GROUP_STRUCTURE, True),
    LayerSpec("show_holes", "Scaffold_Loops_Holes", "Holes", GROUP_STRUCTURE, True),
    LayerSpec("show_chains", "Scaffold_Chains", "Chains", GROUP_STRUCTURE, True),
    LayerSpec("show_islands_unfolded", "Scaffold_Islands_UNFOLDED", "Quilts: rigid frame", GROUP_SKELETON, False),
    LayerSpec("show_islands_frame_free", "Scaffold_Islands_FRAME_FREE", "Quilts: frame-free", GROUP_SKELETON, False),
    LayerSpec("show_islands_strip", "Scaffold_Islands_STRIP", "Quilts: strip", GROUP_SKELETON, False),
    LayerSpec("show_islands_ladder", "Scaffold_Islands_LADDER", "Quilts: bevel strip by itself", GROUP_SKELETON, False),
    LayerSpec("show_lines", "Scaffold_Skeleton_Lines", "Lines", GROUP_SKELETON, True),
    LayerSpec("show_nodes", "Scaffold_Skeleton_Nodes", "Nodes", GROUP_SKELETON, True),
    LayerSpec("show_pins", "Scaffold_Pins", "Pins", GROUP_SKELETON, False),
    LayerSpec("show_seams", "Scaffold_Seams", "Seams", GROUP_SKELETON, True),
    LayerSpec("show_sides", "Scaffold_Patch_Sides", "Sides", GROUP_PATCHES, False),
    LayerSpec("show_corners", "Scaffold_Patch_Corners", "Corners", GROUP_PATCHES, False),
    LayerSpec("show_types_strip", "Scaffold_Types_Strip", "Types: strip", GROUP_PATCHES, False),
    LayerSpec("show_types_strip_off", "Scaffold_Types_StripOff", "Types: strip (option off)", GROUP_PATCHES, False),
    LayerSpec("show_types_rectangle", "Scaffold_Types_Rectangle", "Types: rectangle", GROUP_PATCHES, False),
    LayerSpec("show_types_four_sided", "Scaffold_Types_FourSided", "Types: four-sided", GROUP_PATCHES, False),
    LayerSpec("show_types_other", "Scaffold_Types_Other", "Types: other", GROUP_PATCHES, False),
    LayerSpec("show_families", "Scaffold_L3_Families", "Family Colors", GROUP_LAYER3, False),
    LayerSpec("show_junctions", "Scaffold_L3_Junctions", "Junctions", GROUP_LAYER3, False),
    LayerSpec("show_ladder_rails", "Scaffold_Ladder_Rails", "Ladder rails", GROUP_LADDERS, False),
    LayerSpec("show_ladder_ends", "Scaffold_Ladder_Ends", "Ladder ends", GROUP_LADDERS, False),
    LayerSpec("show_ladder_columns", "Scaffold_Ladder_Columns", "Ladder columns", GROUP_LADDERS, False),
    LayerSpec("show_face_strength", "Scaffold_Source_Face_Strength", "Source face mark", GROUP_LADDERS, False),
    LayerSpec("show_bevel_strip", "Scaffold_Bevel_Strip", "Bevel strip", GROUP_BEVELS, False),
    LayerSpec("show_bevel_junction", "Scaffold_Bevel_Junction", "Bevel junction", GROUP_BEVELS, False),
    LayerSpec(
        "show_bevel_strip_structure", "Scaffold_Bevel_Strip_Structure", "Bevel strip (by structure)", GROUP_BEVELS, False
    ),
    LayerSpec(
        "show_bevel_junction_structure", "Scaffold_Bevel_Junction_Structure", "Bevel junction (by structure)",
        GROUP_BEVELS, False,
    ),
    LayerSpec("show_bevel_not_isolated", "Scaffold_Bevel_Not_Isolated", "Bevel, not isolated", GROUP_BEVELS, False),
)
LAYER_BY_PROP = {spec.prop: spec.layer for spec in LAYER_SPECS}

LEGENDS = {
    GROUP_STRUCTURE: (
        "Patches: one colour per patch",
        "Boundary: outer loop (white); Holes: inner loop (blue)",
        "Chains: each patch's own copy of a boundary chain",
        "  yellow = axis A, cyan = axis B of that island",
        "  grey = oblique or no axis",
        "Labels: P<patch>C<position in loop>",
    ),
    GROUP_SKELETON: (
        "Quilts (islands): fill per quilt, by frame kind",
        "  a quilt is what lies together in UV; the user filter",
        "  splits or joins seams (counts in the text report)",
        "Lines: one colour per island line",
        "Nodes: white crosses; Pins: orange crosses",
        "Seams: green dashed = stitched, red = cut",
    ),
    GROUP_PATCHES: (
        "Sides: mint = surface line, blue = surface curve,",
        "  orange = unresolved",
        "Corners: green = right convex, magenta = right reflex,",
        "  orange = other (straight corners not drawn)",
        "  blue = right corner bridged over one run (on that run)",
        "Types: Layer 4 verdict per patch",
        "  strip = straightened (option on)",
        "  strip (option off) = would be straightened",
        "  with the option on",
    ),
    GROUP_LAYER3: (
        "Family Colors: Layer 3 direction family per run",
        "Junctions: + ScaffoldNode, * run-endpoint junction",
        "  yellow = branch (valence > 2)",
    ),
    GROUP_LADDERS: (
        "Layer 3 quad ladder: the reading Layer 4 chose",
        "  for a bevel strip, else the first reading",
        "Ladder rails: pink = rail A, lime = rail B",
        "Ladder ends: violet (none on a closed ring)",
        "Ladder columns: thin grey lines between columns",
        "Source face mark: Blender Face Strength,",
        "  red = weak, blue = medium, grey = strong",
    ),
    GROUP_BEVELS: (
        "Layer 4 bevel records",
        "Bevel strip: orange; Bevel junction: purple",
        "  (set by the Face Strength mark)",
        "(by structure): light orange / light purple,",
        "  found by mesh structure, not confirmed by a mark",
        "Bevel, not isolated: red = suppressed record of a",
        "  bevel-marked patch (seams missing or mixed marks)",
    ),
}

ROLE_COLORS = {
    "AXIS_A": (1.0, 0.85, 0.0, 1.0),
    "AXIS_B": (0.0, 0.85, 0.85, 1.0),
}
ROLE_WIDTH = 6
OBLIQUE_COLOR = (0.55, 0.55, 0.55, 0.7)
OBLIQUE_WIDTH = 3
BOUNDARY_COLOR = (1.0, 0.95, 0.95, 0.95)
HOLE_COLOR = (0.2, 0.35, 0.85, 0.95)
LOOP_WIDTH = 5
# Lifts along the patch normal, in multiples of the marker unit (the mesh's median
# edge length), so Patches < Loops < Chains (0.016) < Seams < Lines on every mesh.
LOOP_LIFT = 0.014
LINE_HOVER_FACTOR = 0.022
LINE_WIDTH = 10
LABEL_LIFT = 0.025
SEAM_LIFT = 0.018
SEAM_WIDTH = 5
SEAM_ACCEPTED_COLOR = (0.15, 0.9, 0.28, 1.0)
SEAM_REFUSED_COLOR = (1.0, 0.08, 0.08, 1.0)
NODE_COLOR = (1.0, 1.0, 1.0, 1.0)
NODE_WIDTH = 4
PIN_COLOR = (1.0, 0.5, 0.0, 1.0)
PIN_WIDTH = 3
CORNER_COLORS = {
    "RIGHT_CONVEX": (0.2, 0.9, 0.3, 1.0),
    "RIGHT_REFLEX": (1.0, 0.2, 0.9, 1.0),
    "OTHER": (1.0, 0.55, 0.0, 1.0),
    "BRIDGED_RIGHT": (0.25, 0.45, 1.0, 1.0),
}
CORNER_WIDTH = 4
SIDE_WIDTH = 6
FAMILY_WIDTH = 8
JUNCTION_WIDTH = 4
# Marker half-sizes are this many median mesh-edge lengths.
NODE_MARKER_FACTOR = 0.12
PIN_MARKER_FACTOR = 0.07
CORNER_MARKER_FACTOR = 0.08
JUNCTION_MARKER_FACTOR = 0.1
LABEL_SIZE_FACTOR = 0.4
ISLAND_SV = {"UNFOLDED": (0.65, 0.9), "FRAME_FREE": (0.45, 0.75), "STRIP": (0.85, 0.95), "LADDER": (1.0, 0.7)}
ISLAND_LAYERS = {
    "UNFOLDED": "Scaffold_Islands_UNFOLDED",
    "FRAME_FREE": "Scaffold_Islands_FRAME_FREE",
    "STRIP": "Scaffold_Islands_STRIP",
    "LADDER": "Scaffold_Islands_LADDER",
}
PATCH_TYPES = ("STRIP", "STRIP_OFF", "RECTANGLE", "FOUR_SIDED", "OTHER")
PATCH_TYPE_LAYERS = {
    "STRIP": "Scaffold_Types_Strip",
    "STRIP_OFF": "Scaffold_Types_StripOff",
    "RECTANGLE": "Scaffold_Types_Rectangle",
    "FOUR_SIDED": "Scaffold_Types_FourSided",
    "OTHER": "Scaffold_Types_Other",
}
PATCH_TYPE_COLORS = {
    "STRIP": (1.0, 0.78, 0.1, 1.0),
    "STRIP_OFF": (0.7, 0.45, 0.9, 1.0),
    "RECTANGLE": (0.25, 0.6, 1.0, 1.0),
    "FOUR_SIDED": (0.2, 0.8, 0.6, 1.0),
    "OTHER": (0.5, 0.5, 0.5, 1.0),
}
PATCH_TYPE_BY_REASON = {
    "option off": "STRIP_OFF",
    "already a rectangle": "RECTANGLE",
    "long sides are straight on the surface": "FOUR_SIDED",
    "laid from its bevel ladder": "STRIP",
}
PATCH_TYPE_NAMES = {
    "STRIP": "strip (straightened, or laid from its bevel ladder)",
    "STRIP_OFF": "strip (option off, would straighten)",
    "RECTANGLE": "rectangle",
    "FOUR_SIDED": "four-sided",
    "OTHER": "other",
}


@dataclass(frozen=True)
class UsePieceView:
    """A run, a shape piece or a whole use, walked in its use direction."""

    id: str
    patch_id: str
    patch_chain_id: str
    parent_chain_id: str
    vertex_ids: tuple[str, ...]
    polyline: tuple[tuple[float, float, float], ...]


def build_debug_payload(context: Any, solve: Any, *, object_name: str = "") -> dict[str, Any]:
    """Return the serializable debugger payload of a Pass 2 context and its solve."""

    topology = context.topology_snapshot
    geometry = context.geometry_facts
    relations = context.relation_snapshot
    source = context.source_snapshot
    if topology is None or geometry is None or relations is None or source is None:
        raise RuntimeError("The debugger needs source, topology, geometry and relation snapshots.")
    look = _lookups(topology, geometry, relations, source)
    layers: dict[str, list[dict[str, Any]]] = {spec.layer: [] for spec in LAYER_SPECS}

    run_views = _run_views(geometry, relations)
    run_offsets = {
        run_id: _offset(look, view) for run_id, view in run_views.items()
    }
    role_by_run, island_by_run = _roles(solve)

    layers["Scaffold_Patches"] = _patch_items(look)
    boundary, holes = _loop_items(look)
    layers["Scaffold_Loops_Boundary"] = boundary
    layers["Scaffold_Loops_Holes"] = holes
    layers["Scaffold_Chains"] = _chain_items(look, relations, run_offsets, role_by_run, island_by_run)
    for frame_kind, items in _island_items(look, solve).items():
        layers[ISLAND_LAYERS[frame_kind]] = items
    layers["Scaffold_Skeleton_Lines"] = _line_items(look, solve, run_views)
    layers["Scaffold_Skeleton_Nodes"] = _node_items(look, solve, relations)
    layers["Scaffold_Pins"] = _pin_items(look, solve)
    layers["Scaffold_Seams"] = _seam_items(look, solve)
    chain_shape_pieces = _chain_shape_pieces(look, geometry, relations)
    layers["Scaffold_Patch_Sides"] = chain_shape_pieces
    layers["Scaffold_Patch_Corners"] = _corner_items(look, relations, run_offsets)
    patch_types = _patch_types(look, context)
    for type_name, items in _type_items(look, patch_types).items():
        layers[PATCH_TYPE_LAYERS[type_name]] = items
    layers["Scaffold_L3_Families"] = _family_items(relations, run_offsets)
    layers["Scaffold_L3_Junctions"] = _junction_items(look, relations)
    from . import overlay_ladders  # its layer code imports this module's drawing helpers

    bevels = getattr(getattr(context, "feature_snapshot", None), "bevels", ()) or ()
    for layer_name, items in overlay_ladders.bevel_items(look, bevels).items():
        layers[layer_name] = items
    rails, ends, columns = overlay_ladders.ladder_items(look, relations, overlay_ladders.chosen_readings(bevels))
    layers["Scaffold_Ladder_Rails"] = rails
    layers["Scaffold_Ladder_Ends"] = ends
    layers["Scaffold_Ladder_Columns"] = columns
    layers["Scaffold_Source_Face_Strength"] = overlay_ladders.face_strength_items(look)

    labels = _labels(look, role_by_run)
    counts = {
        layer: {"items": len(items), "strokes": sum(len(item["strokes"]) for item in items)}
        for layer, items in layers.items()
    }
    counts["chain_shape"] = _chain_shape_counts(chain_shape_pieces, relations)
    payload = {
        "version": PAYLOAD_VERSION,
        "object_name": object_name,
        "marker_unit": look.unit,
        "layers": layers,
        "labels": labels,
        "chain_shape_pieces": chain_shape_pieces,
        "patch_types": patch_types,
        "ladder_counts": overlay_ladders.ladder_counts(relations),
        "bevel_counts": overlay_ladders.bevel_counts(bevels),
        "bevel_ladders": overlay_ladders.ladder_layout_counts(context, solve),
        "filter": _filter_summary(context),
        "face_strength_counts": {
            item["face_strength"]: len(item["face_ids"]) for item in layers["Scaffold_Source_Face_Strength"]
        },
        "counts": counts,
        "fallback_side_edges": sorted(list(edge) for edge in look.fallback_edges),
    }
    payload["report"] = format_report(payload, solve)
    return payload


# --------------------------------------------------------------------------- lookups


def _lookups(topology, geometry, relations, source):
    normal_sum: dict[tuple[str, str], list[float]] = {}
    for fan in geometry.local_face_fan_facts.values():
        key = (str(fan.patch_id), str(fan.source_vertex_id))
        total = normal_sum.setdefault(key, [0.0, 0.0, 0.0])
        for index in range(3):
            total[index] += float(fan.normal[index])
    fan_normal = {key: _normalize(tuple(value)) for key, value in normal_sum.items()}
    patch_normal = {
        str(patch_id): _normalize(tuple(float(value) for value in facts.normal))
        for patch_id, facts in geometry.patch_facts.items()
    }
    edge_lengths = sorted(
        _distance(source.vertices[edge.vertex_ids[0]].position, source.vertices[edge.vertex_ids[1]].position)
        for edge in source.edges.values()
        if len(edge.vertex_ids) == 2
        and edge.vertex_ids[0] in source.vertices
        and edge.vertex_ids[1] in source.vertices
    )
    unit = edge_lengths[len(edge_lengths) // 2] if edge_lengths else 1.0
    patch_ids = sorted((str(patch_id) for patch_id in topology.patches), key=_natural_key)
    unit = unit if unit > 0.0 else 1.0
    return SimpleNamespace(
        topology=topology,
        geometry=geometry,
        relations=relations,
        source=source,
        fan_normal=fan_normal,
        patch_normal=patch_normal,
        unit=unit,
        patch_rank={patch_id: rank for rank, patch_id in enumerate(patch_ids)},
        patch_by_id={str(patch_id): patch for patch_id, patch in topology.patches.items()},
        side_index=build_side_index(topology, source, fan_normal),
        fallback_edges=set(),
    )


def _vertex_normal(look, patch_id: str, source_vertex_id: Any) -> tuple[float, float, float]:
    normal = look.fan_normal.get((str(patch_id), str(source_vertex_id)))
    if normal is not None and _length(normal) > 0.0:
        return normal
    return look.patch_normal.get(str(patch_id), (0.0, 0.0, 1.0))


def _source_position(look, source_vertex_id: Any) -> tuple[float, float, float] | None:
    vertex = look.source.vertices.get(source_vertex_id)
    if vertex is None:
        for key, candidate in look.source.vertices.items():
            if str(key) == str(source_vertex_id):
                vertex = candidate
                break
    return None if vertex is None else tuple(float(value) for value in vertex.position)


def _vertex_position(look, vertex_id: Any) -> tuple[float, float, float] | None:
    facts = look.geometry.vertex_facts.get(vertex_id)
    if facts is None:
        topology_vertex = look.topology.vertices.get(vertex_id)
        if topology_vertex is not None and topology_vertex.source_vertex_ids:
            return _source_position(look, topology_vertex.source_vertex_ids[0])
        return None
    return tuple(float(value) for value in facts.position)


def _offset(look, view: UsePieceView, *, lift_factor: float = RAIL_NORMAL_HOVER_FACTOR):
    """Per-use display offset by the winding rule; lifts are multiples of the marker unit."""

    polyline, record = offset_use_polyline(
        look.side_index, view.patch_id, view.vertex_ids, view.polyline, lift=lift_factor * look.unit
    )
    look.fallback_edges.update((view.patch_id, a, b) for a, b in record["fallback_edges"])
    return {"polyline": [list(point) for point in polyline], "record": record}


# --------------------------------------------------------------------------- geometry readers


def _chain_points(geometry, chain_id) -> tuple[list[tuple[float, float, float]], list[str]]:
    """Positions and source vertex ids of a Chain in its own segment order."""

    chain_facts = geometry.chain_facts.get(chain_id)
    if chain_facts is None or not chain_facts.segments:
        return [], []
    segments = chain_facts.segments
    points = [tuple(float(value) for value in segments[0].start_position)]
    vertex_ids = [str(segments[0].start_source_vertex_id)]
    for segment in segments:
        points.append(tuple(float(value) for value in segment.end_position))
        vertex_ids.append(str(segment.end_source_vertex_id))
    return points, vertex_ids


def _use_points(look, patch_chain) -> tuple[list[tuple[float, float, float]], list[str]]:
    points, vertex_ids = _chain_points(look.geometry, patch_chain.chain_id)
    if patch_chain.orientation_sign == -1:
        points.reverse()
        vertex_ids.reverse()
    return points, vertex_ids


def _use_view(look, patch_chain) -> UsePieceView | None:
    points, vertex_ids = _use_points(look, patch_chain)
    if len(points) < 2:
        return None
    return UsePieceView(
        id=f"use:{patch_chain.id}",
        patch_id=str(patch_chain.patch_id),
        patch_chain_id=str(patch_chain.id),
        parent_chain_id=str(patch_chain.chain_id),
        vertex_ids=tuple(vertex_ids),
        polyline=tuple(points),
    )


def _run_views(geometry, relations) -> dict[str, UsePieceView]:
    """Each run walked from its START source vertex: a run follows its use (G0 DD-51)."""

    views = {}
    for evidence in sorted(relations.patch_chain_directional_evidence, key=lambda item: item.id):
        chain_facts = geometry.chain_facts.get(evidence.parent_chain_id)
        if chain_facts is None:
            continue
        by_index = {segment.segment_index: segment for segment in chain_facts.segments}
        segments = [by_index[index] for index in evidence.segment_indices if index in by_index]
        walked = _walk(segments, str(evidence.start_source_vertex_id))
        if walked is None:
            continue
        vertex_ids, points = walked
        views[evidence.id] = UsePieceView(
            id=evidence.id,
            patch_id=str(evidence.patch_id),
            patch_chain_id=str(evidence.patch_chain_id),
            parent_chain_id=str(evidence.parent_chain_id),
            vertex_ids=vertex_ids,
            polyline=points,
        )
    return views


def _walk(segments, start_vertex: str):
    """Source vertex ids and positions of chained segments walked from start_vertex."""

    for ordered in (segments, list(reversed(segments))):
        current = start_vertex
        vertex_ids = [current]
        points = []
        for segment in ordered:
            ends = (str(segment.start_source_vertex_id), str(segment.end_source_vertex_id))
            if current not in ends:
                break
            if not points:
                points.append(tuple(float(v) for v in (segment.start_position if current == ends[0] else segment.end_position)))
            forward = current == ends[0]
            current = ends[1] if forward else ends[0]
            vertex_ids.append(current)
            points.append(tuple(float(v) for v in (segment.end_position if forward else segment.start_position)))
        else:
            if len(points) >= 2:
                return tuple(vertex_ids), tuple(points)
    return None


def _face_triangles(look, face_ids) -> list[list[list[float]]]:
    triangles = []
    for face_id in face_ids:
        face = look.source.faces.get(face_id)
        if face is None:
            continue
        points = [_source_position(look, vertex_id) for vertex_id in face.vertex_ids]
        points = [point for point in points if point is not None]
        for index in range(1, len(points) - 1):
            triangles.append([list(points[0]), list(points[index]), list(points[index + 1])])
    return triangles


def _fill_strokes(look, face_ids, material: str, color) -> list[dict[str, Any]]:
    return [
        _stroke(triangle, material, color, 1, fill=True)
        for triangle in _face_triangles(look, face_ids)
    ]


def _stroke(points, material: str, color, width: int, *, fill: bool = False) -> dict[str, Any]:
    return {
        "points": [list(point) for point in points],
        "material": material,
        "color": list(color),
        "width": int(width),
        "fill": bool(fill),
    }


def _cross(center, half: float) -> list[list[list[float]]]:
    x, y, z = center
    return [
        [[x - half, y, z], [x + half, y, z]],
        [[x, y - half, z], [x, y + half, z]],
        [[x, y, z - half], [x, y, z + half]],
    ]


def _star(center, half: float) -> list[list[list[float]]]:
    x, y, z = center
    d = half / math.sqrt(3.0)
    return [
        [[x - d * sx, y - d * sy, z - d], [x + d * sx, y + d * sy, z + d]]
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1))
    ]


def _hsv(hue: float, saturation: float, value: float) -> tuple[float, float, float, float]:
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    return (red, green, blue, 1.0)


# --------------------------------------------------------------------------- Structure


def _patch_items(look) -> list[dict[str, Any]]:
    items = []
    for patch_id, rank in sorted(look.patch_rank.items(), key=lambda item: item[1]):
        color = _hsv(rank * GOLDEN_RATIO, 0.7, 0.85)
        patch = look.patch_by_id[patch_id]
        items.append({
            "patch_id": patch_id,
            "rank": rank,
            "strokes": _fill_strokes(look, patch.source_face_ids, f"patch_{rank}", color),
        })
    return items


def _loop_items(look) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    boundary, holes = [], []
    for loop_id, loop in sorted(look.topology.loops.items(), key=lambda item: str(item[0])):
        points: list[tuple[float, float, float]] = []
        vertex_ids: list[str] = []
        for patch_chain_id in loop.patch_chain_ids:
            patch_chain = look.topology.patch_chains.get(patch_chain_id)
            if patch_chain is None:
                continue
            use_points, use_vertex_ids = _use_points(look, patch_chain)
            if not use_points:
                continue
            if vertex_ids and use_vertex_ids[-1] == vertex_ids[-1] and use_vertex_ids[0] != vertex_ids[-1]:
                use_points.reverse()
                use_vertex_ids.reverse()
            if vertex_ids and use_vertex_ids[0] == vertex_ids[-1]:
                use_points, use_vertex_ids = use_points[1:], use_vertex_ids[1:]
            points.extend(use_points)
            vertex_ids.extend(use_vertex_ids)
        if vertex_ids and vertex_ids[0] != vertex_ids[-1]:
            points.append(points[0])
            vertex_ids.append(vertex_ids[0])
        patch_id = str(loop.patch_id)
        lifted = [
            _add(point, _scale(_vertex_normal(look, patch_id, vertex_id), LOOP_LIFT * look.unit))
            for point, vertex_id in zip(points, vertex_ids)
        ]
        is_outer = loop.kind.value == "OUTER"
        color = BOUNDARY_COLOR if is_outer else HOLE_COLOR
        item = {
            "loop_id": str(loop_id),
            "patch_id": patch_id,
            "kind": loop.kind.value,
            "strokes": [_stroke(lifted, "loop_outer" if is_outer else "loop_inner", color, LOOP_WIDTH)]
            if len(lifted) >= 2 else [],
        }
        (boundary if is_outer else holes).append(item)
    return boundary, holes


def _roles(solve) -> tuple[dict[str, str], dict[str, str]]:
    role_by_run: dict[str, str] = {}
    island_by_run: dict[str, str] = {}
    for skeleton in solve.skeletons:
        for run_id, role in skeleton.axis_role_by_run.items():
            role_by_run[run_id] = role
            island_by_run[run_id] = skeleton.island_id
    return role_by_run, island_by_run


def _role_style(role: str | None) -> tuple[tuple[float, float, float, float], int, str]:
    if role in ROLE_COLORS:
        return ROLE_COLORS[role], ROLE_WIDTH, f"role_{role}"
    return OBLIQUE_COLOR, OBLIQUE_WIDTH, "role_none"


def _chain_items(look, relations, run_offsets, role_by_run, island_by_run) -> list[dict[str, Any]]:
    runs_by_use: dict[str, list[Any]] = defaultdict(list)
    for evidence in relations.patch_chain_directional_evidence:
        runs_by_use[str(evidence.patch_chain_id)].append(evidence)
    items = []
    for patch_chain_id, patch_chain in sorted(look.topology.patch_chains.items(), key=lambda item: str(item[0])):
        runs = sorted(runs_by_use.get(str(patch_chain_id), ()), key=lambda item: item.id)
        if not runs:
            view = _use_view(look, patch_chain)
            offset = _offset(look, view) if view is not None else None
            color, width, material = _role_style(None)
            items.append({
                "patch_chain_id": str(patch_chain_id),
                "patch_id": str(patch_chain.patch_id),
                "run_id": None,
                "role": None,
                "island_id": None,
                "strokes": [_stroke(offset["polyline"], material, color, width)] if offset else [],
            })
            continue
        for evidence in runs:
            role = role_by_run.get(evidence.id)
            color, width, material = _role_style(role)
            offset = run_offsets.get(evidence.id)
            items.append({
                "patch_chain_id": str(patch_chain_id),
                "patch_id": str(patch_chain.patch_id),
                "run_id": evidence.id,
                "role": role,
                "island_id": island_by_run.get(evidence.id),
                "strokes": [_stroke(offset["polyline"], material, color, width)] if offset else [],
            })
    return items


def _labels(look, role_by_run) -> list[dict[str, Any]]:
    runs_by_use: dict[str, list[Any]] = defaultdict(list)
    for evidence in look.relations.patch_chain_directional_evidence:
        runs_by_use[str(evidence.patch_chain_id)].append(evidence)
    loops_per_patch = {patch_id: len(patch.loop_ids) for patch_id, patch in look.patch_by_id.items()}
    labels = []
    for patch_chain_id, patch_chain in sorted(look.topology.patch_chains.items(), key=lambda item: str(item[0])):
        view = _use_view(look, patch_chain)
        if view is None:
            continue
        offset = _offset(look, view)
        midpoint = _arc_midpoint(offset["polyline"])
        normal = tuple(offset["record"]["normal_hover_direction"])
        patch_id = str(patch_chain.patch_id)
        text = f"P{look.patch_rank.get(patch_id, 0)}C{patch_chain.position_in_loop}"
        if loops_per_patch.get(patch_id, 1) > 1:
            loop = look.topology.loops.get(patch_chain.loop_id)
            text = f"{text}L{loop.loop_index if loop is not None else '?'}"
        runs = runs_by_use.get(str(patch_chain_id), ())
        role = role_by_run.get(max(runs, key=lambda item: item.length).id) if runs else None
        color, _width, _material = _role_style(role)
        labels.append({
            "patch_chain_id": str(patch_chain_id),
            "text": text,
            "position": list(_add(midpoint, _scale(normal, LABEL_LIFT * look.unit))),
            "color": list(color[:3]) + [1.0],
            "size": LABEL_SIZE_FACTOR * look.unit,
        })
    return labels


# --------------------------------------------------------------------------- Skeleton


def _island_items(look, solve) -> dict[str, list[dict[str, Any]]]:
    frame_by_island = {skeleton.island_id: skeleton.frame for skeleton in solve.skeletons}
    items: dict[str, list[dict[str, Any]]] = {kind: [] for kind in ISLAND_LAYERS}
    for rank, island in enumerate(solve.assembly.islands):
        frame = frame_by_island.get(island.id)
        if frame not in ISLAND_LAYERS:
            continue  # no skeleton or an unknown frame kind: named in the text report, not drawn
        saturation, value = ISLAND_SV[frame]
        color = _hsv(rank * GOLDEN_RATIO, saturation, value)
        strokes = []
        for patch_id in island.patch_ids:
            patch = look.patch_by_id.get(str(patch_id))
            if patch is not None:
                strokes.extend(_fill_strokes(look, patch.source_face_ids, f"island_{rank}_{frame}", color))
        items[frame].append({
            "island_id": island.id,
            "frame": frame,
            "patch_ids": [str(patch_id) for patch_id in island.patch_ids],
            "strokes": strokes,
        })
    return items


def _line_items(look, solve, run_views) -> list[dict[str, Any]]:
    items = []
    for skeleton in solve.skeletons:
        runs_by_line: dict[str, list[str]] = defaultdict(list)
        for run_id, line_id in skeleton.line_by_run.items():
            runs_by_line[str(line_id)].append(run_id)
        for line_id, run_ids in sorted(runs_by_line.items()):
            key = f"{skeleton.island_id}:{line_id}"
            color = stable_color(key)
            strokes = []
            for run_id in sorted(run_ids):
                view = run_views.get(run_id)
                if view is None:
                    continue
                offset = _offset(look, view, lift_factor=LINE_HOVER_FACTOR)
                strokes.append(_stroke(offset["polyline"], f"line_{key}", color, LINE_WIDTH))
            items.append({
                "island_id": skeleton.island_id,
                "line_id": line_id,
                "run_ids": sorted(run_ids),
                "roles": sorted({str(skeleton.axis_role_by_run.get(run_id)) for run_id in run_ids}),
                "strokes": strokes,
            })
    return items


def _node_items(look, solve, relations) -> list[dict[str, Any]]:
    evidence_by_id = {evidence.id: evidence for evidence in relations.patch_chain_directional_evidence}
    half = NODE_MARKER_FACTOR * look.unit
    items = []
    for skeleton in solve.skeletons:
        ends_by_node: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for run_end, node in skeleton.node_by_run_end.items():
            ends_by_node[str(node)].append(run_end)
        for node, run_ends in sorted(ends_by_node.items()):
            points = []
            for run_id, role in run_ends:
                position = None
                vertex_id = skeleton.vertex_by_run_end.get((run_id, role))
                if vertex_id is not None:
                    position = _vertex_position(look, vertex_id)
                if position is None and run_id in evidence_by_id:
                    evidence = evidence_by_id[run_id]
                    source_vertex = evidence.start_source_vertex_id if role == "START" else evidence.end_source_vertex_id
                    position = _source_position(look, source_vertex)
                if position is not None:
                    points.append(position)
            if not points:
                continue
            center = _mean(points)
            items.append({
                "island_id": skeleton.island_id,
                "node_id": node,
                "position": list(center),
                "run_end_count": len(run_ends),
                "strokes": [_stroke(segment, "node", NODE_COLOR, NODE_WIDTH) for segment in _cross(center, half)],
            })
    return items


def _pin_items(look, solve) -> list[dict[str, Any]]:
    half = PIN_MARKER_FACTOR * look.unit
    items = []
    for vertex in solve.vertices:
        if not vertex.pinned:
            continue
        position = _vertex_position(look, vertex.vertex_id) or _source_position(look, vertex.source_vertex_id)
        if position is None:
            continue
        normal = _vertex_normal(look, vertex.patch_id, vertex.source_vertex_id)
        center = _add(position, _scale(normal, 0.5 * half))
        items.append({
            "island_id": vertex.island_id,
            "patch_id": vertex.patch_id,
            "vertex_id": vertex.vertex_id,
            "source_vertex_id": vertex.source_vertex_id,
            "strokes": [_stroke(segment, "pin", PIN_COLOR, PIN_WIDTH) for segment in _cross(center, half)],
        })
    return items


def _seam_items(look, solve) -> list[dict[str, Any]]:
    items = []
    for decision in solve.assembly.decisions:
        points, vertex_ids = _chain_points(look.geometry, _chain_key(look.geometry, decision.chain_id))
        lifted = []
        for point, vertex_id in zip(points, vertex_ids):
            normal = _normalize(_add(
                _vertex_normal(look, decision.first_patch_id, vertex_id),
                _vertex_normal(look, decision.second_patch_id, vertex_id),
            ))
            lifted.append(_add(point, _scale(normal, SEAM_LIFT * look.unit)))
        if decision.accepted:
            strokes = [
                _stroke(dash, "seam_accepted", SEAM_ACCEPTED_COLOR, SEAM_WIDTH)
                for dash in _dashes(lifted)
            ]
        else:
            strokes = [_stroke(lifted, "seam_refused", SEAM_REFUSED_COLOR, SEAM_WIDTH)] if len(lifted) >= 2 else []
        items.append({
            "chain_id": str(decision.chain_id),
            "first_patch_id": str(decision.first_patch_id),
            "second_patch_id": str(decision.second_patch_id),
            "accepted": bool(decision.accepted),
            "reason": str(decision.reason),
            "strokes": strokes,
        })
    return items


def _chain_key(geometry, chain_id):
    if chain_id in geometry.chain_facts:
        return chain_id
    for key in geometry.chain_facts:
        if str(key) == str(chain_id):
            return key
    return chain_id


def _dashes(points) -> list[list[tuple[float, float, float]]]:
    """Every other mesh edge; a chain of one or two edges is cut in quarters first."""

    if len(points) < 2:
        return []
    if len(points) <= 3:
        fine = [points[0]]
        for first, second in zip(points, points[1:]):
            for step in range(1, 5):
                fine.append(_lerp(first, second, step / 4.0))
        points = fine
    return [[points[index], points[index + 1]] for index in range(0, len(points) - 1, 2)]


# --------------------------------------------------------------------------- Patches: sides and types


def _chain_shape_pieces(look, geometry, relations) -> list[dict[str, Any]]:
    """One payload item per core PatchChainShapeRelation, offset to its own patch side."""

    records = sorted(getattr(relations, "patch_chain_shape_relations", ()), key=lambda item: item.id)
    views = {
        record.id: view
        for record in records
        for view in (_chain_shape_piece_view(look, geometry, record),)
        if view is not None
    }
    messages_by_record_id: dict[str, list[str]] = {}
    for diagnostic in getattr(relations, "diagnostics", ()):
        for entity_id in diagnostic.entity_ids:
            if entity_id in views:
                messages_by_record_id.setdefault(entity_id, []).append(diagnostic.message)
    pieces = []
    for record in records:
        view = views.get(record.id)
        if view is None:
            continue
        offset = _offset(look, view)
        kind = record.kind.value
        color = CHAIN_SHAPE_COLORS.get(kind, NEUTRAL_GRAY)
        pieces.append({
            "id": record.id,
            "kind": kind,
            "patch_id": view.patch_id,
            "patch_chain_id": view.patch_chain_id,
            "chain_id": view.parent_chain_id,
            "polyline": offset["polyline"],
            "color": list(color),
            "length": float(record.length),
            "segment_count": len(record.segment_indices),
            "surface_turn_max_deg": math.degrees(record.surface_turn_max),
            "tilt_range_deg": (
                [math.degrees(record.tilt_min), math.degrees(record.tilt_max)]
                if record.tilt_min is not None and record.tilt_max is not None
                else None
            ),
            "unoffset": bool(offset["record"]["unoffset"]),
            "diagnostics": messages_by_record_id.get(record.id, []),
            "strokes": [_stroke(offset["polyline"], f"side_{kind}", color, SIDE_WIDTH)],
        })
    return pieces


def _chain_shape_piece_view(look, geometry: Any, record: Any) -> UsePieceView | None:
    """A shape piece follows the Chain's segment order; turn it into its use direction."""

    chain_facts = geometry.chain_facts.get(record.chain_id)
    if chain_facts is None:
        return None
    segments_by_index = {segment.segment_index: segment for segment in chain_facts.segments}
    segments = [segments_by_index[index] for index in record.segment_indices if index in segments_by_index]
    if not segments or len(segments) != len(record.segment_indices):
        return None
    walked = _walk(segments, str(record.start_source_vertex_id))
    if walked is None:
        return None
    vertex_ids, points = walked
    patch_chain = look.topology.patch_chains.get(record.patch_chain_id)
    if patch_chain is not None and patch_chain.orientation_sign == -1:
        vertex_ids, points = tuple(reversed(vertex_ids)), tuple(reversed(points))
    return UsePieceView(
        id=record.id,
        patch_id=str(record.patch_id),
        patch_chain_id=str(record.patch_chain_id),
        parent_chain_id=str(record.chain_id),
        vertex_ids=vertex_ids,
        polyline=points,
    )


def _chain_shape_counts(pieces: list[dict[str, Any]], relations) -> dict[str, int]:
    counts = {
        f"chain_shape_{kind.lower()}_count": sum(piece["kind"] == kind for piece in pieces)
        for kind in CHAIN_SHAPE_KINDS
    }
    counts["chain_shape_piece_count"] = len(pieces)
    counts["chain_shape_undrawn_count"] = len(getattr(relations, "patch_chain_shape_relations", ())) - len(pieces)
    return counts


def _corner_items(look, relations, run_offsets) -> list[dict[str, Any]]:
    half = CORNER_MARKER_FACTOR * look.unit
    items = []
    for corner in sorted(relations.run_corner_relations, key=lambda item: item.id):
        kind = corner.kind.value
        if kind == "STRAIGHT":
            continue
        if kind == "RIGHT":
            category = "RIGHT_CONVEX" if corner.interior_angle_sum < math.pi else "RIGHT_REFLEX"
        else:
            category = "OTHER"
        positions = [_vertex_position(look, vertex_id) for vertex_id in corner.vertex_ids]
        positions = [position for position in positions if position is not None]
        if not positions:
            continue
        pulls = [
            tuple(run_offsets[run_id]["record"]["offset_vector"])
            for run_id in (corner.first_directional_evidence_id, corner.second_directional_evidence_id)
            if run_id in run_offsets
        ]
        center = _add(_mean(positions), _mean(pulls) if pulls else (0.0, 0.0, 0.0))
        color = CORNER_COLORS[category]
        items.append({
            "corner_id": corner.id,
            "patch_id": str(corner.patch_id),
            "kind": kind,
            "category": category,
            "interior_angle_sum": float(corner.interior_angle_sum),
            "strokes": [_stroke(segment, f"corner_{category}", color, CORNER_WIDTH) for segment in _cross(center, half)],
        })
    # A right corner turned over one bridge run: one marker at the bridge's
    # midpoint, on its displayed (offset) polyline.
    for corner in sorted(getattr(relations, "run_bridged_corner_relations", ()), key=lambda item: item.id):
        offset = run_offsets.get(corner.bridge_directional_evidence_id)
        if offset is None or not offset["polyline"]:
            continue
        center = _arc_midpoint(offset["polyline"])
        color = CORNER_COLORS["BRIDGED_RIGHT"]
        items.append({
            "corner_id": corner.id,
            "patch_id": str(corner.patch_id),
            "kind": "BRIDGED_RIGHT",
            "category": "BRIDGED_RIGHT",
            "interior_angle_sum": float(corner.interior_angle_sum),
            "bridge_run_id": corner.bridge_directional_evidence_id,
            "strokes": [_stroke(segment, "corner_BRIDGED_RIGHT", color, CORNER_WIDTH) for segment in _cross(center, half)],
        })
    return items


def _patch_types(look, context) -> dict[str, dict[str, Any]]:
    """Per patch, what Layer 4 says today (ACCEPTED wins over a suppression).

    Layer 4 grades the shape before the option, so "option off" marks exactly
    the strips the option would straighten (STRIP_OFF); rectangles and
    four-sided patches keep their verdict whatever the option.
    """

    features = getattr(context, "feature_snapshot", None)
    instances_by_patch: dict[str, list[Any]] = defaultdict(list)
    for instance in getattr(features, "instances", ()) or ():
        instances_by_patch[str(instance.patch_id)].append(instance)
    rows = {}
    for patch_id in look.patch_rank:
        instances = sorted(instances_by_patch.get(patch_id, ()), key=lambda item: item.id)
        type_name = "OTHER"
        if any(instance.status.value == "ACCEPTED" for instance in instances):
            type_name = "STRIP"
        else:
            for instance in instances:
                reason = instance.suppression_reason.value if instance.suppression_reason is not None else ""
                type_name = PATCH_TYPE_BY_REASON.get(reason, type_name)
                if type_name != "OTHER":
                    break
        rows[patch_id] = {"type": type_name, "instance_ids": [instance.id for instance in instances]}
    return rows


def _type_items(look, patch_types) -> dict[str, list[dict[str, Any]]]:
    items: dict[str, list[dict[str, Any]]] = {type_name: [] for type_name in PATCH_TYPES}
    for patch_id, row in sorted(patch_types.items(), key=lambda item: look.patch_rank[item[0]]):
        type_name = row["type"]
        patch = look.patch_by_id[patch_id]
        items[type_name].append({
            "patch_id": patch_id,
            "type": type_name,
            "instance_ids": list(row["instance_ids"]),
            "strokes": _fill_strokes(look, patch.source_face_ids, f"type_{type_name}", PATCH_TYPE_COLORS[type_name]),
        })
    return items


# --------------------------------------------------------------------------- Layer 3 detail


def _family_items(relations, run_offsets) -> list[dict[str, Any]]:
    family_by_run = {
        member: family.id
        for family in relations.connected_direction_families
        for member in family.member_directional_evidence_ids
    }
    items = []
    for evidence in sorted(relations.patch_chain_directional_evidence, key=lambda item: item.id):
        offset = run_offsets.get(evidence.id)
        family_id = family_by_run.get(evidence.id)
        color = stable_color(family_id) if family_id is not None else NEUTRAL_GRAY
        items.append({
            "run_id": evidence.id,
            "family_id": family_id,
            "strokes": [_stroke(offset["polyline"], f"family_{family_id or 'none'}", color, FAMILY_WIDTH)]
            if offset else [],
        })
    return items


def _junction_items(look, relations) -> list[dict[str, Any]]:
    valence_by_node: Counter = Counter()
    for junction in relations.run_endpoint_junctions:
        if junction.anchor_scaffold_node_id is not None:
            valence_by_node[junction.anchor_scaffold_node_id] += len(junction.incident_run_endpoint_occurrences)
    rows = [
        ("SCAFFOLD_NODE", node.id, node.vertex_ids, valence_by_node.get(node.id, 0))
        for node in sorted(relations.scaffold_nodes, key=lambda item: item.id)
    ] + [
        ("RUN_ENDPOINT_JUNCTION", junction.id, junction.topology_vertex_ids, len(junction.incident_run_endpoint_occurrences))
        for junction in sorted(relations.run_endpoint_junctions, key=lambda item: item.id)
    ]
    items = []
    for kind, item_id, vertex_ids, valence in rows:
        positions = [_vertex_position(look, vertex_id) for vertex_id in vertex_ids]
        positions = [position for position in positions if position is not None]
        if not positions:
            continue
        center = _mean(positions)
        color = BRANCH_COLOR if valence > 2 else (
            SCAFFOLD_NODE_COLOR if kind == "SCAFFOLD_NODE" else RUN_ENDPOINT_JUNCTION_COLOR
        )
        half = look.unit * (JUNCTION_MARKER_FACTOR + 0.03 * max(0, min(3, valence - 1)))
        segments = _cross(center, half) if kind == "SCAFFOLD_NODE" else _star(center, half)
        material = "branch" if valence > 2 else kind.lower()
        items.append({
            "id": item_id,
            "kind": kind,
            "valence": valence,
            "position": list(center),
            "strokes": [_stroke(segment, f"junction_{material}", color, JUNCTION_WIDTH) for segment in segments],
        })
    return items


# --------------------------------------------------------------------------- report


def _filter_summary(context: Any) -> dict[str, Any]:
    """The user filter (Pass 3) as counts: options, patch classes, directives by kind and rule."""

    snapshot = getattr(context, "filter_snapshot", None)
    if snapshot is None or snapshot.options.world_up is None:
        return {"on": False}
    return {
        "on": True,
        "world_up": list(snapshot.options.world_up),
        "angle": snapshot.options.horizontal_angle_degrees,
        "classes": dict(Counter(record.patch_class.value for record in snapshot.patch_classes)),
        "directives": {
            f"{kind} ({rule})": count
            for (kind, rule), count in sorted(Counter(
                (directive.kind.value, directive.rule) for directive in snapshot.directives
            ).items())
        },
        "diagnostics": [diagnostic.message for diagnostic in snapshot.diagnostics],
    }


def format_report(payload: dict[str, Any], solve: Any) -> str:
    """Compact text report: islands, stitch decisions, patch types, diagnostics."""

    lines_by_island: dict[str, set[str]] = defaultdict(set)
    for skeleton in solve.skeletons:
        lines_by_island[skeleton.island_id].update(str(line) for line in skeleton.line_by_run.values())
    frame_by_island = {skeleton.island_id: skeleton.frame for skeleton in solve.skeletons}
    pins_by_island = Counter(vertex.island_id for vertex in solve.vertices if vertex.pinned)
    name = payload.get("object_name") or "selection"
    out = [f"Scaffold debug report: {name}"]
    summary = payload.get("filter") or {"on": False}
    if summary["on"]:
        classes = summary["classes"]
        out.append(
            f"user filter: up={tuple(summary['world_up'])} angle={summary['angle']:g}: "
            f"horizontal={classes.get('HORIZONTAL', 0)} vertical={classes.get('VERTICAL', 0)}"
        )
        for directive, count in summary["directives"].items():
            out.append(f"  {directive}: {count}")
        for message in summary["diagnostics"]:
            out.append(f"  filter: {message}")
    else:
        out.append("user filter: off")
    largest = max((len(island.patch_ids) for island in solve.assembly.islands), default=0)
    out.append(
        f"quilts: {len(solve.assembly.islands)} (largest {largest} patches); UV cut chains: "
        f"{len(getattr(solve, 'uv_cut_chain_ids', ()))}, stitched: {len(getattr(solve, 'stitched_chain_ids', ()))}"
    )
    out.append(f"islands: {len(solve.assembly.islands)}")
    for island in solve.assembly.islands:
        out.append(
            f"  {island.id} frame={frame_by_island.get(island.id, '?')} patches={len(island.patch_ids)} "
            f"lines={len(lines_by_island.get(island.id, ()))} pins={pins_by_island.get(island.id, 0)}"
        )
    decisions = Counter(
        ("stitched" if decision.accepted else "cut", str(decision.reason))
        for decision in solve.assembly.decisions
    )
    out.append(f"stitch decisions: {sum(decisions.values())}")
    for (verdict, reason), count in sorted(decisions.items()):
        out.append(f"  {verdict}: {reason}: {count}")
    type_counts = Counter(row["type"] for row in payload["patch_types"].values())
    out.append("patch types: " + ", ".join(
        f"{PATCH_TYPE_NAMES[type_name]}={type_counts.get(type_name, 0)}" for type_name in PATCH_TYPES
    ))
    from . import overlay_ladders

    out.extend(overlay_ladders.report_lines(payload))
    unroled = sum(1 for item in payload["layers"]["Scaffold_Chains"] if item["role"] not in ROLE_COLORS)
    out.append(f"chain strokes without an axis role: {unroled} of {len(payload['layers']['Scaffold_Chains'])}")
    undrawn = [
        island.id for island in solve.assembly.islands if frame_by_island.get(island.id) not in ISLAND_LAYERS
    ]
    if undrawn:
        out.append(f"islands without a skeleton or with an unknown frame (not drawn): {', '.join(undrawn)}")
    out.append(f"edges with fallback side: {len(payload.get('fallback_side_edges', ()))}")
    out.append(f"solver diagnostics: {len(solve.diagnostics)}")
    return "\n".join(out)


# --------------------------------------------------------------------------- vector helpers


def _natural_key(text: str):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text)]


def _add(first, second):
    return (first[0] + second[0], first[1] + second[1], first[2] + second[2])


def _scale(vector, factor: float):
    return (vector[0] * factor, vector[1] * factor, vector[2] * factor)


def _length(vector) -> float:
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


def _normalize(vector):
    size = _length(vector)
    return (0.0, 0.0, 0.0) if size <= 0.0 else (vector[0] / size, vector[1] / size, vector[2] / size)


def _distance(first, second) -> float:
    return _length((first[0] - second[0], first[1] - second[1], first[2] - second[2]))


def _lerp(first, second, t: float):
    return tuple(first[index] + (second[index] - first[index]) * t for index in range(3))


def _mean(points):
    count = len(points)
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _arc_midpoint(polyline):
    points = [tuple(point) for point in polyline]
    if len(points) == 1:
        return points[0]
    lengths = [_distance(first, second) for first, second in zip(points, points[1:])]
    total = sum(lengths)
    if total <= 0.0:
        return points[0]
    walked = 0.0
    for index, size in enumerate(lengths):
        if walked + size >= total * 0.5:
            t = (total * 0.5 - walked) / size if size > 0.0 else 0.0
            return _lerp(points[index], points[index + 1], t)
        walked += size
    return points[-1]
