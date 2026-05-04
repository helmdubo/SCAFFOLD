# Scaffold Core — G0 v1.2

> **Immutable B-rep-inspired Interpretation Pipeline**

**Status:** architectural contract v1.2
**Scope:** implementation-aligned architecture
**Purpose:** stable conceptual and structural model for Scaffold Core.

This document is the canonical reference for subsequent implementation plans: G1, G2, G3, etc. Phase plans cite G0 sections as their contract; they may not override G0 design decisions without an explicit G0 amendment.

---

# Changelog

## v1.2

- Adopted PatchChain as the canonical name for patch-local oriented Chain occurrence.
- Defined final PatchChain as the single source of truth for patch boundary graph edges.
- Clarified materialized seam-cut topology and duplicate topology Vertex occurrences.
- Added LoopCorner / ScaffoldNode / ScaffoldJunction / ScaffoldGraph terminology.
- Clarified LocalFaceFanGeometryFacts as geometry evidence, not graph topology.
- Added PatchChainEndpointSample / PatchChainEndpointRelation terminology.
- Added LoopCorner as patch-local transition between adjacent PatchChains.
- Implemented ScaffoldNode v0 as graph-level evidence, not Layer 1 identity.
- Implemented ScaffoldEdge v0 as a graph-level view of one final PatchChain.
- Implemented ScaffoldGraph v0 as connectivity assembled from ScaffoldNodes and ScaffoldEdges.
- Implemented ScaffoldJunction v0 as a SELF_SEAM/CROSS_PATCH classification overlay.
- Implemented ScaffoldNodeIncidentEdgeRelation v1 all-pairs edge-end occurrence contract.
- Implemented ScaffoldContinuityComponent v0 continuity-family evidence contract.
- Implemented SURFACE_SLIDING_CONTINUATION_CANDIDATE relation-kind contract.
- Amended DD-29 to allow topology/materialization-based border coalescing.
- Marked OQ-11 as partially resolved for polygonal straight/turning Chains.

---

# 0. Executive Summary

Scaffold Core is an immutable B-rep-inspired interpretation pipeline for topology-aware structural UV alignment.

It does not attempt to become a CAD kernel. It borrows B-rep discipline — topology/geometry separation, oriented edge-use, shells, loops, adjacency graphs, feature recognition — and applies it to a polygonal Blender mesh workflow.

Scaffold Core builds a read-only **Topology Snapshot** from a source mesh, attaches derived **Geometry Facts**, derives **Relation Graphs** such as adjacency, alignment, continuation and world semantics, recognizes higher-level **Feature Candidates**, resolves them into **Feature Instances**, and runs **Runtime/Solve** steps such as skeleton solve, pin policy and UV transfer.

Scaffold owns interpretation.  
Blender owns mesh editing.

Recommended Blender add-on metadata:

```python
bl_info = {
    "name": "Scaffold",
    "author": "...",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "category": "UV",
    "description": "Structural UV for architectural meshes",
    "location": "UV Editor > Sidebar > Scaffold",
}
```

`category = "UV"` is intentional. The primary workflow lives in UV space.

The core package is:

```text
scaffold_core/
```

The add-on wrapper may later live in:

```text
scaffold/
```

---

# 1. Core Design Goal

Remove old hard-coded assumptions:

```text
old:
  WALL / FLOOR / SLOPE as primary patch types
  H_FRAME / V_FRAME as primary chain roles
  local patch basis as early truth
  solve logic mixed with recognition logic
  ContinuationEdge ad-hoc alongside Chain

new:
  geometry facts are raw, uninterpreted
  topology is explicit, oriented, immutable
  PatchChain is the final patch-local boundary edge source of truth
  AlignmentClass derives axis-like structure from PatchChain directional evidence
  WorldOrientation is a parallel semantic overlay
  features are graph-pattern interpretations with evidence
  runtime roles are late, derived, and task-specific
  continuation is a first-class Layer 3 relation
```

Two architectural cycles are explicitly forbidden:

```text
forbidden:
  skeleton solve → determines axes
  world orientation → determines alignment
```

Instead:

```text
Layer 2:
  raw geometry directions

Layer 3:
  AlignmentClass and PatchAxes are derived before solve

Layer 5:
  skeleton solve consumes AlignmentClass / PatchAxes and computes coordinates
```

And:

```text
WorldOrientation is a deferred parallel semantic overlay.
WorldOrientation does not depend on skeleton solve.
AlignmentClass and PatchAxes must not use WORLD_UP or WorldOrientation labels.
WorldOrientation must not feed back into Layer 1 topology, PatchChain identity,
AlignmentClass grouping or PatchAxes selection.
```

---

# 2. Non-goals

The following are explicitly excluded from v1.

| Non-goal | Reason |
|---|---|
| Full CAD kernel | Scaffold Core is a polygonal UV/trim interpretation system, not Parasolid/OpenCascade. |
| NURBS / trimmed analytic surfaces | v1 operates on polygonal geometry facts; surface fitting may exist later. |
| CSG / boolean operations | Not relevant to UV/trim solve. |
| In-place topology mutation | Read-only snapshots avoid Euler-operator complexity. |
| Full persistent naming system | Structural fingerprints suffice for v1 override reassociation. |
| Incremental dynamic graph maintenance | Full rebuild is preferred until profiling proves bottleneck. |
| Custom rule DSL | Feature rules start as typed Python-level rules later; G0 defines architecture, not DSL. |
| Detail / decal / wear generation | External consumer of Scaffold interpretation APIs, not part of core. |
| Machine-learning feature recognition | v1 uses explicit graph-pattern rules with evidence. |
| Iterative recognition / solve convergence | Two-pass maximum; no iterative refinement loop. |
| H/V, WALL/FLOOR/SLOPE as primary stored facts | Derived only, never stored on topology entities. |
| Sub-millimeter CAD precision | Production mesh tolerance is enough for v1. |

---

# 3. Layer Overview

```text
Layer 0 — Source Mesh Snapshot
Layer 1 — Immutable Topology Snapshot
Layer 2 — Geometry Facts
Layer 3 — Derived Relations
Layer 4 — Feature Grammar
Layer 5 — Runtime / Solve
```

## 3.1 Layer 0 — Source Mesh Snapshot

Contains mesh provenance and source inputs:

- source mesh object id;
- source vertex/edge/face references;
- seam marks;
- sharp marks;
- material boundaries;
- user marks;
- source checksums/fingerprints;
- classifier override inputs.

Layer 0 is the only core layer allowed to reflect raw Blender/BMesh identity directly.

## 3.2 Layer 1 — Immutable Topology Snapshot

Core entities:

- `SurfaceModel`
- `Shell`
- `Patch`
- `BoundaryLoop`
- `Chain`
- `PatchChain`
- `Vertex`

Layer 1 stores incidence, ownership, loop order and orientation.

It does not store semantic roles.

## 3.3 Layer 2 — Geometry Facts

Derived geometric measurements attached to topology:

- patch normal;
- patch area;
- patch fit quality;
- chain chord direction;
- chain length;
- straightness;
- sawtooth-straight classification;
- detour ratio;
- curvature signals;
- vertex position;
- local tangent samples.

Layer 2 answers:

```text
What is the geometry?
```

It does not answer:

```text
What is this chain used for?
```

## 3.4 Layer 3 — Derived Relations

Derived, cached, provenance-carrying relations over topology and geometry.

Namespaces:

- `adjacency.*`
- `alignment.*`
- `continuation.*`
- `patch_chain_endpoint.*`
- `world_orientation.*`
- `diagnostics.*`

Layer 3 is frozen after Pass 1.

Layer 4 must not write new Layer 3 relations.

Feature-local alignment is expressed as `FeatureConstraint`, not as newly registered `AlignmentClass`.

## 3.7 Glossary

### Current / implemented or conceptually active

| Term | Meaning |
|---|---|
| `Chain` | Shared/logical boundary run referenced by one or more PatchChains. |
| `PatchChain` | Final patch-local oriented occurrence of a Chain in a BoundaryLoop. |
| `BoundaryLoop` | Final ordered sequence of PatchChains. |
| `LocalFaceFanGeometryFacts` | Local owner-normal geometry evidence; not graph topology. |
| `ChainDirectionalRun` | Direction-ready measured run derived from Chain geometry. |
| `PatchChainDirectionalEvidence` | Derived directional measurement for a PatchChain; not competing PatchChain identity. |
| `PatchChainEndpointSample` | Endpoint ray/evidence sample for a PatchChain directional measurement; not a graph node. |
| `PatchChainEndpointRelation` | Pairwise local relation between endpoint samples at one Vertex; not a graph node. |
| `LoopCorner` | Patch-local transition between adjacent PatchChains in one BoundaryLoop. |
| `ScaffoldNode` | Implemented G3c7 graph-level evidence node assembled from LoopCorners and endpoint evidence; not Layer 1 identity. |
| `ScaffoldEdge` | Implemented G3c8 graph-level view of one final PatchChain. |
| `ScaffoldGraph` | Implemented G3c8 connectivity graph assembled from ScaffoldNodes and ScaffoldEdges. |
| `ScaffoldJunction` | Implemented SELF_SEAM/CROSS_PATCH graph-level classification overlay on existing ScaffoldNode records; not a separate graph node identity. |
| `AlignmentClass` | Implemented Layer 3 direction-family grouping over PatchChainDirectionalEvidence. |
| `PatchAxes` | Implemented Layer 3 primary/secondary AlignmentClass selection per Patch. |

Implementation status:
Code has already adopted canonical terms for PatchChain,
PatchChainEndpointSample, PatchChainEndpointRelation, LocalFaceFanGeometryFacts,
LoopCorner and ScaffoldNode. No code rename is required as part of this
documentation cleanup.

### Future / reserved nomenclature, not implemented yet

| Term | Meaning |
|---|---|
| `ScaffoldTrace` | Future connected sequence of ScaffoldEdges through ScaffoldNodes. |
| `ScaffoldCircuit` | Future closed ScaffoldTrace. |
| `ScaffoldRail` | Future direction-stable ScaffoldTrace usable as a conditional axis. |
| `WorldOrientation` | Future/deferred parallel semantic overlay. |

Future terms reserve naming and constraints only. They must not be implemented
during documentation cleanup.

## 3.5 Layer 4 — Feature Grammar

Graph-pattern feature recognition.

Produces:

- `FeatureCandidate`
- `FeatureInstance`
- `FeatureConstraint`
- suppressed/weak/rejected diagnostic records.

## 3.6 Layer 5 — Runtime / Solve

Task-specific interpretation and numerical solving:

- skeleton solve;
- resolved axis labels;
- pin policy;
- UV constraints;
- scaffold placement;
- transfer to UV;
- debug projection;
- reporting/export.

Layer 5 is allowed to produce runtime artifacts. It is not allowed to rewrite topology, geometry, relations or feature decisions.

---

# 4. B-rep Mapping

Conceptual mapping, not literal CAD implementation.

| B-rep concept | Scaffold Core concept | Notes |
|---|---|---|
| Solid | Usually omitted | Inside/outside volume semantics not needed in v1. |
| Shell | `Shell` | Connected surface component; may be open/non-manifold. |
| Face | `Patch` | Polygonal surface region. |
| Loop / Wire | `BoundaryLoop` | Outer or inner patch boundary. |
| Edge | `Chain` | Shared boundary curve/polyline entity. |
| Coedge / Edge-use | `PatchChain` | Oriented use of a Chain by one Loop. Mandatory. |
| Vertex | `Vertex` | Topological point; ScaffoldJunction classification is derived from ScaffoldNode. |
| Face adjacency graph | Patch dual graph | Layer 3 `adjacency.*`. |
| Feature recognition | Feature grammar | Layer 4 graph-pattern recognition. |
| Attributed Adjacency Graph | `PatchAdjacency` | Dihedral, continuity, shared length, evidence. |

What Scaffold adds beyond B-rep:

- `AlignmentClass` — derived axis-like structure over oriented uses.
- `ChainContinuationRelation` — explicit continuation through patch-chain incidence at vertices.
- `WorldOrientation` — world-facing semantic overlay, separate from topology.
- `FeatureConstraint` — explicit bridge from Layer 4 to Layer 5.

---

# 5. Layer 1 — Immutable Topology Snapshot

## 5.1 Purpose

Layer 1 is the stable topological substrate.

It represents how the source mesh is decomposed into surface regions, boundaries, loops and oriented boundary uses.

Layer 1 is intentionally ignorant of:

- H/V roles;
- wall/floor/slope;
- UV coordinates;
- pin decisions;
- feature classifications;
- runtime solve roles.

## 5.2 Entity hierarchy

```text
SurfaceModel
  └── Shell
        └── Patch
              └── BoundaryLoop
                    └── PatchChain
                          └── Chain
                                └── Vertex endpoints
```

## 5.3 Core entities

`SurfaceModel` represents one interpreted mesh object or selected region.

`Shell` is a connected topological surface component. It may be open, partial, non-manifold, intentionally cut, or disconnected from other shells.

`Patch` is a polygonal surface region. It owns boundary loops and belongs to exactly one shell.

`BoundaryLoop` is an ordered loop of final oriented `PatchChain` records.


`Chain` is a shared topological boundary entity. It is not patch-local.

`PatchChain` is the oriented use of a `Chain` in a `BoundaryLoop`. It has
`orientation_sign: +1 | -1`, start/end vertices and position in loop order.


`Vertex` is a topological endpoint. `ScaffoldJunction` is a graph-level
classification overlay on existing ScaffoldNode, not every topology Vertex.

## 5.4 Chain / PatchChain cardinality cases

Layer 1 must explicitly support all four cases.

| Case | Chain has N PatchChains | Meaning |
|---|---:|---|
| Mesh border | 1 | Boundary of model or selected region; no opposite patch use. |
| Normal shared boundary | 2, different patches | Standard patch adjacency. |
| SEAM_SELF | 2, same patch | Same patch uses the same Chain twice. Supported case, not anomaly. |
| Non-manifold | >2 | Ambiguous input; represented explicitly and diagnosed. |

## 5.5 Layer 1 invariants

- Every entity has a snapshot-local id.
- Every `Patch` belongs to exactly one `Shell`.
- Every `BoundaryLoop` belongs to exactly one `Patch`.
- Every `PatchChain` belongs to exactly one `BoundaryLoop`.
- Every `PatchChain` references exactly one `Chain`.
- Every `Chain` references two endpoint vertices unless explicitly marked degenerate.
- BoundaryLoop PatchChains form a closed cycle or emit degraded/blocking diagnostic.
- Chain cardinality cases are explicit.
- SEAM_SELF is supported.
- Non-manifold multi-use is represented and flagged.

Layer 1 must not contain H/V roles, WALL/FLOOR/SLOPE, feature roles, UV coordinates, skeleton solve coordinates, feature confidence, detail semantics or runtime solve decisions.

---

# 6. Diagnostic Severity

All diagnostics must have severity.

```text
BLOCKING:
  pipeline cannot safely continue

DEGRADED:
  pipeline may continue in limited mode

WARNING:
  pipeline continues, issue is visible

INFO:
  informational diagnostic
```

The pipeline halts only on `BLOCKING`.

---

# 7. Layer 0 — Source Mesh Snapshot

Layer 0 is the provenance layer.

It contains:

- raw mesh references;
- mesh marks;
- user marks;
- user overrides;
- checksums/fingerprints.

It is the only core layer allowed to reflect raw Blender/BMesh identity directly.

---

# 8. Layer 2 — Geometry Facts

Layer 2 attaches measured geometry to topology.

It answers:

```text
What shape does this topology have in 3D?
```

It does not answer:

```text
What role does this topology play?
```

The old sawtooth algorithm must not promote `FREE → H/V`.

In Scaffold Core it becomes a pure geometry classifier:

```text
ChainGeometryFacts.shape_hint = SAWTOOTH_STRAIGHT
```

Role assignment happens later through Layer 3 alignment or Layer 4 feature interpretation.

---

# 9. Layer 3 — Derived Relations

Layer 3 contains derived relation caches with provenance.

Layer 3 is computed from:

- Layer 1 topology;
- Layer 2 geometry;
- Layer 0 overrides, where applicable.

Layer 3 does not depend on Layer 5.

Layer 3 is frozen after Pass 1.

Layer 4 must not write into Layer 3.

Namespaces:

```text
adjacency.*
alignment.*
continuation.*
patch_chain_endpoint.*
world_orientation.*
diagnostics.*
```

---

# 10. Adjacency

Patch-to-patch relations through shared Chains form the patch dual graph / AAG-like structure.

`DihedralKind` is an attribute of `PatchAdjacency`, not of `Chain`.

A query by Chain must return a list of adjacency records, not a single dihedral value.

Signed dihedral computation must use both PatchChain orientations.

---

# 11. Alignment

Replace primary H/V classification with derived axis-like structure.

Old model:

```text
BoundaryChain.frame_role = H_FRAME / V_FRAME / FREE
```

New model:

```text
PatchChain belongs to AlignmentClass
PatchAxes choose primary/secondary AlignmentClasses
Runtime may expose H-like/V-like labels for debug
```

Alignment membership is per `PatchChain`, not per `Chain`.

A single Chain may have multiple PatchChains that belong to different AlignmentClasses.

v1 direction clustering is conservative:

- straight-like PatchChains only;
- chord direction only;
- fixed tolerance;
- no adaptive widening;
- no WORLD_UP bias;
- no WorldOrientation labels.

PatchAxes is Layer 3 classification, not solve output.

Skeleton solve must not determine axes.

---

# 12. Continuation

`ChainContinuationRelation` replaces ad-hoc `ContinuationEdge`.

It answers:

```text
this PatchChain continues into that PatchChain through this Vertex
```

Continuation is a Layer 3 relation, not a topology primitive.

## 12.1 PatchChain Endpoint Relations

`patch_chain_endpoint.*` contains derived local relations around topology Vertices.

PatchChain endpoint relations do not create new Layer 1 topology. They are derived views
over Vertex, PatchChain, PatchChain directional evidence
and Layer 2 geometry facts.

The primary low-level unit is a patch-local directional endpoint sample:

```text
PatchChainEndpointSample
```

Pairwise relations between samples answer:

```text
At this Vertex, how does this PatchChain endpoint relate to another?
```

Relation kinds include:

```text
CONTINUATION_CANDIDATE
CORNER_CONNECTOR
OBLIQUE_CONNECTOR
AMBIGUOUS
DEGENERATE
```

These relations are axis-free:

- no U/V;
- no H/V;
- no WORLD_UP;
- no WALL/FLOOR/SLOPE;
- no WorldOrientation dependency.

ScaffoldNode v0 is graph-level evidence assembled from LoopCorners and endpoint
evidence. It is not Layer 1 identity.

ScaffoldGraph is derived from these endpoint relations, LoopCorner data and
ScaffoldNode evidence.

Endpoint samples, endpoint relations and LocalFaceFanGeometryFacts are evidence
or measurements; they are not graph nodes.

`LoopCorner` is the patch-local transition between adjacent PatchChains inside
one BoundaryLoop. It may feed ScaffoldNode evidence.

`ScaffoldJunction` is graph-level classification of an existing ScaffoldNode,
not every PatchChain endpoint sample or LoopCorner. Ordinary ScaffoldNodes
remain unclassified unless a ScaffoldJunction classifier emits a record.

ScaffoldJunction classification is an overlay on existing ScaffoldNode records,
not a separate graph node identity. Implemented `SELF_SEAM` classifies a
ScaffoldNode where two incident final PatchChains share the same ChainId and
same PatchId, representing the supported SEAM_SELF case. Implemented
`CROSS_PATCH` classifies an existing ScaffoldNode whose incident final
ScaffoldEdges reference more than one distinct PatchId. Future kind vocabulary
beyond SELF_SEAM/CROSS_PATCH includes `BRANCH`, `TERMINUS`,
`BORDER_TERMINUS`, `AMBIGUOUS` and `DEGRADED`.

ScaffoldJunction classification must not change ScaffoldNode grouping, change
PatchChain identity, walk traces, detect circuits, select rails, choose
continuations or introduce UV, runtime or feature semantics.

Implemented ScaffoldNodeIncidentEdgeRelation v1 is a complete unordered all-pairs
relation over incident ScaffoldEdge endpoint occurrences at one existing
ScaffoldNode. For n incident edge-end occurrences at one ScaffoldNode, v1 emits
C(n,2) relations. Emission is graph-structural: missing endpoint sample or
endpoint relation evidence must not cause a pair to disappear.

Classification is evidence-backed and may use tangent direction evidence,
owner normal evidence, direction_dot, normal_dot, endpoint sample ids,
PatchChainEndpointRelation id when available, confidence and evidence quality.
It is evidence only. It must not select trace paths, circuits, rails,
continuations, UV behavior or runtime behavior.

Implemented v1 relation kinds:

```text
SURFACE_SLIDING_CONTINUATION_CANDIDATE
STRAIGHT_CONTINUATION_CANDIDATE
SURFACE_CONTINUATION_CANDIDATE
CROSS_SURFACE_CONNECTOR
ORTHOGONAL_CORNER
OBLIQUE_CONNECTOR
SAME_RAY_AMBIGUOUS
MISSING_ENDPOINT_EVIDENCE
DEGRADED
```

SURFACE_SLIDING_CONTINUATION_CANDIDATE is a node-local relation between two
existing ScaffoldEdge endpoint occurrences whose local tangent/chord
classification may otherwise look orthogonal or same-ray, but explicit
same-side-surface evidence plus compatible local owner normals support
continuation along the same curved or side surface. It is not a trace path
choice, not a selected next edge, not a rail/circuit decision and not a UV
direction.

It requires local owner-normal evidence, compatible local owner normals and
explicit same-side-surface evidence. Missing or degraded evidence must not
produce this kind. SharedChainPatchChainRelation alone must not produce this
kind. Cross-patch cap, corner and shared-boundary cases must remain
non-propagating unless same-side-surface evidence is explicit and safe.

ScaffoldNodeIncidentEdgeRelation v1 must not change ScaffoldNode grouping,
ScaffoldEdge identity, PatchChain identity, Chain identity, Vertex identity or
BoundaryLoop identity. It must not use H/V, U/V, WORLD_UP, WorldOrientation,
Feature, API, UI, runtime solve or UV transfer.

Tube examples:
- tube without caps split by multiple seam chains: top border PatchChains may
  become SURFACE_SLIDING_CONTINUATION_CANDIDATE through seam nodes when
  explicit same-side-surface evidence and compatible local owner normals prove
  curved side-surface continuation. The expected continuity result is two side
  families rather than four singleton side boundary edges.
- tube with cap patch: side-to-cap PatchChains may be shared/cross-patch
  neighbors, but they are not side-surface continuation when owner normals
  diverge.
- folded 90 seam, cube-like corner and cap-cross-surface cases remain
  non-propagating unless explicit same-side-surface evidence is safe.
- local D:\cylinder.blend is an exploratory smoke fixture, not the canonical
  synthetic fixture for this contract.

`ScaffoldEdge` is the graph-level view of a final PatchChain. `ScaffoldGraph`
is connectivity-only over ScaffoldNodes and ScaffoldEdges. `ScaffoldTrace` is
a future connected sequence of ScaffoldEdges through ScaffoldNodes.
`ScaffoldCircuit` is a closed ScaffoldTrace. `ScaffoldRail` is a future
direction-stable ScaffoldTrace usable as a conditional axis.

Implemented ScaffoldContinuityComponent v0 is a Layer 3 derived evidence view over
existing ScaffoldEdges and existing ScaffoldNodeIncidentEdgeRelation records. It
groups ScaffoldEdges into continuity families using continuation-compatible
incident relations. It is not a trace, path choice, rail, circuit, UV
direction, runtime behavior or replacement for ScaffoldEdge or PatchChain
identity.

---

# 13. WorldOrientation

WorldOrientation is deferred. It may later restore practical wall/floor/up/down
semantics without polluting topology or solve.

WORLD_UP remains forbidden for current AlignmentClass and PatchAxes builders:

```text
AlignmentClass / PatchAxes:
  no WORLD_UP vector bias
  no SurfaceRole labels
  no WorldOrientation labels
```

Future WorldOrientation must remain a parallel semantic overlay. It must not
depend on skeleton solve, runtime UV, feature recognition or accepted
FeatureInstances.

---

# 14. Layer 4 — Feature Grammar

Feature grammar recognizes higher-level structures through attributed graph patterns.

Feature grammar is not a cascade of `if/elif`.

Layer 4 produces:

- `FeatureCandidate`
- `FeatureInstance`
- `FeatureConstraint`

Layer 4 must not write Layer 3 data.

---

# 15. FeatureConstraint

`FeatureConstraint` is the only feature-to-solve communication channel.

It is the explicit interface from Layer 4 to Layer 5.

A `FeatureConstraint` must be self-contained.

It may reference existing Layer 3 `AlignmentClassId`, but it must not require new Layer 3 AlignmentClasses to be registered after Pass 1.

---

# 16. Layer 5 — Runtime / Solve

Layer 5 consumes Layers 1–4.

It does not:

- discover topology;
- classify raw geometry;
- modify Layer 1–4 outputs.

Skeleton solve consumes AlignmentClasses and PatchAxes from Layer 3, and FeatureConstraints from Layer 4.

---

# 17. Pipeline Passes

Allowed direction:

```text
Layer 0 → Layer 1 → Layer 2 → Layer 3 → Layer 4 → Layer 5
```

Allowed feature-to-solve bridge:

```text
Layer 4 FeatureInstance
  → FeatureConstraint
  → Layer 5 pass 2
```

Forbidden:

```text
Layer 5 → Layer 3
Layer 5 → Layer 2
Layer 5 → Layer 1
Layer 4 → Layer 3
Layer 4 → Layer 2
Layer 4 → Layer 1
Layer 3 → Layer 1
WorldOrientation labels → base Alignment
```

Pass overview:

```text
Pass 0    Source + topology + geometry
Pass 1    Relations + alignment
Pass 2    Features + optional second solve
Pass 3    Final runtime outputs / reports / API
```

---

# 18. Pass 0 — Snapshot Foundations

Inputs:

- Blender mesh state;
- selected faces/objects;
- seams;
- sharp marks;
- material marks;
- user overrides affecting interpretation.

Outputs:

- Layer 0 Source Mesh Snapshot;
- Layer 1 Topology Snapshot;
- Layer 2 Geometry Facts.

Steps:

1. Read BMesh.
2. Extract vertices, edges, faces and marks.
3. Segment faces into patches using configured patch segmentation policy.
4. Build shells.
5. Build boundary loops.
6. Build Chains and PatchChains.
7. Assign structural fingerprints.
8. Compute geometry facts.

Patch segmentation policy is unresolved in G0.

Do not hardcode `seam + sharp` until OQ-01 is resolved.

Pipeline halts only on `BLOCKING` topology errors.

---

# 19. Pass 1 — Relations and Alignment

Inputs:

- Layer 1 topology;
- Layer 2 geometry;
- user relation/alignment overrides.

Outputs:

- Layer 3 complete base relations.

Steps:

1. Build PatchAdjacency.
2. Compute DihedralKind using PatchAdjacency and both PatchChain orientations.
3. Build PatchChain endpoint relations.
4. Build Continuation relations.
5. Build AlignmentClasses.
6. Build PatchAxes.
7. Freeze Layer 3.

Layer 3 is frozen after Pass 1.

Pass 2 must not add or rewrite Layer 3 records.

---

# 20. Pass 2 — Feature Recognition and Optional Second Solve

Inputs:

- Layers 1–3;
- skeleton solve pass 1;
- user feature overrides.

Outputs:

- FeatureCandidates;
- FeatureInstances;
- FeatureConstraints;
- suppressed/weak/rejected diagnostics;
- skeleton solve pass 2, if enabled.

Forbidden:

- writing to Layer 3;
- registering new AlignmentClasses in Layer 3;
- iterative recognition/solve loops;
- mutating topology or geometry.

---

# 21. User Overrides

User overrides are inputs, not mutations.

They influence pipeline rebuilds but do not directly patch Layer 1 topology objects.

Override categories:

- source-level overrides;
- classifier-level overrides;
- feature-level overrides;
- runtime-level overrides.

Overrides store structural fingerprint of the target entity.

---

# 22. Rebuild Policy

v1 uses full rebuild.

Any relevant source change may rebuild the full interpretation snapshot.

Reasons:

- deterministic;
- simple;
- debuggable;
- avoids invalidation complexity;
- likely fast enough.

Partial recompute is future optimization only.

Layers 3, 4 and 5 always full rebuild in v1.

---

# 23. Design Decisions Register

The authoritative compact DD register is also mirrored in `docs/architecture/design_decisions.md`.

## DD-29 — Chain coalescing is staged

Layer 1 materializes final PatchChains from raw boundary elements.

Raw boundary sides, atomic source edges, draft boundary runs and raw boundary
cycles are builder internals. They are not public model entities.

Boundary coalescing uses topology/materialization context only:
- boundary run kind;
- Patch context;
- seam/cut side;
- neighbour context;
- loop materialization.

Border runs may coalesce into ordered Chains when materialization policy
identifies them as one final PatchChain.

Reason:
Cylinder tube without caps + one seam cut showed that edge-atomic border Chains
prevent correct materialized BoundaryLoop construction. Border ring runs must
be allowed to coalesce into final PatchChains.

Geometry may later describe or classify a final PatchChain, but it must not
create a competing public PatchChain identity.

## DD-30 — Chain refinement does not change Layer 1 Chain identity

Layer 1 Chain identity is decided by topology coalescing only.

Geometry-driven Chain refinement, when introduced, lives in Layer 3 and
must be computed before AlignmentClass consumes Chain-like entities.

Refinement may produce derived sub-chain entities or alignment-level
groupings that AlignmentClass consumes. It must not rewrite, split, or
re-id existing Layer 1 Chain records after Pass 0.

This preserves stable Chain ids for downstream references and keeps
geometry-driven decisions inside Layer 3.

## DD-31 — PatchChain endpoint relations are local and axis-free

PatchChain endpoint relations are Layer 3 derived relations between patch-local
`PatchChainDirectionalEvidence` endpoint samples at the same Vertex.

They classify local structural relations such as continuation candidate,
corner connector, oblique connector, ambiguous and degenerate.

They must not use U/V labels, H/V labels, WORLD_UP, WorldOrientation labels or
runtime solve output.

## DD-32 — Surface normals for PatchChain are derived facts, not Layer 1 topology

Layer 1 `PatchChain` must not store face normals or averaged normals.

Owner normals used by endpoint relations are derived from Layer 2 geometry or
Layer 3 evidence. LocalFaceFanGeometryFacts may provide local endpoint
normals; Patch aggregate normals are a fallback.

## DD-33 — ScaffoldGraph is derived from endpoint relations and LoopCorners

ScaffoldGraph is a Layer 3 derived structure built from
`PatchChainEndpointRelation`, `LoopCorner` and implemented `ScaffoldNode` evidence,
not from raw Chain or world axes. ScaffoldTrace remains deferred.

ScaffoldEdge is a graph-level view of final PatchChain, not a competing
PatchChain identity.

## DD-34 — Final PatchChain is the single source of truth

BoundaryLoop contains final PatchChains. Raw boundary sides, atomic source
edges and draft runs are builder internals.

ScaffoldGraph must use final PatchChains as graph edges, not a parallel
effective PatchChain layer.

## DD-35 — LoopCorner is patch-local; ScaffoldJunction is graph-level

LoopCorner is the local transition between adjacent PatchChains inside one
BoundaryLoop. A LoopCorner may feed ScaffoldNode evidence.

It becomes a ScaffoldJunction only when a graph-level classifier assigns
a ScaffoldJunctionKind to an existing ScaffoldNode. ScaffoldJunction is a
classification overlay, not a separate graph node identity. Ordinary
ScaffoldNodes remain unclassified unless a classifier emits a record.

Implemented ScaffoldJunctionKind vocabulary includes:
- SELF_SEAM: two incident final PatchChains share the same ChainId and same
  PatchId, representing the supported SEAM_SELF case.
- CROSS_PATCH: an existing ScaffoldNode's incident final ScaffoldEdges
  reference more than one distinct PatchId.

Future ScaffoldJunctionKind vocabulary beyond SELF_SEAM/CROSS_PATCH includes:
- BRANCH;
- TERMINUS or BORDER_TERMINUS;
- AMBIGUOUS or DEGRADED when describing evidence quality.

## DD-36 — LocalFaceFan is geometry evidence, not graph topology

LocalFaceFanGeometryFacts provides local normals for endpoint evidence.

It is not a ScaffoldNode and not a graph entity.

## DD-37 — Seam cuts may materialize duplicate topology Vertex occurrences

A seam cut may materialize multiple topology Vertex occurrences for one source
vertex.

One source vertex can appear on different sides of a materialized BoundaryLoop
or seam cut. These occurrences may receive distinct topology VertexIds while
retaining provenance to the same source vertex.

Reason:
Materialized UV-cut topology needs separate loop-side occurrences for the same
source vertex. This is required for correct BoundaryLoop traversal, PatchChain
construction, LoopCorner construction and ScaffoldNode grouping.

Implications:
- VertexId equality is topology-occurrence equality, not source-vertex equality.
- SourceVertexId equality is provenance equality.
- Public queries that need source-space grouping must explicitly group by
  SourceVertexId or structural provenance.
- ScaffoldNode construction may aggregate multiple materialized Vertex
  occurrences into one graph node.

## DD-38 — ScaffoldNode v0 is graph-level evidence, not Layer 1 identity

ScaffoldNode v0 is a Layer 3 derived relation record assembled from LoopCorner,
PatchChainEndpointSample and PatchChainEndpointRelation evidence.

Grouping policy v0:
- group materialized topology Vertex occurrences by SourceVertexId when provenance exists;
- fall back to topology VertexId grouping when no SourceVertexId provenance exists;
- retain evidence ids, incident PatchChain ids, Patch ids, confidence and provenance.

ScaffoldNode does not mutate, merge, split or replace Layer 1 Vertex, Chain,
PatchChain or BoundaryLoop identity. It does not classify ScaffoldJunctions.
ScaffoldEdge and ScaffoldGraph consume ScaffoldNode evidence in the implemented
G3c8 builder; ScaffoldTrace, ScaffoldCircuit and ScaffoldRail remain deferred.
ScaffoldJunction classification must not change ScaffoldNode grouping, change
PatchChain identity, walk traces, detect circuits, select rails, choose
continuations or introduce UV, runtime or feature semantics.

## DD-39 - ScaffoldNodeIncidentEdgeRelation v1 is all-pairs evidence

Implemented ScaffoldNodeIncidentEdgeRelation v1 is a complete unordered all-pairs
Layer 3 relation over incident ScaffoldEdge endpoint occurrences at one
existing ScaffoldNode. For n incident edge-end occurrences at one ScaffoldNode,
v1 emits C(n,2) relations.

Emission is graph-structural. Missing PatchChainEndpointSample or
PatchChainEndpointRelation evidence must not cause an edge-end pair to
disappear. When endpoint evidence is missing, the pair remains present and is
classified with missing or degraded evidence quality.

Classification is evidence-backed. It may use tangent direction evidence,
owner normal evidence, direction_dot, normal_dot, endpoint sample ids,
PatchChainEndpointRelation id when available, confidence and evidence quality.
It is evidence only. It must not select trace paths, circuits, rails,
continuations, UV behavior or runtime behavior.

Implemented v1 relation kinds:
- STRAIGHT_CONTINUATION_CANDIDATE: opposite tangent/chord evidence;
  compatible owner-normal proof may be absent or weak.
- SURFACE_CONTINUATION_CANDIDATE: continuation candidate with compatible owner
  normals for opposite-tangent or straight-ish surface continuation.
- CROSS_SURFACE_CONNECTOR: tangent may align or connect, but owner normals
  diverge strongly.
- ORTHOGONAL_CORNER: tangent evidence is orthogonal.
- OBLIQUE_CONNECTOR: tangent evidence is neither collinear nor orthogonal.
- SAME_RAY_AMBIGUOUS: endpoint tangents point in the same ray direction away
  from the node.
- MISSING_ENDPOINT_EVIDENCE: the edge-end pair exists but endpoint
  sample/relation evidence is absent.
- DEGRADED: tangent, normal, confidence or evidence is zero, unknown or
  collapsed.

- SURFACE_SLIDING_CONTINUATION_CANDIDATE: node-local relation between two
  existing ScaffoldEdge endpoint occurrences whose local tangent/chord
  classification may otherwise look orthogonal or same-ray, but explicit
  same-side-surface evidence plus compatible local owner normals support
  continuation along the same curved or side surface. It is not a trace path
  choice, not a selected next edge, not a rail/circuit decision and not a UV
  direction.

SURFACE_SLIDING_CONTINUATION_CANDIDATE requires local owner-normal evidence,
compatible local owner normals and explicit same-side-surface evidence. Missing
or degraded evidence must not produce this kind. SharedChainPatchChainRelation
alone must not produce this kind. Cross-patch cap, corner and shared-boundary
cases must remain non-propagating unless same-side-surface evidence is explicit
and safe.

ScaffoldNodeIncidentEdgeRelation v1 must not change ScaffoldNode grouping,
ScaffoldEdge identity, PatchChain identity, Chain identity, Vertex identity or
BoundaryLoop identity. It must not use H/V, U/V, WORLD_UP, WorldOrientation,
Feature, API, UI, runtime solve or UV transfer.

Examples:
- Tube without caps split by multiple seam chains: top border PatchChains may
  become SURFACE_SLIDING_CONTINUATION_CANDIDATE through seam nodes when
  explicit same-side-surface evidence and compatible local owner normals prove
  curved side-surface continuation. The expected continuity result is two side
  families rather than four singleton side boundary edges.
- Tube with cap patch: side-to-cap PatchChains may be shared/cross-patch
  neighbors, but they are not side-surface continuation when owner normals
  diverge.
- Folded 90 seam, cube-like corner and cap-cross-surface cases remain
  non-propagating unless explicit same-side-surface evidence is safe.
- Local D:\cylinder.blend is an exploratory smoke fixture, not the canonical
  synthetic fixture for this contract.

## DD-40 - ScaffoldContinuityComponent v0 is continuity-family evidence

Implemented ScaffoldContinuityComponent v0 is a Layer 3 derived evidence view over
existing ScaffoldEdges and existing ScaffoldNodeIncidentEdgeRelation records. It
groups ScaffoldEdges into continuity families using continuation-compatible
incident relations.

It is not a trace, path choice, rail, circuit, UV direction, runtime behavior
or replacement for ScaffoldEdge or PatchChain identity. It must not change
ScaffoldNode, ScaffoldEdge, ScaffoldGraph, ScaffoldJunction, PatchChain, Chain
or Vertex identity semantics. It must not introduce H/V, U/V, WORLD_UP,
WorldOrientation, Feature, API, UI, runtime solve or UV transfer.

Default propagation policy:
- SURFACE_CONTINUATION_CANDIDATE propagates continuity.
- SURFACE_SLIDING_CONTINUATION_CANDIDATE propagates continuity by default.
- STRAIGHT_CONTINUATION_CANDIDATE is weak evidence and does not propagate by
  default in v0.
- ORTHOGONAL_CORNER, OBLIQUE_CONNECTOR, CROSS_SURFACE_CONNECTOR,
  SAME_RAY_AMBIGUOUS, MISSING_ENDPOINT_EVIDENCE and DEGRADED do not propagate.
- SAME_RAY_AMBIGUOUS must mark ambiguity.

Every ScaffoldEdge belongs to exactly one continuity component, including
singleton components. If multiple continuation-compatible candidates meet at
the same ScaffoldNode, the component may be marked ambiguous; v0 must preserve
that ambiguity and must not choose one continuation target.

Debug coloring must represent continuity_component_id, not relation kind.
Relation kind remains a separate visual channel such as marker, glyph, label,
dash or warning outline. Component colors must be deterministic pseudo-random
and stable by component id, never true random.

## PatchChain directional evidence

Final PatchChain remains the public source of truth.

Layer 3 may derive directional evidence from final PatchChains to support
alignment, endpoint samples and ScaffoldGraph construction.

Concepts:

```text
ChainDirectionalRun:
  Direction-ready measured run derived from Chain / PatchChain geometry.

PatchChainDirectionalEvidence:
  Patch-local directional evidence derived from final PatchChain.
  It may include source edges, segment indices, direction, length, confidence
  and provenance.
```

These are evidence/views over final PatchChain. They are not competing
PatchChain identities. ScaffoldEdges consume these facts only as evidence and
must not replace final PatchChains as graph source of truth.

---

# 24. Public Consumer APIs

G0 does not define exact signatures, but requires conceptual query groups:

- topology queries;
- geometry queries;
- relation queries;
- feature queries;
- runtime queries;
- world-semantic queries.

Detail/decal/wear systems consume Scaffold APIs but are not part of Scaffold Core.

---

# 25. Roadmap after G0

## G1 — Topology Snapshot Prototype

Scope:

- Layers 0–1 only;
- Shell/Patch/Loop/PatchChain/Chain/Vertex;
- topology invariants;
- SEAM_SELF;
- non-manifold representation;
- diagnostic severity.

## G2 — Geometry Facts

Scope:

- PatchGeometryFacts;
- ChainGeometryFacts;
- VertexGeometryFacts;
- sawtooth as geometry classifier;
- no runtime role promotion.

## G3 — Derived Relations

Implemented:
- G3a - PatchAdjacency / DihedralKind
- G3b - conservative ChainContinuationRelation
- G3c0 - ChainDirectionalRun
- G3c1 - PatchChainDirectionalEvidence
- G3c2 - AlignmentClass v0
- G3c3 - PatchAxes v0
- G3c4 - PatchChainEndpointSample
- G3c5 - PatchChainEndpointRelation
- G3c6 - LoopCorner
- G3c7 - ScaffoldNode v0
- G3c8 - ScaffoldEdge v0 / ScaffoldGraph v0
- G3c9 - ScaffoldJunction v0 SELF_SEAM/CROSS_PATCH
- G3c10 - ScaffoldNodeIncidentEdgeRelation v1 all-pairs edge-end occurrence matrix
- G3c11 - ScaffoldContinuityComponent v0
- G3c12 - SURFACE_SLIDING_CONTINUATION_CANDIDATE conservative classifier

Deferred:
- ScaffoldJunction kinds beyond SELF_SEAM/CROSS_PATCH
- ScaffoldTrace / ScaffoldCircuit / ScaffoldRail
- WorldOrientation
- Layer 4 Feature Grammar
- Layer 5 Runtime / Solve

## G4 — Feature Grammar v0

Scope:

- FeatureCandidate / FeatureInstance lifecycle;
- RuleCandidateStatus vs ResolverDecision;
- FeatureConstraint;
- resolver;
- suppressed candidates;
- BAND_MINIMAL;
- PANEL_SIMPLE.

## G5 — Runtime Solve Bridge

Scope:

- skeleton solve as Layer 5 consumer;
- optional FeatureConstraints;
- two-pass solve;
- compatibility adapter;
- debug/reporting.

## G6 — Feature Grammar Expansion

Scope:

- PANEL_WITH_OPENINGS;
- SIBLING_GROUP;
- BAND_FULL;
- CYLINDER_LIKE;
- CABLE;
- each as separate implementation plan.

---

# 26. Open Questions

## OQ-01 — Patch segmentation policy

Which BMesh marks define Patch boundaries?

Options:

- seams only;
- seams + sharps;
- material boundaries;
- normal angle threshold;
- user marks.

Must be resolved before G1.

## OQ-02 — Shell detection

How are shells identified?

Options:

- connected component over all mesh edges;
- connected component over non-seam edges;
- selection-scoped connected components;
- manifold-only components.

Must be resolved before G1.

## OQ-03 — Alignment coordinate hint derivation

How are U-like/V-like hints selected?

Options:

- first principal direction = U;
- vertical-ish = V for wall-like geometry;
- WORLD_UP vector bias only;
- user-configurable project convention.

Must be resolved before G3.

## OQ-04 — Override persistence tolerance

How tolerant is structural fingerprint reassociation?

## OQ-05 — Non-manifold support scope

Which non-manifold cases are supported, degraded or blocking?

## OQ-06 — Feature rule priority calibration

How are rule priorities calibrated?

## OQ-07 — Performance budgets

What pass timings trigger partial rebuild work?

## OQ-08 — Entity id strategy

Snapshot-local ids only? UUID for override targets? Structural fingerprints only?

## OQ-09 — Patch fit kind detection

How is `PLANAR / CURVED / UNKNOWN` determined?

## OQ-10 — WorldSemanticRule implementation

Distinct class or FeatureRule variant?

## OQ-11 — Geometry-based Chain / PatchChain refinement policy

Status: partially resolved.

Resolved:
- Final PatchChain is the public source of truth.
- Raw boundary elements are builder internals.
- Layer 3 may derive directional evidence from final PatchChains.
- Polygonal straight/turning Chains can be described by ChainDirectionalRun /
  PatchChain directional evidence.
- Directional evidence must not become a competing PatchChain identity.
- ScaffoldNode v0 may group materialized Vertex occurrences as graph-level evidence,
  but not as Layer 1 identity.
- ScaffoldNodeIncidentEdgeRelation v1 is implemented as all-pairs graph evidence
  over existing ScaffoldNode incident edge-end occurrences and must not choose
  traces, circuits, rails or continuations.
- ScaffoldContinuityComponent v0 is implemented as a continuity-family evidence
  view over existing ScaffoldEdges and incident-edge relations. It may group
  edges but must not choose traces, circuits, rails or continuation targets.
- SURFACE_SLIDING_CONTINUATION_CANDIDATE is implemented as conservative
  ScaffoldNodeIncidentEdgeRelationKind evidence for curved/side-surface
  continuation.

Still unresolved:

- curved-chain policy;
- sawtooth tuning;
- user split marks;
- closed-loop wrap merge policy;
- advanced corner detection;
- local face-fan refinement policy;
- trace/circuit/rail construction over ScaffoldGraph.

---

# 27. Document Completion Criteria

Historical G1 kickoff criteria were satisfied during G1.

For the current G3 documentation state, the active contract is complete when:

- G0.md and G0_full.md are v1.2.
- DD-29 includes border-coalescing rationale.
- DD-37 documents seam-cut duplicate topology Vertex occurrences.
- OQ-11 is marked partially resolved.
- PatchChain / LocalFaceFan / EndpointSample / EndpointRelation terminology is consistent.
- docs/phases/G3_derived_relations.md reflects current G3 subphases.
- agent_handoff.md reflects current implementation status and next task.
- AGENTS.md reflects current G3 status.

---

# 28. Canonical Mission Statement

Scaffold Core is an immutable B-rep-inspired interpretation pipeline for topology-aware structural UV alignment.

It builds a topology snapshot from source mesh data, attaches geometry facts, derives relation graphs with provenance, recognizes feature candidates through graph-pattern rules, resolves accepted feature instances, and runs runtime solve / UV transfer without mutating the topology snapshot.

It replaces primary H/V and WALL/FLOOR/SLOPE classifications with derived AlignmentClass and WorldOrientation layers, keeping those concepts available as runtime, debug and downstream semantics without letting them pollute the core topology model.

Feature recognition communicates with solve only through explicit FeatureConstraints.

Layer 3 is frozen after Pass 1.

Scaffold owns interpretation.  
Blender owns mesh editing.
