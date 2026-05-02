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
Edges / Nodes visibility
```

To unregister:

```python
scaffold_graph_debug.unregister()
```

