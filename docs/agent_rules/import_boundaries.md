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

## Phase directory boundaries

During G5a, Layer 5 runtime exists and may consume Layers 0-3 read-only.
The following directories remain future/deferred:

```text
scaffold_core/layer_4_features/
scaffold_core/api/
scaffold_core/ui/
```

`scaffold_core/layer_5_runtime/` is allowed during G5a. It must not be
imported by lower layers, and lower layers must not depend on runtime solve or
UV transfer output.

`bpy` remains forbidden in core except for:

```text
scaffold_core/layer_5_runtime/uv_transfer.py
```

## Enforced by test

`scaffold_core/tests/test_forbidden_imports.py` must scan imports and fail on boundary violations.
