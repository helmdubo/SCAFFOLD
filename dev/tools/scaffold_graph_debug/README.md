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

Spines shows the longest rail in the dominant rail axis for the selected shell
as a thick cyan stroke. Other rails parallel to that axis use the same hue but
are thinner.

Ribs shows rails from the other axis families in orange. These are guide rails,
not solve output.

Seam Verdicts shows Level A stitch/cut checks for shared seam chains. Green
dashed means the seam is geometrically sewable under the current angle-defect
test. Red solid means it must stay cut; red X markers show failing vertices.
There are no labels on this layer.

JunctionsV2 shows ScaffoldNodes as circles and unanchored RunEndpointJunctions
as diamonds. Larger glyphs mean higher run-end valence.

Branches shows explicit yellow branch markers at junctions where more than two
run ends meet in the debug rail graph. The overlay marks the ambiguity and does
not choose a path through it.

Colors are stable across rebuilds. They are derived from ids, never from true
random numbers.

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
