"""
Layer: cross-cutting ids

Rules:
- Contains id aliases only.
- Does not import layer packages.
- Does not contain topology, geometry, relation, feature, or runtime logic.
"""

from typing import NewType

SurfaceModelId = NewType("SurfaceModelId", str)
ShellId = NewType("ShellId", str)
PatchId = NewType("PatchId", str)
BoundaryLoopId = NewType("BoundaryLoopId", str)
ChainId = NewType("ChainId", str)
ChainUseId = NewType("ChainUseId", str)
PatchChainId = ChainUseId
VertexId = NewType("VertexId", str)
SourceMeshId = NewType("SourceMeshId", str)
SourceFaceId = NewType("SourceFaceId", str)
SourceEdgeId = NewType("SourceEdgeId", str)
SourceVertexId = NewType("SourceVertexId", str)
