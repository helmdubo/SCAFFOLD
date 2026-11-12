# Chain shape and surface relation contract (draft)

Status: approved by the user (2026-11-13). Stages A and B are implemented
(plan Slice W; G0 v1.7 DD-48, G0 v1.8 DD-30). Rule 1 was decided as option
(i). Stages C and D are not implemented, and the G0 changes listed at the
end for them are not applied.

As implemented in Stage A (this narrows the contract text below where they
differ):

- a piece ends at a surface corner, a surface turn of at least 42 degrees
  on that side (between a regular 9-gon at 40 and an 8-gon at 45);
- the surface turn is the face angle sum minus pi (DD-45 data); the plane
  tilt is the cross-check, run at interior vertices of a piece only;
- UNRESOLVED means a failed cross-check or a vertex with no single face
  fan for the use. A spatial piece still gets SURFACE_LINE or
  SURFACE_CURVE from its surface turns and records `is_planar = False`; a
  tilt that changes along a piece is not checked by itself;
- a closed Chain is read from the use's own start vertex;
- Layer 2 also stores the side face and its normal for every chain segment
  of a use.

Origin: user review of an arch with bevels (`Decor_Roof_Left_lod00.003`,
`buildings3_3.blend`) against the CFTUV result, 2026-11.

## Problem

CFTUV judges a boundary chain as a whole and per patch: a chain that lies in
a plane and only bends along the patch normal counts as an axis chain for that
patch, although it is not a straight line in 3D.

Scaffold has no such notion:

- a Chain is cut into straight runs wherever its direction turns by more than
  about 5 degrees (`chain_refinement.py`), once per Chain, not per side;
- two runs continue one line only by the face angle sum at their shared vertex
  (DD-45), one vertex at a time;
- a curve has no record of its own: an arc of 16 segments is 16 unrelated
  single-run families;
- the one-run chord shortcut for zigzag chains (`SAWTOOTH_STRAIGHT`) is taken
  for the Chain, so both sides get it, whatever the chain is on each surface.

## Measurement

Two numbers per non-straight Chain (probe, no core change):

- planarity: largest distance of the chain's vertices from its best-fit plane;
- tilt, per side: angle between that plane and the normals of the patch faces
  along the chain. 0 degrees: the normals lie in the chain's plane, the chain
  bends in depth and is straight on the surface. 90 degrees: the chain's plane
  is the surface, the chain is a curve on it.

Sets: the arch, the 4 seamed objects of `buildings3_3.blend`, the 13 seamed
buildings captures, the 7 in-repo captures.

| Finding | Result |
|---|---|
| planarity | every non-straight chain is planar to 0.00% of its length; 5 spatial chains, all in `Main_wall.011` (2 patches on 2219 faces) |
| tilt, buildings | 40 edges at 0-10 degrees, 1001 at 80-90, none between |
| tilt, in-repo captures | 152 at 0-10, 361 at 80-90, none between |
| tilt between the two | a ring on a cone (41-44 degrees, constant), and chains with real corners that pass faces of different orientation |
| law | surface turn at a vertex = 3D turn x sin(tilt). Error against the measured face angle sum: median 0.00, p95 at most 0.15, max 1.0 degree; outliers only on warped single-face patches |
| arcs with tilt near 0 | already one line in Layer 3 everywhere (rims) |
| arcs with tilt near 90 | no record: N single-run families (arch: 16 and 11) |
| chord shortcut on a non-straight chain, buildings | 12 sides, all bend in the surface with 90 degree steps, chord offset 4.5% to 30%; all 12 end as defects in Layer 5 (10 jogs, 2 OBLIQUE) |
| chord shortcut, arch foot chain | correct for the front face (tilt 0-9), wrong for the foot cap (tilt 90): both get one run |

So the plane and the tilt are the cause; the per-vertex angle rule is its
consequence. On the buildings set the new facts do not change any line. They
change behaviour through the chord shortcut (Stage B) and give curves a record
(Stage C).

## Terms

```text
chain piece        a maximal part of a Chain between real corners
plane of a piece   best-fit plane of its vertices (undefined for a straight piece)
tilt of a use      angle between that plane and the surface normal of one
                   PatchChain's own patch faces along the piece
surface turn       3D turn x sin(tilt): how much the piece turns when the
                   surface is laid flat
surface line       a piece whose surface turn stays inside the DD-45 tolerance
surface curve      a planar piece whose surface turn does not
```

A piece is judged per PatchChain use (DD-07, DD-45): one Chain may be a
surface line for one patch and a surface curve, or a cornered outline, for the
other. No world axis, no H/V, no patch type takes part.

## Contract

### Layer 2 (raw facts, additive)

`ChainGeometryFacts` gains, per Chain:

```text
plane_normal        unit normal of the best-fit plane, or none for a straight chain
plane_deviation     largest distance of a chain vertex from that plane
chord_deviation     largest distance of a chain vertex from the chord
```

A per-side fact, one per PatchChain:

```text
tilt_min, tilt_max  range of the angle between the chain's plane and the
                    normals of the patch faces along the chain on this side
```

These are measurements. Layer 2 does not classify a line or a curve, and the
existing `shape_hint` stays as it is.

### Layer 3 (evidence, per PatchChain use)

A shape relation record per use and piece:

```text
kind: SURFACE_LINE | SURFACE_CURVE | UNRESOLVED
surface_turn_max, surface_turning_total, tilt range, piece vertices
```

`UNRESOLVED` covers a spatial piece, a tilt that changes along the piece, and
a warped single-face patch. It carries a diagnostic and decides nothing.

Validation output: at every interior vertex the predicted surface turn agrees
with the face angle sum of DD-45. A disagreement is a diagnostic naming the
vertex, never a silent choice of one of the two.

### Rules that change behaviour

1. The chord shortcut is taken per side (Stage B). A zigzag piece is one run
   only for a side where it is a surface line. On a side where it bends in
   the surface it is split at its corners like any other chain.
2. A surface curve is one record, not N single-run families (Stage C). It is
   not a member of a ConnectedDirectionFamily: a family is a line.

Rule 1 needs a user decision between two measured options:

```text
(i)  shortcut only for surface-line sides (recommended): fixes all 12 buildings
     sides; no real mesh in the measured sets loses a line.
(ii) keep the shortcut on surface-curve sides whose chord offset is below a
     threshold: the smallest measured offset is 4.5%, so any threshold under
     that gives the same result as (i) on these sets.
```

## Stages

```text
A  Facts and visibility. Layer 2 facts, Layer 3 relation, the validation
   output, a debug overlay channel (surface line / surface curve per side),
   Tier 3 counts. No change to runs, families, rails or Layer 5.
B  Chord shortcut per side. Expected on buildings: 10 of 25 jogs and 2 OBLIQUE
   runs become corner-split runs. Baseline changes.
C  Surface curve record. Family counts drop (arch: 27 single-run families
   become 2 curves). Baseline changes.
D  Later, separate decisions: a multi-segment surface line as one run with
   stations, placement of curves, band recognition (Layer 4).
```

Each stage is its own slice with its own measurement and approval.

## Fixtures

```text
arch with bevels          capture of Decor_Roof_Left_lod00.003 (needs the
                          user's permission to commit it as test data)
cylinder tube, tube with cap, artist cylinders     already in the repo
ring on a cone            new synthetic fixture
stepped chain (Z step)    new synthetic fixture: the buildings jog case
zigzag in depth           new synthetic fixture: the arch foot chain
```

Paired acceptance (plan standing rule 5): every "no longer one run" case ships
with a "still one line" case.

## Interactions to guard

- DD-43 straight hinge: SHARED_CHAIN transport needs exactly one directional
  run on both sides. Stages A to C do not merge runs, so the rule is untouched.
  Stage D must restate it as "straight in 3D", or rims leak again
  (artist_cyl_multiseam).
- A chain with real corners is cut at them before the tilt is measured; the
  tilt of a whole cornered chain mixes its pieces (`Main_wall.011`: 199 sides).
- A warped single-face patch has one averaged normal; its tilt means nothing
  and stays UNRESOLVED.

## Out of scope

Layer 5, straightening, bands, texel scale, WORLD_UP, H/V labels, patch types.

## G0 and plan changes this needs

```text
G2 phase doc / Layer 2 facts list: plane facts and the per-side tilt.
DD-30: directional runs are built per PatchChain use, not per Chain.
DD-45: the whole-piece rule and the cross-check next to "the angle alone decides".
OQ-11: "curved-chain in-patch refinement policy" and "sawtooth tuning" close
       with Stages B and C.
Plan standing rule 1 (evidence moratorium): the shape relation record is a
       new Layer 3 evidence type and needs the stated exception.
```

## Probes

`dev/tools/blender_smoke/probes/chain_shape.py` replays captures and prints
the pieces by kind from the core records. The session probes behind the
measurement table (whole-chain planarity and tilt, the chord shortcut per
side, the law error) were not committed; tilt and law error are stored on
every record and appear in the full inspection output.
