# CFTUV Frontier & Skeleton Solve — Algorithm Cards

Extracted from the CFTUV source (dev/tools/CFTUV) as behavior invariants for
G5 migration. CFTUV is the production-proven behavior oracle; SCAFFOLD ports
invariants, never code (see cftuv_lessons.md). Spike v2 on a real wall mesh
(walls.004) showed why these layers matter: the spike had none of them and
produced collapsed fragments, while CFTUV produced clean aligned strips.

## Card 1 — FrontierRank: what to place next

CFTUV ranks placement candidates with a 7-tier lexicographic tuple
(frontier_score.py:698-722):

```text
viability_tier   # 0 dead / 1 risky / 2 viable (gate)
role_tier        # frame (H/V) chains before FREE
ingress_tier     # both-ends-anchored > dual > single > unanchored
patch_fit_tier   # backbone support in patch state
anchor_tier      # same-patch anchors (3 pts) > cross-patch
closure_risk_tier# regular > closure-supported > closure-risky
local_score      # length + downstream bonus - isolation penalty
tie_length       # longer 3D chain wins final ties
```

Placed chains mark neighbors dirty -> re-rank. Invariant: anchored frame
chains grow the placed region; FREE chains follow; nothing is placed without
rank justification.

SCAFFOLD mapping: role_tier must come from island-local
ConnectedDirectionFamily axis roles, not stored H/V (DD-04). Anchors map to
ScaffoldNode incidence with already-placed PatchChains.

## Card 2 — Placement: anchors, direction, scale

- Anchor = known UV for a chain endpoint, found by scanning placed chains at
  the same vertex (vert_to_placements). Kinds: SAME_PATCH, CROSS_PATCH, FREE.
- Direction: dual-anchor forces direction; single-anchor inherits from
  backbone/partner; unanchored uses patch basis.
- Scale: UV_length = 3D_length * final_scale, one global texel scale;
  frame chains keep normalized station parametrization, FREE interpolate.

SCAFFOLD mapping: patch basis = PatchAxes; stations = arc-length along
PatchChain (already in spike); final_scale is a G5 runtime parameter.

## Card 3 — Island assembly is topology-driven, not role-driven

CFTUV does NOT decide splits per-seam: a quilt (tree-structured patch
component) is one island by default; non-tree closure seams stay open;
placement failures degrade to splits. WALL/FLOOR/SLOPE only biases root
selection (+0.06) and seam pair scores (WALL-WALL 1.0, WALL-FLOOR 0.35) for
tree construction.

SCAFFOLD note: our angle-defect Level A gate is MORE principled than CFTUV
here (CFTUV has no dihedral gate at scaffold stage). Keep the defect gate,
add CFTUV's tree-with-closure-seams island structure: islands need a
spanning-tree of stitched seams; remaining seams stay cut even when
geometrically stitchable. Semantic pair scores are the Level B soft layer —
late runtime labels per DD-04/DD-05 territory, replaceable by
dihedral/family-structure scores first.

## Card 4 — P7 skeleton solve: where the visual quality comes from

The clean aligned rows in CFTUV output are produced AFTER placement by a
global sparse least-squares pass (solve_skeleton.py, docs/P7_skeleton_solve.md):

```text
- row-graph: union-find over junctions through H chains;
  col-graph: through V chains. Membership is TOPOLOGICAL; 3D coords are
  only a post-hoc safety check (spread tolerance, singular split valence>=5).
- one variable per col-component (U axis) / row-component (V axis);
  shared chain between two patches is ONE variable, not two.
- equations: u[c_b] - u[c_a] = axis_sign * length_3d(chain)  (weight 1.0);
  sibling equivalence for repeated openings (doors/windows) corrects
  symmetrically (weight 5.0); gauge fixed by pinning the seed component (1e6).
- solve per axis (LSQ), write canonical u/v to junctions, rebuild chain
  points by linear interpolation between canonical endpoints.
```

SCAFFOLD mapping: junctions = ScaffoldNodes; H/V membership = island-local
axis classification of ConnectedDirectionFamily; ChainUse = PatchChain
(axis_sign = orientation_sign). This pass is the single biggest missing
quality layer in the spike.

## Card 5 — Interior fill and holes

Pins = skeleton chain points; Blender unwrap fills interior. Inner loops
(loop_index >= 1: windows, doors) are placed chain-by-chain in frontier order
like outer loops — holes are first-class skeleton citizens, not interior.
Spike v2 ignored inner loops entirely; on walls.004 (walls with window
openings) their vertices fell into fallback projection. This is a primary
spike v3 fix.

## Card 6 — Cross-island row alignment and texel scale

Row/col components are global across the quilt, so even islands that split
later share canonical rows; one final_scale keeps texel density uniform.
This is why CFTUV walls line up in horizontal strips across islands.

## Card 7 — Failure handling

- Singular junction (conflicting row coords): phantom split (valence>=5
  only) or flag UNCONSTRAINED and skip from solve. Never force.
- Frontier stall: unplaced chains classified deferred/rejected; patches go
  to a separate quilt or marked incomplete.
- Open closure: flagged closure_valid=False; conformal salvages or splits.
Invariant: degrade with diagnostics, never silently distort.

## Replacement decisions (what SCAFFOLD must NOT port)

```text
H/V stored frame roles      -> island-local axis roles projected from
                               ConnectedDirectionFamily per island
WALL/FLOOR/SLOPE scores     -> dihedral/defect/family-structure scores first;
                               semantic labels only as late runtime overlay
ad-hoc orientation derivation -> PatchChain.orientation_sign (already done)
scattered drift corrections -> single skeleton solve pass (P7 already
                               proved retiring partial corrections)
scipy dependency            -> numpy dense lstsq is enough at junction counts
                               (hundreds), Blender ships numpy not scipy
```
