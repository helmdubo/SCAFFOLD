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
  uses. Per use: its 3D length, whether its Chain is bent in 3D, whether the
  use is one SURFACE_LINE piece (DD-48).

Instance:
  ACCEPTED when FeatureOptions.straighten_strips is on AND the strip needs
  straightening (some use is not one surface line, or two opposite uses
  differ in length by more than 1%) AND at least one opposite pair has both
  uses bent in 3D. Otherwise SUPPRESSED with a reason. The shape is graded
  first: already a rectangle, then no bent opposite pair; a candidate that
  passes both and only waits for the option is suppressed as option off
  (plan Slice AC). So the reason does not depend on the option except for
  the candidates the option accepts. Suppressed instances stay inspectable.

Constraint STRAIGHT_STRIP (self-contained, DD-26):
  patch id, the four PatchChain ids in loop order, and the target length of
  each opposite pair: the mean of the two 3D lengths.
```

The rule reads structure only: no world axis, no H/V, no patch types.
`straighten_strips` is a user option and is off by default.

## Consumer (Layer 5)

Layer 5 reads constraints only; it does not recognise strips.

```text
A STRAIGHT_STRIP constraint is applied when its patch is an island by itself.
The island then takes the strip layout (IslandSkeleton.frame == "STRIP"):
  - the uses at loop positions 0 and 2 lie on one axis, 1 and 3 on the other;
    the pair with the longer target length is AXIS_A;
  - the runs of a use follow the loop, so going round the loop the sides run
    +A, +B, -A, -B and the rectangle closes without a mirror;
  - each run's length in the equations is its 3D length scaled by target
    length / use length, so opposite sides come out equal;
  - the existing axis solve places the nodes; every run end is pinned.
A constraint whose patch shares its island is not applied, and the island
gets a diagnostic naming the patch.
Island assembly (plan Slice AB) does not stitch a constrained patch when
every seam its stitch gate accepts is a straight hinge (every use of the
Chain carries at most one run): straightening only rescales such a side,
so the patch leaves its island and the constraint applies. A constrained
patch with a bent seam among them stays stitched and is not applied.
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

## Known limits

```text
- A strip stitched along a bent side is not straightened (L-shaped faces
  in the walls of the buildings). A strip stitched across straight sides
  only leaves its island (plan Slice AB: the column's flat back face).
- Pins sit at run ends only: a long side made of one multi-segment run keeps
  its inner vertices unpinned, and Blender's unwrap bows that side.
- No FeatureRule protocol or registry yet: one rule, plain functions.
```

## Bevel kinds (plan Slice AE-2, G0 DD-54)

Approved by the user (2026-11-13). Input: a Bevel was applied, its faces are
bounded by seams and cut by seams into strips and corner junctions, each a
patch; curved or noisy shapes included.

```text
BEVEL_STRIP / BEVEL_JUNCTION, one BevelInstance per bevel patch
(FeatureSnapshot.bevels), built by Pass 2 always. No option, no constraint:
Layer 5 does not read them.

Rule A, by the Layer 0 Face Strength mark (authoritative where any face of
the patch is marked): all MEDIUM -> strip, all WEAK -> junction; MEDIUM and
WEAK in one patch, or bevel faces with STRONG / unmarked faces -> SUPPRESSED
with a reason (the seams do not isolate the bevel). The strip's direction is
the ladder reading (G0 DD-53) whose rails have no bevel face across and
whose ends have a bevel face, the border or the patch itself across.

Rule B, by structure (only patches with no marked face): end-strict
readings, pure junctions, a strip between two patches that are not strips,
a junction that joins at least one strip (G0 DD-54 has the definitions).

A strip keeps its reading, rail and end uses, the neighbour patches on each
rail, faces per column, column count, ring flag and a corner kind (CONVEX /
CONCAVE / MIXED / UNDEFINED, from PatchAdjacency). A junction keeps the
strips it joins in loop order, its other neighbours and a border flag.
```

Known limits of rule B: a miter without junction faces (every window corner
of Blender's default Bevel), a strip that runs to the mesh border, a
junction that also touches a main surface, a closed ring, a triangulated
bevel. The mark finds all of these. A plain quad ladder is not a kind.

Later (not built): user filters that select strips as horizontal, vertical,
under a ceiling, outer or inner corner. The world vertical enters there, as
a user option, never in Layers 1-3. The corner kind beside a curved
neighbour needs a more local source than whole-patch normals.
