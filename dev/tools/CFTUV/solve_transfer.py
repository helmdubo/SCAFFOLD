from __future__ import annotations

from typing import Optional

from mathutils import Vector

try:
    from .analysis import build_patch_graph_derived_topology
    from .console_debug import trace_console
    from .model import (
        BoundaryLoop, FrameRole, FrameAxisKind, PatchGraph,
        ScaffoldPointKey, ScaffoldChainPlacement, ScaffoldPatchPlacement,
        ScaffoldQuiltPlacement, ScaffoldMap, PlacementSourceKind,
    )
    from .solve_records import *
    from .solve_frontier import build_root_scaffold_map
    from .solve_pin_policy import build_patch_pin_map
    from .solve_skeleton import apply_skeleton_solve_to_scaffold_map
except ImportError:
    from analysis import build_patch_graph_derived_topology
    from console_debug import trace_console
    from model import (
        BoundaryLoop, FrameRole, FrameAxisKind, PatchGraph,
        ScaffoldPointKey, ScaffoldChainPlacement, ScaffoldPatchPlacement,
        ScaffoldQuiltPlacement, ScaffoldMap, PlacementSourceKind,
    )
    from solve_records import *
    from solve_frontier import build_root_scaffold_map
    from solve_pin_policy import build_patch_pin_map
    from solve_skeleton import apply_skeleton_solve_to_scaffold_map


def _patch_scaffold_is_supported(patch_placement: Optional[ScaffoldPatchPlacement]) -> bool:
    return patch_placement is not None and not patch_placement.notes and patch_placement.closure_valid


def _format_scaffold_uv_points(points: tuple[tuple[ScaffoldPointKey, Vector], ...]) -> str:
    if not points:
        return "[]"
    return '[' + ' '.join(f'({point.x:.4f},{point.y:.4f})' for _, point in points) + ']'


def _all_patch_ids(graph: PatchGraph) -> list[int]:
    return sorted(graph.nodes.keys())



def _collect_patch_face_indices(graph: PatchGraph, patch_ids: list[int]) -> set[int]:
    face_indices = set()
    for patch_id in patch_ids:
        node = graph.nodes.get(patch_id)
        if node is None:
            continue
        face_indices.update(node.face_indices)
    return face_indices



def _select_patch_faces(bm, graph: PatchGraph, patch_ids: list[int]) -> None:
    face_indices = _collect_patch_face_indices(graph, patch_ids)
    for face in bm.faces:
        face_selected = face.index in face_indices
        if hasattr(face, 'select_set'):
            face.select_set(face_selected)
        else:
            face.select = face_selected
    if hasattr(bm, 'select_flush_mode'):
        bm.select_flush_mode()



def _select_patch_uv_loops(bm, graph: PatchGraph, uv_layer, patch_ids: list[int]) -> None:
    face_indices = _collect_patch_face_indices(graph, patch_ids)
    for face in bm.faces:
        face_selected = face.index in face_indices
        for loop in face.loops:
            uv_data = loop[uv_layer]
            uv_data.select = face_selected
            uv_data.select_edge = face_selected



def _count_selected_patch_uv_loops(bm, graph: PatchGraph, uv_layer, patch_ids: list[int]) -> int:
    face_indices = _collect_patch_face_indices(graph, patch_ids)
    count = 0
    for face in bm.faces:
        if face.index not in face_indices:
            continue
        for loop in face.loops:
            if loop[uv_layer].select:
                count += 1
    return count



def _compute_patch_uv_bbox(bm, graph: PatchGraph, uv_layer, patch_ids: list[int]) -> UvBounds:
    face_indices = _collect_patch_face_indices(graph, patch_ids)
    points = []
    for face in bm.faces:
        if face.index not in face_indices:
            continue
        for loop in face.loops:
            points.append(loop[uv_layer].uv.copy())
    if not points:
        return UvBounds(bbox_min=Vector((0.0, 0.0)), bbox_max=Vector((0.0, 0.0)))
    min_x = min(point.x for point in points)
    min_y = min(point.y for point in points)
    max_x = max(point.x for point in points)
    max_y = max(point.y for point in points)
    return UvBounds(
        bbox_min=Vector((min_x, min_y)),
        bbox_max=Vector((max_x, max_y)),
    )



def _translate_patch_uvs(bm, graph: PatchGraph, uv_layer, patch_ids: list[int], offset: Vector) -> None:
    face_indices = _collect_patch_face_indices(graph, patch_ids)
    for face in bm.faces:
        if face.index not in face_indices:
            continue
        for loop in face.loops:
            loop[uv_layer].uv += offset



def _scale_patch_uvs(
    bm,
    graph: PatchGraph,
    uv_layer,
    patch_ids: list[int],
    scale: float,
    pivot: Vector,
) -> None:
    face_indices = _collect_patch_face_indices(graph, patch_ids)
    for face in bm.faces:
        if face.index not in face_indices:
            continue
        for loop in face.loops:
            uv = loop[uv_layer].uv.copy()
            loop[uv_layer].uv = pivot + ((uv - pivot) * scale)


def _boundary_edge_uv_length(edge, patch_face_indices: set[int], uv_layer) -> float:
    for face in edge.link_faces:
        if face.index not in patch_face_indices:
            continue
        for loop in face.loops:
            if loop.edge.index != edge.index:
                continue
            return (loop[uv_layer].uv - loop.link_loop_next[uv_layer].uv).length
    return 0.0


def _measure_patch_boundary_uv_density(
    bm,
    graph: PatchGraph,
    uv_layer,
    patch_ids: list[int],
) -> float:
    total_world_length = 0.0
    total_uv_length = 0.0
    seen_edge_keys: set[tuple[int, int]] = set()

    for patch_id in patch_ids:
        node = graph.nodes.get(patch_id)
        if node is None:
            continue
        patch_face_indices = set(node.face_indices)
        for boundary_loop in node.boundary_loops:
            for chain in boundary_loop.chains:
                for edge_index in chain.edge_indices:
                    edge_key = (patch_id, edge_index)
                    if edge_index < 0 or edge_key in seen_edge_keys or edge_index >= len(bm.edges):
                        continue
                    seen_edge_keys.add(edge_key)
                    edge = bm.edges[edge_index]
                    world_length = (edge.verts[1].co - edge.verts[0].co).length
                    if world_length <= 1e-12:
                        continue
                    uv_length = _boundary_edge_uv_length(edge, patch_face_indices, uv_layer)
                    if uv_length <= 1e-12:
                        continue
                    total_world_length += world_length
                    total_uv_length += uv_length

    if total_world_length <= 1e-12:
        return 0.0
    return total_uv_length / total_world_length


def _restore_patch_uv_bounds(
    bm,
    graph: PatchGraph,
    uv_layer,
    patch_ids: list[int],
    target_bounds: UvBounds,
    final_scale: float,
) -> None:
    current_bounds = _compute_patch_uv_bbox(bm, graph, uv_layer, patch_ids)
    scale = 1.0
    measured_density = _measure_patch_boundary_uv_density(bm, graph, uv_layer, patch_ids)
    if measured_density > 1e-12 and final_scale > 1e-12:
        scale = final_scale / measured_density

    if abs(scale - 1.0) > 1e-8:
        _scale_patch_uvs(
            bm,
            graph,
            uv_layer,
            patch_ids,
            scale=scale,
            pivot=current_bounds.bbox_min.copy(),
        )
        current_bounds = _compute_patch_uv_bbox(bm, graph, uv_layer, patch_ids)

    offset = target_bounds.bbox_min - current_bounds.bbox_min
    if offset.length > 1e-8:
        _translate_patch_uvs(bm, graph, uv_layer, patch_ids, offset)


def _clear_patch_pins(bm, graph: PatchGraph, uv_layer, patch_ids: list[int]) -> None:
    face_indices = set()
    for patch_id in patch_ids:
        node = graph.nodes.get(patch_id)
        if node is None:
            continue
        face_indices.update(node.face_indices)

    for face_index in face_indices:
        face = bm.faces[face_index]
        for loop in face.loops:
            loop[uv_layer].pin_uv = False


def _pin_corner_vertices(bm, graph: PatchGraph, uv_layer, patch_ids: list[int]) -> int:
    """Пинит только corner vertices (стыки chains).
    Corners определяют прямоугольный каркас для LSCM без over-constraining
    boundary segments. Возвращает кол-во запинённых UV loops."""
    corner_vert_indices = set()
    for patch_id in patch_ids:
        node = graph.nodes.get(patch_id)
        if node is None:
            continue
        for bl in node.boundary_loops:
            for corner in bl.corners:
                if corner.vert_index >= 0:
                    corner_vert_indices.add(corner.vert_index)

    face_indices = set()
    for patch_id in patch_ids:
        node = graph.nodes.get(patch_id)
        if node is None:
            continue
        face_indices.update(node.face_indices)

    pinned = 0
    for face_index in face_indices:
        face = bm.faces[face_index]
        for loop in face.loops:
            if loop.vert.index in corner_vert_indices:
                loop[uv_layer].pin_uv = True
                pinned += 1
    return pinned



def _scaffold_key_id(point_key: ScaffoldPointKey, source_kind: PlacementSourceKind) -> ScaffoldKeyId:
    return (
        point_key.patch_id,
        point_key.loop_index,
        point_key.chain_index,
        point_key.source_point_index,
        source_kind,
    )



def _resolve_scaffold_uv_targets(
    bm,
    graph: PatchGraph,
    key: ScaffoldPointKey,
    source_kind: PlacementSourceKind,
) -> list[ScaffoldUvTarget]:
    node = graph.nodes.get(key.patch_id)
    if node is None or key.loop_index < 0 or key.loop_index >= len(node.boundary_loops):
        return []

    boundary_loop = node.boundary_loops[key.loop_index]
    loop_count = len(boundary_loop.vert_indices)
    if loop_count <= 0 or not boundary_loop.side_face_indices:
        return []

    chain = None
    if source_kind == PlacementSourceKind.CHAIN:
        if key.chain_index < 0 or key.chain_index >= len(boundary_loop.chains):
            return []
        chain = boundary_loop.chains[key.chain_index]
        chain_use = graph.get_chain_use(key.patch_id, key.loop_index, key.chain_index)
        if chain_use is None:
            return []
        resolved_source_point = boundary_loop.resolve_chain_use_source_point(chain_use, key.source_point_index)
        if resolved_source_point is None:
            return []
        loop_point_index, vert_index = resolved_source_point
        if loop_point_index >= len(boundary_loop.vert_indices) or boundary_loop.vert_indices[loop_point_index] != vert_index:
            return []
    else:
        if key.source_point_index < 0:
            return []
        loop_point_index = key.source_point_index % loop_count
        vert_index = boundary_loop.vert_indices[loop_point_index]

    targets = []
    seen: set[TransferTargetId] = set()

    def _add_target(face_index: int) -> None:
        target_id: TransferTargetId = (face_index, vert_index)
        if face_index < 0 or target_id in seen:
            return
        if bm is not None:
            if face_index >= len(bm.faces):
                return
            face = bm.faces[face_index]
            if not any(loop.vert.index == vert_index for loop in face.loops):
                return
        seen.add(target_id)
        targets.append(
            ScaffoldUvTarget(
                face_index=face_index,
                vert_index=vert_index,
                loop_point_index=loop_point_index,
            )
        )

    face_candidates = []
    for side_index in ((loop_point_index - 1) % loop_count, loop_point_index):
        if side_index < 0 or side_index >= len(boundary_loop.side_face_indices):
            continue
        face_index = boundary_loop.side_face_indices[side_index]
        if face_index < 0 or face_index in face_candidates:
            continue
        face_candidates.append(face_index)

    for face_index in face_candidates:
        _add_target(face_index)

    if bm is None:
        return targets

    if boundary_loop.vert_indices.count(vert_index) != 1:
        return targets

    for face_index in node.face_indices:
        if face_index < 0 or face_index >= len(bm.faces):
            continue
        face = bm.faces[face_index]
        for loop in face.loops:
            if loop.vert.index != vert_index:
                continue
            _add_target(face_index)
            break
    return targets
def _count_patch_scaffold_points(patch_placement: ScaffoldPatchPlacement) -> int:
    scaffold_keys: ScaffoldKeySet = set()
    for chain_placement in patch_placement.chain_placements:
        for point_key, _ in chain_placement.points:
            scaffold_keys.add(_scaffold_key_id(point_key, chain_placement.source_kind))
    return len(scaffold_keys)

def _build_patch_transfer_targets(
    bm,
    graph: PatchGraph,
    patch_placement: ScaffoldPatchPlacement,
    uv_offset: Vector,
    band_spine_data: Optional[dict] = None,
) -> PatchTransferTargetsState:
    scaffold_point_count = _count_patch_scaffold_points(patch_placement)
    base_kwargs = {
        'scaffold_points': scaffold_point_count,
        'closure_error': patch_placement.closure_error,
        'max_chain_gap': patch_placement.max_chain_gap,
        'chain_gap_count': len(patch_placement.gap_reports),
    }

    if patch_placement.notes:
        return PatchTransferTargetsState(status=PatchTransferStatus.UNSUPPORTED, **base_kwargs)
    if not patch_placement.closure_valid:
        return PatchTransferTargetsState(
            status=PatchTransferStatus.INVALID_SCAFFOLD,
            invalid_scaffold_patches=1,
            **base_kwargs,
        )

    node = graph.nodes.get(patch_placement.patch_id)
    if node is None:
        return PatchTransferTargetsState(
            status=PatchTransferStatus.MISSING_PATCH,
            scaffold_points=0,
            closure_error=patch_placement.closure_error,
            max_chain_gap=patch_placement.max_chain_gap,
            chain_gap_count=len(patch_placement.gap_reports),
        )

    conformal_patch = all(
        cp.frame_role == FrameRole.FREE for cp in patch_placement.chain_placements
    )
    target_samples: TargetSampleMap = {}
    pin_target_ids: PinnedTargetIdSet = set()
    scaffold_keys: ScaffoldKeySet = set()
    unresolved_keys: ScaffoldKeySet = set()
    pin_map = build_patch_pin_map(graph, patch_placement, band_spine_data=band_spine_data)

    for chain_placement in patch_placement.chain_placements:
        point_count = len(chain_placement.points)
        for point_index, (point_key, target_uv) in enumerate(chain_placement.points):
            key_id = _scaffold_key_id(point_key, chain_placement.source_kind)
            scaffold_keys.add(key_id)
            targets = _resolve_scaffold_uv_targets(bm, graph, point_key, chain_placement.source_kind)
            if not targets:
                unresolved_keys.add(key_id)
                continue

            shifted_uv = target_uv + uv_offset
            should_pin = pin_map.is_point_pinned(chain_placement.chain_index, point_index, point_count)
            for target in targets:
                target_id: TransferTargetId = (target.face_index, target.vert_index)
                target_samples.setdefault(target_id, []).append(shifted_uv.copy())
                if should_pin:
                    pin_target_ids.add(target_id)

    conflicting_uv_targets = 0
    for samples in target_samples.values():
        base_sample = samples[0]
        if any((sample - base_sample).length > 1e-5 for sample in samples[1:]):
            conflicting_uv_targets += 1

    return PatchTransferTargetsState(
        status=PatchTransferStatus.OK,
        scaffold_points=scaffold_point_count,
        resolved_scaffold_points=len(scaffold_keys) - len(unresolved_keys),
        uv_targets_resolved=len(target_samples),
        unresolved_scaffold_points=len(unresolved_keys),
        conflicting_uv_targets=conflicting_uv_targets,
        pinned_uv_targets=len(pin_target_ids),
        unpinned_uv_targets=max(0, len(target_samples) - len(pin_target_ids)),
        closure_error=patch_placement.closure_error,
        max_chain_gap=patch_placement.max_chain_gap,
        chain_gap_count=len(patch_placement.gap_reports),
        target_samples=target_samples,
        pin_target_ids=pin_target_ids,
        scaffold_keys=scaffold_keys,
        unresolved_keys=unresolved_keys,
        conformal_patch=conformal_patch,
        pin_map=pin_map,
    )



def _apply_patch_scaffold_to_uv(
    bm,
    graph: PatchGraph,
    uv_layer,
    patch_placement: ScaffoldPatchPlacement,
    uv_offset: Vector,
    band_spine_data: Optional[dict] = None,
) -> PatchApplyStats:
    transfer_state = _build_patch_transfer_targets(
        bm,
        graph,
        patch_placement,
        uv_offset,
        band_spine_data=band_spine_data,
    )
    if transfer_state.status != PatchTransferStatus.OK:
        return PatchApplyStats(
            status=transfer_state.status,
            scaffold_points=int(transfer_state.scaffold_points),
            resolved_scaffold_points=int(transfer_state.resolved_scaffold_points),
            uv_targets_resolved=int(transfer_state.uv_targets_resolved),
            unresolved_scaffold_points=int(transfer_state.unresolved_scaffold_points),
            missing_uv_targets=int(transfer_state.missing_uv_targets),
            conflicting_uv_targets=int(transfer_state.conflicting_uv_targets),
            pinned_uv_loops=0,
            invalid_scaffold_patches=int(transfer_state.invalid_scaffold_patches),
            closure_error=float(transfer_state.closure_error),
            max_chain_gap=float(transfer_state.max_chain_gap),
            chain_gap_count=int(transfer_state.chain_gap_count),
        )

    target_samples: TargetSampleMap = transfer_state.target_samples
    pin_target_ids: PinnedTargetIdSet = transfer_state.pin_target_ids
    missing_uv_targets = 0
    pinned_uv_loops = 0
    for target_id, samples in target_samples.items():
        face_index, vert_index = target_id
        target_uv = sum(samples, Vector((0.0, 0.0))) / float(len(samples))
        if face_index < 0 or face_index >= len(bm.faces):
            missing_uv_targets += 1
            continue

        face = bm.faces[face_index]
        applied = False
        for loop in face.loops:
            if loop.vert.index != vert_index:
                continue
            loop[uv_layer].uv = target_uv.copy()
            loop[uv_layer].pin_uv = target_id in pin_target_ids
            if loop[uv_layer].pin_uv:
                pinned_uv_loops += 1
            applied = True
            break
        if not applied:
            missing_uv_targets += 1

    return PatchApplyStats(
        status=PatchTransferStatus.OK,
        scaffold_points=int(transfer_state.scaffold_points),
        resolved_scaffold_points=int(transfer_state.resolved_scaffold_points),
        uv_targets_resolved=int(transfer_state.uv_targets_resolved),
        unresolved_scaffold_points=int(transfer_state.unresolved_scaffold_points),
        missing_uv_targets=missing_uv_targets,
        conflicting_uv_targets=int(transfer_state.conflicting_uv_targets),
        pinned_uv_loops=pinned_uv_loops,
        invalid_scaffold_patches=int(transfer_state.invalid_scaffold_patches),
        closure_error=float(transfer_state.closure_error),
        max_chain_gap=float(transfer_state.max_chain_gap),
        chain_gap_count=int(transfer_state.chain_gap_count),
    )

def _compute_quilt_bbox(quilt_scaffold: ScaffoldQuiltPlacement) -> UvBounds:
    placements = [patch for patch in quilt_scaffold.patches.values() if _patch_scaffold_is_supported(patch)]
    if not placements:
        return UvBounds(bbox_min=Vector((0.0, 0.0)), bbox_max=Vector((0.0, 0.0)))
    min_x = min(patch.bbox_min.x for patch in placements)
    min_y = min(patch.bbox_min.y for patch in placements)
    max_x = max(patch.bbox_max.x for patch in placements)
    max_y = max(patch.bbox_max.y for patch in placements)
    return UvBounds(
        bbox_min=Vector((min_x, min_y)),
        bbox_max=Vector((max_x, max_y)),
    )


def _compute_scaffold_patch_group_bounds(
    quilt_scaffold: ScaffoldQuiltPlacement,
    patch_ids: list[int],
    uv_offset: Vector,
) -> UvBounds:
    placements = [
        quilt_scaffold.patches.get(patch_id)
        for patch_id in patch_ids
        if _patch_scaffold_is_supported(quilt_scaffold.patches.get(patch_id))
    ]
    placements = [patch for patch in placements if patch is not None]
    if not placements:
        return UvBounds(bbox_min=Vector((0.0, 0.0)), bbox_max=Vector((0.0, 0.0)))
    min_x = min(patch.bbox_min.x for patch in placements)
    min_y = min(patch.bbox_min.y for patch in placements)
    max_x = max(patch.bbox_max.x for patch in placements)
    max_y = max(patch.bbox_max.y for patch in placements)
    return UvBounds(
        bbox_min=Vector((min_x, min_y)) + uv_offset,
        bbox_max=Vector((max_x, max_y)) + uv_offset,
    )


def _ordered_quilt_patch_ids(quilt_scaffold: ScaffoldQuiltPlacement, quilt_plan: Optional[QuiltPlan]) -> list[int]:
    ordered_patch_ids = []
    seen = set()

    if quilt_plan is not None:
        for step in quilt_plan.steps:
            patch_placement = quilt_scaffold.patches.get(step.patch_id)
            if patch_placement is None or patch_placement.notes:
                continue
            ordered_patch_ids.append(step.patch_id)
            seen.add(step.patch_id)

    root_patch_placement = quilt_scaffold.patches.get(quilt_scaffold.root_patch_id)
    if root_patch_placement is not None and not root_patch_placement.notes and quilt_scaffold.root_patch_id not in seen:
        ordered_patch_ids.append(quilt_scaffold.root_patch_id)
        seen.add(quilt_scaffold.root_patch_id)

    for patch_id, patch_placement in quilt_scaffold.patches.items():
        if patch_id in seen or patch_placement.notes:
            continue
        ordered_patch_ids.append(patch_id)
        seen.add(patch_id)

    return ordered_patch_ids


def _print_phase1_preview_patch_report(
    quilt_index: int,
    patch_id: int,
    stats: PatchApplyStats,
) -> None:
    status = stats.status.value
    status_suffix = '' if status == 'ok' else f" status={status}"
    closure_suffix = ''
    if status != 'ok' or int(stats.chain_gap_count) > 0:
        closure_suffix = (
            f" closure={float(stats.closure_error):.6f}"
            f" max_gap={float(stats.max_chain_gap):.6f}"
            f" gaps={int(stats.chain_gap_count)}"
        )
    trace_console(
        f"[CFTUV][Phase1] Quilt {quilt_index} Patch {patch_id}: "
        f"scaffold={stats.scaffold_points} resolved={stats.resolved_scaffold_points} "
        f"uv_targets={stats.uv_targets_resolved} unresolved={stats.unresolved_scaffold_points} "
        f"missing={stats.missing_uv_targets} conflicts={stats.conflicting_uv_targets} "
        f"pinned={stats.pinned_uv_loops}{status_suffix}{closure_suffix}"
    )


def _print_phase1_preview_quilt_report(quilt_index: int, patch_ids: list[int], stats: dict[str, int]) -> None:
    trace_console(
        f"[CFTUV][Phase1] Quilt {quilt_index}: patches={patch_ids} "
        f"scaffold={stats.get('scaffold_points', 0)} resolved={stats.get('resolved_scaffold_points', 0)} "
        f"uv_targets={stats.get('uv_targets_resolved', 0)} unresolved={stats.get('unresolved_scaffold_points', 0)} "
        f"missing={stats.get('missing_uv_targets', 0)} conflicts={stats.get('conflicting_uv_targets', 0)} "
        f"pinned={stats.get('pinned_uv_loops', 0)} invalid={stats.get('invalid_scaffold_patches', 0)}"
    )


def _collect_phase1_unsupported_patch_ids(scaffold_map: ScaffoldMap) -> list[int]:
    unsupported_patch_ids = set()
    for quilt_scaffold in scaffold_map.quilts:
        for patch_id, patch_placement in quilt_scaffold.patches.items():
            if not _patch_scaffold_is_supported(patch_placement):
                unsupported_patch_ids.add(patch_id)
    return sorted(unsupported_patch_ids)



def _execute_phase1_preview_impl(
    context,
    obj,
    bm,
    patch_graph: PatchGraph,
    settings,
    solve_plan: Optional[SolvePlan] = None,
    run_conformal: bool = True,
    keep_pins: bool = False,
) -> dict[str, object]:
    import bmesh
    import bpy

    patch_ids = _all_patch_ids(patch_graph)
    if not patch_ids:
        return {
            'patches': 0,
            'supported_roots': 0,
            'scaffold_points': 0,
            'resolved_scaffold_points': 0,
            'uv_targets_resolved': 0,
            'unresolved_scaffold_points': 0,
            'missing_uv_targets': 0,
            'conflicting_uv_targets': 0,
            'pinned_uv_loops': 0,
            'quilts': 0,
            'attached_children': 0,
            'invalid_scaffold_patches': 0,
            'unsupported_patch_count': 0,
            'unsupported_patch_ids': [],
            'conformal_applied': 0,
            'frame_group_count': 0,
            'frame_row_max_scatter': 0.0,
            'frame_column_max_scatter': 0.0,
        }

    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.verify()
    _clear_patch_pins(bm, patch_graph, uv_layer, patch_ids)

    straighten_enabled = getattr(settings, 'straighten_strips', False)
    try:
        from .analysis import build_straighten_structural_support
    except ImportError:
        from analysis import build_straighten_structural_support
    # Shape classification always runs; straighten-specific data gated by toggle.
    derived_topology = build_patch_graph_derived_topology(patch_graph)
    inherited_role_map, patch_structural_summaries, patch_shape_classes, straighten_chain_refs, band_spine_data = build_straighten_structural_support(patch_graph)
    scaffold_map = build_root_scaffold_map(
        patch_graph, solve_plan, settings.final_scale,
        straighten_enabled=straighten_enabled,
        inherited_role_map=inherited_role_map if straighten_enabled else None,
        patch_structural_summaries=patch_structural_summaries if straighten_enabled else None,
        patch_shape_classes=patch_shape_classes,
        straighten_chain_refs=straighten_chain_refs if straighten_enabled else None,
        band_spine_data=band_spine_data if straighten_enabled else None,
    )
    scaffold_map, _skeleton_reports = apply_skeleton_solve_to_scaffold_map(
        patch_graph,
        derived_topology,
        scaffold_map,
        solve_plan=solve_plan,
        final_scale=settings.final_scale,
    )
    unsupported_patch_ids = _collect_phase1_unsupported_patch_ids(scaffold_map)
    if unsupported_patch_ids:
        trace_console(f"[CFTUV][Phase1] Unsupported patches: {unsupported_patch_ids}")
    quilt_plan_by_index = {quilt.quilt_index: quilt for quilt in solve_plan.quilts} if solve_plan is not None else {}

    supported_roots = 0
    scaffold_points = 0
    resolved_scaffold_points = 0
    uv_targets_resolved = 0
    unresolved_scaffold_points = 0
    missing_uv_targets = 0
    conflicting_uv_targets = 0
    pinned_uv_loops = 0
    attached_children = 0
    invalid_scaffold_patches = 0
    global_supported_patch_ids: set[int] = set()
    conformal_applied = 0
    all_conformal_patch_ids: list[int] = []
    unpinned_conformal_quilt_groups: dict[int, tuple[list[int], UvBounds]] = {}
    closure_seam_count = 0
    closure_seam_max_mismatch = 0.0
    closure_seam_max_phase = 0.0
    frame_group_count = 0
    frame_row_max_scatter = 0.0
    frame_column_max_scatter = 0.0

    for quilt_scaffold in scaffold_map.quilts:
        quilt_plan = quilt_plan_by_index.get(quilt_scaffold.quilt_index)
        quilt_patch_ids = _ordered_quilt_patch_ids(quilt_scaffold, quilt_plan)
        if not quilt_patch_ids:
            continue
        closure_reports = getattr(quilt_scaffold, 'closure_seam_reports', ())
        closure_seam_count += len(closure_reports)
        closure_seam_max_mismatch = max(
            closure_seam_max_mismatch,
            max((report.span_mismatch for report in closure_reports), default=0.0),
        )
        closure_seam_max_phase = max(
            closure_seam_max_phase,
            max((report.axis_phase_offset_max for report in closure_reports), default=0.0),
        )
        frame_reports = getattr(quilt_scaffold, 'frame_alignment_reports', ())
        frame_group_count += len(frame_reports)
        frame_row_max_scatter = max(
            frame_row_max_scatter,
            max((report.scatter_max for report in frame_reports if report.axis_kind == FrameAxisKind.ROW), default=0.0),
        )
        frame_column_max_scatter = max(
            frame_column_max_scatter,
            max((report.scatter_max for report in frame_reports if report.axis_kind == FrameAxisKind.COLUMN), default=0.0),
        )
        quilt_apply_patch_ids = [
            patch_id
            for patch_id in quilt_patch_ids
            if _patch_scaffold_is_supported(quilt_scaffold.patches.get(patch_id))
        ]

        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.verify()
        _select_patch_faces(bm, patch_graph, quilt_apply_patch_ids)
        _clear_patch_pins(bm, patch_graph, uv_layer, quilt_apply_patch_ids)

        quilt_bounds = _compute_quilt_bbox(quilt_scaffold)
        # Каждый quilt стартует в (0,0) UV — без горизонтального стекания
        uv_offset = Vector((-quilt_bounds.bbox_min.x, -quilt_bounds.bbox_min.y))
        quilt_unpinned_conformal_patch_ids: list[int] = []
        quilt_stats = {
            'scaffold_points': 0,
            'resolved_scaffold_points': 0,
            'uv_targets_resolved': 0,
            'unresolved_scaffold_points': 0,
            'missing_uv_targets': 0,
            'conflicting_uv_targets': 0,
            'pinned_uv_loops': 0,
            'invalid_scaffold_patches': 0,
        }

        for patch_id in quilt_patch_ids:
            patch_placement = quilt_scaffold.patches[patch_id]
            patch_stats = _apply_patch_scaffold_to_uv(
                bm,
                patch_graph,
                uv_layer,
                patch_placement,
                uv_offset,
                band_spine_data=band_spine_data if straighten_enabled else None,
            )
            validate_scaffold_uv_transfer(bm, patch_graph, uv_layer, patch_placement, uv_offset)
            _print_phase1_preview_patch_report(quilt_scaffold.quilt_index, patch_id, patch_stats)

            patch_stats.accumulate_into(quilt_stats)

            if int(patch_stats.resolved_scaffold_points) > 0:
                all_conformal_patch_ids.append(patch_id)
                if int(patch_stats.pinned_uv_loops) <= 0:
                    quilt_unpinned_conformal_patch_ids.append(patch_id)

            if int(patch_stats.pinned_uv_loops) <= 0:
                continue
            if patch_id == quilt_scaffold.root_patch_id:
                supported_roots += 1
            else:
                attached_children += 1

        _print_phase1_preview_quilt_report(quilt_scaffold.quilt_index, quilt_patch_ids, quilt_stats)

        scaffold_points += quilt_stats['scaffold_points']
        resolved_scaffold_points += quilt_stats['resolved_scaffold_points']
        uv_targets_resolved += quilt_stats['uv_targets_resolved']
        unresolved_scaffold_points += quilt_stats['unresolved_scaffold_points']
        missing_uv_targets += quilt_stats['missing_uv_targets']
        conflicting_uv_targets += quilt_stats['conflicting_uv_targets']
        pinned_uv_loops += quilt_stats['pinned_uv_loops']
        invalid_scaffold_patches += quilt_stats['invalid_scaffold_patches']
        global_supported_patch_ids.update(quilt_apply_patch_ids)
        if quilt_unpinned_conformal_patch_ids:
            unpinned_conformal_quilt_groups[quilt_scaffold.quilt_index] = (
                list(quilt_unpinned_conformal_patch_ids),
                _compute_scaffold_patch_group_bounds(
                    quilt_scaffold,
                    quilt_unpinned_conformal_patch_ids,
                    uv_offset,
                ),
            )


    # Финальный Conformal: один вызов ПОСЛЕ всех quilts.
    # bmesh.update_edit_mesh вызывается один раз, потом bpy.ops.uv.unwrap
    # без промежуточных bmesh операций — исключает перезапись результатов.
    if run_conformal and all_conformal_patch_ids:
        bmesh.update_edit_mesh(obj.data)
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.verify()
        _select_patch_faces(bm, patch_graph, all_conformal_patch_ids)
        _select_patch_uv_loops(bm, patch_graph, uv_layer, all_conformal_patch_ids)
        sel_faces = sum(1 for f in bm.faces if f.select)
        pinned_count = sum(
            1 for f in bm.faces if f.select
            for lp in f.loops if lp[uv_layer].pin_uv
        )
        unpinned_count = sum(
            1 for f in bm.faces if f.select
            for lp in f.loops if not lp[uv_layer].pin_uv
        )
        # Снимок UV до Conformal: vert_index → uv для первых unpinned loops
        _pre_uv = {}
        for f in bm.faces:
            if f.select:
                for lp in f.loops:
                    if not lp[uv_layer].pin_uv:
                        key = (f.index, lp.vert.index)
                        _pre_uv[key] = lp[uv_layer].uv.copy()
        bmesh.update_edit_mesh(obj.data)
        trace_console(
            f"[CFTUV][Phase1] Final Conformal: "
            f"patches={all_conformal_patch_ids} faces={sel_faces} "
            f"pinned={pinned_count} unpinned={unpinned_count}"
        )
        trace_console(f"[CFTUV][Phase1] obj.mode={obj.mode} active={bpy.context.active_object == obj}")
        bpy.ops.uv.unwrap(method='CONFORMAL', fill_holes=False, margin=0.0)
        conformal_applied += 1
        # Проверка: сколько UV изменилось
        bm2 = bmesh.from_edit_mesh(obj.data)
        bm2.faces.ensure_lookup_table()
        bm2.verts.ensure_lookup_table()
        bm2.edges.ensure_lookup_table()
        uv2 = bm2.loops.layers.uv.verify()
        for quilt_index, (group_patch_ids, target_bounds) in unpinned_conformal_quilt_groups.items():
            if len(group_patch_ids) > 1:
                trace_console(
                    f"[CFTUV][Phase1] Conformal restore Quilt {quilt_index}: "
                    f"patches={group_patch_ids}"
                )
            _restore_patch_uv_bounds(
                bm2,
                patch_graph,
                uv2,
                group_patch_ids,
                target_bounds,
                settings.final_scale,
            )
        _changed = 0
        _checked = 0
        for f in bm2.faces:
            if f.select:
                for lp in f.loops:
                    if not lp[uv2].pin_uv:
                        key = (f.index, lp.vert.index)
                        pre = _pre_uv.get(key)
                        if pre is not None:
                            _checked += 1
                            if (lp[uv2].uv - pre).length > 1e-6:
                                _changed += 1
        bmesh.update_edit_mesh(obj.data)
        trace_console(f"[CFTUV][Phase1] Conformal result: checked={_checked} changed={_changed}/{len(_pre_uv)}")

    if run_conformal and unsupported_patch_ids:
        for patch_id in unsupported_patch_ids:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.verify()
            _select_patch_faces(bm, patch_graph, [patch_id])
            _select_patch_uv_loops(bm, patch_graph, uv_layer, [patch_id])
            _clear_patch_pins(bm, patch_graph, uv_layer, [patch_id])
            selected_face_count = len(_collect_patch_face_indices(patch_graph, [patch_id]))
            selected_uv_count = _count_selected_patch_uv_loops(bm, patch_graph, uv_layer, [patch_id])
            bmesh.update_edit_mesh(obj.data)
            trace_console(
                f"[CFTUV][Phase1] Unsupported Patch {patch_id} Fallback Conformal: "
                f"faces={selected_face_count} uv_loops={selected_uv_count}"
            )
            target_bounds = _compute_patch_uv_bbox(bm, patch_graph, uv_layer, [patch_id])
            bpy.ops.uv.unwrap(method='CONFORMAL', fill_holes=False, margin=0.0)
            conformal_applied += 1

            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.verify()
            _restore_patch_uv_bounds(
                bm,
                patch_graph,
                uv_layer,
                [patch_id],
                target_bounds,
                settings.final_scale,
            )
            bmesh.update_edit_mesh(obj.data)
    if not run_conformal:
        trace_console(f"[CFTUV][Phase1] Transfer Only: quilts={len(scaffold_map.quilts)} patches={sorted(global_supported_patch_ids)}")

    if not keep_pins:
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.verify()
        _clear_patch_pins(bm, patch_graph, uv_layer, patch_ids)
        bmesh.update_edit_mesh(obj.data)

    return {
        'patches': len(patch_ids),
        'supported_roots': supported_roots,
        'scaffold_points': scaffold_points,
        'resolved_scaffold_points': resolved_scaffold_points,
        'uv_targets_resolved': uv_targets_resolved,
        'unresolved_scaffold_points': unresolved_scaffold_points,
        'missing_uv_targets': missing_uv_targets,
        'conflicting_uv_targets': conflicting_uv_targets,
        'pinned_uv_loops': pinned_uv_loops,
        'quilts': len(scaffold_map.quilts),
        'attached_children': attached_children,
        'invalid_scaffold_patches': invalid_scaffold_patches,
        'unsupported_patch_count': len(unsupported_patch_ids),
        'unsupported_patch_ids': unsupported_patch_ids,
        'conformal_applied': conformal_applied,
        'closure_seam_count': closure_seam_count,
        'closure_seam_max_mismatch': closure_seam_max_mismatch,
        'closure_seam_max_phase': closure_seam_max_phase,
        'frame_group_count': frame_group_count,
        'frame_row_max_scatter': frame_row_max_scatter,
        'frame_column_max_scatter': frame_column_max_scatter,
    }

# ============================================================
# PHASE 2 PATCH — Validation Layer for solve.py
#
# ИНСТРУМЕНТАРИЙ
#
# Шаг 1: Ожидаемый UV
#         Найти vert_index в BMFace loops,
#         Установить UV
#         до конца chain.
#         Между ожидаемым UV и фактическим UV loop.
#
# Шаг 2: Вызвать
#             patch_stats = _apply_patch_scaffold_to_uv(bm, patch_graph, uv_layer, patch_placement, uv_offset)
#         Использовать
#             validate_scaffold_uv_transfer(bm, patch_graph, uv_layer, patch_placement, uv_offset)
#
# Готово.
# ============================================================


def validate_scaffold_uv_transfer(bm, graph, uv_layer, patch_placement, uv_offset, epsilon=1e-4):
    """Phase 2: Diagnostic — проверка scaffold→UV transfer.

    Вызывается после transfer,
    проверяет совпадение UV с ожидаемыми значениями scaffold.

    Каждый scaffold point проверяется на соответствие UV loop.
    Несовпадения собираются в mismatches.
    Также проверяется SEAM_SELF collapsed UV.
    """
    if patch_placement.notes or not patch_placement.closure_valid:
        return

    mismatches = []
    total_points = 0
    verified_ok = 0

    # --- Проверка: scaffold points записаны в правильные UV loops ---
    for chain_placement in patch_placement.chain_placements:
        for point_key, intended_uv in chain_placement.points:
            total_points += 1
            targets = _resolve_scaffold_uv_targets(bm, graph, point_key, chain_placement.source_kind)
            shifted_uv = intended_uv + uv_offset

            if not targets:
                mismatches.append(
                    f"  UNRESOLVED patch:{point_key.patch_id} "
                    f"L{point_key.loop_index}C{point_key.chain_index} "
                    f"pt:{point_key.source_point_index}"
                )
                continue

            point_ok = True
            for target in targets:
                if target.face_index < 0 or target.face_index >= len(bm.faces):
                    mismatches.append(
                        f"  MISSING_FACE patch:{point_key.patch_id} "
                        f"face:{target.face_index}"
                    )
                    point_ok = False
                    continue

                face = bm.faces[target.face_index]
                found_loop = False
                for loop in face.loops:
                    if loop.vert.index != target.vert_index:
                        continue
                    found_loop = True
                    actual_uv = loop[uv_layer].uv.copy()
                    dist = (actual_uv - shifted_uv).length
                    if dist > epsilon:
                        mismatches.append(
                            f"  MISMATCH patch:{point_key.patch_id} "
                            f"L{point_key.loop_index}C{point_key.chain_index} "
                            f"pt:{point_key.source_point_index} "
                            f"vert:{target.vert_index} face:{target.face_index} "
                            f"expected:({shifted_uv.x:.4f},{shifted_uv.y:.4f}) "
                            f"actual:({actual_uv.x:.4f},{actual_uv.y:.4f}) "
                            f"dist:{dist:.6f}"
                        )
                        point_ok = False
                    break

                if not found_loop:
                    mismatches.append(
                        f"  VERT_NOT_IN_FACE patch:{point_key.patch_id} "
                        f"vert:{target.vert_index} face:{target.face_index}"
                    )
                    point_ok = False

            if point_ok:
                verified_ok += 1

    # --- Проверка: SEAM_SELF вершины имеют разные UV на разных сторонах ---
    node = graph.nodes.get(patch_placement.patch_id)
    seam_self_collapsed = 0
    if node is not None and patch_placement.loop_index >= 0:
        if patch_placement.loop_index < len(node.boundary_loops):
            boundary_loop = node.boundary_loops[patch_placement.loop_index]
            for chain in boundary_loop.chains:
                if chain.neighbor_patch_id != -2:  # NB_SEAM_SELF
                    continue
                # Проверяем что UV не схлопнулись на SEAM_SELF
                for vert_index in chain.vert_indices:
                    uv_values = []
                    for face_index in node.face_indices:
                        if face_index >= len(bm.faces):
                            continue
                        face = bm.faces[face_index]
                        for loop in face.loops:
                            if loop.vert.index == vert_index:
                                uv_values.append(loop[uv_layer].uv.copy())
                    # SEAM_SELF vert должен иметь >= 2 разных UV
                    if len(uv_values) >= 2:
                        all_same = all(
                            (uv - uv_values[0]).length < epsilon
                            for uv in uv_values[1:]
                        )
                        if all_same:
                            seam_self_collapsed += 1

    # --- Console output ---
    if mismatches or seam_self_collapsed > 0:
        trace_console(
            f"[CFTUV][Validate] Patch {patch_placement.patch_id}: "
            f"{len(mismatches)} mismatches, "
            f"{seam_self_collapsed} collapsed SEAM_SELF verts "
            f"({verified_ok}/{total_points} OK)"
        )
        for m in mismatches:
            trace_console(m)
    else:
        trace_console(
            f"[CFTUV][Validate] Patch {patch_placement.patch_id}: "
            f"OK ({verified_ok}/{total_points} points verified)"
        )


def execute_phase1_preview(
    context,
    obj,
    bm,
    patch_graph: PatchGraph,
    settings,
    solve_plan: Optional[SolvePlan] = None,
    keep_pins: bool = False,
) -> dict[str, object]:
    return _execute_phase1_preview_impl(
        context,
        obj,
        bm,
        patch_graph,
        settings,
        solve_plan,
        run_conformal=True,
        keep_pins=keep_pins,
    )



def execute_phase1_transfer_only(context, obj, bm, patch_graph: PatchGraph, settings, solve_plan: Optional[SolvePlan] = None) -> dict[str, object]:
    return _execute_phase1_preview_impl(
        context,
        obj,
        bm,
        patch_graph,
        settings,
        solve_plan,
        run_conformal=False,
        keep_pins=True,
    )


