# Import Boundaries

This file is the operational import policy for Scaffold Core.

## Layer direction

Allowed conceptual direction:

```text
Layer 0 → Layer 1 → Layer 2 → Layer 3 → Layer 4 → Layer 5
```

Lower layers must not import higher layers.

The user-filter stage (G0 DD-55, plan Slice AH) is a package between Layer 4
and Layer 5, not a numbered layer:

```text
Layer 0 → Layer 1 → Layer 2 → Layer 3 → Layer 4 → user_filters → Layer 5
```

```text
scaffold_core/user_filters/ imports core, ids, Layer 2 measures and the
  Layer 4 model; it never imports Layer 5.
Layer 5 (layer_5_runtime/islands.py) and pipeline/ import it.
Layers 0-4 and core must not import it.
```

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

During G5a, Layer 5 runtime exists and may consume Layers 0-4 read-only
(Layer 4 only through FeatureConstraint) and the user-filter stage (only
through SeamDirective). Layer 4 (`scaffold_core/layer_4_features/`, plan
decision 14) and `scaffold_core/user_filters/` (plan Slice AH) are open. The
following directories remain future/deferred:

```text
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
It also checks that the user-filter stage imports no Layer 5, that Layers
0-4 import nothing from it, and that no module of `core`, `constants` or a
layer package names the world vertical or the patch classes (the words
world_up, vertical, horizontal, patch_class and their spellings).
