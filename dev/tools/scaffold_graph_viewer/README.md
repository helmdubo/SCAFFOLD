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

## Export To networkx (node-link JSON)

`export_networkx_graph.py` exports the ScaffoldGraph of a synthetic fixture as
a networkx-compatible node-link JSON payload (`scaffold_graph_node_link_v1`):

```powershell
python dev/tools/scaffold_graph_viewer/export_networkx_graph.py cylinder_one_seam
python dev/tools/scaffold_graph_viewer/export_networkx_graph.py extruded_cross --draw
```

`--draw` also renders a PNG next to the JSON (requires optional
`pip install networkx matplotlib`). Node color encodes ScaffoldJunction kind,
edge color encodes continuity component id, node positions use measured
Layer 2 geometry projected onto the two widest axes.

The JSON loads directly in any networkx session:

```python
import json, networkx as nx
data = json.load(open("dev/tools/scaffold_graph_viewer/reports/cylinder_one_seam.nxgraph.json"))
graph = nx.node_link_graph(data, edges="links")  # undirected multigraph
```

The same payload is embedded in `inspect_pipeline_context(context, detail="full")`
output under the `scaffold_graph_node_link` key, so Blender-side JSON exports
carry it too.

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

The default **PatchChain-use topology** view is the QA view for shape reading.
It keeps every PatchChain use separate, expands each loop-use into one visible
ring from ordered trace members or directional evidence, and draws non-loop
PatchChains as patch-local bridges. Shared boundary chains are rendered as
links between uses; they never merge cap and tube PatchChains into one display
node. For example, a capped cylinder with one tube seam should show the tube
rim uses, the cap perimeter uses, patch-local seam bridge uses, and shared-chain
links between cap and tube uses.

`Physics relax loop groups` is an optional layout aid for larger topologies. It
keeps each PatchChain-use loop rigid as a ring, then applies a small force
layout to the loop centers: patch bridges and shared-chain links act like
springs and unrelated groups repel. It is display-only and does not change
Scaffold identities or relations.

Use **Raw evidence** when you need to inspect every exported relation edge
directly. It is intentionally noisier because it overlays ScaffoldEdges,
RunEndpointJunctions, DirectionFamilies, Traces and Rails.

The viewer distinguishes canonical graph facts from display-only aliases:

```text
canonical_id: ScaffoldNode / RunEndpointJunction id from the payload
visual_id: canvas-only id used when a loop or coincident endpoint needs an alias
```

Alias nodes are presentation only. They never mean new Scaffold Core identity.
PatchChain-use loop groups are presentation only too; click a loop, bridge or
shared-chain link to inspect its backing `chain_id`, `patch_chain_id` and
`scaffold_edge_id`.

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
