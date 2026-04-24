"""
Layer: 0 — Source

Rules:
- This is the core mesh-read boundary for Blender/BMesh input.
- Convert Blender mesh state into SourceMeshSnapshot.
- Do not build topology, geometry facts, relations, features, or runtime solve here.
"""

from __future__ import annotations

from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot


def read_source_mesh_from_blender(_context: object) -> SourceMeshSnapshot:
    """Convert Blender context/selection into SourceMeshSnapshot.

    Placeholder for G1. The implementation may import bpy/bmesh locally when
    Blender integration starts.
    """

    raise NotImplementedError("Blender mesh import is not implemented yet.")
