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

## Test tiers

Use progressively heavier validation tiers. Do not run Blender for every small
core change.

```text
Tier 0 - Architecture gates
  forbidden imports
  module docstrings
  phase scope
  forbidden future directories

Tier 1 - Synthetic core tests
  small explicit fixtures
  pure Python only

Tier 2 - Compact pipeline reports
  inspection summaries
  stable report fields
  no Blender required

Tier 3 - Headless Blender smoke
  small .blend fixtures
  compact JSON/text report
  optional screenshot artifacts

Tier 4 - Production regression
  selected real meshes
  screenshots / UV comparison
  run manually or nightly
```

Tier 3 runner: `dev/tools/blender_smoke/` (see its README). Default check:

```bash
python dev/tools/blender_smoke/run_smoke.py <file.blend> --seamed --write-uv \
  --baseline dev/tools/blender_smoke/baselines/buildings_seamed.json
```

An unchanged run prints two lines. Rewrite the baseline with
`--update-baseline` only when a behavior change is intended, and record the
diff in the plan. Hard Tier 3 invariants: `opposite_side_families`,
`axis_violations`, `seam_mismatches` and `foreign_loops_changed` are 0.

Real-mesh Tier 2 captures from `buildings.blend` live in
`scaffold_core/tests/data/artist_walls_*.json`; dump new ones with
`--capture-dir` and replay them in pure Python instead of relaunching Blender.

AI agents should prefer Tier 0-2 during ordinary core work. Use Tier 3 only when
the slice touches Blender boundaries, mesh snapshot integration, geometry cases
that cannot be represented synthetically, or runtime/UV behavior in later phases.
