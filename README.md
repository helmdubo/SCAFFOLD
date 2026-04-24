# Scaffold

Scaffold is a Blender UV workflow for architectural meshes.

The current implementation focus is **Scaffold Core**: an immutable B-rep-inspired interpretation pipeline for topology-aware structural UV alignment.

## Repository structure

```text
AGENTS.md                  # agent router and operating rules
G0.md                      # compact canonical architecture contract
Scaffold_G0.md             # pointer to current G0 files
docs/context_map.yaml      # machine-readable routing/index
docs/                      # modular architecture, phase, layer and agent-rule docs
scaffold_core/             # core implementation package
```

## Current phase

```text
G1 — Topology Snapshot Prototype
```

G1 implements only:

- Layer 0 — Source Mesh Snapshot
- Layer 1 — Immutable Topology Snapshot
- Pipeline Pass 0
- Diagnostics and tests

Future layers are intentionally not created yet.

## Agent workflow

Agents should read `AGENTS.md` first.

`AGENTS.md` routes tasks to the smallest relevant doc set instead of forcing every agent to read the full architecture every time.

Formula:

```text
AGENTS.md = rules of movement
G0.md = constitution
phase docs = what we are doing now
layer docs = contract of a specific layer
agent_rules = operational guardrails
docs/context_map.yaml = machine-readable index
```

## Core package

The core package is:

```text
scaffold_core/
```

The Blender add-on wrapper may later live separately as:

```text
scaffold/
```

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

`category = "UV"` is intentional because the primary workflow lives in UV space.

## Run tests

From repository root:

```bash
pytest scaffold_core/tests
```

The first architectural tests to keep green are:

```text
scaffold_core/tests/test_forbidden_imports.py
scaffold_core/tests/test_module_docstrings.py
```

## Important docs

| Need | Read |
|---|---|
| Architecture contract | `G0.md` |
| Full architecture reference | `docs/architecture/G0_full.md` |
| Current phase | `docs/phases/G1_topology_snapshot.md` |
| Layer 0 contract | `docs/layers/layer_0_source.md` |
| Layer 1 contract | `docs/layers/layer_1_topology.md` |
| Import boundaries | `docs/agent_rules/import_boundaries.md` |
| Anti-overengineering | `docs/agent_rules/anti_overengineering.md` |
| Bug fix protocol | `docs/agent_rules/minimal_patch_protocol.md` |
