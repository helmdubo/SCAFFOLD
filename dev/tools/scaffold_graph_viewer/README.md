# Scaffold Graph Viewer

Development-only topological graph viewer for Scaffold QA.

The viewer is intentionally outside `scaffold_core/`. It consumes JSON
inspection payloads and does not build Scaffold relations, traces, rails, UVs
or solve data.

## Open

Open:

```text
dev/tools/scaffold_graph_viewer/index.html
```

Drag a JSON payload into the canvas or use **Open JSON**.

Supported payloads:

```text
1. raw inspect_pipeline_context(context, detail="full") output;
2. scaffold_graph_viewer_payload_v1 wrapper from the export scripts here.
```

## Export From A Synthetic Fixture

From the repository root:

```powershell
python dev/tools/scaffold_graph_viewer/export_fixture_payload.py l_corridor --open-dir
python dev/tools/scaffold_graph_viewer/export_fixture_payload.py cylinder_two_seam
python dev/tools/scaffold_graph_viewer/export_fixture_payload.py extruded_cross
```

Outputs go to:

```text
dev/tools/scaffold_graph_viewer/reports/
```

## Export From Blender

Preferred path:

```text
View3D > Sidebar > Scaffold > Scaffold Graph > SCAFFOLD JSON
```

The button opens a save dialog and writes the active mesh / selected faces as
`scaffold_graph_viewer_payload_v1`.

Fallback from Blender Text Editor or with `blender --python`:

```python
exec(open(r"E:\GITHUB\SCAFFOLD\dev\tools\scaffold_graph_viewer\export_selected_graph.py").read())
```

The script reads the active mesh through the normal Scaffold Blender IO
boundary, runs Pass 0 / Pass 1, and writes a viewer payload under:

```text
dev/tools/scaffold_graph_viewer/reports/
```

Selection behavior matches Scaffold read semantics:

```text
- Edit Mode selected faces: export selected faces.
- Object Mode active mesh: export all faces when no face selection exists.
```

## Visual Model

The viewer distinguishes canonical graph facts from display-only aliases:

```text
canonical_id: ScaffoldNode / RunEndpointJunction id from the payload
visual_id: canvas-only id used when a loop or coincident endpoint needs an alias
```

Alias nodes are presentation only. They never mean new Scaffold Core identity.

Layer meaning:

| Layer | Meaning |
| --- | --- |
| ScaffoldEdges | Base ScaffoldGraph edges over final PatchChains. |
| RunEndpointJunctions | Directional-run endpoint atoms inside final PatchChains. |
| DirectionFamilies | ConnectedDirectionFamily membership on directional evidence members. |
| Traces | ScaffoldTrace ordered member edges. |
| Rails | ScaffoldRail direction-stability view; ambiguous rails stay marked. |
| Ambiguities | Branch, loop, and occurrence diagnostics. |

## Guard Rails

```text
- No viewer-side rail construction.
- No viewer-side branch choice.
- No viewer-side loop opening except display-only aliasing.
- No UV, pins, packing, texel policy, feature grammar or solve.
- If a relation is missing from JSON, show it as missing; do not infer it.
```
