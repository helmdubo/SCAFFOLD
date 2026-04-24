# Agent Handoff — Scaffold Core

This file is the continuity document for independent AI agents.

Read this after `AGENTS.md` and before changing code.

---

## Current state

```text
Project: Scaffold
Core package: scaffold_core/
Current phase: G1 — Topology Snapshot Prototype
Architecture: immutable B-rep-inspired interpretation pipeline
```

Scaffold Core currently focuses on the G1 foundation:

```text
Layer 0 — Source Mesh Snapshot
Layer 1 — Immutable Topology Snapshot
Pipeline Pass 0
Diagnostics
Synthetic tests
```

Future layers are intentionally not created yet:

```text
layer_2_geometry/
layer_3_relations/
layer_4_features/
layer_5_runtime/
api/
ui/
```

Do not create them during G1.

---

## Essential reading order for a new agent

1. `AGENTS.md`
2. `docs/context_map.yaml`
3. `docs/phases/G1_topology_snapshot.md`
4. `docs/layers/layer_1_topology.md`
5. `docs/architecture/segmentation_shell_policy.md`
6. `docs/agent_rules/import_boundaries.md`
7. `docs/agent_rules/anti_overengineering.md`
8. `docs/agent_rules/minimal_patch_protocol.md` if fixing existing code

Read `G0.md` only when the task touches architecture or phase boundaries.

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
run_pass_0()
assert_no_blocking_diagnostics()
```

Implemented test fixtures:

```text
single_patch.py
l_shape.py
seam_self.py
non_manifold.py
```

Implemented tests:

```text
test_forbidden_imports.py
test_module_docstrings.py
test_chainuse_orientation.py
test_layer_1_invariants.py
test_seam_self.py
test_pipeline_pass0.py
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

### Must do before G1 is complete

- Replace fixture-oriented `build_topology_snapshot()` with real selected-face edge graph construction.
- Implement Shell detection as selected-face edge-connected components.
- Implement Patch segmentation as flood fill blocked by the G1 boundary predicate.
- Build real BoundaryLoops from Patch boundary edges instead of one face = one loop baseline.
- Build Chains / ChainUses from Patch boundary uses after segmentation.
- Add tests for seam-based patch split.
- Add tests that seam splits Patch but not Shell.
- Add tests that vertex-only contact creates separate Shells.
- Add tests that non-manifold edge remains in Shell candidate and emits DEGRADED diagnostic.
- Run the full test suite locally.

### Explicitly not part of G1

- Layer 2 Geometry Facts.
- Layer 3 Relations.
- AlignmentClass.
- WorldOrientation.
- Feature Grammar.
- Skeleton solve.
- UV transfer.
- Blender UI.

---

## Recommended next task

Implement G1 topology builder policy in small steps:

1. Add selected-face edge adjacency helper inside `scaffold_core/layer_1_topology/build.py` or a small sibling module if the file grows too large.
2. Add Shell component detection from selected-face edge adjacency.
3. Add Patch component detection using the G1 boundary predicate.
4. Add seam split fixture/test.
5. Add shell-not-split-by-seam test.
6. Replace the current one-face-one-patch baseline only after tests cover the new behavior.

Do not refactor unrelated data models while doing this.

---

## Known baseline limitation

Current `build_topology_snapshot()` is intentionally simple and fixture-oriented.

It currently behaves roughly as:

```text
each selected face = one Patch
all selected faces = one Shell
```

This is not the final G1 policy. It is a temporary baseline to support early invariant tests.

---

## Agent safety rules

- Do not create future phase directories.
- Do not add `utils.py`, `helpers.py`, `manager.py`, `service.py`, `factory.py`, `registry.py`.
- Do not put H/V or WALL/FLOOR/SLOPE on Layer 1 topology entities.
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
