# G4a — Layer 4 v0: the strip feature (phase contract)

Opened by the user in autonomous mode (plan decision 14, 2026-11-13) while
G5a is still the main phase. Layer 4 v0 holds the feature kind STRIP and one
constraint kind, STRAIGHT_STRIP. G0 DD-50. The bevel kinds BEVEL_STRIP and
BEVEL_JUNCTION (G0 DD-54, plan Slice AE-2) are described at the end of this
file; they are records only and change no layout.

## Why

The CFTUV reference lays a curved four-sided patch as a straight rectangle
when its "Straighten Strips" option is on: the front face of an arch (a flat
ring with bevels) and the body of a profiled half column, which is not
developable. Scaffold had no place for such a decision: it is not a fact of
the surface, it is a choice of parametrization. G0 puts choices of that kind
in Layer 4 and lets them reach the solve only as a FeatureConstraint.

## Module contract (scaffold_core/layer_4_features/)

```text
model.py  - frozen records: FeatureCandidate, FeatureInstance,
            FeatureConstraint, FeatureSnapshot, FeatureOptions.
build.py  - build_feature_snapshot(topology, geometry, relations, options):
            the strip rule and the resolver.
```

Layer 4 imports Layers 0-3 only. It never writes Layer 3 (DD-25) and never
imports Layer 5.

Pipeline: `run_pass_2_features(context, options)` stores a `feature_snapshot`
on the PipelineContext after Pass 1. Without Pass 2, or with the default
options, every output is identical to a run without Layer 4.

## The strip rule

```text
Candidate (evidence, always produced, DD-15, DD-20):
  a patch with exactly one boundary loop made of exactly four PatchChain
  uses. Per use: its 3D length, whether the use is one SURFACE_LINE piece
  (DD-48), and the Layer 2 chord area vector of its Chain as the use
  walks the loop (plan Slice AJ; flipped for a reversed use, none when the
  Chain has none).

Rail pair (plan Slice AJ):
  an opposite pair whose two uses are both not one surface line and whose
  chord area vectors, each oriented by its use, point opposite ways.
  Opposite sides of a loop are walked in opposite directions, so two sides
  that bend the same way in space have opposite vectors; mirrored sides
  (the two profiles of a flat wall) have the same one. A side without a
  vector (collinear, or bows that cancel exactly) is no rail. No floor on
  the bend, no bound on how alike the sides are. A single rail pair holds
  the rails whatever its length; when both pairs are rail pairs the longer
  one does (pair 0 on an exact tie). The other pair are the ends.

Instance (plans Slices AF, AJ):
  ACCEPTED when FeatureOptions.straighten_strips is on AND both uses of the
  longer opposite pair (the larger sum of the two 3D lengths; on an exact
  tie either pair) are not one surface line: curved, cornered or
  unresolved, AND the candidate has a rail pair. Bending in 3D is not
  read, so a wall of a cylinder is not a strip. Otherwise SUPPRESSED with
  a reason. The shape is graded first: already a rectangle, then long
  sides straight on the surface, then no rail pair (NO_RAIL_PAIR, "no
  curved opposite sides bend the same way (mirrored or unlike)"); a
  candidate that passes all three and only waits for the option is
  suppressed as option off (plan Slice AC). An instance that would be accepted on a
  patch with a STRAIGHT_LADDER constraint is suppressed as laid from its
  bevel ladder. A strip by mark without that constraint (both rails
  straight on its surface, plan Slice AI) is graded like any other patch.
  Suppressed instances stay inspectable.

Constraint STRAIGHT_STRIP (self-contained, DD-26):
  patch id, the four PatchChain ids in loop order, and the target length of
  each opposite pair: the mean of the two 3D lengths. Since plan Slice AJ
  also rail_pair (0: loop positions 0 and 2, 1: positions 1 and 3) and
  free_end_patch_chain_ids, the end uses that are not one surface line.
```

The rule reads structure only: no world axis, no H/V, no patch types.
`straighten_strips` is a user option and is off by default.

## Consumer (Layer 5)

Layer 5 reads constraints only; it does not recognise strips.

```text
A STRAIGHT_STRIP constraint is applied when its patch is an island by itself.
The island then takes the strip layout (IslandSkeleton.frame == "STRIP"):
  - the uses at loop positions 0 and 2 lie on one axis, 1 and 3 on the other;
    the rail pair is AXIS_A (a constraint without one: the pair with the
    longer target length);
  - the runs of a use follow the loop, so going round the loop the sides run
    +A, +B, -A, -B and the rectangle closes without a mirror;
  - each run's length in the equations is its 3D length scaled by target
    length / use length, so opposite sides come out equal;
  - the existing axis solve places the nodes; every run end is pinned,
    except the inner run ends of a free end (plan Slice AJ): a free end
    keeps only its two end points (the rail ends, tied across); its inner
    vertices get no coordinate, no pin and no stations
    (IslandSkeleton.fill_run_ids) and are left to the fill. An end that
    is one surface line is laid straight.
A constraint whose patch shares its island is not applied, and the island
gets a diagnostic naming the patch.
Island assembly (plan Slice AB) does not stitch a constrained patch when
every seam its stitch gate accepts is a straight hinge (every use of the
Chain carries at most one run): straightening only rescales such a side,
so the patch leaves its island and the constraint applies. A constrained
patch with a bent seam among them stays stitched and is not applied.
A seam that the user filter joins (plan Slice AH, G0 DD-55) is stitched
whatever this rule says; a constrained patch with such a seam shares its
quilt and the constraint is not applied (with the diagnostic above).
```

## Results (2026-11)

CFTUV parity on the reference scene, Straighten Strips on for Arc and
collumn as in the reference:

| Mesh | line recall | pin coverage |
|---|---|---|
| Arc | 67% -> 96% | 60% -> 85% |
| collumn | 0% -> 51% | 0% -> 54% |

The arch front face becomes a 2.90 x 0.44 rectangle (the arcs at the mean of
3.56 and 2.25), the column body a 6.54 x 2.88 rectangle. With the option off
all 25 replayed captures are identical to the run without Layer 4.

After plan Slice AJ (2026-11-15), strips on, after Blender 4.5's
conformal fill: the column body f1 takes its two arcs as rails and leaves
its profile seams to the fill (34 pins, 3.59 degrees of mean corner angle
error, edge error 0.087, 0 flips, 0 overlaps; before: 76 pins, 3.98,
0.096). The column's flat back face f355 is no strip (NO_RAIL_PAIR) and
is laid as an ordinary patch: 16 pins, 3.90 degrees, edge error 0.020,
identical to a run with the option off (before: 46 pins, 37.71 degrees).
The reference lays both as full rectangles, which the user's decision now
contradicts: collumn parity recall 100% to 16%, pin coverage 100% to 40%,
shape 53% to 49%. Arc is unchanged (96%, 97%, 100%). With strips on and
straighten_bevel_strips off, the marked strips c_arch_s2 f26,
e_arch_s2_n20 f26, d_cyl_s2 f112 and f114 lose 2 pins each, the inner
vertex of each 2-segment profile end, now a free end; with the bevel
option on (the default) their ladders lay them, unchanged.

## Known limits

```text
- A strip stitched along a bent side is not straightened (L-shaped faces
  in the walls of the buildings). A strip stitched across straight sides
  only leaves its island (plan Slice AB: the column's flat back face; since
  plan Slice AJ that face is no strip, its profiles are mirrored).
- Pins sit at run ends only: a long side made of one multi-segment run keeps
  its inner vertices unpinned, and Blender's unwrap bows that side.
  (Since plan Slice Z stations pin the inner vertices of an axis run;
  since plan Slice AJ a free end's inner vertices are left to the fill.)
- Limits of the rail pair (plan Slice AJ): a wrong reading of the bend is
  possible only where the bow of a side is below its noise. An inflected
  (S-shaped) side is read by its net bow; an exactly symmetric S has none
  and is no rail. A cornered side counts as curved, as before: a planar
  band with a right-angle corner inside each long side is still accepted
  and straightened with the option on (a synthetic L band: 23.6 degrees
  after the fill against 0.0 unstraightened); the four one-face building
  patches the option accepts are unchanged; cutting such sides at their
  corners is not done. Only patches with one loop of exactly four uses
  are candidates: the noisy top u_rounded_wall_noise_top f0 (five uses,
  because of a 6 cm chamfer; 30 triangles inside) and f111 are not. The
  rails of a strip with free ends lie at equal UV length (the mean of the
  two 3D lengths) and at a distance equal to the mean end length; with
  free ends only the rails are pinned, so the column's interior rings come
  out nearly straight, not exactly.
- No FeatureRule protocol or registry yet: one rule, plain functions.
```

## Bevel kinds (plan Slice AE-2, G0 DD-54)

Approved by the user (2026-11-13). Input: a Bevel was applied, its faces are
bounded by seams and cut by seams into strips and corner junctions, each a
patch; curved or noisy shapes included.

```text
BEVEL_STRIP / BEVEL_JUNCTION, one BevelInstance per bevel patch
(FeatureSnapshot.bevels), built by Pass 2 always. Layer 5 does not read
the records. A strip confirmed by the mark, with an open chosen reading
and no shared use, emits a STRAIGHT_LADDER constraint (plan Slice AF,
option straighten_bevel_strips, on by default): u per profile line (the
mean of the rails' arc lengths), the two rail vertices of each line, the
width (mean profile length). Exception (plan Slice AI): a strip whose two
rails are each one use whose PatchChainShapeRelation on the strip's own
side is exactly one SURFACE_LINE already unfolds with straight rails
(a planar mitred strip, a piece of a cylinder). It emits no constraint;
FEATURE_BEVEL_STRIP_NOT_LAID at INFO gives the reason "both rails are
straight on its surface: it unfolds straight as it is" (the other reasons
stay WARNING). The gate does not establish that the strip develops: a
conical bevel also develops, as a curved band, and it is straightened.
The test is the rail shape, not planarity. A strip with one
straight rail and one that is not still emits. Without the constraint the
strip is an ordinary patch for Layer 5.
Layer 5 pins every boundary vertex of the
patch where the constraint says (frame LADDER) when the patch is an island
by itself, which it is when no seam of it is joined by the user filter.
When the filter joins one of its seams (plan Slice AH, G0 DD-55) the patch
lies in its quilt and the quilt lays its runs. A quilt without a rigid
frame then keeps the strip's two rails together (plan Slice AI,
layer_5_runtime/quilt_ladders.py, G0 DD-54): when exactly one rail is
stitched and the quilt lays that rail on an axis, the free rail gives no
length equations and each of its vertices takes the along-rail coordinate
of its profile-line partner on the stitched rail. The ladder gives the
quilt no axis, but its mark makes the stitched rail one line, with no
length equation from it and stations by 3D length for its nodes (plan
Slice AL, G0 DD-47). A quilt with a rigid frame reads nothing (its patches in
the frame are planar and unfold exactly); a strip outside the frame is
not laid and says so. A strip that meets the conditions in a quilt that
pins none of its vertices is not counted as kept together and says so.

Rule A, by the Layer 0 Face Strength mark (authoritative where any face of
the patch is marked): all MEDIUM -> strip, all WEAK -> junction; MEDIUM and
WEAK in one patch, or bevel faces with STRONG / unmarked faces -> SUPPRESSED
with a reason (the seams do not isolate the bevel). The strip's direction is
the ladder reading (G0 DD-53) whose rails have no bevel face across and
whose ends have a bevel face, the border or the patch itself across.

Rule B, by structure (only patches with no marked face), gives candidates,
not truth: a ladder patch with one end-strict reading is decided; a
non-ladder patch bounded only by ends of decided readings, undecided
ladders and the border is a junction; junctions decide the undecided
ladders next to them, in rounds to a fixpoint; a strip lies between two
patches that are not strips and has an end on a junction; a junction
joins at least one strip (G0 DD-54 has the definitions).

A strip keeps its reading, rail and end uses, the neighbour patches on each
rail, faces per column, column count, ring flag and a corner kind (CONVEX /
CONCAVE / MIXED / UNDEFINED, from PatchAdjacency). A junction keeps the
strips it joins in loop order, its other neighbours and a border flag.
```

Known limits of rule B: a miter without junction faces (every window corner
of Blender's default Bevel), a strip that runs to the mesh border, a
junction that also touches a main surface, a closed ring, a triangulated
bevel, a bevel between non-quad main surfaces. The mark finds all of these.
Known false positive of rule B: a quad band capped by non-quad patches
(the top of a free-standing slab with n-gon end caps). Known limit of rule
A: a strip that ends on an unbevelled face gets no direction. A plain quad
ladder is not a kind. The debugger draws rule B records on their own
layers ("by structure").

Known limits of the ladder layout (plan Slice AF): one width and parallel
rails, so a strip of varying width is not isometric; interior vertices of
a multi-segment strip are left to Blender; a closed ring, a strip without
a reading (triangulated, or ending on an unbevelled face) and a strip
with a shared use get no constraint. A fully triangulated bevel gets no
layout at all: its strips are no longer STRIP either, stay stitched into
the main island and leave it without a rigid frame (h_rect_s2_tri with
strips on: 72 pins on Slice AE, 36 now, equal to strips off).

Known limits of the quilt reading (plan Slice AI): a strip is read only
when its quilt already lays its stitched rail on an axis (since plan Slice
AK in at least one piece: the stitched rail is cut where its axis changes,
and a line on no piece is not tied); otherwise, and when both or no rails
are stitched, the quilt's own layout lays its runs.
A free-rail edge copies its partner edge on the stitched rail, so it is
as short as that partner. A strip that unfolds straight and no longer
gets a ladder can lie unpinned in a larger island (d_cyl_s2 strip f154:
width ratio 3.33 after Blender's fill). With straighten_strips on, such a
strip could get a STRAIGHT_STRIP if its longer pair were its curved ends;
no capture has one.
The gate reads Layer 3's SURFACE_LINE. In Slice AI that was decided per
vertex only (a turn under 0.1 rad at each vertex), so a finely tessellated
curved rail could read as one surface line. Since plan Slice AJ a surface
line is also straight in total (at most 15 degrees of accumulated turn,
G0 DD-48): a rail that turns more is a curve however fine its
tessellation, one that turns less in total still reads as a line. No gate
verdict changed: on the present captures every strip let through turns at
most 0.1 degree in total and every strip kept turns 18 to 167 degrees.
After Blender's fill the user's bottom quilt (+Z) has 10 overlapping
triangle pairs and 2 self-intersecting faces (f36 face 98, f111 face 123),
none before the slice: the stitched rail of f36 turns a corner around
f111 over a 1.4 mm OBLIQUE bridge run, and its unpinned vertex there
lands on the wrong side of its neighbour. Laying that corner is left to
the band slice. (2026-11-15: the slice after Slice AI became Slice AJ,
which changed the strip rule and the surface line; it did not take this
corner.) Resolved by plan Slice AK (2026-11-15): the cause was not the
vertex. The two sides of the stitched Chain f36/f111 were two island
lines, so no run of f111 took an axis and the bridged right corner on
f111's side was never laid, and the ladder was read along one axis only.
With the sides joined, the ladder read in pieces and the frame-free drift
per metre of the island, that quilt has 0 overlapping triangle pairs and
0 self-intersecting faces after the fill, f36's shear is 0.01 / 0.13
degrees (mean / max) and f73 is kept together too. The cost: the band f111
is laid straight and the curved middle of its inner side stays OBLIQUE;
4 of f73's 12 profile lines are on no piece; f36's 40.8 mm mitre edge is
laid at 106.6 mm. (Corrected 2026-11-15, measured in the study of plan
Slice AL: the pins force that middle to 3.522 m for 2.889 m in 3D and the
fill lays it as a zigzag of up to 0.036 m across, not a bulge; f73 has 12
profile lines, not 10; f73's largest corner angle error, about 24 degrees,
sits on its end faces f75 and f91, whose 3D corners are 66 and 114
degrees, not where its pieces meet that middle.) Plan Slice AL makes f73's
stitched rail one line: that middle is laid straight, every profile line
of f73 is tied, and the 24 degrees on its end faces stay.
Without the filter a strip without a ladder joins by structure, as before
Slice AF; such a quilt has no rigid frame and its frame-free layout is not
checked for overlap, so overlaps after the fill rise on several bevel
cases (the plan's Slice AI entry has the numbers).

User filters: the first one is built (plan Slice AH, G0 DD-55, pass 3,
`scaffold_core/user_filters/`). With the user's world vertical a bevel
strip by mark takes the class (HORIZONTAL or VERTICAL) of its rail
neighbours, a junction the majority class of its strips, and a bevel by mark
is joined to the patches of its class. The world vertical is a user option
of that stage, never an input of Layers 1-4. Not built: filters that select
strips as under a ceiling, outer or inner corner. The corner kind beside a
curved neighbour needs a more local source than whole-patch normals.
