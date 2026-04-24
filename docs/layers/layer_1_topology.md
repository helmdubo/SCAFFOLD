# Layer 1 — Immutable Topology Snapshot

Layer 1 is the stable topological substrate.

## Purpose

Layer 1 represents how a source mesh is decomposed into surface regions, boundaries, loops and oriented boundary uses.

Layer 1 is intentionally ignorant of:

- H/V roles;
- WALL/FLOOR/SLOPE;
- UV coordinates;
- pin decisions;
- feature classifications;
- runtime solve roles.

## Owns

- `SurfaceModel`
- `Shell`
- `Patch`
- `BoundaryLoop`
- `Chain`
- `ChainUse`
- `Vertex` / `Junction`
- topology invariants
- topology queries

## ChainUse rule

`ChainUse` is mandatory.

A `Chain` is the shared boundary entity.
A `ChainUse` is the oriented use of a `Chain` inside a loop/patch.

All orientation-sensitive logic must use `ChainUse`, not raw `Chain`.

## Cardinality cases

| Case | Chain has ChainUses | Meaning |
|---|---:|---|
| Mesh border | 1 | Boundary of model or selection. |
| Normal shared boundary | 2, different patches | Standard adjacency. |
| SEAM_SELF | 2, same patch | Supported self-use case. |
| Non-manifold | >2 | Represent and diagnose explicitly. |

## Layer 1 must not contain

- `H_FRAME`
- `V_FRAME`
- `FREE`
- `WALL`
- `FLOOR`
- `SLOPE`
- `BAND`
- `PANEL`
- `PINNED`
- `GUIDE`
- UV coordinates
- skeleton solve coordinates
- feature confidence

If any of these appear in Layer 1 models, higher-level interpretation leaked into topology.
