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
uv_transfer.py - the ONLY bpy write boundary (G5 rule): writes UVs+pins
  in the mesh's current mode without bpy operators. It does not call
  mode_set or unwrap; the artist runs Blender's U > Unwrap after the
  pins are written so the conformal fill is owned by Blender UI state.
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

## Implemented status (H3)

```text
Layer 5 v0 is implemented in scaffold_core/layer_5_runtime/.

islands.py:
  spanning-tree island assembly over Level A stitch decisions;
  mid-chain would-be-interior vertices use Layer 2 angle sums;
  stitch endpoints are excluded while remaining cut incidence keeps
  them boundary (T-junction rule);
  SEAM_SELF always splits and non-tree seams stay cut.

skeleton.py:
  selection-wide skeleton solve over ScaffoldNode UNION
  RunEndpointJunction atoms;
  one length equation per directional run endpoint pair;
  island-local AXIS_A / AXIS_B roles are derived from
  ConnectedDirectionFamily v1 in the unfolded island frame;
  contradictions are excluded as UNCONSTRAINED with diagnostics.

pins.py:
  run_skeleton_solve() orchestrates islands -> skeleton -> pinned UVs;
  per-patch pins preserve duplicated seam occurrences;
  axis-parallel and SEAM_SELF length checks are validation outputs.

uv_transfer.py:
  writes UV coordinates and pin flags only;
  uses bmesh in Edit Mode and Object Mode (from_edit_mesh / from_mesh);
  calls no bpy operators and performs no automatic unwrap.
```

## Blender workflow

```text
1. Select the target mesh faces, or select one mesh object in Object Mode
   to use all faces of that object.
2. Press Write UV (G5a) in the Scaffold Graph debug panel.
3. Check the info-bar summary and console diagnostics.
4. In the UV Editor run U > Unwrap to fill the fabric between pinned rails.
```

Expected currently validated behavior:

```text
- cylinder tube with two seams: rectangular side band, one seam stitched
  inside the island and the other left open;
- extruded_cross: side band plus two separate cap islands;
- l_corridor_tunnel_seamed_folds: one island through the folds;
- artist_cyl32/Cylinder: 68 pins, residual about 4e-15, zero diagnostics
  in the validated capture.
```

Known limitation:

```text
artist_cross_band currently degrades partially with diagnostics instead of
silently smearing. This is an accepted G5a diagnostic case, not a green
quality target yet.
```
