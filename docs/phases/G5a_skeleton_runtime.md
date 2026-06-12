# G5a — Skeleton Runtime (phase contract)

Phase start authorized by the user after artist validation of stage-1
structure (rails/families/junctions/seam verdicts on real meshes).
Layer 4 remains deferred: G5a runs FeatureConstraint-free (DD-18 allows
optional constraints; the L4 grammar plugs in later without rework).

## Consumed API (validated by tracer + overlay consumption)

```text
Layer 1 topology, Layer 2 facts (incl. per-vertex angle defect,
LocalFaceFan), Layer 3: ConnectedDirectionFamily v1 (per-use, geodesic),
RunEndpointJunction, ScaffoldNode/PatchAdjacency/ScaffoldJunction,
PatchChainDirectionalEvidence, PatchAxes.
```

## Module contract (scaffold_core/layer_5_runtime/)

```text
islands.py   - island assembly: spanning tree of stitch decisions.
  Stitch gate (Level A): would-be-interior vertex set =
  mid-chain seam vertices tested |2pi - angle_sum| <= tolerance;
  chain endpoints excluded while they keep any remaining cut incidence
  (T-junction rule). SEAM_SELF always splits. Non-tree seams stay cut.

skeleton.py  - selection-wide solve:
  nodes = ScaffoldNode UNION RunEndpointJunction (rail atoms);
  one equation per RUN per axis connecting ITS OWN endpoints
  (the spike's chain-endpoint bug is contract-forbidden);
  axes = island-local AXIS_A/AXIS_B projected from families in the
  island's unfolded frame (stitch-tree parallel transport);
  numpy dense lstsq per axis; gauge = seed component pinned;
  spread safety: contradictory components -> UNCONSTRAINED, excluded,
  their vertices unpinned; residual reported.

pins.py      - output model: vertex -> (uv, pinned flag, island id).
uv_transfer.py - the ONLY bpy write boundary (G5 rule): writes UVs+pins,
  invokes Blender pinned conformal unwrap for the fabric.
```

## Invariants (validation outputs, not hopes)

```text
1. axis-parallel: an axis-classified run's endpoints differ in UV only
   along its own axis (zero violations on flat-grid fixtures);
2. lstsq residual ~0 on developable grids; nonzero residual must be
   accompanied by UNCONSTRAINED diagnostics, never silent smearing;
3. SEAM_SELF sides equal length in UV (band closure invariant);
4. degradation always carries diagnostics naming entities.
```

## Non-goals in G5a

Texel scale policy, packing, trim semantics, Layer 4 grammar,
WorldOrientation, curved-chain refinement (OQ-11 remainder).
