"""
Layer: pipeline

Rules:
- Owns pass orchestration.
- May import layers.
- Layers must not import this module.
- Do not place topology, geometry, relation, feature, or runtime logic here.
"""

from __future__ import annotations

from scaffold_core.core.diagnostics import DiagnosticReport
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
    diagnostics = DiagnosticReport(
        validate_topology(topology_snapshot) + geometry_facts.diagnostics
    )
    return PipelineContext(
        source_snapshot=source_snapshot,
        topology_snapshot=topology_snapshot,
        geometry_facts=geometry_facts,
        diagnostics=diagnostics,
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
