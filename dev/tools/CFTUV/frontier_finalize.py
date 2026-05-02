from __future__ import annotations

from typing import Optional

from mathutils import Vector

try:
    from .console_debug import trace_console
    from .model import (
        ChainGapReport,
        ChainRef,
        PatchEdgeKey,
        PatchGraph,
        PatchPlacementStatus,
        ScaffoldChainPlacement,
        ScaffoldPatchPlacement,
        ScaffoldQuiltPlacement,
    )
    from .solve_diagnostics import (
        _collect_quilt_closure_seam_reports,
        _collect_quilt_frame_alignment_reports,
        _print_quilt_closure_seam_reports,
        _print_quilt_frame_alignment_reports,
    )
    from .solve_pin_policy import _compute_scaffold_connected_chains
    from .solve_records import (
        FinalizedQuiltScaffold,
        PatchChainGapDiagnostics,
        QuiltPlan,
        SolveView,
    )
except ImportError:
    from console_debug import trace_console
    from model import (
        ChainGapReport,
        ChainRef,
        PatchEdgeKey,
        PatchGraph,
        PatchPlacementStatus,
        ScaffoldChainPlacement,
        ScaffoldPatchPlacement,
        ScaffoldQuiltPlacement,
    )
    from solve_diagnostics import (
        _collect_quilt_closure_seam_reports,
        _collect_quilt_frame_alignment_reports,
        _print_quilt_closure_seam_reports,
        _print_quilt_frame_alignment_reports,
    )
    from solve_pin_policy import _compute_scaffold_connected_chains
    from solve_records import (
        FinalizedQuiltScaffold,
        PatchChainGapDiagnostics,
        QuiltPlan,
        SolveView,
    )


def _compute_patch_chain_gap_reports(
    patch_placements: list[ScaffoldChainPlacement],
    total_chains: int,
) -> PatchChainGapDiagnostics:
    """Вычисляет gap между соседними placed chains в loop order."""
    if total_chains < 2 or not patch_placements:
        return PatchChainGapDiagnostics()

    placements_by_chain_index = {
        placement.chain_index: placement
        for placement in patch_placements
    }

    reports: list[ChainGapReport] = []
    max_gap = 0.0
    for chain_index in sorted(placements_by_chain_index):
        next_chain_index = (chain_index + 1) % total_chains
        current_placement = placements_by_chain_index[chain_index]
        next_placement = placements_by_chain_index.get(next_chain_index)
        if next_placement is None:
            continue
        if not current_placement.points or not next_placement.points:
            continue

        current_end = current_placement.points[-1][1]
        next_start = next_placement.points[0][1]
        gap = (current_end - next_start).length
        reports.append(ChainGapReport(
            chain_index=chain_index,
            next_chain_index=next_chain_index,
            gap=gap,
        ))
        if gap > max_gap:
            max_gap = gap

    return PatchChainGapDiagnostics(
        gap_reports=tuple(reports),
        max_chain_gap=max_gap,
    )


def _cf_build_envelopes(
    solve_view: SolveView,
    runtime_policy,
    build_order: Optional[list[ChainRef]] = None,
):
    """Группирует размещённые chains в ScaffoldPatchPlacement per patch."""
    graph = runtime_policy.graph
    quilt_patch_ids = runtime_policy.quilt_patch_ids
    placed_chains_map = runtime_policy.placed_chains_map
    placed_chain_refs = runtime_policy.placed_chain_refs
    chain_dependency_patches = runtime_policy.chain_dependency_patches
    patches = {}

    for patch_id in quilt_patch_ids:
        node = graph.nodes.get(patch_id)
        if node is None:
            continue

        patch_placements = [
            placement
            for ref, placement in placed_chains_map.items()
            if ref[0] == patch_id
        ]
        patch_placements.sort(key=lambda placement: placement.chain_index)

        if not patch_placements:
            patches[patch_id] = ScaffoldPatchPlacement(
                patch_id=patch_id,
                loop_index=-1,
                root_chain_index=-1,
                notes=('no_placed_chains',),
                status=PatchPlacementStatus.EMPTY,
            )
            continue

        outer_loop_index = solve_view.primary_loop_index(patch_id)

        if outer_loop_index < 0:
            patches[patch_id] = ScaffoldPatchPlacement(
                patch_id=patch_id,
                loop_index=-1,
                root_chain_index=-1,
                notes=('no_outer_loop',),
                status=PatchPlacementStatus.UNSUPPORTED,
            )
            continue

        boundary_loop = node.boundary_loops[outer_loop_index]

        corner_positions = {}
        for corner_idx, corner in enumerate(boundary_loop.corners):
            prev_ref = (patch_id, outer_loop_index, corner.prev_chain_index)
            next_ref = (patch_id, outer_loop_index, corner.next_chain_index)
            if prev_ref in placed_chains_map:
                pts = placed_chains_map[prev_ref].points
                if pts:
                    corner_positions[corner_idx] = pts[-1][1].copy()
            elif next_ref in placed_chains_map:
                pts = placed_chains_map[next_ref].points
                if pts:
                    corner_positions[corner_idx] = pts[0][1].copy()

        all_pts = [pt for cp in patch_placements for _, pt in cp.points]
        if all_pts:
            bbox_min = Vector((min(p.x for p in all_pts), min(p.y for p in all_pts)))
            bbox_max = Vector((max(p.x for p in all_pts), max(p.y for p in all_pts)))
        else:
            bbox_min = Vector((0.0, 0.0))
            bbox_max = Vector((0.0, 0.0))

        total_chains = len(boundary_loop.chains)
        placed_count = sum(
            1 for ci in range(total_chains)
            if (patch_id, outer_loop_index, ci) in placed_chain_refs
        )

        if placed_count >= total_chains:
            status = PatchPlacementStatus.COMPLETE
        elif placed_count > 0:
            status = PatchPlacementStatus.PARTIAL
        else:
            status = PatchPlacementStatus.EMPTY

        unplaced = tuple(
            ci for ci in range(total_chains)
            if (patch_id, outer_loop_index, ci) not in placed_chain_refs
        )

        dep_set = set()
        for cp in patch_placements:
            cp_ref = (cp.patch_id, cp.loop_index, cp.chain_index)
            dep_set.update(chain_dependency_patches.get(cp_ref, ()))

        closure_error = 0.0
        closure_valid = True
        if status == PatchPlacementStatus.COMPLETE and total_chains >= 2:
            if patch_placements[-1].points and patch_placements[0].points:
                last_end = patch_placements[-1].points[-1][1]
                first_start = patch_placements[0].points[0][1]
                closure_error = (last_end - first_start).length
                closure_valid = closure_error < 0.05

        gap_diagnostics = _compute_patch_chain_gap_reports(
            patch_placements,
            total_chains,
        )

        # Scaffold connectivity: найти root chain для этого patch из build_order,
        # вычислить связные H/V chains. Изолированные H/V за FREE не пинятся.
        root_ci = -1
        if build_order:
            for bo_ref in build_order:
                if bo_ref[0] == patch_id:
                    root_ci = bo_ref[2]
                    break
        scaffold_connected = _compute_scaffold_connected_chains(
            patch_placements,
            total_chains,
            root_ci,
            patch_id=patch_id,
            band_spine_data=getattr(runtime_policy, 'band_spine_data', None),
        )

        patches[patch_id] = ScaffoldPatchPlacement(
            patch_id=patch_id,
            loop_index=outer_loop_index,
            root_chain_index=root_ci,
            corner_positions=corner_positions,
            chain_placements=patch_placements,
            bbox_min=bbox_min,
            bbox_max=bbox_max,
            closure_error=closure_error,
            max_chain_gap=gap_diagnostics.max_chain_gap,
            gap_reports=gap_diagnostics.gap_reports,
            closure_valid=closure_valid,
            notes=(),
            status=status,
            dependency_patches=tuple(sorted(dep_set)),
            unplaced_chain_indices=unplaced,
            scaffold_connected_chains=scaffold_connected,
        )

    return patches


def _finalize_quilt_scaffold_frontier(
    graph: PatchGraph,
    solve_view: SolveView,
    quilt_plan: QuiltPlan,
    quilt_scaffold: ScaffoldQuiltPlacement,
    runtime_policy,
    final_scale: float,
    allowed_tree_edges: set[PatchEdgeKey],
    seed_ref: ChainRef,
    total_available: int,
) -> FinalizedQuiltScaffold:
    quilt_scaffold.patches = _cf_build_envelopes(
        solve_view,
        runtime_policy,
        build_order=[seed_ref] + list(runtime_policy.build_order),
    )
    untouched_patch_ids = [
        patch_id
        for patch_id, patch_placement in quilt_scaffold.patches.items()
        if patch_placement.status == PatchPlacementStatus.EMPTY and 'no_placed_chains' in patch_placement.notes
    ]

    quilt_scaffold.build_order = list(runtime_policy.build_order)
    quilt_scaffold.closure_seam_reports = _collect_quilt_closure_seam_reports(
        graph,
        quilt_plan,
        quilt_scaffold,
        runtime_policy.placed_chains_map,
        final_scale,
        allowed_tree_edges,
    )
    quilt_scaffold.frame_alignment_reports = _collect_quilt_frame_alignment_reports(
        graph,
        quilt_plan,
        quilt_scaffold,
        final_scale,
        quilt_scaffold.closure_seam_reports,
    )
    _print_quilt_closure_seam_reports(quilt_plan.quilt_index, quilt_scaffold.closure_seam_reports)
    _print_quilt_frame_alignment_reports(quilt_plan.quilt_index, quilt_scaffold.frame_alignment_reports)

    trace_console(
        f"[CFTUV][Frontier] Quilt {quilt_plan.quilt_index}: "
        f"placed {runtime_policy.total_placed()}/{total_available} chains"
    )
    return FinalizedQuiltScaffold(
        quilt_scaffold=quilt_scaffold,
        untouched_patch_ids=untouched_patch_ids,
    )
