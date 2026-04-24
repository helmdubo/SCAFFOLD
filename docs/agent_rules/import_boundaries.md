# Import Boundaries

This file is the operational import policy for Scaffold Core.

## Layer direction

Allowed conceptual direction:

```text
Layer 0 → Layer 1 → Layer 2 → Layer 3 → Layer 4 → Layer 5
```

Lower layers must not import higher layers.

## Pipeline rule

`pipeline/` orchestrates passes.

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

```python
from scaffold_core.pipeline.context import PipelineContext
```

Layer builder functions may type-reference `PipelineContext` when needed, but must not control pass order.

## G3 forbidden future directories

During G3, the following future-phase directories must not exist:

```text
scaffold_core/layer_4_features/
scaffold_core/layer_5_runtime/
scaffold_core/api/
scaffold_core/ui/
```

`scaffold_core/layer_2_geometry/` and `scaffold_core/layer_3_relations/` are allowed during G3.

## Enforced by test

`scaffold_core/tests/test_forbidden_imports.py` must scan imports and fail on boundary violations.
