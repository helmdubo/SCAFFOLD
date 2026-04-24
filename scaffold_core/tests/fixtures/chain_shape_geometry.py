"""
Layer: tests fixtures

Rules:
- Synthetic chain geometry source/topology fixture only.
- Fixtures build small explicit source/topology data.
- No production logic here.
"""

from __future__ import annotations

from scaffold_core.ids import ChainId, SourceEdgeId, SourceMeshId, SourceVertexId, SurfaceModelId, VertexId
from scaffold_core.layer_0_source.snapshot import MeshEdgeRef, MeshVertexRef, SourceMeshSnapshot
from scaffold_core.layer_1_topology.model import Chain, SurfaceModel, Vertex


def make_chain_shape_source_and_topology() -> tuple[SourceMeshSnapshot, SurfaceModel]:
    """Return straight and detoured Chains over explicit source edges."""

    v0 = SourceVertexId("v0")
    v1 = SourceVertexId("v1")
    v2 = SourceVertexId("v2")
    v3 = SourceVertexId("v3")
    v4 = SourceVertexId("v4")
    v5 = SourceVertexId("v5")
    v6 = SourceVertexId("v6")

    e0 = SourceEdgeId("e0")
    e1 = SourceEdgeId("e1")
    e2 = SourceEdgeId("e2")
    e3 = SourceEdgeId("e3")
    e4 = SourceEdgeId("e4")

    source = SourceMeshSnapshot(
        id=SourceMeshId("chain_shape"),
        vertices={
            v0: MeshVertexRef(v0, (0.0, 0.0, 0.0)),
            v1: MeshVertexRef(v1, (1.0, 0.0, 0.0)),
            v2: MeshVertexRef(v2, (2.0, 0.0, 0.0)),
            v3: MeshVertexRef(v3, (0.0, 1.0, 0.0)),
            v4: MeshVertexRef(v4, (1.0, 1.25, 0.0)),
            v5: MeshVertexRef(v5, (2.0, 0.75, 0.0)),
            v6: MeshVertexRef(v6, (3.0, 1.0, 0.0)),
        },
        edges={
            e0: MeshEdgeRef(e0, (v0, v1)),
            e1: MeshEdgeRef(e1, (v1, v2)),
            e2: MeshEdgeRef(e2, (v3, v4)),
            e3: MeshEdgeRef(e3, (v4, v5)),
            e4: MeshEdgeRef(e4, (v5, v6)),
        },
        faces={},
    )

    straight_chain_id = ChainId("chain:straight")
    sawtooth_chain_id = ChainId("chain:sawtooth")
    tv0 = VertexId("vertex:v0")
    tv2 = VertexId("vertex:v2")
    tv3 = VertexId("vertex:v3")
    tv6 = VertexId("vertex:v6")

    topology = SurfaceModel(
        id=SurfaceModelId("surface:chain_shape"),
        chains={
            straight_chain_id: Chain(
                id=straight_chain_id,
                start_vertex_id=tv0,
                end_vertex_id=tv2,
                source_edge_ids=(e0, e1),
            ),
            sawtooth_chain_id: Chain(
                id=sawtooth_chain_id,
                start_vertex_id=tv3,
                end_vertex_id=tv6,
                source_edge_ids=(e2, e3, e4),
            ),
        },
        vertices={
            tv0: Vertex(id=tv0, source_vertex_ids=(v0,)),
            tv2: Vertex(id=tv2, source_vertex_ids=(v2,)),
            tv3: Vertex(id=tv3, source_vertex_ids=(v3,)),
            tv6: Vertex(id=tv6, source_vertex_ids=(v6,)),
        },
    )
    return source, topology
