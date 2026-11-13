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


class SourceFaceStrength(str, Enum):
    """Blender's Face Strength class of one source face, as Blender wrote it.

    Read from the FACE-domain int attribute that Blender's Bevel modifier
    (Face Strength mode) and the Weighted Normal modifier share. A raw source
    mark: it states the stored value, not what the face is. Stored values
    other than the three below map to None (no mark), as does a mesh
    without the attribute.
    """

    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"


FACE_STRENGTH_ATTRIBUTE = "__mod_weightednormals_faceweight"
FACE_STRENGTH_BY_VALUE = {
    -16384: SourceFaceStrength.WEAK,
    0: SourceFaceStrength.MEDIUM,
    16384: SourceFaceStrength.STRONG,
}


@dataclass(frozen=True)
class SourceMark:
    """A source-level mark attached to a source mesh element."""

    kind: SourceMarkKind
    target_id: SourceVertexId | SourceEdgeId | SourceFaceId
    value: str | bool = True
