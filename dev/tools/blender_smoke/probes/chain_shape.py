"""Measure PatchChainShapeRelation pieces (chain shape Stage A) on captures.

Replays SourceMeshSnapshot captures (dump them once with
``run_smoke.py ... --capture-dir DIR``) in pure Python, without Blender.

Usage, from the repository root:

    python dev/tools/blender_smoke/probes/chain_shape.py DIR [--detail]

Per capture and in total it prints:

- line, curve, unresolved: pieces by PatchChainShapeKind;
- multi_lines: SURFACE_LINE pieces of more than one segment;
- multi_lines_one_family / multi_lines_split: of those, pieces whose
  directional runs all lie in one ConnectedDirectionFamily today, and pieces
  whose runs do not (a regression signal for later stages);
- law_mismatches: PATCH_CHAIN_SHAPE_LAW_MISMATCH diagnostics;
- unresolved_occurrences: PATCH_CHAIN_SHAPE_OCCURRENCE_UNRESOLVED diagnostics;
- curve_segs_N: SURFACE_CURVE pieces of N segments.

With --detail it also lists every SURFACE_CURVE piece with its segment count,
and the patches of UNRESOLVED pieces and law mismatches.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot  # noqa: E402
from scaffold_core.layer_3_relations.patch_chain_shape import (  # noqa: E402
    LAW_MISMATCH_CODE,
    UNRESOLVED_OCCURRENCE_CODE,
)
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations  # noqa: E402


def measure(capture: Path, detail: bool) -> Counter:
    relations = run_pass_1_relations(run_pass_0(load_source_snapshot(capture))).relation_snapshot
    family_of = {
        member: family.id
        for family in relations.connected_direction_families
        for member in family.member_directional_evidence_ids
    }
    runs_by_use: dict[str, list] = {}
    for run in relations.patch_chain_directional_evidence:
        runs_by_use.setdefault(str(run.patch_chain_id), []).append(run)
    counts = Counter(line=0, curve=0, unresolved=0, multi_lines=0, multi_lines_one_family=0, multi_lines_split=0)
    for piece in relations.patch_chain_shape_relations:
        kind = piece.kind.value
        counts[{"SURFACE_LINE": "line", "SURFACE_CURVE": "curve"}.get(kind, "unresolved")] += 1
        if kind == "SURFACE_CURVE":
            counts[f"curve_segs_{len(piece.segment_indices)}"] += 1
            if detail:
                print(f"  curve {piece.patch_chain_id} segs={len(piece.segment_indices)}")
        if kind == "UNRESOLVED" and detail:
            print(f"  unresolved {piece.patch_chain_id} segs={len(piece.segment_indices)}")
        if kind != "SURFACE_LINE" or len(piece.segment_indices) < 2:
            continue
        counts["multi_lines"] += 1
        segments = set(piece.segment_indices)
        families = {
            family_of.get(run.id)
            for run in runs_by_use.get(str(piece.patch_chain_id), ())
            if set(run.segment_indices) & segments
        }
        if len(families) == 1 and None not in families:
            counts["multi_lines_one_family"] += 1
        else:
            counts["multi_lines_split"] += 1
    codes = Counter(diagnostic.code for diagnostic in relations.diagnostics)
    counts["law_mismatches"] = codes.get(LAW_MISMATCH_CODE, 0)
    counts["unresolved_occurrences"] = codes.get(UNRESOLVED_OCCURRENCE_CODE, 0)
    if detail:
        for diagnostic in relations.diagnostics:
            if diagnostic.code in (LAW_MISMATCH_CODE, UNRESOLVED_OCCURRENCE_CODE):
                print(f"  {diagnostic.code} {diagnostic.message}")
    return counts


def main() -> None:
    detail = "--detail" in sys.argv
    total: Counter = Counter()
    for capture in sorted(Path(sys.argv[1]).glob("*.json")):
        if detail:
            print(capture.stem)
        counts = measure(capture, detail)
        total.update(counts)
        print(f"{capture.stem:10s} " + " ".join(f"{key}={value}" for key, value in counts.items()))
    print("TOTAL " + " ".join(f"{key}={value}" for key, value in total.items()))


if __name__ == "__main__":
    main()
