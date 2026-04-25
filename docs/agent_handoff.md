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
ChainUse
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
- BoundaryLoops, Chains and ChainUses are built from real Patch boundary uses.
```

Layer 1 Chain coalescing is implemented for shared boundary runs:

```text
- Chain is no longer always one source edge.
- Atomic boundary sides are ordered into BoundaryLoops.
- Consecutive shared boundary sides with the same Patch adjacency context are
  coalesced into one Chain.
- Chain.source_edge_ids stores source edges in run order.
- ChainId is built from source_edge_ids in run order.
- Lookup remains orientation-independent so opposite ChainUses resolve to the
  same Chain.
```

Current Chain coalescing limitations:

- Coalescing is topology/context-based only.
- Border chains are not guaranteed to coalesce yet.
- Geometry-based split/refinement by tangent, angle, normal or user split
  future work.

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
    2 ChainUses, one per Patch loop
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
ChainUse orientations, skips border / SEAM_SELF / non-manifold Chains for
normal adjacency, and exposes `run_pass_1_relations()` in the pipeline.

G3b1 implements Junction incidence queries as derived views over Vertex.
It does not introduce a Junction entity.
It does not implement disk-cycle ordering.
It does not implement ChainContinuationRelation.

G3b2 implements conservative ChainContinuationRelation records.
Current policy is intentionally narrow:

```text
0 candidates -> TERMINUS
1 candidate  -> TERMINUS
2+ candidates -> SPLIT to each candidate
```

Current caution:
  Continuation must not assume Chains are direction-stable.
  Full geometric continuation policy is deferred.
  OQ-11 remains unresolved and blocks AlignmentClass, not conservative continuation.

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
test_chainuse_orientation.py
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
1 Shell, 2 Patches, 1 Chain and 2 ChainUses.
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

- Decide whether border boundary runs should coalesce into Chains.
- Add geometry-based Chain split/refinement before AlignmentClass,
  ChainContinuationRelation or continuation-heavy work.
- Consider `ChainUse` -> `PatchChain` naming separately, if desired.

### G3 relation work still open

- Add relation queries when consumers appear, e.g. `adjacencies_for_chain()` or
  `adjacency_between_patches()`.
- Implement G3b2 Conservative ChainContinuationRelation using TERMINUS / SPLIT
  as the safe baseline.
- Add diagnostics for skipped Chains in `build_relation_snapshot()` only after
  there is a clear reporting requirement.
- Continue with G3b only after Chain coalescing/refinement assumptions are
  stable enough for continuation and junction relations.

### Explicitly not part of G3a

- AlignmentClass.
- PatchAxes.
- WorldOrientation.
- ChainContinuationRelation.
- Junction relations.
- Feature Grammar.
- Skeleton solve.
- UV transfer.
- Blender UI.

---

## Recommended next task

G3b2 Conservative ChainContinuationRelation.

```text
Use G3b1 deterministic incidence.
Prefer TERMINUS / SPLIT over false SMOOTH / TURN.
Do not solve OQ-11.
Do not start AlignmentClass.
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
