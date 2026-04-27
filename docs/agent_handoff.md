# Agent Handoff — Scaffold Core

This file is the continuity document for independent AI agents.

Read this after `AGENTS.md` and before changing code.

---

## Current state

```text
Project: Scaffold
Core package: scaffold_core/
Current phase: G3 - Derived Relations
Architecture: immutable B-rep-inspired interpretation pipeline
```

Scaffold Core currently focuses on the G3 foundation:

```text
Layer 0 — Source Mesh Snapshot
Layer 1 — Immutable Topology Snapshot
Layer 2 — Geometry Facts
Layer 3 - Derived Relations
Pipeline Pass 0
Diagnostics
```

Future layers are intentionally not created yet:

```text
layer_4_features/
layer_5_runtime/
api/
ui/
```

Do not create them during G3.

The Blender add-on wrapper package `scaffold/` is also intentionally deferred during G3. Do not create it until an explicit UI/add-on phase begins, likely no earlier than G5 / UV transfer / UI integration work.

Root `scaffold_blender_inspection.json` is a user-only debug artifact and may be stale. Do not use it as an architecture reference; use code, docs and tests instead.

---

## Essential reading order for a new agent

1. `AGENTS.md`
2. `docs/context_map.yaml`
3. `docs/phases/G3_derived_relations.md`
4. `docs/architecture/G0_full.md`
5. `docs/agent_rules/import_boundaries.md`
6. `docs/agent_rules/anti_overengineering.md`
7. `docs/agent_rules/testing_rules.md`
8. `docs/agent_rules/minimal_patch_protocol.md` if fixing existing code

Read `G0.md` only when the task touches architecture or phase boundaries.

---

## Versioning note

Scaffold uses three separate numbering systems:

```text
G0 vX.Y:
  architecture contract version

G1 / G2 / G3 / ...:
  implementation phase names

bl_info.version:
  Blender add-on semantic version
```

Example: `G0 v1.1`, `G1`, and `bl_info.version = (0, 1, 0)` can all be true at the same time.

---

## What is already done

### Documentation

- Compact `AGENTS.md` router exists.
- Canonical compact `G0.md` exists.
- Full reference `docs/architecture/G0_full.md` exists.
- `Scaffold_G0.md` is now only a pointer.
- `docs/context_map.yaml` exists and defines current phase, allowed/forbidden dirs and routing.
- G1 segmentation/shell policy is resolved in `docs/architecture/segmentation_shell_policy.md`.
- Agent rule docs exist for imports, testing, Blender boundaries, anti-overengineering and minimal patch protocol.

### Code skeleton

Implemented packages:

```text
scaffold_core/core/
scaffold_core/layer_0_source/
scaffold_core/layer_1_topology/
scaffold_core/layer_2_geometry/
scaffold_core/layer_3_relations/
scaffold_core/pipeline/
scaffold_core/tests/
```

Implemented core data structures:

```text
SourceMeshSnapshot
MeshVertexRef
MeshEdgeRef
MeshFaceRef
SourceMark
UserOverride
SurfaceModel
Shell
Patch
BoundaryLoop
Chain
PatchChain
Vertex
GeometryFactSnapshot
PatchGeometryFacts
ChainGeometryFacts
VertexGeometryFacts
PipelineContext
Diagnostic
DiagnosticReport
Evidence
```

Current terminology:

```text
PatchChain:
  final patch-local oriented occurrence of a Chain in a BoundaryLoop.

PatchChainDirectionalEvidence:
  derived directional measurement for a PatchChain.

PatchChainEndpointSample:
  endpoint ray/evidence sample for a PatchChain directional measurement.

PatchChainEndpointRelation:
  pairwise local relation between endpoint samples at one Vertex.

LocalFaceFanGeometryFacts:
  local owner-normal geometry evidence.

LoopCorner:
  patch-local transition between adjacent PatchChains in one BoundaryLoop.

ScaffoldJunction:
  future graph-level ScaffoldNode classification for branch/seam/cross-patch structures.
```

Endpoint samples, endpoint relations and LocalFaceFanGeometryFacts are evidence
or measurements; they are not graph nodes.

Implemented baseline functions:

```text
build_topology_snapshot()
validate_topology()
validate_loop_closure()
validate_chain_cardinality()
validate_patch_outer_loops()
build_geometry_facts()
run_pass_0()
assert_no_blocking_diagnostics()
```

`build_topology_snapshot()` now implements the G1 topology policy instead of
the old fixture baseline:

```text
- selected-face edge adjacency;
- Shell detection as edge-connected selected-face components;
- Patch flood fill blocked by mesh/selection border, selected non-manifold edge,
  explicit Scaffold boundary mark and Blender UV Seam;
- Blender Sharp is read as a source mark but ignored by default Patch segmentation;
- BoundaryLoops, Chains and PatchChains are built from real Patch boundary uses.
```

Layer 1 Chain coalescing is implemented for materialized boundary runs:

```text
- Chain is no longer always one source edge.
- Atomic boundary sides are ordered into BoundaryLoops.
- Consecutive boundary sides with the same boundary run kind and Patch context
  are coalesced into one Chain.
- Chain.source_edge_ids stores source edges in run order.
- ChainId is built from source_edge_ids in run order.
- Lookup remains orientation-independent so opposite PatchChains resolve to the
  same Chain.
```

Layer 1 boundary run kinds:

```text
BORDER_RUN
PATCH_ADJACENCY_RUN
SEAM_SELF_RUN
NON_MANIFOLD_RUN
```

SEAM_SELF loops may materialize duplicate topology Vertex occurrences so one
source vertex can appear on both sides of a seam cut. `PatchChain` may carry
materialized start/end vertices for the patch-local occurrence. These are
topology/provenance only; normals are not stored on Layer 1 PatchChain.

Current Chain coalescing limitation:

- Geometry-based split/refinement by tangent, angle, normal or user split is
  future Layer 3 work.

Chain refinement is staged (DD-29):

- G3a Chain identity is topological.
- Closed, turning, or direction-ambiguous Chains are accepted at this stage.
- They must be refined using Layer 2 geometry before AlignmentClass.
- Refinement must not change Layer 1 Chain identity (DD-30).

Future agents:

- Do not build AlignmentClass on the assumption that every Chain is
  straight or direction-stable.
- Resolve OQ-11 before starting G3c AlignmentClass work.
- See `scaffold_core/tests/test_chain_refinement_pending.py` for an
  executable reminder.

Example:

```text
Closed seam loop of 4 source edges between two Patches:
  expected:
    1 Chain
    Chain.source_edge_ids = (e10, e9, e6, e7)
    2 PatchChains, one per Patch loop
```

Example:

```text
Cylinder tube without caps and one seam cut:
  expected:
    1 Patch
    1 materialized BoundaryLoop
    3 Chains
    4 PatchChains

  Chains:
    top border run
    bottom border run
    seam Chain with two uses in the same Patch
```

`validate_chain_cardinality()` classifies all G1 Chain cardinality cases:

```text
- TOPOLOGY_CHAIN_BORDER
- TOPOLOGY_CHAIN_SHARED
- TOPOLOGY_CHAIN_SEAM_SELF
- TOPOLOGY_CHAIN_NON_MANIFOLD
```

Blender source mesh inspection is available without an add-on UI through:

```text
scaffold_core/layer_0_source/blender_io.py
scaffold_core/pipeline/inspection.py
```

Structured inspection exists in `scaffold_core/pipeline/inspection.py`.
It provides JSON-serializable read-only snapshots for topology, geometry,
relations and diagnostics. It is debug/reporting only and must not contain
topology or relation logic.

Layer 2 geometry facts are now available through:

```text
scaffold_core/layer_2_geometry/facts.py
scaffold_core/layer_2_geometry/measures.py
scaffold_core/layer_2_geometry/build.py
```

G2a includes raw patch area/normal/centroid, chain length/chord direction,
vertex position and degraded diagnostics for degenerate patch/chain geometry.
G2b adds chain chord length, straightness, detour ratio and raw shape hints
including `SAWTOOTH_STRAIGHT`.
G2.1 now exposes per-source-edge Chain segment geometry facts. This is raw
geometry only. It does not refine Chain identity. It is intended as input for
future Layer 3 OQ-11 chain refinement.

G3 phase transition is active. Initial G3a work should stay limited to:

```text
PatchAdjacency
DihedralKind
RelationSnapshot
```

Layer 3 adjacency foundation is implemented through:

```text
scaffold_core/layer_3_relations/model.py
scaffold_core/layer_3_relations/build.py
```

G3a builds `PatchAdjacency` from normal shared two-Patch Chains, stores
`DihedralKind` on the adjacency record, computes signed dihedral using both
PatchChain orientations, skips border / SEAM_SELF / non-manifold Chains for
normal adjacency, and exposes `run_pass_1_relations()` in the pipeline.

G3b1 implements PatchChain incidence queries as derived views over Vertex.
It does not introduce a ScaffoldJunction entity.
It does not implement disk-cycle ordering.
It does not implement ChainContinuationRelation.

G3b2 implements conservative ChainContinuationRelation records.
Current policy is intentionally narrow:

```text
0 candidates -> TERMINUS
1 candidate  -> TERMINUS
2+ candidates -> one SPLIT with candidate_count evidence
```

Current caution:
  Continuation must not assume Chains are direction-stable.
  Full geometric continuation policy is deferred.
  OQ-11 remains unresolved and blocks AlignmentClass, not conservative continuation.

G3c0 chain directional refinement view is implemented:

```text
Layer 3 now exposes ChainDirectionalRun as a derived direction-ready view
from Layer 2 ChainSegmentGeometryFacts.
This does not mutate Layer 1 Chain identity.
AlignmentClass is still not implemented.
```

This is a partial OQ-11 decision for straight/turning polygonal Chains only.
Curved, sawtooth tuning, user split marks, closed-loop wrap merge, advanced
corner detection and relation to disk-cycle ordering remain unresolved.

G3c1 implemented PatchChainDirectionalEvidence:

```text
PatchChainDirectionalEvidence is a patch-local directional occurrence of
ChainDirectionalRun.
This is the bridge between topology-level Chain refinement and future
AlignmentClass.
AlignmentClass is still not implemented.
PatchAxes is still not implemented.
```

G3c2 AlignmentClass v0 is implemented:

```text
AlignmentClass consumes PatchChainDirectionalEvidence, not Chain.
It groups patch-local directional run uses into sign-insensitive direction
families.
PatchAxes remains deferred.
```

G3c3 PatchAxes v0 is implemented:

```text
PatchAxes selects primary/secondary AlignmentClass ids per Patch.
It does not use U/V labels.
WORLD_UP fallback remains deferred.
```

G3c3 PatchAxes candidate evidence is implemented:

```text
PatchAxes evidence exposes candidate_scores for explainable primary/secondary
selection.
The policy still uses geometry-only AlignmentClass length scores.
```

## Next architectural direction

The graph-prep relation work should use PatchChain endpoint relations and
LoopCorners.

Current implemented chain:

```text
Layer 1 Chain / PatchChain
-> Layer 2 ChainSegmentGeometryFacts
-> Layer 3 ChainDirectionalRun
-> Layer 3 PatchChainDirectionalEvidence
-> Layer 3 AlignmentClass
-> Layer 3 PatchAxes
```

Current graph-prep relation layer:

```text
PatchChainEndpointSample
-> PatchChainEndpointRelation
-> LoopCorner
```

Goal: classify local relations at a Vertex:

- continuation candidate;
- corner connector;
- oblique connector;
- ambiguous;
- degenerate.

This is the basis for future ScaffoldGraph / ScaffoldTrace.

Do not implement ScaffoldGraph yet.
Do not use U/V labels, H/V labels, WORLD_UP, WorldOrientation or runtime solve.
Do not store normals on Layer 1 PatchChain.

G3c4 PatchChainEndpointSample is implemented:

```text
Layer 3 now exposes patch_chain_endpoint_samples for START and END endpoints
of each PatchChain directional evidence record.
tangent_away_from_vertex is oriented away from the endpoint Vertex.
owner_normal prefers Layer 2 LocalFaceFanGeometryFacts.normal with
owner_normal_source = LOCAL_FACE_FAN_NORMAL, falling back to PatchGeometryFacts.normal
when a non-zero fan normal is unavailable.
Layer 1 PatchChain still stores topology only.
Endpoint samples do not themselves classify pairwise relations.
ScaffoldGraph is still not implemented.
```

G3c5 PatchChainEndpointRelation v0 is implemented:

```text
Layer 3 now exposes patch_chain_endpoint_relations as unordered pairwise
relations between patch_chain_endpoint_samples at the same topology Vertex.
direction_relation records OPPOSITE_COLLINEAR, SAME_RAY_COLLINEAR,
ORTHOGONAL, OBLIQUE or DEGENERATE.
kind records CONTINUATION_CANDIDATE, CORNER_CONNECTOR, OBLIQUE_CONNECTOR,
AMBIGUOUS or DEGENERATE.
ScaffoldGraph / ScaffoldTrace are still not implemented.
```

G3c6 LoopCorner is the next patch-local bridge:

```text
LoopCorner = transition between previous PatchChain and next PatchChain
inside one BoundaryLoop at one materialized Vertex occurrence.

LoopCorner is patch-local.
ScaffoldNode is graph-level.
ScaffoldJunction is a ScaffoldNode kind, not every corner.
```

Implemented test fixtures:

```text
single_patch.py
l_shape.py
seam_self.py
non_manifold.py
corner_touch.py
degenerate_geometry.py
chain_shape_geometry.py
closed_shared_loop.py
```

Implemented tests:

```text
test_forbidden_imports.py
test_module_docstrings.py
test_patch_chain_orientation.py
test_layer_1_invariants.py
test_seam_self.py
test_pipeline_pass0.py
test_shared_chain.py
test_seam_splits_patch.py
test_seam_does_not_split_shell.py
test_vertex_only_contact_separates_shells.py
test_non_manifold_stays_in_shell.py
test_shared_chain_two_uses.py
test_boundary_mark_splits_patch.py
test_sharp_does_not_split_patch.py
test_multi_face_patch_loop.py
test_blender_io.py
test_pipeline_inspection.py
test_layer_2_geometry_facts.py
test_layer_2_no_semantic_roles.py
test_chain_coalescing.py
test_layer_3_adjacency.py
test_layer_3_no_semantic_roles.py
test_pipeline_pass1.py
```

Recent cleanup:

```text
scaffold_core/layer_0_source/fingerprints.py removed as premature speculative infrastructure.
SourceMeshSnapshot.checksum documented as optional future rebuild provenance.
l_shape.py fixture is now covered by test_shared_chain.py.
README documents versioning and deferred add-on wrapper.
```

Recent implementation:

```text
Commit 26dbd6a implements G1 topology segmentation policy and Blender inspection.
Commit ca7cd72 adds normal shared Chain diagnostics.
Commit 92c188d coalesces shared boundary runs into topology Chains.
Commit c39b789 coalesces closed shared seam loops.
Commit 61b5cd7 builds coalesced Chain ids from source_edge_ids in run order.
Full local verification at the time of handoff: python -m pytest scaffold_core/tests
Result: 46 passed.
Blender smoke test: cube with all faces selected and seam loop around one face produced
1 Shell, 2 Patches, 1 Chain and 2 PatchChains.
```

---

## Resolved architectural decisions relevant to G1

### Patch segmentation

Patch segmentation uses selected-face flood fill.

A source edge blocks Patch flood fill and becomes a Patch boundary if:

```text
- it is a mesh/selection border;
- it is non-manifold in selected scope;
- it has an explicit Scaffold boundary mark;
- it has a Blender UV Seam.
```

Blender Sharp is not a default Patch boundary source in G1.

A future optional command may support `make seams by sharps`, but Sharp must not become a hidden default segmentation source.

### Shell detection

Shell detection uses edge-connected components of selected faces.

Shell connectivity ignores Patch segmentation boundaries.

Vertex-only contact does not connect Shells.

Non-manifold edge connectivity keeps faces in the same Shell candidate, but emits a degraded diagnostic.

---

## What is not done yet

### Layer 1 / Chain refinement still open

- OQ-11 is partially resolved for straight/turning polygonal Chains through
  ChainDirectionalRun and PatchChainDirectionalEvidence.
- Curved-chain handling, sawtooth tuning, user split marks, closed-loop wrap
  merge remain unresolved.

### G3 relation work still open

- Add relation queries when consumers appear, e.g. `adjacencies_for_chain()` or
  `adjacency_between_patches()`.
- Implement future ScaffoldGraph / ScaffoldTrace only after
  PatchChainEndpointRelation and LoopCorner data exist.
- WorldOrientation.
- Add diagnostics for skipped relation inputs only after there is a clear
  reporting requirement.
- Feature Grammar.
- Runtime/Solve.
- UV.
- Blender UI.

---

## Recommended next task

Review full inspection JSON for `patch_chain_endpoint_relations` and
`loop_corners`.

```text
Confirm local relation output on cube/seam and any cylinder-like fixtures
before starting ScaffoldGraph / ScaffoldTrace v0.
```

---

## Agent safety rules

- Do not create future phase directories.
- Do not create the deferred `scaffold/` add-on wrapper during G3.
- Do not add `utils.py`, `helpers.py`, `manager.py`, `service.py`, `factory.py`, `registry.py`.
- Do not put Feature, runtime solve, pin or UV facts in Layer 3.
- Do not feed WorldOrientation labels into base Alignment.
- Do not import higher layers from lower layers.
- Do not import `pipeline.passes` or `pipeline.validator` from layer code.
- Do not touch `G0.md` unless the task is explicitly an architecture amendment.
- For bug fixes, use Minimal Patch Protocol.

---

## How to verify

Run:

```bash
pytest scaffold_core/tests
```

Architectural tests to keep green:

```text
scaffold_core/tests/test_forbidden_imports.py
scaffold_core/tests/test_module_docstrings.py
```

If these fail, fix architecture violations before continuing feature work.
