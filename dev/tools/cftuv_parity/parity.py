"""CFTUV parity scoreboard: how much of a reference UV structure Scaffold reproduces.

Pure Python, no Blender. From the repository root:

    python dev/tools/cftuv_parity/parity.py [--object NAME] [--json OUT] [--detail]

Inputs live in dev/tools/cftuv_parity/reference/: <name>.capture.json (the
SourceMeshSnapshot of the object) and <name>.uv.json (reference UVs written by
extract_reference.py). Scaffold is replayed from the capture
(run_pass_0 -> run_pass_1_relations -> run_pass_2_features -> run_skeleton_solve),
with straighten_strips as in STRAIGHTEN_STRIPS. The common frame is
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

Shape agreement (WHERE the pins are, not only which corners are pinned):
  common pins   boundary corners (patch, vertex occurrence) pinned in both
                descriptions, the same keys as pin_cov. Scaffold UV = the
                pinned UV of that occurrence (metres); reference UV = the UV of
                the reference-pinned face corner of that key (the smallest
                (face, vertex) when several).
  pair test     pairwise distances are invariant to rotation (any angle,
                quarter turns included), translation and MIRRORING (a mirrored
                island scores 100%); uniform scale is the object scale s. A
                pair agrees when
                |d_scaffold * s - d_reference| <= max(SHAPE_REL_TOL * d_reference,
                SHAPE_EXTENT_TOL * reference UV extent of the group), the extent
                being max(du, dv) of the reference UVs of the group's faces.
                All pairs when there are at most SHAPE_MAX_PAIRS; otherwise every
                k-th pair (k = ceil(pairs / SHAPE_MAX_PAIRS)) in sorted key order.
                No randomness.
  groups        only corners the reference laid rigidly together are compared:
                a group is the common pins of one patch (or one Scaffold island)
                that lie in ONE reference UV island (the island of the face the
                reference UV is read from). A patch or island whose pins lie in
                several reference islands is compared per reference island and
                counted as "spread" (patches/islands over several ref islands).
  not scored    a group with fewer than SHAPE_MIN_POINTS common pins, or no
                object scale: left out, never counted as 100%.
  shape/torn    groups from patches. shape = agreeing pairs over all tested
                pairs of the object (pair-weighted mean); torn = scored groups
                whose own agreement is below TORN_BELOW ("torn/scored").
  ishape/itorn  the same over groups from Scaffold islands, which also catches
                patches placed wrongly against each other inside one island.
                Coincident points (e.g. the two sides of a rigid seam: same
                Scaffold UV and same reference UV) are kept once.
  Strips the reference laid straight (stretch away from 1, Straighten Strips)
  are compared as they are, since Scaffold replays the same option: a strip
  the reference straightened and Scaffold did not shows as torn, which is
  correct.
Corner turn (information; the corner law of a solved, unmirrored layout):
  at a Layer 3 RunCornerRelation of kind RIGHT the run with endpoint role END
  arrives and the run with role START leaves, both along the patch's boundary
  loop. A convex corner (interior_angle_sum < pi) must turn left in the solved
  coordinates of the two runs' ends, a reflex corner right. Checked: both runs
  in one island, all four run-end coordinates solved, a clear turn
  (|cross| >= TURN_MIN_SINE times the two lengths). turn = corners with the
  law / corners checked; mirrored = islands with more corners against the law
  than with it.
Not measured: island orientation, scale between islands, packing.
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
# The CFTUV "Straighten Strips" option each reference was made with; Scaffold
# replays Pass 2 with the same FeatureOptions.straighten_strips.
STRAIGHTEN_STRIPS = {"Arc": True, "building_walls": False, "collumn": True, "Main_wall": False}

STRAIGHT_TOL = 0.01  # max point-to-chord distance over UV length
AXIS_TOL_DEG = 1.0
LINE_TOL = 1e-5  # Scaffold pin cross-coordinate spread over island extent
STRUCTURED_SHARE = 0.8
STRETCH_TOL = 0.1  # info: |stretch - 1| above this counts as stretched
SHAPE_REL_TOL = 0.02  # pair distance tolerance, share of the reference distance
SHAPE_EXTENT_TOL = 0.01  # tolerance floor, share of the group's reference UV extent
SHAPE_MAX_PAIRS = 300
SHAPE_MIN_POINTS = 3
TORN_BELOW = 0.9
TURN_MIN_SINE = 0.5  # corner turn: a clear turn in the solved layout

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
    ref_corner: dict = field(default_factory=dict)  # ref-pinned key -> (face, source vertex)


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


def sample_pairs(count, max_pairs=SHAPE_MAX_PAIRS):
    """Index pairs (i < j) of count points: all, or every k-th in row order when more than max_pairs."""

    total = count * (count - 1) // 2
    step = max(1, math.ceil(total / max_pairs))
    pairs, start = [], 0
    for i in range(count):
        row = count - 1 - i
        first = -(-start // step) * step
        pairs.extend((i, i + 1 + index - start) for index in range(first, start + row, step))
        start += row
    return pairs


def shape_agreement(points, scale, extent):
    """(tested pairs, agreeing pairs) of [(scaffold_uv, reference_uv)] points, or None when not scored."""

    if not scale or len(points) < SHAPE_MIN_POINTS:
        return None
    floor = SHAPE_EXTENT_TOL * extent
    pairs = sample_pairs(len(points))
    agree = 0
    for i, j in pairs:
        d_sc = math.dist(points[i][0], points[j][0]) * scale
        d_ref = math.dist(points[i][1], points[j][1])
        agree += abs(d_sc - d_ref) <= max(SHAPE_REL_TOL * d_ref, floor)
    return len(pairs), agree


def summarize_shapes(results):
    """{"shape", "torn", "scored", "pairs"} over {group: (pairs, agree) or None}."""

    scored = {g: r for g, r in results.items() if r is not None and r[0] > 0}
    pairs = sum(r[0] for r in scored.values())
    return {
        "shape": _share(sum(r[1] for r in scored.values()), pairs),
        "torn": sum(1 for r in scored.values() if r[1] / r[0] < TORN_BELOW),
        "scored": len(scored),
        "pairs": pairs,
    }


def _worst(rows, count=3):
    torn = [r for r in rows if r["agreement"] < TORN_BELOW]
    return sorted(torn, key=lambda r: (r["agreement"], -r["faces"]))[:count]


def _uv_extent(points):
    if not points:
        return 0.0
    return max(max(p[0] for p in points) - min(p[0] for p in points), max(p[1] for p in points) - min(p[1] for p in points))


def shape_scores(uses, context, solve, reference, scale):
    """Patch and island shape agreement (see module docstring) plus the worst torn groups."""

    ref_uv, _ = _reference_corners(reference)
    ref_island_of_face = {f: i for i, faces in enumerate(reference["islands"]) for f in faces}
    pinned_uv = {(v.vertex_id, v.patch_id): v.uv for v in solve.vertices if v.pinned}
    island_of_patch = solve.assembly.island_by_patch_id
    topology = context.topology_snapshot
    common: dict[str, dict] = {}  # patch -> key -> (scaffold uv, reference uv, reference island)
    for use in uses:
        for key in use.ref_pins & use.sc_pins:
            corner = use.ref_corner.get(key)
            sc_uv = pinned_uv.get((key[1], key[0]))
            if corner is None or sc_uv is None:
                continue
            common.setdefault(use.patch_id, {})[key] = (tuple(sc_uv), ref_uv[corner], ref_island_of_face.get(corner[0]))

    def faces_extent(face_ids, ref_island=None):
        return _uv_extent([
            (u, v) for f in face_ids if ref_island is None or ref_island_of_face.get(f) == ref_island
            for _vertex, u, v, _pin in reference["faces"].get(f, ())
        ])

    # Group = one patch x one reference island (a patch the reference cut
    # into several islands is compared per piece).
    patch_results, patch_rows, patch_spread = {}, [], 0
    for patch_id in sorted(common):
        parts: dict = {}
        for key in sorted(common[patch_id]):
            sc, ref, ref_island = common[patch_id][key]
            parts.setdefault(ref_island, []).append((sc, ref))
        patch_spread += len(parts) > 1
        patch_faces = [str(f) for f in topology.patches[patch_id].source_face_ids]
        for ref_island in sorted(parts, key=str):
            faces = [f for f in patch_faces if ref_island_of_face.get(f) == ref_island]
            result = shape_agreement(parts[ref_island], scale, faces_extent(faces, ref_island))
            patch_results[(patch_id, ref_island)] = result
            if result is not None and result[0] > 0:
                name = patch_id if len(parts) == 1 else f"{patch_id}&ref{ref_island}"
                patch_rows.append({"patch": name, "faces": len(faces), "common_pins": len(parts[ref_island]),
                                   "agreement": round(result[1] / result[0], 4)})

    faces_by_island: dict = {}
    for face_id, patch_id in solve.patch_by_source_face.items():
        faces_by_island.setdefault(island_of_patch.get(patch_id), []).append(str(face_id))
    # Group = one Scaffold island x one reference island: only corners the
    # reference also laid rigidly together are compared.
    by_part: dict = {}
    for patch_id in sorted(common):
        for key in sorted(common[patch_id]):
            sc, ref, ref_island = common[patch_id][key]
            by_part.setdefault((island_of_patch.get(patch_id), ref_island), []).append((sc, ref))
    ref_islands_of: dict = {}
    for island_id, ref_island in by_part:
        ref_islands_of.setdefault(island_id, set()).add(ref_island)
    island_results, island_rows = {}, []
    for part in sorted(by_part, key=lambda part: (str(part[0]), str(part[1]))):
        entries, seen = [], set()
        for sc, ref in by_part[part]:
            point = (round(sc[0], 9), round(sc[1], 9), round(ref[0], 7), round(ref[1], 7))
            if point not in seen:
                seen.add(point)
                entries.append((sc, ref))
        island_id, ref_island = part
        faces = [f for f in faces_by_island.get(island_id, ()) if ref_island_of_face.get(f) == ref_island]
        result = shape_agreement(entries, scale, faces_extent(faces, ref_island))
        island_results[part] = result
        if result is not None and result[0] > 0:
            name = str(island_id) if len(ref_islands_of[island_id]) == 1 else f"{island_id}&ref{ref_island}"
            island_rows.append({"island": name, "faces": len(faces), "common_pins": len(entries),
                                "agreement": round(result[1] / result[0], 4)})
    island_spread = sum(1 for refs in ref_islands_of.values() if len(refs) > 1)

    patch_summary = summarize_shapes(patch_results)
    island_summary = summarize_shapes(island_results)
    return {
        **patch_summary,
        "spread": patch_spread,
        "ishape": island_summary["shape"],
        "itorn": island_summary["torn"],
        "iscored": island_summary["scored"],
        "ipairs": island_summary["pairs"],
        "ispread": island_spread,
        "torn_patches": _worst(patch_rows),
        "torn_islands": _worst(island_rows),
        "_agree": sum(r[1] for r in patch_results.values() if r),
        "_iagree": sum(r[1] for r in island_results.values() if r),
    }


def corner_turns(relations, solve):
    """(corners with the corner law, corners checked, mirrored islands); see the docstring."""

    skeleton_of_run = {
        run_id: skeleton for skeleton in solve.skeletons for run_id in skeleton.axis_role_by_run
    }
    with_by_island: Counter = Counter()
    against_by_island: Counter = Counter()
    for corner in relations.run_corner_relations:
        if corner.kind.value != "RIGHT":
            continue
        run_by_role = {
            corner.first_endpoint_role.value: corner.first_directional_evidence_id,
            corner.second_endpoint_role.value: corner.second_directional_evidence_id,
        }
        arriving, leaving = run_by_role.get("END"), run_by_role.get("START")
        skeleton = skeleton_of_run.get(arriving)
        if leaving is None or skeleton is None or skeleton_of_run.get(leaving) is not skeleton:
            continue
        points = []
        for run_id, role in ((arriving, "START"), (arriving, "END"), (leaving, "START"), (leaving, "END")):
            node = skeleton.node_by_run_end.get((run_id, role))
            a = skeleton.axis_a.coordinate_by_node.get(node)
            b = skeleton.axis_b.coordinate_by_node.get(node)
            if a is None or b is None:
                break
            points.append((a, b))
        if len(points) != 4:
            continue
        first = (points[1][0] - points[0][0], points[1][1] - points[0][1])
        second = (points[3][0] - points[2][0], points[3][1] - points[2][1])
        cross = first[0] * second[1] - first[1] * second[0]
        if abs(cross) < TURN_MIN_SINE * math.hypot(*first) * math.hypot(*second) or cross == 0.0:
            continue
        if (cross > 0.0) == (corner.interior_angle_sum < math.pi):
            with_by_island[skeleton.island_id] += 1
        else:
            against_by_island[skeleton.island_id] += 1
    with_law = sum(with_by_island.values())
    checked = with_law + sum(against_by_island.values())
    mirrored = sum(1 for island, count in against_by_island.items() if count > with_by_island[island])
    return with_law, checked, mirrored


# ---------------------------------------------------------- pipeline reading


def _replay(capture: Path, straighten_strips: bool = False):
    sys.path.insert(0, str(REPO_ROOT))
    from dev.tools.scaffold_graph_debug.snapshot_io import load_source_snapshot
    from scaffold_core.layer_4_features.model import FeatureOptions
    from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
    from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations, run_pass_2_features

    context = run_pass_2_features(
        run_pass_1_relations(run_pass_0(load_source_snapshot(capture))),
        FeatureOptions(straighten_strips=straighten_strips),
    )
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
            keys, ref_corner = {}, {}
            for face, source in corners:
                key = (patch_id, str(corner_vertex.get((face, source), f"{face}:{source}")))
                keys[key] = keys.get(key, False) or ref_pin[(face, source)]
                if ref_pin[(face, source)]:
                    ref_corner[key] = min(ref_corner.get(key, (face, source)), (face, source))
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
                    sc_pins=sc_pins, corners=frozenset(keys), reason=reason, ref_corner=ref_corner,
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
    straighten = STRAIGHTEN_STRIPS.get(name, False)
    context, solve = _replay(REFERENCE_DIR / f"{name}.capture.json", straighten)
    uses, unread, scale = build_uses(context, solve, reference)
    scores = score_uses(uses)
    return {
        "object": name,
        "straighten_strips": straighten,
        "patches_total": len(context.topology_snapshot.patches),
        "uses": len(uses),
        "unread_uses": unread,
        "scale": scale,
        "scores": {k: v for k, v in scores.__dict__.items() if k != "extra"},
        "islands": island_info(solve, reference),
        "gaps": top_gaps(uses, context, solve),
        "shape": shape_scores(uses, context, solve, reference, scale),
        "turn": dict(zip(("with_law", "checked", "mirrored"), corner_turns(context.relation_snapshot, solve))),
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
    strips = {True: "on", False: "off"}.get(r.get("straighten_strips"), "")
    shape = r["shape"]
    torn = f"{shape['torn']}/{shape['scored']}"
    itorn = f"{shape['itorn']}/{shape['iscored']}"
    return (
        f"{name:14s} {strips:>6s} {_pct(s['line_recall'])}  {_pct(s['false_lines'])}  {_pct(s['pin_cov'])}  {_pct(s['pin_extra'])}"
        f"  {_pct(s['axis_agree'])}  {structured:>20s}  {islands:>8s}  {split:>7s}  {scale:5s}"
        f"  {_pct(shape['shape'])} {torn:>8s}  {_pct(shape['ishape'])} {itorn:>7s}"
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
    counts = ("torn", "scored", "pairs", "spread", "itorn", "iscored", "ipairs", "ispread", "_agree", "_iagree")
    shape = {k: sum(r["shape"][k] for r in results) for k in counts}
    shape["shape"] = _share(shape["_agree"], shape["pairs"])
    shape["ishape"] = _share(shape["_iagree"], shape["ipairs"])
    return {"scores": {k: v for k, v in scores.__dict__.items() if k != "extra"}, "islands": islands, "scale": None,
            "shape": shape}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="CFTUV parity scoreboard")
    parser.add_argument("--object", action="append")
    parser.add_argument("--json")
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args(argv)
    results = [evaluate(name) for name in (args.object or OBJECTS)]
    print(
        "object         strips recall  false  pincov  pinext  axisagr  structd ref/sc/both  isl r/s  spl/mrg  scale"
        "  shape     torn  ishape   itorn"
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
            f" turn={r['turn']['with_law']}/{r['turn']['checked']} mirrored={r['turn']['mirrored']}"
        )
        for gap in r["gaps"]:
            print(
                f"  gap {gap['patch']} faces={gap['faces']} missed={gap['missed']:.2f}"
                f" reason={gap['reason']} island_diags={gap['island_diagnostics']}"
            )
        shape = r["shape"]
        print(
            f"  shape: groups scored={shape['scored']} pairs={shape['pairs']} patches over several ref islands="
            f"{shape['spread']}; island groups scored={shape['iscored']} pairs={shape['ipairs']}"
            f" islands over several ref islands={shape['ispread']}"
        )
        for row in shape["torn_patches"]:
            print(f"  torn patch {row['patch']} faces={row['faces']} common_pins={row['common_pins']}"
                  f" agreement={_pct(row['agreement']).strip()}")
        for row in shape["torn_islands"]:
            print(f"  torn island {row['island']} faces={row['faces']} common_pins={row['common_pins']}"
                  f" agreement={_pct(row['agreement']).strip()}")
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
                           "structured_share": STRUCTURED_SHARE, "shape_rel": SHAPE_REL_TOL,
                           "shape_extent": SHAPE_EXTENT_TOL, "shape_max_pairs": SHAPE_MAX_PAIRS,
                           "shape_min_points": SHAPE_MIN_POINTS, "torn_below": TORN_BELOW},
            "objects": [{k: v for k, v in r.items() if k != "_uses"} for r in results],
            "total": total if len(results) > 1 else None,
        }
        Path(args.json).write_text(json.dumps(payload, indent=1))


if __name__ == "__main__":
    main()
