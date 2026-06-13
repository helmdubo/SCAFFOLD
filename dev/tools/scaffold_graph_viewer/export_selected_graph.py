"""
Layer: dev tooling

Rules:
- Blender-side JSON exporter for the external graph viewer.
- Reads meshes only through scaffold_core.layer_0_source.blender_io.
- Writes inspection JSON only; does not draw overlays, write UVs or solve.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def default_output_path(context: object) -> Path:
    """Return the default graph-viewer JSON path for the active Blender object."""

    obj = getattr(context, "active_object", None) or getattr(context, "object", None)
    object_name = getattr(obj, "name", "active_mesh")
    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in object_name)
    return Path(__file__).with_name("reports") / f"{safe_name}.graph.json"


def build_payload(context: object) -> dict[str, object]:
    """Build the graph-viewer payload from the active Blender mesh context."""

    from scaffold_core.layer_0_source.blender_io import read_source_mesh_from_blender
    from scaffold_core.pipeline.inspection import inspect_pipeline_context
    from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations

    blender_context = context
    source = read_source_mesh_from_blender(context)
    pipeline_context = run_pass_1_relations(run_pass_0(source))
    obj = getattr(blender_context, "active_object", None) or getattr(blender_context, "object", None)
    object_name = obj.name if obj is not None else "active_mesh"
    return {
        "format": "scaffold_graph_viewer_payload_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "id": str(source.id),
            "name": object_name,
            "mode": obj.mode if obj is not None else "",
            "selected_face_count": len(source.selected_face_ids),
            "face_count": len(source.faces),
            "selection_fallback_used": not bool(source.selected_face_ids),
            "selection_fallback_reason": (
                "empty selected_face_ids; Pass 0 uses all faces"
                if not source.selected_face_ids
                else ""
            ),
        },
        "inspection": inspect_pipeline_context(pipeline_context, detail="full"),
    }


def write_payload(context: object, path: str | Path | None = None) -> Path:
    """Write the active mesh graph-viewer payload to JSON."""

    payload = build_payload(context)
    out = Path(path) if path else default_output_path(context)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> Path:
    try:
        import bpy
    except ImportError as exc:  # pragma: no cover - Blender-only script
        raise RuntimeError("Run export_selected_graph.py inside Blender") from exc

    out = write_payload(bpy.context)
    print(f"[scaffold graph viewer] wrote {out}")
    print(
        "[scaffold graph viewer] open dev/tools/scaffold_graph_viewer/index.html "
        "and drop this JSON into the canvas"
    )
    return out


if __name__ == "__main__":
    main()
