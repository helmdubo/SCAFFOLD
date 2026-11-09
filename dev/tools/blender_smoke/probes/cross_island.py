"""Measure how ConnectedDirectionFamilies spread across G5a islands.

Replays SourceMeshSnapshot captures (dump them once with
``run_smoke.py ... --capture-dir DIR``) in pure Python, without Blender.

Usage, from the repository root:

    python dev/tools/blender_smoke/probes/cross_island.py DIR

Per capture and in total it prints:

- families: ConnectedDirectionFamily count;
- multi_island_families: families whose runs land in more than one island;
- role_disagreements: multi-island families whose runs carry both AXIS_A and
  AXIS_B. Axis labels are local to each island frame, so this is an upper
  bound on real disagreement, not a defect count;
- islands, framed_islands: G5a islands and those with a rigid frame.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot  # noqa: E402
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve  # noqa: E402
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations  # noqa: E402


def measure(capture: Path) -> Counter:
    context = run_pass_1_relations(run_pass_0(load_source_snapshot(capture)))
    relations = context.relation_snapshot
    family_of = {
        member: family.id
        for family in relations.connected_direction_families
        for member in family.member_directional_evidence_ids
    }
    solve = run_skeleton_solve(context)
    islands_by_family: dict[str, set[str]] = {}
    roles_by_family: dict[str, set[str]] = {}
    for skeleton in solve.skeletons:
        for run_id, role in skeleton.axis_role_by_run.items():
            family_id = family_of.get(run_id)
            if family_id is None:
                continue
            islands_by_family.setdefault(family_id, set()).add(skeleton.island_id)
            if role in ("AXIS_A", "AXIS_B"):
                roles_by_family.setdefault(family_id, set()).add(role)
    multi = [family_id for family_id, islands in islands_by_family.items() if len(islands) > 1]
    return Counter(
        families=len(relations.connected_direction_families),
        multi_island_families=len(multi),
        role_disagreements=sum(1 for family_id in multi if len(roles_by_family.get(family_id, ())) > 1),
        islands=len(solve.skeletons),
        framed_islands=sum(1 for skeleton in solve.skeletons if skeleton.frame == "UNFOLDED"),
    )


def main() -> None:
    total: Counter = Counter()
    for capture in sorted(Path(sys.argv[1]).glob("*.json")):
        counts = measure(capture)
        total.update(counts)
        print(f"{capture.stem:10s} " + " ".join(f"{key}={value}" for key, value in counts.items()))
    print("TOTAL " + " ".join(f"{key}={value}" for key, value in total.items()))


if __name__ == "__main__":
    main()
