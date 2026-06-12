"""Source mesh snapshot JSON capture for headless repro of artist meshes.

Dump the exact SourceMeshSnapshot a Blender overlay rebuild consumed, so the
Architect can replay the artist's geometry through the pipeline without
Blender. Debug-side only; scaffold_core stays untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dump_source_snapshot(snapshot: Any, path: str | Path) -> Path:
    payload = {
        "format": "scaffold_source_snapshot_v1",
        "id": str(snapshot.id),
        "vertices": {
            str(vertex_id): [float(c) for c in ref.position]
            for vertex_id, ref in snapshot.vertices.items()
        },
        "edges": {
            str(edge_id): [str(v) for v in ref.vertex_ids]
            for edge_id, ref in snapshot.edges.items()
        },
        "faces": {
            str(face_id): {
                "vertex_ids": [str(v) for v in ref.vertex_ids],
                "edge_ids": [str(e) for e in ref.edge_ids],
            }
            for face_id, ref in snapshot.faces.items()
        },
        "selected_face_ids": [str(f) for f in snapshot.selected_face_ids],
        "selection_fallback_used": not bool(snapshot.selected_face_ids),
        "selection_fallback_reason": (
            "empty selected_face_ids; Pass 0 falls back to all faces"
            if not snapshot.selected_face_ids
            else ""
        ),
        "marks": [
            {"kind": mark.kind.value, "target_id": str(mark.target_id)}
            for mark in snapshot.marks
        ],
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return out


def load_source_snapshot(path: str | Path) -> Any:
    from scaffold_core.ids import (
        SourceEdgeId,
        SourceFaceId,
        SourceMeshId,
        SourceVertexId,
    )
    from scaffold_core.layer_0_source.marks import SourceMark, SourceMarkKind
    from scaffold_core.layer_0_source.snapshot import (
        MeshEdgeRef,
        MeshFaceRef,
        MeshVertexRef,
        SourceMeshSnapshot,
    )

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data.get("format") == "scaffold_source_snapshot_v1"
    vertices = {
        SourceVertexId(k): MeshVertexRef(SourceVertexId(k), tuple(v))
        for k, v in data["vertices"].items()
    }
    edges = {
        SourceEdgeId(k): MeshEdgeRef(
            SourceEdgeId(k), (SourceVertexId(v[0]), SourceVertexId(v[1]))
        )
        for k, v in data["edges"].items()
    }
    faces = {
        SourceFaceId(k): MeshFaceRef(
            SourceFaceId(k),
            tuple(SourceVertexId(v) for v in f["vertex_ids"]),
            tuple(SourceEdgeId(e) for e in f["edge_ids"]),
        )
        for k, f in data["faces"].items()
    }
    return SourceMeshSnapshot(
        id=SourceMeshId(data["id"]),
        vertices=vertices,
        edges=edges,
        faces=faces,
        selected_face_ids=tuple(SourceFaceId(f) for f in data.get("selected_face_ids", ())),
        marks=tuple(
            SourceMark(kind=SourceMarkKind(m["kind"]), target_id=SourceEdgeId(m["target_id"]))
            for m in data.get("marks", ())
        ),
    )
