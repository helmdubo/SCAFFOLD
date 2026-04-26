# Testing Rules

Tests must mirror the architecture.

G1 required tests:

```text
test_forbidden_imports.py
test_module_docstrings.py
test_layer_1_invariants.py
test_patch_chain_orientation.py
test_seam_self.py
test_pipeline_pass0.py
```

## test_forbidden_imports.py

This test scans `scaffold_core/` and enforces architectural boundaries.

It must fail on:

- future-phase directories during G1;
- lower layers importing higher layers;
- layer files importing `pipeline.passes` or `pipeline.validator`;
- `model.py` files importing builders, pipeline, higher layers or Blender modules;
- forbidden generic module names like `utils.py`, `helpers.py`, `manager.py`, `service.py`.

## test_module_docstrings.py

Every module must have a contract docstring containing:

```text
Layer:
Rules:
```

The goal is not documentation polish. The goal is architectural boundary declaration.

## Synthetic fixtures

Fixtures should be small and explicit.

Required early fixtures:

```text
single_patch.py
l_shape.py
seam_self.py
non_manifold.py
```

Fixtures should not depend on large production assets.
