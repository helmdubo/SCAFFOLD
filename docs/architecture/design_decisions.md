# Design Decisions — Scaffold Core

This file mirrors the authoritative DD register in `G0.md`.

Agents may read this file for quick lookup. If it disagrees with `G0.md`, `G0.md` wins.

## Core decisions

- **DD-01 — Topology is immutable snapshot.** Scaffold Core does not mutate topology in place.
- **DD-02 — ChainUse is mandatory.** All oriented boundary use is represented through `ChainUse`.
- **DD-03 — Topology and geometry are separate.** Layer 1 stores incidence/orientation; Layer 2 stores measured geometry.
- **DD-04 — H/V is not a primary stored role.** H/V-like labels are derived runtime/debug labels.
- **DD-05 — WALL/FLOOR/SLOPE is not a primary patch type.** World-facing semantics are derived WorldOrientation facts.
- **DD-06 — Relations are derived caches with provenance.** Relations store confidence, evidence, source and snapshot context.
- **DD-07 — Alignment membership is per ChainUse.** A Chain may have multiple ChainUses with different AlignmentClass memberships.
- **DD-08 — Patch axes are derived from AlignmentClasses.** PatchAxes is Layer 3 classification, not solve output.
- **DD-09 — Continuation is a Layer 3 relation.** Old ContinuationEdge becomes ChainContinuationRelation.
- **DD-10 — Dihedral is a PatchAdjacency relation.** Signed dihedral references patch pair, shared Chain and both ChainUses.
- **DD-11 — WorldOrientation is a derived relation namespace.** SurfaceRole, WorldEdgeKind and WorldCornerKind are derived semantics.
- **DD-12 — Base WorldOrientation does not depend on Runtime/Solve.** Solve output must not redefine world semantics.
- **DD-13 — Alignment does not use WorldOrientation labels.** Alignment may use WORLD_UP vector as raw geometric bias, but must not use SurfaceRole labels.
- **DD-14 — Runtime solve consumes lower layers only.** Runtime solve must not discover or mutate topology, geometry or base relations.
- **DD-15 — Feature recognition returns candidates, not decisions.** Rules produce FeatureCandidates; resolver produces FeatureInstances.
- **DD-16 — Full rebuild is preferred in v1.** Correctness and debuggability beat incremental complexity.
- **DD-17 — User overrides are inputs, not topology mutations.** Overrides affect rebuild interpretation.
- **DD-18 — Skeleton solve supports optional FeatureConstraints.** FeatureConstraints are the Layer 4 → Layer 5 bridge.
- **DD-19 — Two-pass maximum in v1.** No iterative feature/solve convergence loop.
- **DD-20 — Suppressed candidates are retained.** Suppressed/rejected/weak candidates are inspectable diagnostics.
- **DD-21 — Detail generation is external.** Detail/decal/wear systems consume Scaffold APIs.
- **DD-22 — SEAM_SELF is first-class.** Two ChainUses of one Chain in one Patch is supported.
- **DD-23 — Architecture allows N AlignmentClasses per patch; v1 resolves at most two.** Non-orthogonal/curved/N-family cases are future work.
- **DD-24 — Direction clustering is conservative in v1.** Straight-like ChainUses only, chord direction only, fixed tolerance.
- **DD-25 — Layer 3 is frozen after Pass 1.** Pass 2 may consume Layer 3 but must not write to it.
- **DD-26 — FeatureConstraint is first-class.** FeatureConstraint is the only channel from accepted features into solve.
- **DD-27 — G1 Patch segmentation is seam-only by default.** Patch flood fill is blocked by border, non-manifold selected edge, explicit Scaffold boundary mark, and Blender UV Seam. Blender Sharp is not a default boundary source.
- **DD-28 — G1 Shell detection ignores Patch boundaries.** Shells are selected-face edge-connected components. Seams and explicit Patch boundaries may split Patches but do not split Shells. Vertex-only contact does not connect Shells.

## Future policy notes

A future optional command/flag may support:

```text
make seams by sharps
```

That future option should convert sharp information into seam/boundary input before segmentation. It must not make Sharp a hidden default segmentation source.
