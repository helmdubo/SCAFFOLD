"""
Layer: 2 - Geometry

Rules:
- Frozen geometry fact dataclasses only.
- No topology building, relation derivation, feature interpretation, or solve logic.
- Store measured data only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from scaffold_core.core.diagnostics import Diagnostic
from scaffold_core.ids import ChainId, PatchId, VertexId


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class PatchGeometryFacts:
    patch_id: PatchId
    area: float
    normal: Vector3
    centroid: Vector3


@dataclass(frozen=True)
class ChainGeometryFacts:
    chain_id: ChainId
    length: float
    chord_direction: Vector3


@dataclass(frozen=True)
class VertexGeometryFacts:
    vertex_id: VertexId
    position: Vector3


@dataclass(frozen=True)
class GeometryFactSnapshot:
    patch_facts: Mapping[PatchId, PatchGeometryFacts] = field(default_factory=dict)
    chain_facts: Mapping[ChainId, ChainGeometryFacts] = field(default_factory=dict)
    vertex_facts: Mapping[VertexId, VertexGeometryFacts] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] = ()
