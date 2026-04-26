# Scaffold Core — G0 v1.1

> **Immutable B-rep-inspired Interpretation Pipeline**

**Status:** architectural contract v1.1  
**Scope:** design before implementation  
**Purpose:** stable conceptual and structural model for Scaffold Core before any code is written.

This document is the canonical reference for subsequent implementation plans: G1, G2, G3, etc. Phase plans cite G0 sections as their contract; they may not override G0 design decisions without an explicit G0 amendment.

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
  AlignmentClass derives axis-like structure
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
WorldOrientation is derived from topology + geometry + adjacency + WORLD_UP + overrides.
WorldOrientation does not depend on skeleton solve.
Alignment may use WORLD_UP vector as soft geometric bias.
Alignment must not use SurfaceRole / WorldOrientation semantic labels.
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

## 3.7 Terminology

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
| Vertex | `Vertex` | Topological point; graph-level ScaffoldJunction is derived later. |
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


`Vertex` is a topological endpoint. `ScaffoldJunction` is a future graph-level
classification, not every topology Vertex.

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
- Layer 0 overrides, where applicable;
- WORLD_UP vector as raw geometric input where explicitly allowed.

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
PatchAxes choose U/V-like axes from AlignmentClasses
Runtime may expose H-like/V-like labels for debug
```

Alignment membership is per `PatchChain`, not per `Chain`.

A single Chain may have multiple PatchChains that belong to different AlignmentClasses.

v1 direction clustering is conservative:

- straight-like PatchChains only;
- chord direction only;
- fixed tolerance;
- no adaptive widening;
- WORLD_UP vector may be used as soft geometric bias;
- WorldOrientation labels must not be used for alignment ranking.

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

Future ScaffoldGraph / ScaffoldTrace may be derived from these endpoint
relations.

`PatchChainEndpointSample` is not a ScaffoldJunction.
`PatchChainEndpointRelation` is not a ScaffoldJunction.
`LocalFaceFanGeometryFacts` is not a ScaffoldJunction.

`LoopCorner` is the patch-local transition between adjacent PatchChains inside
one BoundaryLoop. It may later feed ScaffoldNode assembly.

`ScaffoldJunction` is graph-level: a ScaffoldNode classified as branch-like,
not every PatchChain endpoint sample or LoopCorner.

---

# 13. WorldOrientation

WorldOrientation restores practical wall/floor/up/down semantics without polluting topology or solve.

There are two different uses of WORLD_UP:

```text
WORLD_UP vector:
  raw geometric input
  allowed as soft bias in alignment

WorldOrientation labels:
  derived semantics
  not allowed as base alignment input
```

Therefore:

```text
Alignment may use WORLD_UP vector.
Alignment must not use SurfaceRole / WorldOrientation labels.
```

Base WorldOrientation does not depend on skeleton solve, runtime UV, feature recognition or accepted FeatureInstances.

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
Pass 0.5  Basic world orientation
Pass 1    Relations + alignment + base solve
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

# 19. Pass 0.5 — Basic WorldOrientation

Inputs:

- Layer 2 patch normals;
- Layer 2 chain directions;
- WORLD_UP vector;
- user world-orientation overrides.

Outputs:

- `PatchWorldOrientation`
- `ChainWorldOrientation`

Pass 0.5 does not feed SurfaceRole labels into alignment.

Alignment may independently use WORLD_UP vector as geometric bias.

---

# 20. Pass 1 — Relations, Alignment, Base Solve

Inputs:

- Layer 1 topology;
- Layer 2 geometry;
- WORLD_UP vector;
- user relation/alignment overrides.

Outputs:

- Layer 3 complete base relations;
- Layer 5 skeleton solve pass 1.

Steps:

1. Build PatchAdjacency.
2. Compute DihedralKind using PatchAdjacency and both PatchChain orientations.
3. Build PatchChain endpoint relations.
4. Build Continuation relations.
5. Build AlignmentClasses.
6. Build PatchAxes.
7. Freeze Layer 3.
8. Run skeleton solve pass 1.

Layer 3 is frozen after Pass 1.

Pass 2 must not add or rewrite Layer 3 records.

---

# 21. Pass 2 — Feature Recognition and Optional Second Solve

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

# 22. User Overrides

User overrides are inputs, not mutations.

They influence pipeline rebuilds but do not directly patch Layer 1 topology objects.

Override categories:

- source-level overrides;
- classifier-level overrides;
- feature-level overrides;
- runtime-level overrides.

Overrides store structural fingerprint of the target entity.

---

# 23. Rebuild Policy

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

# 24. Design Decisions Register

The authoritative compact DD register is also mirrored in `docs/architecture/design_decisions.md`.

## DD-29 — Chain coalescing is staged

G1 / G3a:
- Boundary coalescing uses topology/materialization context only.
- Consecutive boundary sides with the same boundary run kind and Patch context
  may coalesce into logical Chains.
- Border runs may coalesce into ordered Chains.
- Seam cuts may materialize duplicate topology Vertex occurrences so one
  source vertex can appear on both sides of a Patch loop.

Before Alignment / PatchAxes:
- Chains that are closed, turning, or direction-ambiguous must be refined
  using Layer 2 geometry facts.

Scope:
- Coalescing/refinement is constrained to one ordered atomic boundary cycle
  that materializes as one final BoundaryLoop.
- Coalescing/refinement must not cross OUTER/INNER loop boundaries.

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

## DD-33 — ScaffoldGraph is derived from endpoint relations

ScaffoldGraph / ScaffoldTrace are future Layer 3 derived structures built from
`PatchChainEndpointRelation`, not from raw Chain or world axes.

They must not be introduced before pairwise endpoint relations exist.

## DD-34 — Final PatchChain is the single source of truth

BoundaryLoop contains final PatchChains. Raw boundary sides, atomic source
edges and draft runs are builder internals.

ScaffoldGraph must use final PatchChains as graph edges, not a parallel
effective PatchChain layer.

## DD-35 — LoopCorner is patch-local; ScaffoldJunction is graph-level

LoopCorner is the local transition between adjacent PatchChains inside one
BoundaryLoop. A LoopCorner may become a ScaffoldNode.

It becomes a ScaffoldJunction only when graph-level classification says it is
branch-like: 3+ incident PatchChains, seam pair, cross-patch connection,
branch, or other structural ScaffoldJunction.

## DD-36 — LocalFaceFan is geometry evidence, not graph topology

LocalFaceFanGeometryFacts provides local normals for endpoint evidence.

It is not a ScaffoldNode and not a graph entity.

---

# 25. Public Consumer APIs

G0 does not define exact signatures, but requires conceptual query groups:

- topology queries;
- geometry queries;
- relation queries;
- feature queries;
- runtime queries;
- world-semantic queries.

Detail/decal/wear systems consume Scaffold APIs but are not part of Scaffold Core.

---

# 26. Roadmap after G0

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

Scope:

- PatchAdjacency;
- DihedralKind;
- ChainContinuationRelation;
- PatchChain endpoint relations;
- AlignmentClass;
- PatchAxes;
- WorldOrientation;
- Layer 3 freeze after Pass 1.

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

# 27. Open Questions

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

## OQ-11 — Geometry-based Chain refinement policy

How do Layer 2 geometry facts split or merge topology Chains before
Alignment?

OQ-11 is partially resolved for straight/turning polygonal Chains through
Layer 3 `ChainDirectionalRun` and `PatchChainDirectionalEvidence`.

Still unresolved:

- curved-chain handling;
- sawtooth tuning;
- user split marks;
- closed-loop wrap merge;
- advanced corner detection;
- relation to PatchChainEndpointRelation / ScaffoldGraph.

---

# 28. Document Completion Criteria

G0 v1.1 is complete for G1 kickoff when:

1. OQ-01 and OQ-02 are resolved.
2. OQ-03 is at least directionally agreed before G3.
3. Layer 1 invariants are implementation-ready.
4. One independent review confirms no unresolved architectural contradictions.
5. All Design Decisions are reflected in pipeline pass rules.

---

# 29. Canonical Mission Statement

Scaffold Core is an immutable B-rep-inspired interpretation pipeline for topology-aware structural UV alignment.

It builds a topology snapshot from source mesh data, attaches geometry facts, derives relation graphs with provenance, recognizes feature candidates through graph-pattern rules, resolves accepted feature instances, and runs runtime solve / UV transfer without mutating the topology snapshot.

It replaces primary H/V and WALL/FLOOR/SLOPE classifications with derived AlignmentClass and WorldOrientation layers, keeping those concepts available as runtime, debug and downstream semantics without letting them pollute the core topology model.

Feature recognition communicates with solve only through explicit FeatureConstraints.

Layer 3 is frozen after Pass 1.

Scaffold owns interpretation.  
Blender owns mesh editing.
