# Anti-overengineering Rules

Scaffold Core should stay simple, layer-aligned and testable.

## Do not create generic buckets

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

## Do not create one file per tiny concept

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

## Do not add abstract base classes prematurely

Do not create abstractions unless there are at least two real implementations and the abstraction is approved by the current phase plan.

`FeatureRule` is the single authorized extensibility Protocol, and only from G4 onward.

## Do not add caching during G1

G0 v1 uses full rebuild.

No cache manager, invalidation graph, incremental recompute or dynamic connectivity structure unless profiling proves a bottleneck and the phase plan authorizes it.

## Do not create future directories

During G1, do not create future phase packages.

Physical structure should prevent G0 violations, but must not invite framework building.
