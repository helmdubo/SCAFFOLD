# G5a — Skeleton Runtime (phase contract)

Phase start authorized by the user after artist validation of stage-1
structure (rails/families/junctions/seam verdicts on real meshes).
Layer 4 remains deferred: G5a runs FeatureConstraint-free (DD-18 allows
optional constraints; the L4 grammar plugs in later without rework).

## Consumed API (validated by tracer + overlay consumption)

```text
Layer 1 topology, Layer 2 facts (incl. per-vertex angle defect,
LocalFaceFan), Layer 3: ConnectedDirectionFamily v1 (per-use, geodesic),
RunEndpointJunction, ScaffoldNode/PatchAdjacency/ScaffoldJunction,
PatchChainDirectionalEvidence, PatchAxes, ScaffoldRail v1 through the
island cut view (cut_scaffold_rail, plan Slice O).
```

## Module contract (scaffold_core/layer_5_runtime/)

```text
islands.py   - island assembly: spanning tree of stitch decisions.
  Stitch gate (Level A): would-be-interior vertex set =
  mid-chain seam vertices tested |2pi - angle_sum| <= tolerance;
  chain endpoints excluded while they keep any remaining cut incidence
  (T-junction rule). SEAM_SELF always splits. Non-tree seams stay cut.
  Tree-edge priority (plan Slice P): rigid seams first (a straight hinge
  or a coplanar join between planar, unwarped patches; the same
  predicate, is_rigid_seam, decides what the rigid frame crosses), then
  the other accepted seams; longest first inside each group.

skeleton.py  - selection-wide solve:
  nodes = ScaffoldNode UNION RunEndpointJunction (rail atoms);
  one equation per RUN per axis connecting ITS OWN endpoints
  (the spike's chain-endpoint bug is contract-forbidden);
  axes = island-local AXIS_A/AXIS_B projected from families in the
  island's unfolded frame (stitch-tree parallel transport);
  numpy dense lstsq per axis; gauge = seed component pinned;
  spread safety: contradictory components -> UNCONSTRAINED, excluded,
  their vertices unpinned; residual reported;
  island rails: Layer 3 cuts each family's ScaffoldRail by the island
  (its runs and stitched hinges) and orders the pieces; the pieces are
  the island lines (plan Slice Q), Layer 5 checks them against the frame
  and never orders a line.

pins.py      - output model: vertex -> (uv, pinned flag, island id).
uv_transfer.py - the ONLY bpy write boundary (G5 rule): writes UVs+pins
  in the mesh's current mode without bpy operators. It does not call
  mode_set or unwrap; the artist runs Blender's U > Unwrap after the
  pins are written so the conformal fill is owned by Blender UI state.
```

## Invariants (validation outputs, not hopes)

```text
1. axis-parallel: an axis-classified run's endpoints differ in UV only
   along its own axis (zero violations on flat-grid fixtures);
2. lstsq residual ~0 on developable grids; nonzero residual must be
   accompanied by UNCONSTRAINED diagnostics, never silent smearing;
3. SEAM_SELF sides equal length in UV (band closure invariant);
4. degradation always carries diagnostics naming entities;
5. node/frame agreement (plan Slice N): in an island with a rigid unfolded
   frame, the occurrences unioned into one solve node coincide in that
   frame (node_frame_mismatches is a validation output);
6. rail/line/frame agreement (plan Slice O): every island line with more
   than one run is exactly one island rail segment, and in an island with
   a rigid unfolded frame an ordered island rail runs one way along its
   axis (rail sign times frame sign is constant; rail_frame_conflicts is a
   validation output).
```

## Non-goals in G5a

Texel scale policy, packing, trim semantics, Layer 4 grammar,
WorldOrientation, curved-chain refinement (OQ-11 remainder), and
ScaffoldTrace/ScaffoldRail construction.

Since plan Slice Q, G5a has no rail order or in-line sign derivation of its
own: lines and the signs of islands without a rigid frame come from the
island rails. Layer 5 must not compensate for a missing or unordered
ScaffoldTrace/ScaffoldRail by adding new rail-order, loop-orientation,
BFS/greedy traversal or sign-propagation heuristics inside Layer 5. If a
fixture needs a direction-stable ordered rail or trace to solve, the correct
G5a behavior is to diagnose/degrade and keep the behavior pinned until the
Layer 3 rail/trace contract exists.

## Implemented status (H3)

```text
Layer 5 v0 is implemented in scaffold_core/layer_5_runtime/.

islands.py:
  spanning-tree island assembly over Level A stitch decisions;
  mid-chain would-be-interior vertices use Layer 2 angle sums;
  stitch endpoints are excluded while remaining cut incidence keeps
  them boundary (T-junction rule);
  SEAM_SELF always splits and non-tree seams stay cut;
  rigid seams enter the tree first (plan Slice P), so a planar patch
  with a path of rigid seams to the frame root joins the frame
  instead of hanging off a warped n-gon.

skeleton.py:
  selection-wide skeleton solve over ScaffoldNode UNION
  RunEndpointJunction atoms;
  one length equation per directional run endpoint pair;
  island lines and rails (plan Slices N, O, Q): the Layer 3 cut view
  keeps only crossings inside one patch or through a hinge stitched in
  the island, so a family that crosses a cut seam splits into several
  lines, and it orders every piece through its stations, so
  a ring opens exactly at the seam the island leaves cut; branches and
  uncut loops stay unordered with diagnostics; IslandSkeleton.rail_segments
  holds the pieces, and the checks of invariant 6 go to
  IslandSkeleton.rail_frame_conflicts (the solve does not use rail order
  yet);
  rigid unfolded frame when no island patch is curved: each patch is
  rotated into the root plane along the stitch tree (rotation about the
  hinge Chain); the frame crosses only straight hinges (the Layer 3
  straight-hinge rule) or joins of coplanar patches (no rotation), warped
  n-gons and patches behind a bent hinge stay outside (OBLIQUE with a
  diagnostic);
  chain ends of a closed rim cut by a SEAM_SELF are matched to their own
  seam side through the face fan of the run's end edge;
  framed runs take AXIS_A / AXIS_B and their orientation sign from the
  unfolded direction (AXIS_A = longest island line, AXIS_B = root normal x
  AXIS_A, so islands are not mirrored); a line whose members disagree
  degrades to OBLIQUE with a diagnostic;
  an island without a rigid frame bipartitions its lines into axes by 3D
  perpendicularity at nodes, takes in-line run signs from its ordered
  island rails (plan Slice Q; a run on an unordered rail stays unsigned
  with a diagnostic and adds no equation) and co-orients parallel lines
  through their cross runs;
  contradictions are excluded as UNCONSTRAINED with diagnostics.

pins.py:
  run_skeleton_solve() orchestrates islands -> skeleton -> pinned UVs;
  pins are keyed by topology vertex occurrence (DD-37), so the two sides of
  a seam keep their own UV (plan Task Card M2); a run end on a seam-cut
  mid-chain vertex touches both seam sides and stays unpinned with a
  diagnostic;
  axis-parallel, SEAM_SELF length, node/frame and rail/line/frame checks
  are validation outputs.

uv_transfer.py:
  writes UV coordinates and pin flags only, and only on faces of the solved
  selection (Slice M1: faces outside it are never touched);
  a loop takes only the pin of its own vertex occurrence in its own patch,
  found through the face corner's Layer 2 face fan; there is no fallback to
  another patch's pin (Task Card M2);
  uses bmesh in Edit Mode and Object Mode (from_edit_mesh / from_mesh);
  calls no bpy operators and performs no automatic unwrap.
```

## Blender workflow

```text
1. Select the target mesh faces, or select one mesh object in Object Mode
   to use all faces of that object.
2. Press Write UV (G5a) in the Scaffold Graph debug panel.
3. Check the info-bar summary and console diagnostics.
4. In the UV Editor run U > Unwrap to fill the fabric between pinned rails.
```

Expected currently validated behavior:

```text
- cylinder tube with two seams: rectangular side band, one seam stitched
  inside the island and the other left open;
- extruded_cross: side band plus two separate cap islands;
- l_corridor_tunnel_seamed_folds: one island through the folds;
- artist_cyl32/Cylinder: 68 pins, residual about 4e-15, zero diagnostics
  in the validated capture;
- artist_cyl_multiseam (6 strips): 76 band pins on two straight rows,
  residual about 9e-7 (float32 capture noise), zero diagnostics.
```

Known limitation:

```text
artist_cross_band: the side band solves with aligned columns (before Slice N
its bottom row was silently mirrored: the closed rim's ends sat on the wrong
seam sides, residual 5e-15, zero diagnostics). The two planar end patches
still degrade with diagnostics: they close their loops only to 0.004 while
RESIDUAL_TOLERANCE is an absolute 1e-5, so every equation is dropped as
contradictory; exact orientation from the frame does not change that.
Tolerance policy belongs to the later unwrap stage.

artist_cyl_multiseam is RESOLVED (plan Slice L1). The collapse was a Layer 3
ConnectedDirectionFamily leak through curved shared chains that welded the
top and bottom rims into one family. The straight-hinge transport rule fixed
it in Layer 3; the G5a solve itself is unchanged and must still not gain
local traversal heuristics.

Rail contract: G0 DD-46/DD-47 (v1.6); background in
`docs/architecture/scaffold_rail_trace_contract_draft.md`.
```

## Tier 3 validation (buildings.blend, Blender 4.5.9, 2026-09)

`dev/tools/blender_smoke/` runs the real read and write boundaries headless on
the 13 seamed objects of the artist file; the baseline lives in
`dev/tools/blender_smoke/baselines/buildings_seamed.json`. All objects keep
zero axis-parallel violations, zero seam-length mismatches, zero opposite-side
family glue, zero loops changed outside the solved faces and zero node/frame
mismatches. After Slice N 60 of 62 islands have a rigid unfolded frame (the
frame-free bipartition no longer runs there), 97 of 10214 runs stay OBLIQUE,
and the remaining structure signals are 5 island lines through curved runs
and 10 patches outside a rigid frame (warped n-gons folded around a corner).

After Slice O (2026-11) 2094 island rails have more than one run; 2090 are
ordered and 4 stay unordered at nodes touched by more than two stations
of one family. No island rail splits an island line or runs against the frame
(rail_frame_conflicts 0). The fold-back repair (Slice O1) raised island
lines 7606 -> 7646; pins, Layer 5 diagnostics and OBLIQUE runs are
unchanged.

After Slice P (2026-11) the island tree takes rigid seams first: patches
outside the frame 10 -> 5 (only warped n-gons folded around a corner
remain), OBLIQUE runs 97 -> 65, pins 6926 -> 6957, Layer 5 diagnostics
36 -> 31; invariants and rail/frame conflicts stay 0.

