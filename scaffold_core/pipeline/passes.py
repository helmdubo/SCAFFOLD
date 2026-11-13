"""
Layer: pipeline

Rules:
- Owns pass orchestration.
- May import layers.
- Layers must not import this module.
- Do not place topology, geometry, relation, feature, or runtime logic here.
"""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from scaffold_core.core.diagnostics import Diagnostic, DiagnosticReport, DiagnosticSeverity
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import validate_topology
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.layer_4_features.build import build_feature_snapshot
from scaffold_core.layer_4_features.model import FeatureOptions
from scaffold_core.pipeline.context import PassTiming, PipelineContext
from scaffold_core.user_filters.build import build_filter_snapshot
from scaffold_core.user_filters.model import FilterOptions


def run_pass_0(source_snapshot: SourceMeshSnapshot) -> PipelineContext:
    """Run G2 Pass 0: source snapshot to topology and geometry facts."""

    topology_started = perf_counter()
    topology_snapshot = build_topology_snapshot(source_snapshot)
    topology_seconds = perf_counter() - topology_started

    geometry_started = perf_counter()
    geometry_facts = build_geometry_facts(source_snapshot, topology_snapshot)
    geometry_seconds = perf_counter() - geometry_started

    validation_started = perf_counter()
    fallback_diagnostics = _selection_fallback_diagnostics(source_snapshot)
    diagnostics = DiagnosticReport(
        fallback_diagnostics + validate_topology(topology_snapshot) + geometry_facts.diagnostics
    )
    validation_seconds = perf_counter() - validation_started

    return PipelineContext(
        source_snapshot=source_snapshot,
        topology_snapshot=topology_snapshot,
        geometry_facts=geometry_facts,
        diagnostics=diagnostics,
        pass_timings=(
            PassTiming("pass_0.topology_snapshot", topology_seconds),
            PassTiming("pass_0.geometry_facts", geometry_seconds),
            PassTiming("pass_0.validate_topology", validation_seconds),
        ),
    )


def _selection_fallback_diagnostics(source_snapshot: SourceMeshSnapshot) -> tuple[Diagnostic, ...]:
    if source_snapshot.selected_face_ids:
        return ()
    return (
        Diagnostic(
            code="SELECTION_FALLBACK_ALL_FACES",
            severity=DiagnosticSeverity.WARNING,
            message="No selected faces; Pass 0 used all mesh faces as fallback.",
            source="pipeline.run_pass_0",
            entity_ids=(str(source_snapshot.id),),
            evidence={
                "selected_face_count": 0,
                "fallback_face_count": len(source_snapshot.faces),
            },
        ),
    )


def run_pass_1_relations(context: PipelineContext) -> PipelineContext:
    """Run G3 Pass 1 relation building from topology and geometry facts."""

    if context.topology_snapshot is None or context.geometry_facts is None:
        raise ValueError("Pass 1 requires topology_snapshot and geometry_facts.")

    relations_started = perf_counter()
    relation_snapshot = build_relation_snapshot(
        context.topology_snapshot,
        context.geometry_facts,
        context.source_snapshot,
    )
    relations_seconds = perf_counter() - relations_started

    return PipelineContext(
        source_snapshot=context.source_snapshot,
        topology_snapshot=context.topology_snapshot,
        geometry_facts=context.geometry_facts,
        relation_snapshot=relation_snapshot,
        diagnostics=context.diagnostics.extend(relation_snapshot.diagnostics),
        pass_timings=context.pass_timings
        + (PassTiming("pass_1.relation_snapshot", relations_seconds),),
    )


def run_pass_2_features(context: PipelineContext, options: FeatureOptions = FeatureOptions()) -> PipelineContext:
    """Run Pass 2 feature recognition after Pass 1; Layer 3 is read, never written."""

    if context.topology_snapshot is None or context.geometry_facts is None or context.relation_snapshot is None:
        raise ValueError("Pass 2 requires topology_snapshot, geometry_facts and relation_snapshot.")

    features_started = perf_counter()
    feature_snapshot = build_feature_snapshot(
        context.topology_snapshot,
        context.geometry_facts,
        context.relation_snapshot,
        options,
        source=context.source_snapshot,
    )
    features_seconds = perf_counter() - features_started

    return replace(
        context,
        feature_snapshot=feature_snapshot,
        diagnostics=context.diagnostics.extend(feature_snapshot.diagnostics),
        pass_timings=context.pass_timings + (PassTiming("pass_2.feature_snapshot", features_seconds),),
    )


def run_pass_3_filters(context: PipelineContext, options: FilterOptions = FilterOptions()) -> PipelineContext:
    """Run Pass 3, the over filter of user options, after Pass 2; Layers 0-4 are read, never written.

    With options.world_up None the snapshot is empty and the solve equals a
    run without this pass.
    """

    if context.topology_snapshot is None or context.geometry_facts is None or context.relation_snapshot is None:
        raise ValueError("Pass 3 requires topology_snapshot, geometry_facts and relation_snapshot.")

    filters_started = perf_counter()
    filter_snapshot = build_filter_snapshot(
        context.topology_snapshot,
        context.geometry_facts,
        context.relation_snapshot,
        context.feature_snapshot,
        options,
        source=context.source_snapshot,
    )
    filters_seconds = perf_counter() - filters_started

    return replace(
        context,
        filter_snapshot=filter_snapshot,
        diagnostics=context.diagnostics.extend(filter_snapshot.diagnostics),
        pass_timings=context.pass_timings + (PassTiming("pass_3.filter_snapshot", filters_seconds),),
    )
