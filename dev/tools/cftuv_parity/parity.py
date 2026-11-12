"""CFTUV parity scoreboard: how much of a reference UV structure Scaffold reproduces.

Pure Python, no Blender. From the repository root:

    python dev/tools/cftuv_parity/parity.py [--object NAME] [--json OUT] [--detail]

Inputs live in dev/tools/cftuv_parity/reference/: <name>.capture.json (the
SourceMeshSnapshot of the object) and <name>.uv.json (reference UVs written by
extract_reference.py). Scaffold is replayed from the capture
(run_pass_0 -> run_pass_1_relations -> run_skeleton_solve). The common frame is
Scaffold's own PatchChain uses: one side of one Chain in one Patch. The tool
defines no Scaffold relation; it only reads pipeline output.

Reference description of a use, from the reference UVs of that patch's own side
face of every chain segment (PatchChainGeometryFacts.segment_side_face_ids):
  straight  every UV point of the chain polyline lies within STRAIGHT_TOL times
            the polyline's UV length of the line through its UV end points;
            a closed chain or one with zero UV chord is never straight.
  axis      U or V when straight and the chord is within AXIS_TOL_DEG of that
            UV axis; else oblique.
  class     AXIS_LINE (straight, on an axis), FREE_LINE (straight, oblique),
            SHAPED (not straight).
  pinned    chain vertices whose corner in a side face carries the pin flag.
  stretch   (UV length / 3D length) / object scale, where the object scale is
            the length-weighted median ratio of its AXIS_LINE uses. A use laid
            straight by "Straighten Strips" shows stretch away from 1.
Uses with an unknown side face are skipped (counted as "unread").

Scaffold description of the same use:
  AXIS_LINE when the use has runs, every run carries the same axis role
  (AXIS_A or AXIS_B) in its island skeleton, at least two of the runs' end
  vertices are pinned, and all pinned run-end vertices share the cross
  coordinate (v for AXIS_A, u for AXIS_B) within LINE_TOL relative to the
  island's pinned extent; otherwise NOT_LINE. Pinned: chain vertices whose
  occurrence on this side has a pinned UV.

Scores per object (weights: 3D chain length, unless noted):
  line_recall   reference AXIS_LINE length that Scaffold also has as AXIS_LINE,
                over all reference AXIS_LINE length.
  false_lines   Scaffold AXIS_LINE length whose reference class is FREE_LINE or
                SHAPED, over all Scaffold AXIS_LINE length.
  pin_cov       (count) reference-pinned boundary corners (patch, vertex
                occurrence) that Scaffold also pins, over reference-pinned ones.
  pin_extra     (count) Scaffold-pinned boundary corners the reference does not
                pin, over Scaffold-pinned ones.
  axis_agree    (count of pairs) pairs of uses in one patch that are AXIS_LINE in
                both descriptions, where "same axis vs different axis" agrees.
                Invariant to quarter-turns of an island: orientation not scored.
  patches       a patch is structured in a description when >= 80% of its
                boundary length is AXIS_LINE there; counts structured in the
                reference / Scaffold / both, out of all patches.
  info only     reference UV island count vs Scaffold island count; reference
                islands split over several Scaffold islands; Scaffold islands
                holding faces of several reference islands (merged).
Not measured: UV coordinates, island orientation, scale between islands, packing.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DIR = Path(__file__).resolve().parent / "reference"
OBJECTS = ("Arc", "building_walls", "collumn", "Main_wall")

STRAIGHT_TOL = 0.01  # max point-to-chord distance over UV length
AXIS_TOL_DEG = 1.0
LINE_TOL = 1e-5  # Scaffold pin cross-coordinate spread over island extent
STRUCTURED_SHARE = 0.8
STRETCH_TOL = 0.1  # info: |stretch - 1| above this counts as stretched

AXIS_LINE = "AXIS_LINE"
FREE_LINE = "FREE_LINE"
SHAPED = "SHAPED"
NOT_LINE = "NOT_LINE"


# ---------------------------------------------------------------- pure parts


def classify_uv_polyline(points, straight_tol=STRAIGHT_TOL, axis_tol_deg=AXIS_TOL_DEG):
    """Return (class, axis, uv_length, max_relative_deviation) of a UV polyline.

    axis is "U", "V" or None. A closed or zero-chord polyline is SHAPED.
    """

    uv_length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    if len(points) < 2 or uv_length <= 0.0:
        return SHAPED, None, uv_length, math.inf
    (u0, v0), (u1, v1) = points[0], points[-1]
    du, dv = u1 - u0, v1 - v0
    chord = math.hypot(du, dv)
    if chord <= 1e-9 * max(uv_length, 1e-12):
        return SHAPED, None, uv_length, math.inf
    deviation = max(abs((u - u0) * dv - (v - v0) * du) / chord for u, v in points) / uv_length
    if deviation > straight_tol:
        return SHAPED, None, uv_length, deviation
    angle = math.degrees(math.atan2(abs(dv), abs(du)))  # 0 = along U, 90 = along V
    if angle <= axis_tol_deg:
        return AXIS_LINE, "U", uv_length, deviation
    if angle >= 90.0 - axis_tol_deg:
        return AXIS_LINE, "V", uv_length, deviation
    return FREE_LINE, None, uv_length, deviation


def weighted_median(pairs):
    """Median of values weighted by weights; pairs = [(value, weight)]."""

    pairs = sorted(p for p in pairs if p[1] > 0)
    if not pairs:
        return None
    half = sum(w for _, w in pairs) / 2.0
    acc = 0.0
    for value, weight in pairs:
        acc += weight
        if acc >= half:
            return value
    return pairs[-1][0]


@dataclass
class Use:
    """One PatchChain use in both descriptions."""

    id: str
    patch_id: str
    length: float  # 3D
    ref_class: str
    ref_axis: str | None
    uv_length: float
    sc_class: str
    sc_axis: str | None
    ref_pins: frozenset = frozenset()  # boundary corner keys
    sc_pins: frozenset = frozenset()
    corners: frozenset = frozenset()
    stretch: float | None = None
    reason: str = ""


@dataclass
class Scores:
    line_recall: float | None = None
    false_lines: float | None = None
    pin_cov: float | None = None
    pin_extra: float | None = None
    axis_agree: float | None = None
    axis_pairs: int = 0
    patches: int = 0
    ref_structured: int = 0
    sc_structured: int = 0
    both_structured: int = 0
    ref_axis_length: float = 0.0
    stretched_share: float | None = None
    extra: dict = field(default_factory=dict)


def _share(numerator, denominator):
    return None if denominator <= 0 else numerator / denominator


def score_uses(uses) -> Scores:
    """Scores over a list of Use records (see module docstring)."""

    scores = Scores()
    ref_axis = [u for u in uses if u.ref_class == AXIS_LINE]
    sc_axis = [u for u in uses if u.sc_class == AXIS_LINE]
    scores.ref_axis_length = sum(u.length for u in ref_axis)
    scores.line_recall = _share(sum(u.length for u in ref_axis if u.sc_class == AXIS_LINE), scores.ref_axis_length)
    scores.false_lines = _share(
        sum(u.length for u in sc_axis if u.ref_class in (FREE_LINE, SHAPED)), sum(u.length for u in sc_axis)
    )
    ref_pins = set().union(*(u.ref_pins for u in uses)) if uses else set()
    sc_pins = set().union(*(u.sc_pins for u in uses)) if uses else set()
    scores.pin_cov = _share(len(ref_pins & sc_pins), len(ref_pins))
    scores.pin_extra = _share(len(sc_pins - ref_pins), len(sc_pins))
    by_patch: dict[str, list[Use]] = {}
    for use in uses:
        by_patch.setdefault(use.patch_id, []).append(use)
    agree = pairs = 0
    for patch_uses in by_patch.values():
        both = [u for u in patch_uses if u.ref_class == AXIS_LINE and u.sc_class == AXIS_LINE]
        for i, a in enumerate(both):
            for b in both[i + 1:]:
                pairs += 1
                agree += (a.ref_axis == b.ref_axis) == (a.sc_axis == b.sc_axis)
    scores.axis_agree = _share(agree, pairs)
    scores.axis_pairs = pairs
    scores.patches = len(by_patch)
    for patch_uses in by_patch.values():
        total = sum(u.length for u in patch_uses)
        ref_ok = total > 0 and sum(u.length for u in patch_uses if u.ref_class == AXIS_LINE) >= STRUCTURED_SHARE * total
        sc_ok = total > 0 and sum(u.length for u in patch_uses if u.sc_class == AXIS_LINE) >= STRUCTURED_SHARE * total
        scores.ref_structured += ref_ok
        scores.sc_structured += sc_ok
        scores.both_structured += ref_ok and sc_ok
    with_stretch = [u for u in uses if u.stretch is not None]
    scores.stretched_share = _share(
        sum(u.length for u in with_stretch if abs(u.stretch - 1.0) > STRETCH_TOL), sum(u.length for u in with_stretch)
    )
    return scores


# ---------------------------------------------------------- pipeline reading


def _replay(capture: Path):
    sys.path.insert(0, str(REPO_ROOT))
    from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
    from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
    from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations

    context = run_pass_1_relations(run_pass_0(load_source_snapshot(capture)))
    return context, run_skeleton_solve(context)


def _reference_corners(reference):
    uv, pin = {}, {}
    for face_id, corners in reference["faces"].items():
        for vertex, u, v, pinned in corners:
            uv[(face_id, f"v{vertex}")] = (u, v)
            pin[(face_id, f"v{vertex}")] = bool(pinned)
    return uv, pin


def build_uses(context, solve, reference):
    """Both descriptions for every readable PatchChain use; plus unread count."""

    topology = context.topology_snapshot
    geometry = context.geometry_facts
    relations = context.relation_snapshot
    ref_uv, ref_pin = _reference_corners(reference)
    runs_by_use: dict[str, list] = {}
    for run in relations.patch_chain_directional_evidence:
        runs_by_use.setdefault(str(run.patch_chain_id), []).append(run)
    curve_uses = {
        str(piece.patch_chain_id)
        for piece in relations.patch_chain_shape_relations
        if piece.kind.value == "SURFACE_CURVE"
    }
    skeleton_by_island = {s.island_id: s for s in solve.skeletons}
    causes_by_island = {s.island_id: oblique_causes(s) for s in solve.skeletons}
    island_of_patch = solve.assembly.island_by_patch_id
    pinned_uv = {(v.vertex_id, v.patch_id): v.uv for v in solve.vertices if v.pinned}
    points_by_island: dict[str, list] = {}
    for v in solve.vertices:
        points_by_island.setdefault(v.island_id, []).append(v.uv)
    extent_by_island = {
        island_id: max(
            max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts), 1.0
        )
        for island_id, pts in points_by_island.items()
    }
    corner_vertex = solve.vertex_by_face_corner
    uses, unread = [], 0
    for pc_id, pc in topology.patch_chains.items():
        pc_id, patch_id = str(pc_id), str(pc.patch_id)
        chain_facts = geometry.chain_facts.get(pc.chain_id)
        side = geometry.patch_chain_facts.get(pc.id)
        if chain_facts is None or side is None or not chain_facts.segments:
            unread += 1
            continue
        faces = side.segment_side_face_ids
        if len(faces) != len(chain_facts.segments) or any(f is None for f in faces):
            unread += 1
            continue
        points, corners = [], []  # corners: (face, source vertex)
        for segment, face in zip(chain_facts.segments, faces):
            face = str(face)
            start, end = str(segment.start_source_vertex_id), str(segment.end_source_vertex_id)
            if (face, start) not in ref_uv or (face, end) not in ref_uv:
                break
            if not points:
                points.append(ref_uv[(face, start)])
                corners.append((face, start))
            points.append(ref_uv[(face, end)])
            corners.append((face, end))
        else:
            ref_class, ref_axis, uv_length, _ = classify_uv_polyline(points)
            length = float(chain_facts.length)
            keys = {}
            for face, source in corners:
                key = (patch_id, str(corner_vertex.get((face, source), f"{face}:{source}")))
                keys[key] = keys.get(key, False) or ref_pin[(face, source)]
            ref_pins = frozenset(k for k, p in keys.items() if p)
            sc_pins = frozenset(k for k in keys if (k[1], patch_id) in pinned_uv)
            island_id = island_of_patch.get(patch_id)
            skeleton = skeleton_by_island.get(island_id)
            sc_class, sc_axis, reason = _scaffold_use(
                runs_by_use.get(pc_id, ()), skeleton, patch_id, pinned_uv, extent_by_island.get(island_id, 1.0),
                causes_by_island.get(island_id),
            )
            if sc_class == NOT_LINE:
                tags = [reason]
                if skeleton is not None and skeleton.frame == "FRAME_FREE":
                    tags.append("FRAME_FREE")
                if pc_id in curve_uses:
                    tags.append("SURFACE_CURVE")
                reason = "+".join(tags)
            uses.append(
                Use(
                    id=pc_id, patch_id=patch_id, length=length, ref_class=ref_class, ref_axis=ref_axis,
                    uv_length=uv_length, sc_class=sc_class, sc_axis=sc_axis, ref_pins=ref_pins,
                    sc_pins=sc_pins, corners=frozenset(keys), reason=reason,
                )
            )
            continue
        unread += 1
    scale = weighted_median([(u.uv_length / u.length, u.length) for u in uses if u.ref_class == AXIS_LINE and u.length > 0])
    for use in uses:
        if scale and use.length > 0:
            use.stretch = use.uv_length / use.length / scale
    return uses, unread, scale


_OBLIQUE_DIAGNOSTICS = (
    ("axis bipartition conflict", "OBLIQUE_CONFLICT"),
    ("island line not straight", "OBLIQUE_LINE_BENT"),
    ("island line jogs", "OBLIQUE_JOG"),
    ("patch outside the rigid island frame", "OBLIQUE_OUTSIDE_FRAME"),
)


def oblique_causes(skeleton):
    """Subject (line, run or patch id) -> cause, read from '<kind>: <subject> -> OBLIQUE' diagnostics."""

    causes = {}
    for message in skeleton.diagnostics:
        if not message.endswith("-> OBLIQUE"):
            continue
        for prefix, cause in _OBLIQUE_DIAGNOSTICS:
            if message.startswith(prefix):
                subject = message.split(": ", 1)[1].rsplit(" -> ", 1)[0]
                causes[subject] = cause
    return causes


def _oblique_reason(runs, skeleton, patch_id, causes):
    for run in runs:
        if skeleton.axis_role_by_run.get(run.id) == "AXIS_A" or skeleton.axis_role_by_run.get(run.id) == "AXIS_B":
            continue
        line = skeleton.line_by_run.get(run.id)
        for subject in (line, run.id, patch_id):
            if subject in causes:
                return causes[subject]
        if line is None:
            return "OBLIQUE_NO_LINE"
    # Frame-free: the line never met an AXIS line orthogonally; framed: off-axis.
    return "OBLIQUE_UNLINKED" if skeleton.frame == "FRAME_FREE" else "OBLIQUE_OFF_AXIS"


def _scaffold_use(runs, skeleton, patch_id, pinned_uv, extent, causes=None):
    """(class, axis, failure reason) of one use in Scaffold's skeleton."""

    if not runs:
        return NOT_LINE, None, "NO_RUNS"
    if skeleton is None:
        return NOT_LINE, None, "NO_ISLAND"
    roles = {skeleton.axis_role_by_run.get(run.id, "NONE") for run in runs}
    if len(roles) > 1 and roles <= {"AXIS_A", "AXIS_B"}:
        return NOT_LINE, None, "MIXED_ROLES"
    role = next(iter(roles))
    if len(roles) > 1 or role not in ("AXIS_A", "AXIS_B"):
        return NOT_LINE, None, _oblique_reason(runs, skeleton, patch_id, causes or {})
    cross = []
    for run in runs:
        for end in ("START", "END"):
            vertex = skeleton.vertex_by_run_end.get((run.id, end))
            uv = pinned_uv.get((str(vertex), patch_id)) if vertex is not None else None
            if uv is not None:
                cross.append(uv[1] if role == "AXIS_A" else uv[0])
    if len(cross) < 2:
        return NOT_LINE, None, "ENDS_UNPINNED"
    if max(cross) - min(cross) > LINE_TOL * extent:
        return NOT_LINE, None, "PINS_OFF_LINE"
    return AXIS_LINE, role, ""


def island_info(solve, reference):
    island_of_face = {}
    for face_id, patch_id in solve.patch_by_source_face.items():
        island_of_face[face_id] = solve.assembly.island_by_patch_id.get(patch_id)
    split = sum(1 for faces in reference["islands"] if len({island_of_face.get(f) for f in faces}) > 1)
    ref_of_face = {f: i for i, faces in enumerate(reference["islands"]) for f in faces}
    refs_by_island: dict = {}
    for face_id, island_id in island_of_face.items():
        refs_by_island.setdefault(island_id, set()).add(ref_of_face.get(face_id))
    merged = sum(1 for refs in refs_by_island.values() if len(refs) > 1)
    return {
        "ref_islands": len(reference["islands"]),
        "sc_islands": len(solve.assembly.islands),
        "ref_split": split,
        "sc_merged": merged,
    }


def top_gaps(uses, context, solve, count=3):
    """Patches with the most reference AXIS_LINE length that Scaffold misses."""

    missed: dict[str, float] = {}
    reasons: dict[str, Counter] = {}
    for use in uses:
        if use.ref_class == AXIS_LINE and use.sc_class != AXIS_LINE:
            missed[use.patch_id] = missed.get(use.patch_id, 0.0) + use.length
            reasons.setdefault(use.patch_id, Counter())[use.reason] += use.length
    topology = context.topology_snapshot
    diag_count = Counter()
    for skeleton in solve.skeletons:
        diag_count[skeleton.island_id] = len(skeleton.diagnostics)
    rows = []
    for patch_id, length in sorted(missed.items(), key=lambda item: -item[1])[:count]:
        island_id = solve.assembly.island_by_patch_id.get(patch_id)
        rows.append(
            {
                "patch": patch_id,
                "faces": len(topology.patches[patch_id].source_face_ids),
                "missed": round(length, 4),
                "reason": reasons[patch_id].most_common(1)[0][0],
                "island": island_id,
                "island_diagnostics": diag_count.get(island_id, 0),
            }
        )
    return rows


def evaluate(name):
    reference = json.loads((REFERENCE_DIR / f"{name}.uv.json").read_text())
    context, solve = _replay(REFERENCE_DIR / f"{name}.capture.json")
    uses, unread, scale = build_uses(context, solve, reference)
    scores = score_uses(uses)
    return {
        "object": name,
        "patches_total": len(context.topology_snapshot.patches),
        "uses": len(uses),
        "unread_uses": unread,
        "scale": scale,
        "scores": {k: v for k, v in scores.__dict__.items() if k != "extra"},
        "islands": island_info(solve, reference),
        "gaps": top_gaps(uses, context, solve),
        "_uses": uses,
    }


# -------------------------------------------------------------------- output


def _pct(value):
    return "  -  " if value is None else f"{100 * value:4.0f}%"


def _table_row(name, r):
    s = r["scores"]
    i = r["islands"]
    structured = f"{s['ref_structured']}/{s['sc_structured']}/{s['both_structured']} of {s['patches']}"
    islands = f"{i['ref_islands']}/{i['sc_islands']}"
    split = f"{i['ref_split']}/{i['sc_merged']}"
    scale = "" if r["scale"] is None else format(r["scale"], ".3f")
    return (
        f"{name:14s} {_pct(s['line_recall'])}  {_pct(s['false_lines'])}  {_pct(s['pin_cov'])}  {_pct(s['pin_extra'])}"
        f"  {_pct(s['axis_agree'])}  {structured:>20s}  {islands:>8s}  {split:>7s}  {scale}"
    )


def _total(results):
    # Patch ids repeat across objects: prefix them for the total.
    prefixed = [
        Use(**{**u.__dict__, "patch_id": f"{r['object']}:{u.patch_id}",
               "ref_pins": frozenset((r["object"],) + k for k in u.ref_pins),
               "sc_pins": frozenset((r["object"],) + k for k in u.sc_pins)})
        for r in results for u in r["_uses"]
    ]
    scores = score_uses(prefixed)
    islands = {k: sum(r["islands"][k] for r in results) for k in results[0]["islands"]}
    return {"scores": {k: v for k, v in scores.__dict__.items() if k != "extra"}, "islands": islands, "scale": None}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="CFTUV parity scoreboard")
    parser.add_argument("--object", action="append")
    parser.add_argument("--json")
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args(argv)
    results = [evaluate(name) for name in (args.object or OBJECTS)]
    print(
        "object         recall  false  pincov  pinext  axisagr  structd ref/sc/both  isl r/s  spl/mrg  scale"
    )
    for r in results:
        print(_table_row(r["object"], r))
    total = _total(results)
    if len(results) > 1:
        print(_table_row("TOTAL", total))
    for r in results:
        s = r["scores"]
        print(
            f"{r['object']}: patches={r['patches_total']} uses={r['uses']} unread={r['unread_uses']}"
            f" ref_axis_len={s['ref_axis_length']:.2f} axis_pairs={s['axis_pairs']}"
            f" stretched(>{STRETCH_TOL:.0%})={_pct(s['stretched_share']).strip()}"
        )
        for gap in r["gaps"]:
            print(
                f"  gap {gap['patch']} faces={gap['faces']} missed={gap['missed']:.2f}"
                f" reason={gap['reason']} island_diags={gap['island_diagnostics']}"
            )
        if args.detail:
            for u in sorted(r["_uses"], key=lambda u: (u.patch_id, u.id)):
                print(
                    f"    {u.id} len={u.length:.3f} ref={u.ref_class}/{u.ref_axis} sc={u.sc_class}/{u.sc_axis}"
                    f" stretch={'-' if u.stretch is None else format(u.stretch, '.2f')}"
                    f" pins ref={len(u.ref_pins)} sc={len(u.sc_pins)} {u.reason}"
                )
    if args.json:
        payload = {
            "tolerances": {"straight": STRAIGHT_TOL, "axis_deg": AXIS_TOL_DEG, "line": LINE_TOL,
                           "structured_share": STRUCTURED_SHARE},
            "objects": [{k: v for k, v in r.items() if k != "_uses"} for r in results],
            "total": total if len(results) > 1 else None,
        }
        Path(args.json).write_text(json.dumps(payload, indent=1))


if __name__ == "__main__":
    main()
