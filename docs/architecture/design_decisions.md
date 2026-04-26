# Design Decisions — Scaffold Core

This file mirrors the authoritative DD register in `G0.md`.

Agents may read this file for quick lookup. If it disagrees with `G0.md`, `G0.md` wins.

## Terminology

Current terminology for the final boundary graph model:

| Term | Meaning |
|---|---|
| `PatchChain` | Final patch-local oriented occurrence of a Chain in a BoundaryLoop. |
| `PatchChainDirectionalEvidence` | Derived directional measurement for a PatchChain. |
| `PatchChainEndpointSample` | Endpoint ray/evidence sample for a PatchChain directional measurement. |
| `PatchChainEndpointRelation` | Pairwise local relation between endpoint samples at one Vertex. |
| `LocalFaceFanGeometryFacts` | Local owner-normal geometry evidence. |
| `LoopCorner` | Patch-local transition between adjacent PatchChains in one BoundaryLoop. |
| `ScaffoldJunction` | Future graph-level ScaffoldNode classification for branch/seam/cross-patch structures. |

Endpoint samples, endpoint relations and LocalFaceFanGeometryFacts are evidence
or measurements; they are not graph nodes. A ScaffoldJunction is introduced
only after graph-level classification.

## Core decisions

- **DD-01 — Topology is immutable snapshot.** Scaffold Core does not mutate topology in place.
- **DD-02 — PatchChain is mandatory.** All oriented boundary use is represented through `PatchChain`.
- **DD-03 — Topology and geometry are separate.** Layer 1 stores incidence/orientation; Layer 2 stores measured geometry.
- **DD-04 — H/V is not a primary stored role.** H/V-like labels are derived runtime/debug labels.
- **DD-05 — WALL/FLOOR/SLOPE is not a primary patch type.** World-facing semantics are derived WorldOrientation facts.
- **DD-06 — Relations are derived caches with provenance.** Relations store confidence, evidence, source and snapshot context.
- **DD-07 — Alignment membership is per PatchChain.** A Chain may have multiple PatchChains with different AlignmentClass memberships.
- **DD-08 — Patch axes are derived from AlignmentClasses.** PatchAxes is Layer 3 classification, not solve output.
- **DD-09 — Continuation is a Layer 3 relation.** Old ContinuationEdge becomes ChainContinuationRelation.
- **DD-10 — Dihedral is a PatchAdjacency relation.** Signed dihedral references patch pair, shared Chain and both PatchChains.
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
- **DD-22 — SEAM_SELF is first-class.** Two PatchChains of one Chain in one Patch is supported.
- **DD-23 — Architecture allows N AlignmentClasses per patch; v1 resolves at most two.** Non-orthogonal/curved/N-family cases are future work.
- **DD-24 — Direction clustering is conservative in v1.** Straight-like PatchChains only, chord direction only, fixed tolerance.
- **DD-25 — Layer 3 is frozen after Pass 1.** Pass 2 may consume Layer 3 but must not write to it.
- **DD-26 — FeatureConstraint is first-class.** FeatureConstraint is the only channel from accepted features into solve.
- **DD-27 — G1 Patch segmentation is seam-only by default.** Patch flood fill is blocked by border, non-manifold selected edge, explicit Scaffold boundary mark, and Blender UV Seam. Blender Sharp is not a default boundary source.
- **DD-28 — G1 Shell detection ignores Patch boundaries.** Shells are selected-face edge-connected components. Seams and explicit Patch boundaries may split Patches but do not split Shells. Vertex-only contact does not connect Shells.
- **DD-29 — Chain coalescing is staged.** G1 / G3a uses
  topology/materialization context only. Consecutive boundary sides with the
  same boundary run kind and Patch context may coalesce into logical Chains,
  including border runs. Seam cuts may materialize duplicate topology Vertex
  occurrences so one source vertex can appear on both sides of a Patch loop.
  Closed, turning, or direction-ambiguous Chains require Layer 2
  geometry-based refinement before Alignment. Coalescing and refinement are
  scoped to one ordered atomic boundary cycle that materializes as one final
  BoundaryLoop.
- **DD-30 — Chain refinement does not change Layer 1 Chain identity.**
  Layer 1 Chain identity is topology-only. Geometry-driven refinement
  lives in Layer 3 and produces derived sub-chain entities or alignment
  groupings. It must not split, rewrite, or re-id Layer 1 Chains.
- **DD-31 — PatchChain endpoint relations are local and axis-free.** PatchChain endpoint relations
  are Layer 3 derived relations between patch-local `PatchChainDirectionalEvidence`
  endpoint samples at the same Vertex. They classify local structural
  relations such as continuation candidate, corner connector, oblique
  connector, ambiguous and degenerate. They must not use U/V labels, H/V
  labels, WORLD_UP, WorldOrientation labels or runtime solve output.
- **DD-32 — Surface normals for PatchChain are derived facts, not Layer 1
  topology.** Layer 1 `PatchChain` must not store face normals or averaged
  normals. Owner normals used by endpoint relations are derived from Layer 2
  geometry or Layer 3 evidence. LocalFaceFanGeometryFacts may provide local
  endpoint normals; Patch aggregate normals are a fallback.
- **DD-33 — ScaffoldGraph is derived from endpoint relations.**
  ScaffoldGraph / ScaffoldTrace are future Layer 3 derived structures built
  from `PatchChainEndpointRelation`, not from raw Chain or world axes. They
  must not be introduced before pairwise endpoint relations exist.
- **DD-34 — Final PatchChain is the single source of truth.**
  BoundaryLoop contains final PatchChains. Raw boundary sides, atomic source
  edges and draft runs are builder internals. ScaffoldGraph must use final
  PatchChains as graph edges, not a parallel effective PatchChain layer.
- **DD-35 — LoopCorner is patch-local; ScaffoldJunction is graph-level.**
  LoopCorner is the local transition between adjacent PatchChains inside one
  BoundaryLoop. A LoopCorner may become a ScaffoldNode. It becomes a
  ScaffoldJunction only when graph-level classification says it is
  structural: 3+ incident PatchChains, seam pair, cross-patch connection,
  branch, or other graph-level structure.
- **DD-36 — LocalFaceFan is geometry evidence, not graph topology.**
  LocalFaceFanGeometryFacts provides local normals for endpoint evidence. It
  is not a ScaffoldNode and not a graph entity.

## Future policy notes

A future optional command/flag may support:

```text
make seams by sharps
```

That future option should convert sharp information into seam/boundary input before segmentation. It must not make Sharp a hidden default segmentation source.

## Open questions

- **OQ-11 — Geometry-based Chain refinement policy.** Partially resolved for
  straight/turning polygonal Chains through Layer 3 `ChainDirectionalRun` and
  `PatchChainDirectionalEvidence`. Curved-chain handling, sawtooth tuning, user split
  marks, closed-loop wrap merge and relation to PatchChainEndpointRelation /
  ScaffoldGraph remain unresolved. See `G0.md` Section 6.
