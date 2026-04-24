"""
Layer: pipeline

Rules:
- Pipeline context data only.
- No topology, geometry, relation, feature, or runtime logic here.
- Layers may type-reference PipelineContext but must not control pass order.
"""

from __future__ import annotations

from dataclasses import dataclass

from scaffold_core.core.diagnostics import DiagnosticReport
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.model import SurfaceModel


@dataclass(frozen=True)
class PipelineContext:
    """Immutable container for pipeline pass outputs."""

    source_snapshot: SourceMeshSnapshot | None = None
    topology_snapshot: SurfaceModel | None = None
    diagnostics: DiagnosticReport = DiagnosticReport()
