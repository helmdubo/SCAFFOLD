# ScaffoldGraph Debug Add-on

Development-only Blender add-on for the ScaffoldGraph Grease Pencil overlay.

It consumes Pass 0 / Pass 1 snapshots from Scaffold Core. It does not write UVs,
does not store roles, and does not add Scaffold Core relation records. The v2
overlay rebuilds a temporary artist-facing view each time you press Rebuild.

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
Close Graph
Family Colors / Spines / Ribs / Seam Verdicts / Junctions / Branches visibility
```

`Rebuild Overlay` hides the source mesh while the overlay is active. `Close Graph`
removes the overlay and restores the mesh visibility.

## Overlay v2 Layers

```text
ScaffoldGraph_FamilyRuns
ScaffoldGraph_Spines
ScaffoldGraph_Ribs
ScaffoldGraph_SeamVerdicts
ScaffoldGraph_JunctionsV2
ScaffoldGraph_Branches
```

Family Runs shows every directional run segment. ConnectedDirectionFamily ids
get stable deterministic colors. Runs without a family are neutral gray.

Spines shows the longest core family rail in the dominant rail axis for the
selected shell. Other rails parallel to that axis use their own family colors
but are thinner.

Ribs shows rails from the other axis families. These are guide rails, not solve
output.

Rails are debug-side views over core `ConnectedDirectionFamily v1`, rebuilt on
each overlay refresh. In-patch geodesic continuation, occurrence-aware
face-fan angles, and cross-patch transport are supplied by core evidence; the
overlay does not run a separate geodesic grouping rule.

Rail membership is per PatchChain use. The same source edge can draw twice:
one offset line for the side-band patch view and one offset line for the cap
patch view. Shared chains are drawn as per-use double lines, each nudged inward
toward its owning patch by `RAIL_OFFSET_FACTOR` times local edge length. Cap
perimeters are no longer hidden; the cap-side cornered perimeter and the
band-side continuous rail are both visible.

Seam Verdicts shows Level A stitch/cut checks for shared seam chains. Green
dashed means the seam is geometrically sewable under the current angle-defect
test. Red solid means it must stay cut; red X markers show failing vertices.
There are no labels on this layer.

SELF_SEAM chains are always treated as cut rails/seams and use the dedicated
cut color.

JunctionsV2 shows ScaffoldNodes as circles and unanchored RunEndpointJunctions
as diamonds. Larger glyphs mean higher run-end valence.

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
