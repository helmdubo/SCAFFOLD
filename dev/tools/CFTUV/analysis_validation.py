from __future__ import annotations

try:
    from .constants import CORNER_ANGLE_THRESHOLD_DEG
    from .model import ChainNeighborKind, FrameRole, LoopKind
    from .analysis_records import CornerJunctionKey, PatchLoopKey, _LoopFrameRunBuildResult
    from .analysis_reporting import (
        _build_junction_role_signature_labels,
        _build_label_sequence_view,
        _format_label_sequence_view,
    )
    from .analysis_junctions import (
        _derive_junction_role_signature,
        _junction_chain_ref_key,
        _junction_run_endpoint_ref_key,
    )
except ImportError:
    from constants import CORNER_ANGLE_THRESHOLD_DEG
    from model import ChainNeighborKind, FrameRole, LoopKind
    from analysis_records import CornerJunctionKey, PatchLoopKey, _LoopFrameRunBuildResult
    from analysis_reporting import (
        _build_junction_role_signature_labels,
        _build_label_sequence_view,
        _format_label_sequence_view,
    )
    from analysis_junctions import (
        _derive_junction_role_signature,
        _junction_chain_ref_key,
        _junction_run_endpoint_ref_key,
    )


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _validate_patch_graph_junctions(graph, derived_topology, report_junction_invariant_violation):
    """Validate the derived junction layer against final corner/chain/run topology."""

    junctions = derived_topology.junctions
    corner_to_junction: dict[CornerJunctionKey, int] = {}
    loop_frame_results = derived_topology.loop_frame_results or {}
    run_refs_by_corner = derived_topology.run_refs_by_corner or {}
    for junction in junctions:
        if junction.valence != len(junction.corner_refs):
            report_junction_invariant_violation(
                junction.vert_index,
                "J2",
                f"valence_mismatch expected={len(junction.corner_refs)} actual={junction.valence}",
            )

        expected_patch_ids = tuple(sorted({corner_ref.patch_id for corner_ref in junction.corner_refs}))
        if tuple(junction.patch_ids) != expected_patch_ids:
            report_junction_invariant_violation(
                junction.vert_index,
                "J4",
                f"patch_ids_mismatch expected={expected_patch_ids} actual={junction.patch_ids}",
            )

        if junction.is_open != junction.has_mesh_border:
            report_junction_invariant_violation(
                junction.vert_index,
                "J3",
                f"open_flag_mismatch is_open={junction.is_open} has_mesh_border={junction.has_mesh_border}",
            )

        expected_chain_keys: set[tuple[int, int, int]] = set()
        expected_run_ref_keys: set[tuple[int, int, int, str]] = set()
        for corner_ref in junction.corner_refs:
            corner_key = (corner_ref.patch_id, corner_ref.loop_index, corner_ref.corner_index)
            if corner_key in corner_to_junction:
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J1",
                    f"corner_shared_between_junctions corner={corner_key} other=V{corner_to_junction[corner_key]}",
                )
                continue
            corner_to_junction[corner_key] = junction.vert_index

            node = graph.nodes.get(corner_ref.patch_id)
            if node is None or corner_ref.loop_index >= len(node.boundary_loops):
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J4",
                    f"missing_corner_patch corner={corner_key}",
                )
                continue
            boundary_loop = node.boundary_loops[corner_ref.loop_index]
            if corner_ref.corner_index >= len(boundary_loop.corners):
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J4",
                    f"missing_corner_index corner={corner_key}",
                )
                continue
            corner = boundary_loop.corners[corner_ref.corner_index]
            if corner.vert_index != junction.vert_index:
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J4",
                    f"corner_vert_mismatch corner={corner_key} actual_vert={corner.vert_index}",
                )
            if (corner.vert_co - junction.vert_co).length > 1e-5:
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J4",
                    f"corner_co_mismatch corner={corner_key}",
                )

            expected_chain_keys.add((corner_ref.patch_id, corner_ref.loop_index, corner_ref.prev_chain_index))
            expected_chain_keys.add((corner_ref.patch_id, corner_ref.loop_index, corner_ref.next_chain_index))
            for run_ref in run_refs_by_corner.get(corner_key, []):
                expected_run_ref_keys.add(_junction_run_endpoint_ref_key(run_ref))

        actual_chain_keys = {_junction_chain_ref_key(chain_ref) for chain_ref in junction.chain_refs}
        if actual_chain_keys != expected_chain_keys:
            report_junction_invariant_violation(
                junction.vert_index,
                "J3",
                f"chain_ref_set_mismatch expected={sorted(expected_chain_keys)} actual={sorted(actual_chain_keys)}",
            )

        actual_run_ref_keys = {
            _junction_run_endpoint_ref_key(run_ref) for run_ref in junction.run_endpoint_refs
        }
        if actual_run_ref_keys != expected_run_ref_keys:
            report_junction_invariant_violation(
                junction.vert_index,
                "J3",
                f"run_ref_set_mismatch expected={sorted(expected_run_ref_keys)} actual={sorted(actual_run_ref_keys)}",
            )

        expected_role_signature = _derive_junction_role_signature(graph, junction.corner_refs)
        if junction.role_signature != expected_role_signature:
            report_junction_invariant_violation(
                junction.vert_index,
                "J5",
                f"role_signature_mismatch expected={_format_label_sequence_view(_build_junction_role_signature_labels(expected_role_signature))} "
                f"actual={_format_label_sequence_view(_build_junction_role_signature_labels(junction.role_signature))}",
            )

        for chain_ref in junction.chain_refs:
            chain = graph.get_chain(chain_ref.patch_id, chain_ref.loop_index, chain_ref.chain_index)
            if chain is None:
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J3",
                    f"missing_chain_ref ref=P{chain_ref.patch_id}L{chain_ref.loop_index}C{chain_ref.chain_index}",
                )
                continue
            if junction.vert_index not in (chain.start_vert_index, chain.end_vert_index):
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J3",
                    f"chain_not_touching_junction ref=P{chain_ref.patch_id}L{chain_ref.loop_index}C{chain_ref.chain_index} "
                    f"endpoints=({chain.start_vert_index},{chain.end_vert_index})",
                )

        for run_ref in junction.run_endpoint_refs:
            frame_runs = loop_frame_results.get(
                (run_ref.patch_id, run_ref.loop_index),
                _LoopFrameRunBuildResult(effective_roles=(), runs=()),
            ).runs
            if run_ref.run_index < 0 or run_ref.run_index >= len(frame_runs):
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J3",
                    f"missing_run_ref ref=P{run_ref.patch_id}L{run_ref.loop_index}R{run_ref.run_index}",
                )
                continue
            frame_run = frame_runs[run_ref.run_index]
            if frame_run.dominant_role != run_ref.dominant_role:
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J3",
                    f"run_role_mismatch ref=P{run_ref.patch_id}L{run_ref.loop_index}R{run_ref.run_index} "
                    f"expected={frame_run.dominant_role.value} actual={run_ref.dominant_role.value}",
                )
            if run_ref.endpoint_kind == "start" and frame_run.start_corner_index != run_ref.corner_index:
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J3",
                    f"run_start_corner_mismatch ref=P{run_ref.patch_id}L{run_ref.loop_index}R{run_ref.run_index} "
                    f"expected={frame_run.start_corner_index} actual={run_ref.corner_index}",
                )
            if run_ref.endpoint_kind == "end" and frame_run.end_corner_index != run_ref.corner_index:
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J3",
                    f"run_end_corner_mismatch ref=P{run_ref.patch_id}L{run_ref.loop_index}R{run_ref.run_index} "
                    f"expected={frame_run.end_corner_index} actual={run_ref.corner_index}",
                )
            if run_ref.endpoint_kind == "both" and (
                frame_run.start_corner_index != run_ref.corner_index
                or frame_run.end_corner_index != run_ref.corner_index
            ):
                report_junction_invariant_violation(
                    junction.vert_index,
                    "J3",
                    f"run_both_corner_mismatch ref=P{run_ref.patch_id}L{run_ref.loop_index}R{run_ref.run_index} "
                    f"start={frame_run.start_corner_index} end={frame_run.end_corner_index} actual={run_ref.corner_index}",
                )

    for patch_id, node in graph.nodes.items():
        for loop_index, boundary_loop in enumerate(node.boundary_loops):
            for corner_index, corner in enumerate(boundary_loop.corners):
                if corner.vert_index < 0:
                    continue
                corner_key = (patch_id, loop_index, corner_index)
                if corner_key not in corner_to_junction:
                    report_junction_invariant_violation(
                        corner.vert_index,
                        "J4",
                        f"corner_missing_from_junctions corner={corner_key}",
                    )
    return junctions


def _validate_patch_graph_derived_topology(graph, derived_topology, report_graph_topology_invariant_violation):
    """Validate the canonical derived topology bundle against the final PatchGraph."""

    patch_summaries = derived_topology.patch_summaries
    patch_summaries_by_id = derived_topology.patch_summaries_by_id
    loop_summaries_by_key = derived_topology.loop_summaries_by_key
    loop_frame_results = derived_topology.loop_frame_results
    frame_runs_by_loop = derived_topology.frame_runs_by_loop
    junctions = derived_topology.junctions
    junctions_by_vert_index = derived_topology.junctions_by_vert_index
    run_refs_by_corner = derived_topology.run_refs_by_corner
    aggregate = derived_topology.aggregate_counts

    expected_patch_ids = tuple(sorted(summary.patch_id for summary in patch_summaries))
    actual_patch_ids = tuple(sorted(patch_summaries_by_id.keys()))
    if actual_patch_ids != expected_patch_ids:
        report_graph_topology_invariant_violation(
            "D1",
            f"patch_summary_index_mismatch expected={expected_patch_ids} actual={actual_patch_ids}",
        )

    expected_loop_keys: set[PatchLoopKey] = set()
    expected_run_keys: set[PatchLoopKey] = set()
    total_chains = 0
    total_corners = 0
    total_holes = 0
    total_sharp_corners = 0
    total_h = 0
    total_v = 0
    total_free = 0
    total_patch_links = 0
    total_self_seams = 0
    total_mesh_borders = 0
    total_runs = 0
    total_run_h = 0
    total_run_v = 0
    total_run_free = 0

    patch_summary_order = tuple(summary.patch_id for summary in patch_summaries)
    if patch_summary_order != tuple(sorted(patch_summary_order)):
        report_graph_topology_invariant_violation(
            "D1",
            f"patch_summary_order_mismatch actual={patch_summary_order}",
        )

    for patch_summary in patch_summaries:
        indexed_patch_summary = patch_summaries_by_id.get(patch_summary.patch_id)
        if indexed_patch_summary != patch_summary:
            report_graph_topology_invariant_violation(
                "D1",
                f"patch_summary_lookup_mismatch patch={patch_summary.patch_id}",
            )

        node = graph.nodes.get(patch_summary.patch_id)
        if node is None:
            report_graph_topology_invariant_violation(
                "D1",
                f"missing_patch_node patch={patch_summary.patch_id}",
            )
            continue

        if patch_summary.face_count != len(node.face_indices):
            report_graph_topology_invariant_violation(
                "D1",
                f"patch_face_count_mismatch patch={patch_summary.patch_id} "
                f"expected={len(node.face_indices)} actual={patch_summary.face_count}",
            )

        if len(patch_summary.loop_summaries) != len(node.boundary_loops):
            report_graph_topology_invariant_violation(
                "D1",
                f"patch_loop_count_mismatch patch={patch_summary.patch_id} "
                f"expected={len(node.boundary_loops)} actual={len(patch_summary.loop_summaries)}",
            )

        patch_chain_count = 0
        patch_corner_count = 0
        patch_hole_count = 0
        patch_run_count = 0
        patch_h = 0
        patch_v = 0
        patch_free = 0
        loop_summary_order = tuple(loop_summary.loop_index for loop_summary in patch_summary.loop_summaries)
        if loop_summary_order != tuple(sorted(loop_summary_order)):
            report_graph_topology_invariant_violation(
                "D2",
                f"loop_summary_order_mismatch patch={patch_summary.patch_id} actual={loop_summary_order}",
            )

        for loop_index, boundary_loop in enumerate(node.boundary_loops):
            loop_key = (patch_summary.patch_id, loop_index)
            expected_loop_keys.add(loop_key)
            patch_chain_count += len(boundary_loop.chains)
            patch_corner_count += len(boundary_loop.corners)
            total_chains += len(boundary_loop.chains)
            total_corners += len(boundary_loop.corners)
            total_sharp_corners += sum(
                1
                for corner in boundary_loop.corners
                if corner.turn_angle_deg >= CORNER_ANGLE_THRESHOLD_DEG
            )

            indexed_loop_summary = loop_summaries_by_key.get(loop_key)
            if indexed_loop_summary is None:
                report_graph_topology_invariant_violation(
                    "D2",
                    f"missing_loop_summary loop=P{patch_summary.patch_id}L{loop_index}",
                )
                continue

            expected_loop_summary = (
                patch_summary.loop_summaries[loop_index]
                if loop_index < len(patch_summary.loop_summaries)
                else None
            )
            if expected_loop_summary != indexed_loop_summary:
                report_graph_topology_invariant_violation(
                    "D2",
                    f"loop_summary_lookup_mismatch loop=P{patch_summary.patch_id}L{loop_index}",
                )

            if indexed_loop_summary.kind != boundary_loop.kind:
                report_graph_topology_invariant_violation(
                    "D2",
                    f"loop_kind_mismatch loop=P{patch_summary.patch_id}L{loop_index} "
                    f"expected={boundary_loop.kind.value} actual={indexed_loop_summary.kind.value}",
                )
            if boundary_loop.kind == LoopKind.HOLE:
                patch_hole_count += 1
                total_holes += 1
            if indexed_loop_summary.chain_count != len(boundary_loop.chains):
                report_graph_topology_invariant_violation(
                    "D2",
                    f"loop_chain_count_mismatch loop=P{patch_summary.patch_id}L{loop_index} "
                    f"expected={len(boundary_loop.chains)} actual={indexed_loop_summary.chain_count}",
                )
            if indexed_loop_summary.corner_count != len(boundary_loop.corners):
                report_graph_topology_invariant_violation(
                    "D2",
                    f"loop_corner_count_mismatch loop=P{patch_summary.patch_id}L{loop_index} "
                    f"expected={len(boundary_loop.corners)} actual={indexed_loop_summary.corner_count}",
                )

            frame_result = loop_frame_results.get(loop_key)
            if frame_result is None:
                report_graph_topology_invariant_violation(
                    "D3",
                    f"missing_loop_frame_result loop=P{patch_summary.patch_id}L{loop_index}",
                )
                continue
            expected_run_keys.add(loop_key)

            indexed_frame_runs = frame_runs_by_loop.get(loop_key)
            if indexed_frame_runs != frame_result.runs:
                report_graph_topology_invariant_violation(
                    "D3",
                    f"frame_run_lookup_mismatch loop=P{patch_summary.patch_id}L{loop_index}",
                )

            if indexed_loop_summary.run_count != len(frame_result.runs):
                report_graph_topology_invariant_violation(
                    "D2",
                    f"loop_run_count_mismatch loop=P{patch_summary.patch_id}L{loop_index} "
                    f"expected={len(frame_result.runs)} actual={indexed_loop_summary.run_count}",
                )
            patch_run_count += len(frame_result.runs)

            for chain in boundary_loop.chains:
                if chain.frame_role == FrameRole.H_FRAME:
                    patch_h += 1
                    total_h += 1
                elif chain.frame_role == FrameRole.V_FRAME:
                    patch_v += 1
                    total_v += 1
                else:
                    patch_free += 1
                    total_free += 1

                if chain.neighbor_kind == ChainNeighborKind.PATCH:
                    total_patch_links += 1
                elif chain.neighbor_kind == ChainNeighborKind.SEAM_SELF:
                    total_self_seams += 1
                else:
                    total_mesh_borders += 1

            for frame_run in frame_result.runs:
                total_runs += 1
                if frame_run.dominant_role == FrameRole.H_FRAME:
                    total_run_h += 1
                elif frame_run.dominant_role == FrameRole.V_FRAME:
                    total_run_v += 1
                else:
                    total_run_free += 1

        if patch_summary.chain_count != patch_chain_count:
            report_graph_topology_invariant_violation(
                "D1",
                f"patch_chain_count_mismatch patch={patch_summary.patch_id} "
                f"expected={patch_chain_count} actual={patch_summary.chain_count}",
            )
        if patch_summary.corner_count != patch_corner_count:
            report_graph_topology_invariant_violation(
                "D1",
                f"patch_corner_count_mismatch patch={patch_summary.patch_id} "
                f"expected={patch_corner_count} actual={patch_summary.corner_count}",
            )
        if patch_summary.hole_count != patch_hole_count:
            report_graph_topology_invariant_violation(
                "D1",
                f"patch_hole_count_mismatch patch={patch_summary.patch_id} "
                f"expected={patch_hole_count} actual={patch_summary.hole_count}",
            )
        if patch_summary.run_count != patch_run_count:
            report_graph_topology_invariant_violation(
                "D1",
                f"patch_run_count_mismatch patch={patch_summary.patch_id} "
                f"expected={patch_run_count} actual={patch_summary.run_count}",
            )
        if (
            patch_summary.h_count != patch_h
            or patch_summary.v_count != patch_v
            or patch_summary.free_count != patch_free
        ):
            report_graph_topology_invariant_violation(
                "D1",
                f"patch_role_count_mismatch patch={patch_summary.patch_id} "
                f"expected=({patch_h},{patch_v},{patch_free}) actual=({patch_summary.h_count},{patch_summary.v_count},{patch_summary.free_count})",
            )

    actual_loop_keys = set(loop_summaries_by_key.keys())
    if actual_loop_keys != expected_loop_keys:
        report_graph_topology_invariant_violation(
            "D2",
            f"loop_summary_keyset_mismatch expected={sorted(expected_loop_keys)} actual={sorted(actual_loop_keys)}",
        )

    actual_run_keys = set(frame_runs_by_loop.keys())
    if actual_run_keys != expected_run_keys or set(loop_frame_results.keys()) != expected_run_keys:
        report_graph_topology_invariant_violation(
            "D3",
            f"frame_run_keyset_mismatch expected={sorted(expected_run_keys)} actual={sorted(actual_run_keys)} "
            f"build={sorted(loop_frame_results.keys())}",
        )

    expected_junction_vert_indices = tuple(sorted(junction.vert_index for junction in junctions))
    if tuple(junction.vert_index for junction in junctions) != expected_junction_vert_indices:
        report_graph_topology_invariant_violation(
            "D4",
            f"junction_order_mismatch actual={tuple(junction.vert_index for junction in junctions)}",
        )
    actual_junction_vert_indices = tuple(sorted(junctions_by_vert_index.keys()))
    if actual_junction_vert_indices != expected_junction_vert_indices:
        report_graph_topology_invariant_violation(
            "D4",
            f"junction_index_mismatch expected={expected_junction_vert_indices} actual={actual_junction_vert_indices}",
        )
    for junction in junctions:
        indexed_junction = junctions_by_vert_index.get(junction.vert_index)
        if indexed_junction != junction:
            report_graph_topology_invariant_violation(
                "D4",
                f"junction_lookup_mismatch vert={junction.vert_index}",
            )

    for corner_key in run_refs_by_corner.keys():
        patch_id, loop_index, corner_index = corner_key
        node = graph.nodes.get(patch_id)
        if node is None or loop_index >= len(node.boundary_loops):
            report_graph_topology_invariant_violation(
                "D5",
                f"run_ref_missing_loop corner=P{patch_id}L{loop_index}K{corner_index}",
            )
            continue
        boundary_loop = node.boundary_loops[loop_index]
        if corner_index < 0 or corner_index >= len(boundary_loop.corners):
            report_graph_topology_invariant_violation(
                "D5",
                f"run_ref_missing_corner corner=P{patch_id}L{loop_index}K{corner_index}",
            )

    if aggregate.total_patches != len(patch_summaries):
        report_graph_topology_invariant_violation(
            "D6",
            f"aggregate_patch_count_mismatch expected={len(patch_summaries)} actual={aggregate.total_patches}",
        )
    if aggregate.total_loops != len(loop_summaries_by_key):
        report_graph_topology_invariant_violation(
            "D6",
            f"aggregate_loop_count_mismatch expected={len(loop_summaries_by_key)} actual={aggregate.total_loops}",
        )
    if (
        aggregate.total_chains != total_chains
        or aggregate.total_corners != total_corners
        or aggregate.total_holes != total_holes
    ):
        report_graph_topology_invariant_violation(
            "D6",
            f"aggregate_topology_count_mismatch expected=({total_chains},{total_corners},{total_holes}) "
            f"actual=({aggregate.total_chains},{aggregate.total_corners},{aggregate.total_holes})",
        )
    if aggregate.total_sharp_corners != total_sharp_corners:
        report_graph_topology_invariant_violation(
            "D6",
            f"aggregate_sharp_corner_count_mismatch expected={total_sharp_corners} actual={aggregate.total_sharp_corners}",
        )
    if aggregate.total_h != total_h or aggregate.total_v != total_v or aggregate.total_free != total_free:
        report_graph_topology_invariant_violation(
            "D6",
            f"aggregate_role_count_mismatch expected=({total_h},{total_v},{total_free}) "
            f"actual=({aggregate.total_h},{aggregate.total_v},{aggregate.total_free})",
        )
    if (
        aggregate.total_patch_links != total_patch_links
        or aggregate.total_self_seams != total_self_seams
        or aggregate.total_mesh_borders != total_mesh_borders
    ):
        report_graph_topology_invariant_violation(
            "D6",
            f"aggregate_neighbor_count_mismatch expected=({total_patch_links},{total_self_seams},{total_mesh_borders}) "
            f"actual=({aggregate.total_patch_links},{aggregate.total_self_seams},{aggregate.total_mesh_borders})",
        )
    if (
        aggregate.total_run_h != total_run_h
        or aggregate.total_run_v != total_run_v
        or aggregate.total_run_free != total_run_free
    ):
        report_graph_topology_invariant_violation(
            "D6",
            f"aggregate_run_role_count_mismatch expected=({total_run_h},{total_run_v},{total_run_free}) "
            f"actual=({aggregate.total_run_h},{aggregate.total_run_v},{aggregate.total_run_free})",
        )
    if aggregate.total_run_h + aggregate.total_run_v + aggregate.total_run_free != total_runs:
        report_graph_topology_invariant_violation(
            "D6",
            f"aggregate_run_total_mismatch expected={total_runs} "
            f"actual={aggregate.total_run_h + aggregate.total_run_v + aggregate.total_run_free}",
        )


def _validate_patch_graph_console_view(
    derived_topology,
    console_view,
    report_graph_topology_invariant_violation,
):
    """Validate the typed console/snapshot view against canonical derived topology."""

    patch_views = console_view.patch_views
    patch_summaries = derived_topology.patch_summaries
    if tuple(patch_view.patch_id for patch_view in patch_views) != tuple(
        patch_summary.patch_id for patch_summary in patch_summaries
    ):
        report_graph_topology_invariant_violation(
            "RV1",
            f"patch_view_order_mismatch actual={tuple(patch_view.patch_id for patch_view in patch_views)} "
            f"expected={tuple(patch_summary.patch_id for patch_summary in patch_summaries)}",
        )

    for patch_view, patch_summary in zip(patch_views, patch_summaries):
        if patch_view.semantic_key != patch_summary.semantic_key:
            report_graph_topology_invariant_violation(
                "RV1",
                f"patch_semantic_key_mismatch patch={patch_summary.patch_id} "
                f"expected={patch_summary.semantic_key} actual={patch_view.semantic_key}",
            )
        if (
            patch_view.face_count != patch_summary.face_count
            or patch_view.hole_count != patch_summary.hole_count
            or patch_view.run_count != patch_summary.run_count
            or patch_view.chain_count != patch_summary.chain_count
            or patch_view.corner_count != patch_summary.corner_count
        ):
            report_graph_topology_invariant_violation(
                "RV1",
                f"patch_count_mismatch patch={patch_summary.patch_id}",
            )
        if (
            patch_view.h_count != patch_summary.h_count
            or patch_view.v_count != patch_summary.v_count
            or patch_view.free_count != patch_summary.free_count
        ):
            report_graph_topology_invariant_violation(
                "RV1",
                f"patch_role_count_mismatch patch={patch_summary.patch_id}",
            )
        expected_loop_kind_labels = _build_label_sequence_view(
            _enum_value(kind) for kind in patch_summary.loop_kinds
        )
        if patch_view.loop_kind_labels != expected_loop_kind_labels:
            report_graph_topology_invariant_violation(
                "RV1",
                f"patch_loop_kind_labels_mismatch patch={patch_summary.patch_id}",
            )
        expected_role_labels = _build_label_sequence_view(
            _enum_value(role) for role in patch_summary.role_sequence
        )
        if patch_view.role_labels != expected_role_labels:
            report_graph_topology_invariant_violation(
                "RV1",
                f"patch_role_labels_mismatch patch={patch_summary.patch_id}",
            )
        if len(patch_view.loop_views) != len(patch_summary.loop_summaries):
            report_graph_topology_invariant_violation(
                "RV2",
                f"patch_loop_view_count_mismatch patch={patch_summary.patch_id} "
                f"expected={len(patch_summary.loop_summaries)} actual={len(patch_view.loop_views)}",
            )

        if tuple(loop_view.loop_index for loop_view in patch_view.loop_views) != tuple(
            loop_summary.loop_index for loop_summary in patch_summary.loop_summaries
        ):
            report_graph_topology_invariant_violation(
                "RV2",
                f"loop_view_order_mismatch patch={patch_summary.patch_id} "
                f"actual={tuple(loop_view.loop_index for loop_view in patch_view.loop_views)} "
                f"expected={tuple(loop_summary.loop_index for loop_summary in patch_summary.loop_summaries)}",
            )

        for loop_view, loop_summary in zip(patch_view.loop_views, patch_summary.loop_summaries):
            if (
                loop_view.kind != _enum_value(loop_summary.kind)
                or loop_view.chain_count != loop_summary.chain_count
                or loop_view.corner_count != loop_summary.corner_count
            ):
                report_graph_topology_invariant_violation(
                    "RV2",
                    f"loop_view_mismatch patch={patch_summary.patch_id} loop={loop_summary.loop_index}",
                )
            if len(loop_view.run_views) != loop_summary.run_count:
                report_graph_topology_invariant_violation(
                    "RV2",
                    f"loop_run_view_count_mismatch patch={patch_summary.patch_id} loop={loop_summary.loop_index} "
                    f"expected={loop_summary.run_count} actual={len(loop_view.run_views)}",
                )

    junction_summary = console_view.junction_summary
    if tuple(junction_view.vert_index for junction_view in console_view.junction_views) != tuple(
        junction.vert_index for junction in junction_summary.interesting_junctions
    ):
        report_graph_topology_invariant_violation(
            "RV3",
            f"junction_view_order_mismatch actual={tuple(junction_view.vert_index for junction_view in console_view.junction_views)} "
            f"expected={tuple(junction.vert_index for junction in junction_summary.interesting_junctions)}",
        )

    summary_view = console_view.summary_view
    expected_valence_labels = _build_label_sequence_view(
        f"v{valence}:{count}" for valence, count in junction_summary.valence_histogram
    )
    if summary_view.valence_labels != expected_valence_labels:
        report_graph_topology_invariant_violation(
            "RV3",
            "valence_labels_mismatch",
        )
    if (
        summary_view.total_junctions != junction_summary.total_junctions
        or summary_view.interesting_junction_count != len(junction_summary.interesting_junctions)
        or summary_view.open_junction_count != junction_summary.open_junction_count
        or summary_view.closed_junction_count != junction_summary.closed_junction_count
    ):
        report_graph_topology_invariant_violation(
            "RV3",
            "junction_summary_view_mismatch",
        )
