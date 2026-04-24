# File Tree Target

This document describes the intended Scaffold Core package shape.

`AGENTS.md` is the operational router. `G0.md` is the architectural constitution.

## G1 physical tree

During G1, only this implementation tree should exist:

```text
scaffold_core/
├── __init__.py
├── constants.py
├── ids.py
├── core/
│   ├── __init__.py
│   ├── diagnostics.py
│   └── evidence.py
├── layer_0_source/
│   ├── __init__.py
│   ├── snapshot.py
│   ├── marks.py
│   ├── overrides.py
│   └── blender_io.py
├── layer_1_topology/
│   ├── __init__.py
│   ├── model.py
│   ├── build.py
│   ├── invariants.py
│   └── queries.py
├── pipeline/
│   ├── __init__.py
│   ├── context.py
│   ├── passes.py
│   └── validator.py
└── tests/
    ├── fixtures/
    ├── test_forbidden_imports.py
    ├── test_module_docstrings.py
    ├── test_layer_1_invariants.py
    ├── test_chainuse_orientation.py
    ├── test_seam_self.py
    └── test_pipeline_pass0.py
```

## Future target tree

Future phase directories are documentation-only until their phase begins.

```text
scaffold_core/
├── layer_2_geometry/
├── layer_3_relations/
├── layer_4_features/
├── layer_5_runtime/
├── api/
└── ui/  # likely in Blender add-on wrapper, not core
```

Do not create empty future directories during G1.
