# AGENTS.md — Scaffold Core

Mandatory operating rules for AI agents working in this repository.

Scaffold Core is an immutable B-rep-inspired interpretation pipeline for topology-aware structural UV alignment.

This file is a router, not the full architecture.

Full architectural contract:

```text
G0.md
```

Machine routing index:

```text
docs/context_map.yaml
```

---

## Current phase

```text
G3 - Derived Relations
```

Allowed during G3:

```text
scaffold_core/core/
scaffold_core/layer_0_source/
scaffold_core/layer_1_topology/
scaffold_core/layer_2_geometry/
scaffold_core/layer_3_relations/
scaffold_core/pipeline/
scaffold_core/tests/
```

Forbidden during G3:

```text
scaffold_core/layer_4_features/
scaffold_core/layer_5_runtime/
scaffold_core/api/
scaffold_core/ui/
```

Do not create future-phase directories.

---

## Read-only architecture

`G0.md` is read-only for agents.

Agents may read it. Agents may not modify it.

If a task conflicts with G0, stop and report:

- the conflicting G0 section;
- why the task cannot be completed under current G0;
- what amendment would be required.

---

## Routing table

Before coding, read only the routed docs needed for the task.

| Task | Read |
|---|---|
| Any architecture question | `G0.md` |
| Planning / Architect workflow | `docs/agent_rules/planning_workflow.md` |
| Codex dense slice / prompt workflow | `docs/agent_rules/codex_workflow.md` |
| Prompt templates | `docs/agent_rules/codex_prompt_library.md` |
| CFTUV migration / bridge | `docs/migration/cftuv_lessons.md` + `docs/migration/cftuv_bridge.md` |
| CFTUV parity fixtures | `docs/migration/cftuv_parity_fixtures.md` |
| G1 topology work | `docs/phases/G1_topology_snapshot.md` + `docs/layers/layer_1_topology.md` + `docs/architecture/segmentation_shell_policy.md` |
| G2 geometry facts | `docs/phases/G2_geometry_facts.md` + `docs/architecture/G0_full.md` |
| G3 derived relations | `docs/phases/G3_derived_relations.md` + `docs/architecture/G0_full.md` |
| Patch segmentation / shell detection | `docs/architecture/segmentation_shell_policy.md` |
| Source mesh snapshot | `docs/layers/layer_0_source.md` |
| Import rule / new file | `docs/agent_rules/import_boundaries.md` |
| Bug fix / regression | `docs/agent_rules/minimal_patch_protocol.md` |
| New test | `docs/agent_rules/testing_rules.md` |
| Blender IO | `docs/agent_rules/blender_boundaries.md` |
| File split / new abstraction | `docs/agent_rules/anti_overengineering.md` |
| Design decision lookup | `docs/architecture/design_decisions.md` |

---

## G1 segmentation rule

Patch segmentation is seam-only by default.

Patch flood fill is blocked by:

```text
mesh/selection border
non-manifold selected edge
explicit Scaffold boundary mark
Blender UV Seam
```

Blender Sharp is not a default Patch boundary source.

A future optional command may support `make seams by sharps`, but Sharp must not become a hidden default segmentation source.

---

## G2 geometry rule

Layer 2 stores raw measured geometry facts only.

Allowed G2 facts:

```text
area
normal
centroid
length
chord direction
vertex position
degenerate geometry diagnostics
```

Forbidden in Layer 2:

```text
H_FRAME
V_FRAME
WALL
FLOOR
SLOPE
AlignmentClass
PatchAxes
WorldOrientation
DihedralKind
Feature
Pin
UV
```

Sawtooth/straightness work exists only as raw G2 geometry facts.

---

## G3 relations rule

Layer 3 stores derived relations over topology and geometry.

## G3 relations status

Implemented in G3:

```text
PatchAdjacency
DihedralKind
RelationSnapshot
PatchChain incidence queries
conservative ChainContinuationRelation (TERMINUS/SPLIT)
ChainDirectionalRun
PatchChainDirectionalEvidence
AlignmentClass v0
PatchAxes v0
PatchChainEndpointSample
PatchChainEndpointRelation v0
LoopCorner v0
LocalFaceFanGeometryFacts
```

Deferred in G3:

```text
ScaffoldNode / ScaffoldJunction / ScaffoldEdge
ScaffoldGraph / ScaffoldTrace / ScaffoldCircuit / ScaffoldRail
WorldOrientation
```

Forbidden during G3:

```text
Layer 4 Feature Grammar
Layer 5 Runtime/Solve
UV transfer
API
UI
Blender add-on wrapper
```

Layer 3 must not import or depend on Layer 4 features, Layer 5 runtime/solve,
UV transfer, API, UI or Blender modules.

---

## Import rules

Allowed layer direction:

```text
Layer 0 → Layer 1 → Layer 2 → Layer 3 → Layer 4 → Layer 5
```

Lower layers must not import higher layers.

`pipeline/` may import layers.

Layers must not import:

```text
pipeline.passes
pipeline.validator
```

Limited exception: layer builders may type-import `pipeline.context.PipelineContext` if needed.

---

## Blender boundaries

Mesh read boundary:

```text
scaffold_core/layer_0_source/blender_io.py
```

UV write boundary, introduced only in G5:

```text
scaffold_core/layer_5_runtime/uv_transfer.py
```

Blender add-on UI code may import `bpy`, but it must not duplicate core logic.

---

## Anti-overengineering

Do not create:

```text
utils.py
helpers.py
common.py
manager.py
factory.py
service.py
registry.py
```

Do not add new top-level directories without architectural review.

Prefer frozen dataclasses and simple functions over service classes.

Split a file only when the rule in `docs/agent_rules/anti_overengineering.md` allows it.

---

## Minimal Patch Protocol

For bug fixes, regressions and small corrections:

- identify exact file/function/line range before editing;
- apply the smallest patch;
- do not refactor;
- do not rename;
- do not reformat unrelated code;
- separate `PATCH` from `NOTES`.

Full protocol:

```text
docs/agent_rules/minimal_patch_protocol.md
```

---

## Add-on metadata

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

`category = "UV"` is intentional.

---

## Final checklist

```text
[ ] I read the routed docs.
[ ] I stayed within current phase scope.
[ ] I did not create future-phase directories.
[ ] I did not introduce forbidden imports.
[ ] I did not add utils/helpers/managers/services.
[ ] I did not mutate lower-layer data from a higher layer.
[ ] I added or updated tests.
[ ] I did not reintroduce H/V or WALL/FLOOR/SLOPE as primary topology or geometry facts.
[ ] If this was a bug fix, I followed Minimal Patch Protocol.
```

When in doubt, choose the simpler structure.
