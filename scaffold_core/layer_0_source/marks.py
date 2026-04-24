"""
Layer: 0 — Source

Rules:
- Source mark data models only.
- No topology entities, geometry facts, relations, features, or runtime solve here.
- No direct Blender access here; Blender conversion lives in blender_io.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from scaffold_core.ids import SourceEdgeId, SourceFaceId, SourceVertexId


class SourceMarkKind(str, Enum):
    """Supported source mark kinds read from Blender/source fixtures."""

    SEAM = "SEAM"
    SHARP = "SHARP"
    MATERIAL_BOUNDARY = "MATERIAL_BOUNDARY"
    USER = "USER"


@dataclass(frozen=True)
class SourceMark:
    """A source-level mark attached to a source mesh element."""

    kind: SourceMarkKind
    target_id: SourceVertexId | SourceEdgeId | SourceFaceId
    value: str | bool = True
