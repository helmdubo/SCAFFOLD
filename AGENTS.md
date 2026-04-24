# AGENTS.md — Scaffold Core

> Operational rules for AI agents working on Scaffold Core.  
> This file is mandatory reading before modifying any code.

Scaffold Core is an immutable B-rep-inspired interpretation pipeline for topology-aware structural UV alignment.

Scaffold is a Blender UV workflow for architectural meshes.

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

This document governs the core package:

```text
scaffold_core/
```

A Blender add-on wrapper may later live separately as:

```text
scaffold/
```

---

## 0. Canonical References

The source of truth is:

```text
G0.md
```

G0 defines layers, entities, invariants, pipeline passes, dependency rules, design decisions, and non-goals.

Phase implementation plans may cite G0. They may not override G0.

### G0.md is read-only for agents

`G0.md` is read-only reference material for agents.

Agents may read it. Agents may not modify it.

G0 amendments require explicit human architectural review and are not part of normal coding work.

If implementation appears to require changing G0, stop and report:

- which G0 section conflicts with the task;
- why the task cannot be completed under current G0;
- what amendment would be needed.

---

## 1. Architectural Mantra

```text
Scaffold owns interpretation.
Blender owns mesh editing.
```

Scaffold Core does not mutate topology in place. It builds immutable interpretation snapshots from Blender mesh state.

---

## 2. Current Phase

The current implementation phase is:

```text
G1 — Topology Snapshot Prototype
```

G1 scope:

```text
Layer 0 — Source Mesh Snapshot
Layer 1 — Immutable Topology Snapshot
Pipeline Pass 0
Diagnostics
Tests
```

G1 must not implement:

- Layer 2 Geometry Facts;
- Layer 3 Relations;
- Layer 4 Feature Grammar;
- Layer 5 Runtime/Solve;
- skeleton solve;
- feature rules;
- world orientation;
- alignment classes;
- UV transfer;
- detail/decal systems.

Future phase directories must not be physically created during G1.

---

## 3. G1 Physical File Tree

Only the following tree should exist during G1:

```text
scaffold_core/
├── __init__.py
├── AGENTS.md
├── G0.md
│
├── constants.py
├── ids.py
│
├── core/
│   ├── __init__.py
│   ├── diagnostics.py
│   └── evidence.py
│
├── layer_0_source/
│   ├── __init__.py
│   ├── snapshot.py
│   ├── marks.py
│   ├── overrides.py
│   └── blender_io.py
│
├── layer_1_topology/
│   ├── __init__.py
│   ├── model.py
│   ├── build.py
│   ├── invariants.py
│   └── queries.py
│
├── pipeline/
│   ├── __init__.py
│   ├── context.py
│   ├── passes.py
│   └── validator.py
│
└── tests/
    ├── fixtures/
    │   ├── single_patch.py
    │   ├── l_shape.py
    │   ├── seam_self.py
    │   └── non_manifold.py
    ├── test_forbidden_imports.py
    ├── test_module_docstrings.py
    ├── test_layer_1_invariants.py
    ├── test_chainuse_orientation.py
    ├── test_seam_self.py
    └── test_pipeline_pass0.py
```

Do not create empty future directories such as:

```text
layer_2_geometry/
layer_3_relations/
layer_4_features/
layer_5_runtime/
api/
ui/
```

until their corresponding phase begins.

Empty future directories invite AI agents to fill them prematurely.

---

## 4. Target Tree After Later Phases

This is documentation, not permission to create these directories during G1.

```text
scaffold_core/
├── constants.py
├── ids.py
├── core/
│   ├── diagnostics.py
│   └── evidence.py
├── layer_0_source/
│   ├── snapshot.py
│   ├── marks.py
│   ├── overrides.py
│   └── blender_io.py
├── layer_1_topology/
│   ├── model.py
│   ├── build.py
│   ├── invariants.py
│   └── queries.py
├── layer_2_geometry/
│   ├── model.py
│   ├── facts.py
│   ├── chain_shape.py
│   ├── patch_fit.py
│   └── build.py
├── layer_3_relations/
│   ├── model.py
│   ├── adjacency.py
│   ├── alignment.py
│   ├── continuation.py
│   ├── junction.py
│   ├── world_orientation.py
│   ├── diagnostics.py
│   └── build.py
├── layer_4_features/
│   ├── model.py
│   ├── constraints.py
│   ├── rule_protocol.py
│   ├── resolver.py
│   ├── rules/
│   │   ├── panel_simple.py
│   │   └── band_minimal.py
│   └── world_rules/
│       ├── resolver.py
│       └── rules/
├── layer_5_runtime/
│   ├── skeleton_solve.py
│   ├── constraint_assembly.py
│   ├── resolved_labels.py
│   ├── pin_policy.py
│   └── uv_transfer.py
├── pipeline/
│   ├── context.py
│   ├── passes.py
│   └── validator.py
├── api/
│   ├── queries.py
│   └── reports.py
└── tests/
```

The Blender UI/add-on package may live outside `scaffold_core/`, for example:

```text
scaffold/
├── __init__.py
├── ui/
│   ├── operators.py
│   ├── panels.py
│   └── debug_overlay.py
```

---

## 5. Module-to-G0 Mapping

Before modifying a file, read the matching G0 section.

| Module | G0 section |
|---|---|
| `layer_0_source/` | Layer 0 / Source Mesh Snapshot |
| `layer_1_topology/` | Layer 1 / Topology Snapshot |
| `layer_1_topology/model.py` | Topology entities |
| `layer_1_topology/invariants.py` | Layer 1 invariants |
| `layer_1_topology/queries.py` | Topology query contract |
| `pipeline/` | Pipeline passes and dependency rules |
| `core/diagnostics.py` | Diagnostic severity model |
| `core/evidence.py` | Evidence model |
| `layer_2_geometry/` | Geometry Facts, created in G2 |
| `layer_3_relations/` | Derived Relations, created in G3 |
| `layer_4_features/` | Feature Grammar, created in G4 |
| `layer_5_runtime/` | Runtime/Solve, created in G5 |

---

## 6. Before Modifying Code

Before writing code, answer:

1. Which layer does this change belong to?
2. Which G0 section defines this layer?
3. Does the change require imports across layer boundaries?
4. Does it mutate data from a lower layer?
5. Does it introduce a new file or directory?
6. Does it create an abstraction before there are at least two real use cases?
7. Can this change be split into smaller layer-local commits?

If you cannot answer clearly, stop.

---

## 7. Import Direction Rules

Allowed direction:

```text
Layer 0 → Layer 1 → Layer 2 → Layer 3 → Layer 4 → Layer 5
```

A layer may import lower layers. A layer must not import higher layers.

Forbidden examples:

```text
layer_1_topology importing layer_2_geometry
layer_2_geometry importing layer_3_relations
layer_3_relations importing layer_4_features
layer_4_features importing layer_5_runtime
layer_5_runtime writing back to lower layers
```

### Pipeline rule

`pipeline/` orchestrates passes.

Layers must not import pipeline orchestration.

Allowed:

```text
pipeline imports layers
```

Forbidden:

```text
layers import pipeline.passes
layers import pipeline.validator
layers call run_pass_*
```

Limited exception:

Layer builder functions may accept `PipelineContext` as a typed parameter when needed.

Allowed:

```python
from pipeline.context import PipelineContext
```

Forbidden:

```python
from pipeline.passes import run_pass_1
from pipeline.validator import validate_pipeline
```

A layer may receive context data. A layer must not control pass order.

### API and add-on UI rule

`api/` and Blender UI code are consumers.

They may import pipeline/layers as needed, but they must not define core interpretation logic.

Blender UI code may import `bpy` for operators, panels, debug overlays and user interaction.

Blender UI code must not:

- build topology directly from BMesh;
- compute Geometry Facts;
- compute Relations;
- run FeatureRules directly outside pipeline;
- write UVs outside the runtime UV transfer boundary.

---

## 8. File-Level Import Rules

### `model.py`

Layer model files are pure data.

Allowed imports:

```text
ids.py
core/diagnostics.py if needed for typed diagnostics
core/evidence.py if needed
standard library
```

Forbidden in `model.py`:

```text
Blender bpy/bmesh
pipeline
higher layers
builder functions
solver code
feature rules
runtime code
```

### `build.py`

Layer builder files may import:

```text
their own model.py
lower-layer data/models
core diagnostics/evidence
ids
constants
```

Builder files must not orchestrate pipeline passes.

### `queries.py`

Query files are read-only.

Allowed:

```text
own layer model.py
ids.py
standard library
```

Forbidden:

```text
build logic
mutation
diagnostics generation except explicit query errors
higher layers
```

### `invariants.py`

Invariant files may import:

```text
own layer model.py
core/diagnostics.py
ids.py
```

They must not fix invalid data. They only report diagnostics.

---

## 9. Blender Boundary Rules

### Mesh read boundary

```text
layer_0_source/blender_io.py
```

is the mesh-read entry point.

It is responsible for converting Blender/BMesh state into `SourceMeshSnapshot`.

Other core layers must not read Blender mesh data directly.

### UV write boundary

```text
layer_5_runtime/uv_transfer.py
```

is the UV write-back exit point.

It is the only runtime module allowed to write UVs back to BMesh.

### Blender add-on exception

The Blender add-on package may import `bpy` for registration, UI, operators and overlays.

The add-on package must call into `scaffold_core` through public pipeline/API boundaries.

It must not duplicate core logic.

---

## 10. Layer Responsibilities

### Layer 0 — Source

Owns source mesh snapshot, source marks, source overrides and Blender mesh read boundary.

Does not own topology, geometry facts, relations, features or runtime solve.

### Layer 1 — Topology

Owns:

- `SurfaceModel`;
- `Shell`;
- `Patch`;
- `BoundaryLoop`;
- `Chain`;
- `ChainUse`;
- `Vertex` / `Junction`;
- topology invariants;
- topology queries.

Does not own H/V labels, WALL/FLOOR/SLOPE, geometry classification, alignment, feature recognition or solve.

### Layer 2 — Geometry

Created in G2.

Owns geometry facts and shape hints.

Does not own alignment roles, world semantic roles, feature instances or solve decisions.

### Layer 3 — Relations

Created in G3.

Owns adjacency, alignment, continuation, junction relations, world orientation and relation diagnostics.

Layer 3 is frozen after Pass 1.

Does not own feature candidates, feature instances, runtime solve or FeatureConstraints.

### Layer 4 — Features

Created in G4.

Owns FeatureRules, FeatureCandidates, FeatureInstances, FeatureConstraints, FeatureResolver and WorldSemanticRules.

Does not own topology mutation, Layer 3 mutation or solve execution.

### Layer 5 — Runtime

Created in G5.

Owns skeleton solve, constraint assembly, resolved labels, pin policy and UV transfer.

Does not own topology construction, geometry classification, relation construction or feature recognition.

---

## 11. Anti-Overengineering Rules

### Do not create generic buckets

Forbidden module names:

```text
utils.py
helpers.py
common.py
manager.py
factory.py
service.py
base.py
framework.py
registry.py
```

If you believe one is needed, stop and write a short design note.

### Do not create new top-level directories

New top-level directories require architecture review.

Do not add:

```text
services/
managers/
framework/
engine/
plugins/
shared/
misc/
internal/
impl/
```

### Do not create one file per tiny concept

Bad:

```text
patch.py
chain.py
chain_use.py
vertex.py
shell.py
loop.py
```

Good:

```text
layer_1_topology/model.py
```

Keep strongly related dataclasses together.

Split a file only when at least one condition is true:

```text
1. The file exceeds ~800 lines.
2. Three or more concurrent PRs regularly touch unrelated parts of the same file.
3. A subset of the file becomes a stable public boundary used by 3+ consumers.
4. The split matches a G0 layer/namespace boundary already approved for the current phase.
```

Prefer adding clear sections inside a file over splitting prematurely.

Do not split because “it feels cleaner”.

### Do not add abstract base classes prematurely

Do not create:

```text
AbstractTopologyBuilder
BaseSolver
IChainRepository
PatchService
```

unless there are at least two real implementations and the abstraction is approved by the current phase plan.

`FeatureRule` is the single authorized extensibility Protocol.

Important:

```text
FeatureRule exists in G4 only.
Before G4, do not introduce abstract protocols.
```

During G1, there should be no `Protocol`-based extension system.

### Do not create plugin systems early

No plugin registry before G4.

In G4, rule registration may be a simple list:

```python
FEATURE_RULES = [
    BandMinimalRule(),
    PanelSimpleRule(),
]
```

Do not build a plugin manager.

### Do not add caching

G0 v1 uses full rebuild.

Do not add:

```text
cache manager
invalidation graph
incremental recompute
dynamic connectivity structure
```

unless profiling proves a bottleneck and G0/G-plan authorizes it.

### Do not add empty future directories

Do not create `layer_2_geometry/` during G1.  
Do not create `layer_3_relations/` during G1.  
Do not create `layer_4_features/` during G1.

Create a layer directory only when that phase starts.

---

## 12. Constants Rules

`constants.py` contains only global project-level defaults.

Allowed examples:

```text
WORLD_UP
DEFAULT_TOLERANCE_GROUP
GLOBAL_DEBUG_FLAG
```

Algorithm-specific constants belong near the algorithm.

Examples:

```text
layer_2_geometry/chain_shape.py
  SAWTOOTH_*

layer_3_relations/alignment.py
  COS_DIRECTION_TOLERANCE
  ALIGNMENT_CLASS_SPREAD_TOLERANCE

layer_4_features/rules/panel_simple.py
  PANEL_SIMPLE_*
```

Do not turn `constants.py` into a global dumping ground.

---

## 13. Core Directory Rules

`core/` is dangerous because it can become a dumping ground.

It is allowed to contain only cross-cutting data models:

```text
core/diagnostics.py
core/evidence.py
```

`core/` must not contain:

```text
utils
helpers
base classes
factories
services
protocols
layer-specific logic
```

If you need to add a new file to `core/`, write a short design note first.

---

## 14. Diagnostics and Evidence

Use shared diagnostic and evidence models.

Do not invent local ad-hoc warning/error formats.

Diagnostics must include:

- severity;
- code;
- message;
- affected entity ids;
- source/pass;
- evidence where applicable.

Severity levels:

```text
BLOCKING
DEGRADED
WARNING
INFO
```

The pipeline halts only on `BLOCKING`.

Evidence is structured data, not a free-text explanation.

---

## 15. Multi-Layer Change Rule

If a task touches more than one layer, split it into separate commits:

```text
1. lower-layer data/model change
2. derived-layer consumer update
3. runtime/API/UI adaptation
```

Do not mix topology model change, relation consumer change, runtime solve adaptation and UI update in one commit.

If the task cannot be split, explain why before coding.

---

## 16. Minimal Patch Protocol

Use this protocol for bug fixes, regression fixes and edits to existing working code.

Over-editing is an architecture risk.

Over-editing means fixing the reported issue while unnecessarily rewriting surrounding code: renaming variables, changing formatting, adding unrelated guards, changing control flow, extracting helpers or touching unrelated files.

Minimality is part of correctness.

A patch is not correct if it fixes the bug but unnecessarily changes stable code.

### When Minimal Patch Protocol applies

Apply this protocol when the task says or implies:

```text
fix bug
regression
small correction
adapt existing function
change one behavior
repair failing test
```

Do not use this protocol for explicitly approved greenfield implementation tasks.

### Required workflow

#### Step 1 — diagnosis only

Before editing, identify:

```text
file
function/class
line range
root cause
minimal patch strategy
expected changed lines
```

Do not edit files during diagnosis.

#### Step 2 — patch plan

Propose the smallest patch.

Include:

```text
changed files
changed functions
estimated changed lines
behavior affected
tests to run
```

#### Step 3 — apply patch

Apply only the approved minimal patch.

Do not modify anything else.

### Hard constraints

When Minimal Patch Protocol applies:

```text
Do not refactor.
Do not rename variables, functions, classes, or files.
Do not reformat unrelated code.
Do not modernize code style.
Do not add defensive checks unless the bug directly requires them.
Do not change public behavior outside the failing case.
Do not touch unrelated functions.
Do not change imports unless directly necessary.
Do not update docs, README, configs, or tests unless required by the bug.
```

If the fix requires more than 10 changed lines, stop and explain why before editing.

### Patch output format

Separate patch from notes.

```text
PATCH:
  minimal fix only

NOTES:
  optional suggestions for later cleanup
```

Do not include cleanup suggestions in the patch.

### Reject patch if

```text
changed files > expected files
changed functions > expected functions
changed lines > agreed edit budget
public API changed without explicit approval
formatter changed unrelated blocks
imports changed without direct need
defensive try/except was added without direct need
```

If a useful unrelated improvement is discovered, report it under `NOTES` and leave the code unchanged.

---

## 17. Feature Work Rules

Feature work starts in G4.

Before G4, do not add:

```text
FeatureRule
FeatureCandidate
FeatureInstance
FeatureConstraint
FeatureResolver
rules/
world_rules/
```

When G4 starts, every new FeatureRule must specify:

1. feature kind;
2. anchor entities;
3. required topology pattern;
4. required geometry facts;
5. required relation facts;
6. hard constraints;
7. soft scoring evidence;
8. produced bindings;
9. ownership policy;
10. conflict compatibility;
11. FeatureConstraints produced;
12. debug/report output.

Every new rule requires:

- one positive synthetic fixture;
- one negative synthetic fixture;
- one tolerance-edge fixture.

---

## 18. FeatureConstraint Rule

FeatureConstraint is the only feature-to-solve communication channel.

Layer 4 must not write Layer 3 data.

Forbidden:

```text
FeatureInstance registers AlignmentClass
FeatureRule writes PatchAxes
FeatureRule mutates relations
```

Allowed:

```text
FeatureInstance produces FeatureConstraint
Layer 5 consumes FeatureConstraint in solve pass 2
```

---

## 19. Pipeline Rules

`pipeline/passes.py` owns pass orchestration.

Layer modules implement local builders.

Good:

```text
layer_1_topology/build.py
  build_topology(...)

pipeline/passes.py
  run_pass_0(...)
```

Bad:

```text
layer_1_topology/build.py
  runs pass 0, validates pass 1, calls relations, triggers solve
```

Pipeline order is defined by G0.

Do not invent new pass order inside layer modules.

---

## 20. Testing Rules

Tests must mirror architecture.

G1 required tests:

```text
test_forbidden_imports.py
test_module_docstrings.py
test_layer_1_invariants.py
test_chainuse_orientation.py
test_seam_self.py
test_pipeline_pass0.py
```

### `test_forbidden_imports.py`

This test is mandatory and should be created early.

It scans the package source tree and enforces architectural boundaries.

Implementation spec:

1. Parse every `.py` file in `scaffold_core/` via Python `ast`.
2. Extract all import statements:
   - `import X`
   - `from X import Y`
3. Determine source module by file path.
4. Determine target module by imported package path.
5. Apply rules:

```text
Layer N files must not import from layer_{N+1..5}/.

layer_*/ must not import:
  pipeline.passes
  pipeline.validator

layer model.py files must not import:
  builders
  pipeline
  higher layers
  Blender bpy/bmesh

No file may import modules matching:
  utils
  helpers
  common
  manager
  factory
  service
```

6. During G1, scan `scaffold_core/` and fail if future-phase directories exist:

```text
layer_2_geometry/
layer_3_relations/
layer_4_features/
layer_5_runtime/
api/
ui/
```

7. Fail with a clear diagnostic.

This test must run in CI and block merges on violation.

### `test_module_docstrings.py`

Every module must have a contract docstring.

The test scans all `.py` files in `scaffold_core/`, excluding:

```text
__init__.py
tests/
```

Each module docstring must contain:

```text
Layer:
Rules:
```

The goal is not documentation polish. The goal is to force every module to declare its architectural boundary.

---

## 21. Naming Rules

Use explicit names.

Good:

```text
ChainUse
PatchAdjacency
ChainContinuationRelation
AlignmentClass
PatchAxes
FeatureConstraint
DiagnosticSeverity
```

Avoid ambiguous names:

```text
Data
Info
ContextThing
Manager
Processor
Handler
Helper
Util
```

`orientation_sign` means topology orientation.

Do not call it:

```text
axis_sign
```

because “axis” suggests H/V semantics.

---

## 22. Do Not Reintroduce Old Primary Roles

Forbidden in Layer 1:

```text
H_FRAME
V_FRAME
FREE
STRAIGHTEN
WALL
FLOOR
SLOPE
BAND
PANEL
PINNED
GUIDE
```

These concepts may appear only as:

- derived relations;
- feature interpretations;
- runtime/debug labels;
- world orientation overlay;
- compatibility adapter output.

If such fields appear in Layer 1 model, it is an architecture violation.

---

## 23. Blender Add-on Entry

The Blender add-on `__init__.py` may contain add-on entry logic.

Keep it thin.

Allowed:

- `bl_info`;
- register/unregister;
- importing UI/operator registration when UI exists.

Forbidden:

- topology construction logic;
- geometry facts;
- relation building;
- feature recognition;
- solve logic.

Recommended metadata:

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

---

## 24. When Adding a New File

Before adding a file, answer:

1. Which layer owns this file?
2. Which G0 section authorizes it?
3. Why can it not live in an existing file?
4. Does it create a new abstraction?
5. Does it introduce a new import direction?
6. Does it create a future-phase directory prematurely?

If the file is outside the current phase scope, do not add it.

---

## 25. When Adding a New Directory

New directories require architectural review.

Allowed during G1:

```text
core/
layer_0_source/
layer_1_topology/
pipeline/
tests/
```

Forbidden during G1:

```text
layer_2_geometry/
layer_3_relations/
layer_4_features/
layer_5_runtime/
api/
ui/
```

unless the phase scope has officially changed.

---

## 26. Implementation Style

Prefer simple functions over service classes.

The codebase uses:

```text
frozen dataclasses:
  immutable data records:
  entities, facts, relations, diagnostics, evidence

functions:
  builders, validators, transforms, query helpers

stateful classes:
  only when persistent runtime state is truly required
  example: PipelineContext
```

Avoid service classes, managers, factories and framework-style objects.

Do not introduce a class just to group functions.

---

## 27. Module Docstring Template

Every module should start with a contract docstring.

Example for `layer_1_topology/model.py`:

```python
"""
Layer: 1 — Topology

Rules:
- No geometry facts here.
- No H/V, WALL/FLOOR/SLOPE, feature, or runtime roles here.
- ChainUse is the only oriented boundary-use entity.
- This module may import ids and core data models only.
"""
```

---

## 28. Git / PR Discipline

Keep changes reviewable.

One commit should have one purpose.

Prefer commits by layer:

```text
1. lower-layer data/model change
2. derived-layer consumer update
3. runtime/API/UI adaptation
```

Do not mix architecture, bug fix, formatting, tests and cleanup in one commit.

Commit message examples:

```text
G1 topology: add ChainUse orientation invariant
G1 tests: add SEAM_SELF fixture
G1 source: add SourceMeshSnapshot model
```

A PR is suspicious if it:

```text
touches more than 2 layers
adds a new directory
adds a new abstraction
changes more than 3 files for a bug fix
mixes refactor and behavior change
```

---

## 29. Common Red Flags

Stop and reconsider if your change includes:

- a new manager/factory/service/helper module;
- a new empty future directory;
- a higher layer importing a lower layer’s builder directly without pipeline;
- a lower layer importing a higher layer;
- a Layer 1 entity gaining semantic fields;
- a FeatureRule writing Layer 3 data;
- runtime solve recomputing topology or relations;
- direct BMesh reads outside `layer_0_source/blender_io.py`;
- UV writes outside `layer_5_runtime/uv_transfer.py`;
- caching/invalidation infrastructure;
- a large multi-layer commit;
- over-editing unrelated stable code.

---

## 30. Agent Checklist

Before finishing a task, verify:

```text
[ ] I read the relevant G0 section.
[ ] I stayed within the current phase scope.
[ ] I did not create future-phase directories.
[ ] I did not introduce forbidden imports.
[ ] I did not add generic helpers/utils/managers.
[ ] I did not mutate lower-layer data from a higher layer.
[ ] I added or updated tests.
[ ] I kept diagnostics structured.
[ ] I preserved immutability of snapshot entities.
[ ] I did not reintroduce H/V or WALL/FLOOR/SLOPE as primary topology facts.
[ ] If this was a bug fix, I followed Minimal Patch Protocol.
[ ] I identified the exact edit span before editing.
[ ] I did not rename/reformat/refactor unrelated code.
[ ] I separated PATCH from NOTES.
[ ] My changed files/functions/lines stayed within the planned edit budget.
```

If any checkbox fails, do not submit.

---

## 31. Final Rule

When in doubt, choose the simpler structure.

The goal is not to build a framework.

The goal is to build a clear, testable, immutable interpretation pipeline that follows G0.

```text
Physical structure should prevent G0 violations,
but must not invite framework building.
```
