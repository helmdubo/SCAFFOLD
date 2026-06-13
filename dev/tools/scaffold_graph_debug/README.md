# ScaffoldGraph Debug Add-on

Development-only Blender add-on for the ScaffoldGraph Grease Pencil overlay
and the temporary G5a UV write button.

It consumes Pass 0 / Pass 1 snapshots from Scaffold Core. The overlay does not
store roles and does not add Scaffold Core relation records. The v2 overlay
rebuilds a temporary artist-facing view each time you press Rebuild. `Write UV
(G5a)` consumes the Layer 5 runtime result and writes pinned UV skeleton loops.

## Register From Blender

In Blender Python Console:

```python
import sys
sys.path.insert(0, r"D:\_mimirhead\website\SCAFFOLD\dev\tools")
import scaffold_graph_debug
scaffold_graph_debug.register()
```

Then use:

```text
View3D > Sidebar > Scaffold > Scaffold Graph
```

Controls:

```text
Rebuild Overlay
Write UV (G5a)
Close Graph
Family Colors / Spines / Ribs / Seam Verdicts (also CutRails) / Junctions / Branches visibility
```

`Rebuild Overlay` hides the source mesh while the overlay is active. `Close Graph`
removes the overlay and restores the mesh visibility.

## Write UV (G5a)

`Write UV (G5a)` runs the Layer 5 v0 runtime:

```text
Pass 0 / Pass 1 -> build_islands -> build_island_skeletons -> run_skeleton_solve
-> uv_transfer.write_pinned_uvs
```

The button writes UV coordinates and pin flags for the skeleton only. It does
not call `bpy.ops.uv.unwrap`, does not switch modes by operator, and does not
perform conformal fill. After the info-bar reports success, run Blender's
manual command:

```text
UV Editor -> U -> Unwrap
```

Blender's unwrap respects the pins written by G5a. This split is intentional:
the `uv_transfer.py` boundary is crash-proof in Blender 4.3 because it writes
pin flags through bmesh in Edit Mode and avoids operator-context unwrap calls.

Current expected validation on the artist Cylinder capture:

```text
pinned:68 loops:192 residual:~4e-15 axis_violations:0 diags:0
```

If the button reports diagnostics, treat them as part of the G5a validation
surface. They should name the degraded entities instead of silently smearing
the UV skeleton.

## Overlay v2 Layers

```text
ScaffoldGraph_FamilyRuns
ScaffoldGraph_Spines
ScaffoldGraph_Ribs
ScaffoldGraph_CutRails
ScaffoldGraph_SeamVerdicts
ScaffoldGraph_JunctionsV2
ScaffoldGraph_Branches
```

| Layer | Meaning |
| --- | --- |
| ScaffoldGraph_FamilyRuns | Raw core ConnectedDirectionFamily runs. Every directional run segment is drawn, including n-gon cap chains. |
| ScaffoldGraph_Spines | Derived debug rails: the dominant rail in a patch group plus rails parallel to it. |
| ScaffoldGraph_Ribs | Derived debug rails that are not spines/parallel rails. Ribs may carry multiple related rail ids. |
| ScaffoldGraph_CutRails | SEAM_SELF and cut rails in the dedicated cut color. |
| ScaffoldGraph_SeamVerdicts | Level A stitch verdicts for shared seam chains. |
| ScaffoldGraph_JunctionsV2 | Node atoms: every ScaffoldNode and every RunEndpointJunction. |
| ScaffoldGraph_Branches | Explicit branch markers where the debug rail graph has valence > 2. |

Rails are debug-side views over core `ConnectedDirectionFamily v1`, rebuilt on
each overlay refresh. In-patch geodesic continuation, occurrence-aware
face-fan angles, and cross-patch transport are supplied by core evidence; the
overlay does not run a separate geodesic grouping rule.

Rail membership is per PatchChain use. The same source edge can draw twice:
one offset line for the side-band patch view and one offset line for the cap
patch view. Shared chains are drawn as per-use double lines, each lifted along
the owning patch-use face normal and then nudged slightly inward toward that
patch by `RAIL_OFFSET_FACTOR` times local edge length. Rail layers draw those
rails as continuous Grease Pencil strokes with intermediate vertices instead
of one stroke per source edge. Cap perimeters are no longer
hidden; the cap-side cornered perimeter and the band-side continuous rail are
both visible.

Seam Verdicts shows Level A stitch/cut checks for shared seam chains. Green
dashed means the seam is geometrically sewable under the current angle-defect
test. Red solid means it must stay cut; red X markers show failing vertices.
There are no labels on this layer.

SELF_SEAM chains are always treated as cut rails/seams and use the dedicated
cut color.

JunctionsV2 shows ScaffoldNodes as circles and RunEndpointJunctions as
diamonds. Anchored run endpoints share the same position as their ScaffoldNode
but remain separate glyphs. Larger glyphs mean higher run-end valence.

Branches shows explicit yellow branch markers at junctions where more than two
run ends meet in the debug rail graph. The overlay marks the ambiguity and does
not choose a path through it.

Colors are stable across rebuilds. They are derived from ids, never from true
random numbers.

## Canonical Artist Example

For an extruded-cross building:

```text
side band = one patch with one vertical seam
top and bottom caps = separate patches
```

Expected overlay:

```text
1. The entire top rim is one visible rail.
2. The entire bottom rim is a second visible rail with a different family color.
3. The vertical seam is rendered in the cut color.
4. The cap patch views still see those same rim edges as cornered perimeter
   pieces, not as one straight rail; those cap-view pieces draw beside the
   side-band rail as their own offset lines.
```

## Avoiding Stale Add-ons

The panel header shows:

```text
Build: <short git hash>[-dirty]
```

After `git pull`, update the Blender add-on with a clean reload:

```text
1. Close Graph.
2. Unregister/remove the add-on module from Blender.
3. Restart Blender.
4. Register/install the add-on again from this checkout.
5. Confirm the panel Build stamp matches the new git hash and has no `-dirty`
   suffix unless you intentionally run local edits.
```

Python bytecode cache for this add-on lives under:

```text
dev/tools/scaffold_graph_debug/__pycache__/
```

If Blender appears to run stale code after an update, close Blender and delete
that directory before registering the add-on again.

## Staged Validation Checklist

Stage 1 is structural validation before UVs exist:

```text
1. Family Runs: expected same-direction flow uses one stable color across seams.
2. Spines: the main long rail follows the intended length direction.
3. Parallel rails: the opposite long rail appears thinner but same hue family.
4. Ribs: cross rails appear in the contrasting hue.
5. Seam Verdicts: green seams are candidates for sewing; red seams stay cut.
6. Junctions: mid-chain corners appear as diamonds when they are not
   ScaffoldNodes.
7. Branches: branch markers are warnings; do not expect the overlay to choose
   the continuation.
```

To unregister:

```python
scaffold_graph_debug.unregister()
```
