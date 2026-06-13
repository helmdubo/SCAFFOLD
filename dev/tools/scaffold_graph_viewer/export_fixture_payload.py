"""
Layer: dev tooling

Rules:
- Export Scaffold inspection payloads for the external graph viewer.
- Import scaffold_core as a consumer; do not define Scaffold relations here.
- Do not import Blender.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scaffold_core.pipeline.inspection import inspect_pipeline_context
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.cylinder_tube import (
    make_cylinder_tube_without_caps_with_two_seams_source,
)
from scaffold_core.tests.fixtures.extruded_cross import make_extruded_cross_source
from scaffold_core.tests.fixtures.l_corridor_tunnel import make_l_corridor_tunnel_seamed_folds_source
from scaffold_core.tests.fixtures.tube_with_cap import make_tube_with_cap_source


FIXTURES = {
    "l_corridor": make_l_corridor_tunnel_seamed_folds_source,
    "cylinder_two_seam": make_cylinder_tube_without_caps_with_two_seams_source,
    "extruded_cross": make_extruded_cross_source,
    "tube_with_cap": make_tube_with_cap_source,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a Scaffold fixture graph-viewer payload.")
    parser.add_argument("fixture", choices=sorted(FIXTURES))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--open-dir", action="store_true")
    args = parser.parse_args()

    source = FIXTURES[args.fixture]()
    context = run_pass_1_relations(run_pass_0(source))
    payload = {
        "format": "scaffold_graph_viewer_payload_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "id": str(source.id),
            "name": args.fixture,
            "selected_face_count": len(source.selected_face_ids),
            "face_count": len(source.faces),
        },
        "inspection": inspect_pipeline_context(context, detail="full"),
    }
    out = args.out or Path(__file__).with_name("reports") / f"{args.fixture}.graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out)
    if args.open_dir:
        os.startfile(str(out.parent))  # type: ignore[attr-defined]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
