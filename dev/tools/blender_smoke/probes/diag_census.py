"""Census of G5a island diagnostics and OBLIQUE runs over captures.

Usage, from the repository root:

    python dev/tools/blender_smoke/probes/diag_census.py DIR

Prints each island diagnostic kind (ids masked as #) with its count and the
first captures it occurs in, then the OBLIQUE total and the islands with the
most OBLIQUE runs.
"""

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot  # noqa: E402
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve  # noqa: E402
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations  # noqa: E402

ID = re.compile(r"[\w:.@-]*\d[\w:.@-]*")


def main() -> None:
    kinds: Counter = Counter()
    where: dict[str, set[str]] = {}
    oblique: Counter = Counter()
    for capture in sorted(Path(sys.argv[1]).glob("*.json")):
        solve = run_skeleton_solve(run_pass_1_relations(run_pass_0(load_source_snapshot(capture))))
        for skeleton in solve.skeletons:
            for diagnostic in skeleton.diagnostics:
                kind = ID.sub("#", diagnostic)[:90]
                kinds[kind] += 1
                where.setdefault(kind, set()).add(capture.stem)
            count = sum(1 for role in skeleton.axis_role_by_run.values() if role == "OBLIQUE")
            if count:
                oblique[f"{capture.stem}/{skeleton.island_id}"] += count
    for kind, count in kinds.most_common():
        print(count, kind, sorted(where[kind])[:6])
    print("OBLIQUE", sum(oblique.values()), oblique.most_common(12))


if __name__ == "__main__":
    main()
