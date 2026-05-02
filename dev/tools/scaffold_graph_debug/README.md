# ScaffoldGraph Debug Add-on

Development-only Blender add-on for the ScaffoldGraph Grease Pencil overlay.

It consumes `scaffold_graph_overlay` from Scaffold Core inspection. It does not
recompute graph semantics and does not write UVs.

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
Show Graph
Refresh Graph
Close Graph
Edges / Nodes / Junctions / Labels visibility
```

`Show Graph` hides the source mesh while the overlay is active. `Close Graph`
removes the overlay and restores the mesh visibility.

Labels are Blender text objects. Node and edge labels prefer the compact
`display_label` from the inspection overlay, with raw ids only as a fallback
for older payloads. Exact coincident or reversed edge polylines are spread into
small deterministic display lanes while leaving the overlay payload and core
graph records unchanged.

SELF_SEAM ScaffoldJunction records from the overlay payload render as distinct
markers on `ScaffoldGraph_Junctions`, at the existing ScaffoldNode position.

To unregister:

```python
scaffold_graph_debug.unregister()
```
