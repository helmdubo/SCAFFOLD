# Agent Handoff — Scaffold Core

This file is the continuity document for independent AI agents.

Read this after `AGENTS.md` and before changing code.

---

## Current state

```text
Project: Scaffold
Core package: scaffold_core/
Current phase: G2 — Geometry Facts
Architecture: immutable B-rep-inspired interpretation pipeline
```

Scaffold Core currently focuses on the G2 foundation:

```text
Layer 0 — Source Mesh Snapshot
Layer 1 — Immutable Topology Snapshot
Layer 2 — Geometry Facts
Pipeline Pass 0
Diagnostics
```

Future layers are intentionally not created yet:

```text
layer_3_relations/
layer_4_features/
layer_5_runtime/
api/
ui/
```

Do not create them during G2.

The Blender add-on wrapper package `scaffold/` is also intentionally deferred during G2. Do not create it until an explicit UI/add-on phase begins, likely no earlier than G5 / UV transfer / UI integration work.

---

## Essential reading order for a new agent

1. `AGENTS.md`
2. `docs/context_map.yaml`
3. `docs/phases/G2_geometry_facts.md`
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

Implemented test fixtures:

```text
single_patch.py
l_shape.py
seam_self.py
non_manifold.py
corner_touch.py
degenerate_geometry.py
chain_shape_geometry.py
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
Full local verification at the time of handoff: python -m pytest scaffold_core/tests -q
Result: 34 passed.
Blender smoke test: cube with all faces selected and seam loop around one face produced
1 Shell, 2 Patches, 4 Chains and 8 ChainUses.
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

### Must do next

- Review whether G2 is sufficient for G3 relation work.
- If yes, transition to G3 before creating `layer_3_relations/`.
- If more G2 work is needed, keep it limited to raw measured geometry facts.

### Explicitly not part of G2a

- Layer 3 Relations.
- AlignmentClass.
- PatchAxes.
- WorldOrientation.
- DihedralKind.
- Feature Grammar.
- Skeleton solve.
- UV transfer.
- Blender UI.

---

## Recommended next task

Review G2a, then choose the next slice:

1. G3 phase transition for derived relations.
2. Additional raw geometry measurements, if needed.
3. Defer Blender UI, runtime solve and transfer work until their phases.

---

## Agent safety rules

- Do not create future phase directories.
- Do not create the deferred `scaffold/` add-on wrapper during G2.
- Do not add `utils.py`, `helpers.py`, `manager.py`, `service.py`, `factory.py`, `registry.py`.
- Do not put H/V, WALL/FLOOR/SLOPE, alignment, world-orientation, feature,
  pin or UV facts in Layer 2.
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
