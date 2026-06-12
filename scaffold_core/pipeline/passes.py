"""
Layer: pipeline

Rules:
- Owns pass orchestration.
- May import layers.
- Layers must not import this module.
- Do not place topology, geometry, relation, feature, or runtime logic here.
"""

from __future__ import annotations

from scaffold_core.core.diagnostics import Diagnostic, DiagnosticReport, DiagnosticSeverity
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.invariants import validate_topology
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations.build import build_relation_snapshot
from scaffold_core.pipeline.context import PipelineContext


def run_pass_0(source_snapshot: SourceMeshSnapshot) -> PipelineContext:
    """Run G2 Pass 0: source snapshot to topology and geometry facts."""

    topology_snapshot = build_topology_snapshot(source_snapshot)
    geometry_facts = build_geometry_facts(source_snapshot, topology_snapshot)
    fallback_diagnostics = _selection_fallback_diagnostics(source_snapshot)
    diagnostics = DiagnosticReport(
        fallback_diagnostics + validate_topology(topology_snapshot) + geometry_facts.diagnostics
    )
    return PipelineContext(
        source_snapshot=source_snapshot,
        topology_snapshot=topology_snapshot,
        geometry_facts=geometry_facts,
        diagnostics=diagnostics,
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

    relation_snapshot = build_relation_snapshot(
        context.topology_snapshot,
        context.geometry_facts,
    )
    return PipelineContext(
        source_snapshot=context.source_snapshot,
        topology_snapshot=context.topology_snapshot,
        geometry_facts=context.geometry_facts,
        relation_snapshot=relation_snapshot,
        diagnostics=context.diagnostics.extend(relation_snapshot.diagnostics),
    )
