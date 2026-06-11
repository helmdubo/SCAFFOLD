"""
Layer: tests

Rules:
- Canonical production-shape fixture baselines only.
- Tests may import Scaffold Core but must not define production logic.
- KNOWN LIMITATION tests document current behavior that later slices must
  change; flip them together with the fixing slice, do not delete them.
"""

from __future__ import annotations

from scaffold_core.layer_2_geometry.measures import dot, normalize
from scaffold_core.pipeline.context import PipelineContext
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.beveled_wall_corner import (
    make_beveled_wall_corner_source,
    make_rounded_wall_corner_two_segment_source,
)
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.detached_parallel_walls import (
    make_detached_parallel_walls_source,
)
from scaffold_core.tests.fixtures.l_corridor_tunnel import (
    make_l_corridor_tunnel_seamed_folds_source,
    make_l_corridor_tunnel_single_patch_source,
)
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


def _run(source) -> PipelineContext:
    return run_pass_1_relations(run_pass_0(source))


def _classes_along(relation_snapshot, direction):
    reference = normalize(direction)
    return tuple(
        alignment_class
        for alignment_class in relation_snapshot.alignment_classes
        if abs(dot(normalize(alignment_class.dominant_direction), reference)) > 0.99
    )


def _relation_kind_counts(relation_snapshot) -> dict[str, int]:
    counts: dict[str, int] = {}
    for relation in relation_snapshot.scaffold_node_incident_edge_relations:
        counts[relation.kind.value] = counts.get(relation.kind.value, 0) + 1
    return counts


def test_detached_parallel_walls_share_no_topology() -> None:
    context = _run(make_detached_parallel_walls_source())
    topology = context.topology_snapshot
    relations = context.relation_snapshot

    assert len(topology.shells) == 2
    assert len(topology.patches) == 2
    assert len(relations.patch_adjacencies) == 0


def test_detached_parallel_walls_merge_into_world_alignment_families() -> None:
    # KNOWN LIMITATION: build_alignment_classes groups by absolute world
    # direction, so two disconnected walls share alignment families despite
    # having no adjacency path. A connectivity-aware direction family must
    # keep them apart. Flip this test when connected direction families land.
    context = _run(make_detached_parallel_walls_source())
    relations = context.relation_snapshot

    assert len(relations.alignment_classes) == 2
    for alignment_class in relations.alignment_classes:
        assert len(alignment_class.patch_ids) == 2


def test_beveled_wall_corner_baseline_topology() -> None:
    context = _run(make_beveled_wall_corner_source())
    topology = context.topology_snapshot
    relations = context.relation_snapshot

    assert len(topology.shells) == 1
    assert len(topology.patches) == 3
    assert len(relations.patch_adjacencies) == 2


def test_beveled_wall_corner_vertical_family_spans_all_patches() -> None:
    context = _run(make_beveled_wall_corner_source())
    relations = context.relation_snapshot

    vertical_classes = _classes_along(relations, (0.0, 0.0, 1.0))
    assert len(vertical_classes) == 1
    assert len(vertical_classes[0].patch_ids) == 3


def test_beveled_wall_corner_horizontal_flow_is_currently_lost() -> None:
    # KNOWN LIMITATION: the horizontal chains of wall A, chamfer and wall B
    # form one continuous surface flow around the corner, but world-direction
    # grouping splits them into three single-patch families and no
    # continuation candidate is emitted: every continuity component stays a
    # singleton. This is the primary middle-poly production case the
    # continuity layer must eventually support.
    context = _run(make_beveled_wall_corner_source())
    relations = context.relation_snapshot

    horizontal_classes = tuple(
        alignment_class
        for alignment_class in relations.alignment_classes
        if alignment_class not in _classes_along(relations, (0.0, 0.0, 1.0))
    )
    assert len(horizontal_classes) == 3
    for alignment_class in horizontal_classes:
        assert len(alignment_class.patch_ids) == 1

    assert len(relations.scaffold_continuity_components) == 8
    for component in relations.scaffold_continuity_components:
        assert len(component.scaffold_edge_ids) == 1


def test_rounded_wall_corner_matches_single_chamfer_baseline() -> None:
    context = _run(make_rounded_wall_corner_two_segment_source())
    topology = context.topology_snapshot
    relations = context.relation_snapshot

    assert len(topology.patches) == 3
    assert len(relations.patch_adjacencies) == 2
    vertical_classes = _classes_along(relations, (0.0, 0.0, 1.0))
    assert len(vertical_classes) == 1
    assert len(vertical_classes[0].patch_ids) == 3
    for component in relations.scaffold_continuity_components:
        assert len(component.scaffold_edge_ids) == 1


def test_l_corridor_tunnel_single_patch_coalesces_one_border_chain() -> None:
    context = _run(make_l_corridor_tunnel_single_patch_source())
    topology = context.topology_snapshot
    relations = context.relation_snapshot

    assert len(topology.patches) == 1
    assert len(topology.chains) == 1
    assert len(topology.patch_chains) == 1
    # The turning border polyline still yields per-direction evidence.
    assert len(relations.alignment_classes) == 3


def test_l_corridor_tunnel_seamed_folds_baseline_topology() -> None:
    context = _run(make_l_corridor_tunnel_seamed_folds_source())
    topology = context.topology_snapshot
    relations = context.relation_snapshot

    assert len(topology.patches) == 3
    assert len(relations.patch_adjacencies) == 2

    width_classes = _classes_along(relations, (0.0, 1.0, 0.0))
    assert len(width_classes) == 1
    assert len(width_classes[0].patch_ids) == 3


def test_l_corridor_tunnel_seamed_folds_length_flow_is_currently_lost() -> None:
    # KNOWN LIMITATION: the tunnel length rails span X, Z and X world
    # directions across floor, wall and ceiling. World-direction grouping
    # merges floor+ceiling by coincidental world parallelism while the wall
    # stays separate, and every continuity component stays a singleton. A
    # length-preserving unwrap lays this strip straight, so the target is one
    # connected length family across all three patches.
    context = _run(make_l_corridor_tunnel_seamed_folds_source())
    relations = context.relation_snapshot

    length_x_classes = _classes_along(relations, (1.0, 0.0, 0.0))
    assert len(length_x_classes) == 1
    assert len(length_x_classes[0].patch_ids) == 2

    kind_counts = _relation_kind_counts(relations)
    assert kind_counts.get("MISSING_ENDPOINT_EVIDENCE", 0) == 0

    for component in relations.scaffold_continuity_components:
        assert len(component.scaffold_edge_ids) == 1


def test_tube_with_cap_baseline_topology() -> None:
    context = _run(make_tube_with_cap_source())
    topology = context.topology_snapshot
    relations = context.relation_snapshot

    assert len(topology.shells) == 1
    assert len(topology.patches) == 2
    assert len(relations.patch_adjacencies) == 1
    assert len(relations.scaffold_edges) == 5

    seam_self_codes = tuple(
        diagnostic
        for diagnostic in context.diagnostics.diagnostics
        if diagnostic.code == "TOPOLOGY_CHAIN_SEAM_SELF"
    )
    assert len(seam_self_codes) == 1


def test_tube_with_cap_keeps_cap_and_side_continuity_separate() -> None:
    # DD-39: side-to-cap PatchChains may be shared/cross-patch neighbors, but
    # diverging owner normals must not promote side-surface continuation.
    context = _run(make_tube_with_cap_source())
    relations = context.relation_snapshot

    sliding_touching_cap = tuple(
        relation
        for relation in relations.scaffold_node_incident_edge_relations
        if relation.kind.value == "SURFACE_SLIDING_CONTINUATION_CANDIDATE"
        and any(
            "f_cap" in str(edge_id)
            for edge_id in {relation.first_scaffold_edge_id, relation.second_scaffold_edge_id}
        )
    )
    assert sliding_touching_cap == ()

    cap_and_side_components = tuple(
        component
        for component in relations.scaffold_continuity_components
        if len(component.scaffold_edge_ids) == 2
        and any("f_cap" in str(edge_id) for edge_id in component.scaffold_edge_ids)
    )
    assert cap_and_side_components == ()


def test_tube_with_two_seams_keeps_cross_patch_side_ring_flow() -> None:
    # DD-39 positive example: a tube split by two seam chains must keep its
    # top and bottom border ring flow across the seam nodes — two side
    # continuity families, not four singleton border edges. This guards the
    # cap/side gate (test above) against over-blocking legitimate rule A
    # ring flow, where owner normals diverge around the curved surface.
    context = _run(make_cylinder_tube_without_caps_with_two_seams_source())
    topology = context.topology_snapshot
    relations = context.relation_snapshot

    assert len(topology.patches) == 2

    kind_counts = _relation_kind_counts(relations)
    assert kind_counts.get("SURFACE_SLIDING_CONTINUATION_CANDIDATE", 0) == 4
    assert kind_counts.get("MISSING_ENDPOINT_EVIDENCE", 0) == 0
    assert len(relations.surface_flow_compatibility_evidence) == 4

    edges_by_id = {edge.id: edge for edge in relations.scaffold_edges}
    ring_components = tuple(
        component
        for component in relations.scaffold_continuity_components
        if len(component.scaffold_edge_ids) == 2
    )
    assert len(ring_components) == 2
    for component in ring_components:
        first, second = (edges_by_id[edge_id] for edge_id in component.scaffold_edge_ids)
        assert first.patch_id != second.patch_id
        assert first.chain_id != second.chain_id
