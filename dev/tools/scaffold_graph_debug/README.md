# Scaffold Structure Debugger (Blender add-on)

Development-only Blender add-on: a Grease Pencil overlay that shows what the
Scaffold pipeline decided about a mesh, plus the temporary G5a UV write button.

It draws pipeline records only. One rebuild runs Pass 0, Pass 1, Pass 2 (with
the panel's Straighten Strips option) and the Layer 5 skeleton solve
(`build_islands`, `build_island_skeletons`, pins) once, then draws every layer.
The add-on computes display offsets and marker shapes and nothing else; it
assigns no roles and recomputes no stitch, line or strip decision.

Split:

```text
overlay_v2.py   pure Python payload builder (no bpy), tested headless
overlay_ladders.py  its Ladders and Bevels layers and their report lines
draw_v2.py      thin bpy drawing: one GP layer per payload layer
debug.py        Grease Pencil / text-label primitives (legacy GPENCIL and GP v3)
rail_offsets.py per-use display offset (inward + lift along the patch normal)
session.py      Analyze / Rebuild / close, report Text datablock
operators.py    panel, settings, operators
```

## Register From Blender

In Blender Python Console:

```python
import sys
sys.path.insert(0, r"<repo>\dev\tools")
import scaffold_graph_debug
scaffold_graph_debug.register()
```

Then use `View3D > Sidebar > Scaffold > Scaffold Graph`.

Works with legacy Grease Pencil (Blender 4.1 / 4.2) and Grease Pencil v3
(Blender 4.3+).

## Panel

```text
Analyze             toggle: build the overlay and hide the mesh / remove it and restore the mesh
Rebuild             rerun the pipeline and redraw every layer
Straighten Strips   Pass 2 option; applies on the next Rebuild (and on Write UV)
Straighten Bevel Strips
                    Pass 2 option, on by default: every bevel strip marked by Face
                    Strength is laid from its ladder as a straight island of its own
                    (STRAIGHT_LADDER); applies on the next Rebuild (and on Write UV)
Structure / Skeleton / Patches: sides and types / Layer 3 (detail) / Ladders / Bevels
                    collapsible groups, one eye toggle per layer, legend underneath
Write UV (G5a)      unchanged
SCAFFOLD JSON       unchanged
```

The eye toggles only show or hide Grease Pencil layers, so they act at once
and never rebuild. If the analysed mesh is deleted or renamed, Analyze still
ends the session (removing its overlay and labels) and Rebuild works on the
active mesh. Unregistering the add-on ends every session and shows the source
meshes again. A rebuild touches only its own object's overlay (exact names).

`Line thickness` (slider under Straighten Strips) is a multiplier for every
stroke of the overlay: 1.0 = as built, 2.0 = twice as thick. It acts at once
through a live layer property, never rebuilds, and is re-applied after each
Rebuild. Fill layers (Patches, Islands, Types) are not touched. Per layer:

- Grease Pencil v3 (Blender 4.3+): strokes are world-space radii (width x
  0.00075, times max(1, median edge length / 0.2) on large meshes). The layer's
  `radius_offset` is added to every point radius, so it is set to
  `(multiplier - 1) x` the radius of the layer's thinnest stroke. That stroke
  becomes exactly `multiplier` times as thick; thicker strokes in the same layer
  (Chains with an axis role) grow by the same amount.
- Legacy Grease Pencil (Blender 4.1 / 4.2): strokes are screen-space pixels.
  The layer's `line_change` (pixels) is added to every line width, so it is set
  to `round((multiplier - 1) x` the layer's thinnest width`)`, never below 1 px.

In GP v3 a stroke keeps its world thickness when you zoom out, so at
whole-building zoom raise the slider (3 to 5 makes chains and lines clearly
visible); in legacy GP 1.0 is usually right. Changing Straighten Strips does not rebuild by itself:
press Rebuild.

After each rebuild a compact report is printed to the system console and
written to the Text datablock `Scaffold_Debug_Report__<object>`: per island its
id, frame kind, patch count, number of lines and pins; stitch decisions counted
by reason; patch types; ladder patches (of them closed, with two readings);
faces by source face mark when the mesh has Blender's Face Strength
attribute; when there are bevel records, bevel strips by source (mark or
structure) with the unresolved ones and their corner kinds (convex /
concave / mixed / undefined), bevel junctions by source and bevel-marked
patches that are not isolated, by reason; when there are STRAIGHT_LADDER
constraints or marked bevel strips that got none, the bevel strips laid from
their ladder (islands of frame LADDER of the constraints) and each strip not
laid with its reason; the number of chain strokes without an axis role; the number of
solver diagnostics.

## Layers

Group Structure:

| Toggle | GP layer | Draws |
| --- | --- | --- |
| Patches | `Scaffold_Patches` | fill of each patch (its source faces), one colour per patch |
| Boundary | `Scaffold_Loops_Boundary` | OUTER loops, near-white |
| Holes | `Scaffold_Loops_Holes` | INNER (and DEGRADED) loops, blue |
| Chains | `Scaffold_Chains` | every PatchChain use, one stroke per directional run, coloured by the axis role Layer 5 gave that run |
| Labels | collection `Scaffold_Debug_Labels__<object>` | `P<patch>C<position in loop>` (`L<loop>` when the patch has several loops), created only while the toggle is on |

Group Skeleton:

| Toggle | GP layer | Draws |
| --- | --- | --- |
| Islands: rigid frame / frame-free / strip / bevel strip | `Scaffold_Islands_UNFOLDED`, `_FRAME_FREE`, `_STRIP`, `_LADDER` | fill of every patch of an island, one colour per island, layer by the island's frame kind (bevel strip: a marked bevel strip laid from its ladder, frame LADDER) |
| Lines | `Scaffold_Skeleton_Lines` | each island line (`line_by_run`): all its runs in one colour |
| Nodes | `Scaffold_Skeleton_Nodes` | white 3D cross at every skeleton node |
| Pins | `Scaffold_Pins` | small orange 3D cross at every pinned vertex occurrence of the solve |
| Seams | `Scaffold_Seams` | every Layer 5 stitch decision along its chain: green dashed = stitched, red solid = cut |

Group Patches: sides and types:

| Toggle | GP layer | Draws |
| --- | --- | --- |
| Sides | `Scaffold_Patch_Sides` | one stroke per `PatchChainShapeRelation` piece: mint = surface line, blue = surface curve, orange = unresolved |
| Corners | `Scaffold_Patch_Corners` | `RunCornerRelation` RIGHT and OTHER: green = right convex, magenta = right reflex, orange = other; STRAIGHT is not drawn. `RunBridgedCornerRelation` (a right corner turned over one bridge run): blue cross at the bridge run's midpoint |
| Types: strip / strip (option off) / rectangle / four-sided / other | `Scaffold_Types_*` | patch fill by the Layer 4 verdict: strip = accepted strip (straightened) or suppressed "laid from its bevel ladder" (a strip the bevel ladder lays instead); suppressed "option off" (a strip the option would straighten); suppressed "already a rectangle"; four-sided = suppressed "long sides are straight on the surface"; no candidate |

Layer 4 grades the shape before it reads the option, so Rectangle, Four-sided
and Other are the same with Straighten Strips on or off; only the strips the
option would straighten move between Strip (option on) and Strip (option off).

Group Layer 3 (detail), collapsed by default:

| Toggle | GP layer | Draws |
| --- | --- | --- |
| Family Colors | `Scaffold_L3_Families` | each run in the colour of its ConnectedDirectionFamily (grey without one) |
| Junctions | `Scaffold_L3_Junctions` | ScaffoldNode as a 3D `+`, RunEndpointJunction as a 3D `*`; yellow when more than two run ends meet |

Group Ladders, collapsed by default (Layer 3 `PatchQuadLadderRelation`: for
a bevel strip the reading Layer 4 chose, for every other ladder patch the
first reading; a patch may have a second reading, counted in the report).
Where a patch that is not a bevel strip has two readings with the same
column count, the first one, and so the one drawn, is decided by ids
(face and edge order) and means nothing:

| Toggle | GP layer | Draws |
| --- | --- | --- |
| Ladder rails | `Scaffold_Ladder_Rails` | rail A pink, rail B lime, beside their edges on the patch's own faces like Chains |
| Ladder ends | `Scaffold_Ladder_Ends` | the two end profile lines of an open ladder, violet; a closed ring has none |
| Ladder columns | `Scaffold_Ladder_Columns` | thin grey profile lines between consecutive columns, on the surface at the Chains' lift |
| Source face mark | `Scaffold_Source_Face_Strength` | fill by the raw Blender Face Strength of each face (Layer 0): red = weak, blue = medium, grey = strong; unmarked faces and meshes without the attribute draw nothing |

Group Bevels, collapsed by default (Layer 4 `BevelInstance`, by the Face
Strength mark where a patch has one, else by the strict structural rule):

| Toggle | GP layer | Draws |
| --- | --- | --- |
| Bevel strip | `Scaffold_Bevel_Strip` | fill of each accepted bevel strip set by the mark, orange (also those whose ladder direction is unresolved) |
| Bevel junction | `Scaffold_Bevel_Junction` | fill of each accepted bevel junction set by the mark, purple |
| Bevel strip (by structure) | `Scaffold_Bevel_Strip_Structure` | fill of each bevel strip found by mesh structure, light orange: a candidate, not confirmed by a mark |
| Bevel junction (by structure) | `Scaffold_Bevel_Junction_Structure` | fill of each bevel junction found by mesh structure, light purple: a candidate, not confirmed by a mark |
| Bevel, not isolated | `Scaffold_Bevel_Not_Isolated` | fill of each SUPPRESSED bevel record, red: a patch with bevel-marked faces mixed with strong or unmarked faces, or with strip and junction faces in one patch; seams are missing there |

Defaults: Patches, Boundary, Holes, Chains, Lines, Nodes and Seams are on;
everything else is off. Island fills compete with Patches; turning an Islands
layer on does not hide Patches, so turn Patches off yourself if needed.

### What the two chain colours mean

Yellow and cyan are the two axes of one island (Layer 5 `AXIS_A` and `AXIS_B`):
runs of the same colour in one island are laid along the same UV axis. The
colours have no world meaning, and there is no relation between islands:
yellow in one island and yellow in another island are unrelated. Grey runs
are `OBLIQUE` or have no role.

### Positions

Every PatchChain use is drawn as its own copy, on its own side of the edge.
The side comes from the winding rule (G0 DD-51: a use walks its loop the way
its patch's faces wind): for a use edge a -> b the owning face is the patch
face whose vertex cycle contains a -> b in that order, and the inward
direction is `normalize(cross(face normal, b - a))`, left of the edge for that
face's own winding (for an n-gon of 5+ vertices the patch's Layer 2 face-fan
normals at a and b replace the face normal). This holds for concave and
non-planar faces and puts the two uses of a SEAM_SELF chain on their two faces
without any flip. An edge that no patch face walks a -> b falls back to the
old rule (towards the centroid of the single patch face holding it) and is
counted in the report line `edges with fallback side`; none occur on the test
captures.

Each stroke point moves inward by `RAIL_OFFSET_FACTOR` (0.012) x the stroke's
average edge length and is lifted along the owning face normal. Lifts are
multiples of the marker unit, the mesh's median edge length, so the stack
order holds on every mesh size:

```text
Patches 0 (on the surface) < Loops 0.014 < Chains / Sides 0.016 < Seams 0.018
< Lines 0.022 < Labels 0.025   (x median edge length)
```

Loops lift along the patch's face-fan normal at each vertex; seams along the
mean of both patches' fan normals. Marker half-sizes are also multiples of the
marker unit (nodes 0.12, corners 0.08, pins 0.07, junctions 0.1 to 0.19).

An island that has no skeleton or an unknown frame kind is not drawn in any
Islands layer; the report names it.

GP materials are shared between the overlays of several objects, so every
material name carries the colour it holds (as RGBA hex): drawing a second
object never recolours the first.

## Headless checkpoint

```text
blender -b scene.blend --python dev/tools/scaffold_graph_debug/write_debug_scene.py -- \
    --objects Arc,collumn --straighten Arc --out debug.blend \
    [--render-dir pngs --render Arc,collumn] [--sets bevels_ladders,face_mark]
```

Builds the overlay for the named objects with the panel's default layer
visibility, hides each source mesh as Analyze does, prints stroke counts per
layer and the report, and saves a copy (the opened file is never written).
`--render` writes Workbench PNGs of layer sets per object: by default
patches_chains, islands_lines_seams and types; `--sets` picks others
(bevels_ladders = Bevels fills with Ladder rails, ends and columns;
face_mark = Source face mark).

## Write UV (G5a)

`Write UV (G5a)` runs the Layer 5 v0 runtime:

```text
Pass 0 / Pass 1 / Pass 2 (Straighten Strips toggle) -> build_islands -> build_island_skeletons -> run_skeleton_solve
-> uv_transfer.write_pinned_uvs
```

The button writes UV coordinates and pin flags for the skeleton only. It does
not call `bpy.ops.uv.unwrap`. In Edit Mode, selected faces define the run. In
Object Mode, selecting one mesh object means all faces of that object are
used. Then run Blender's manual command:

```text
UV Editor -> U -> Unwrap
```

Blender's unwrap respects the pins written by G5a. If the button reports
diagnostics, treat them as part of the G5a validation surface.

## SCAFFOLD JSON

`SCAFFOLD JSON` exports the active mesh / selected faces as a graph-viewer
payload (`Pass 0 / Pass 1 -> inspect_pipeline_context(detail="full")`), by
default to `dev/tools/scaffold_graph_viewer/reports/<object>.graph.json`, for
the external flat viewer `dev/tools/scaffold_graph_viewer/index.html`.

## Avoiding Stale Add-ons

The panel header shows `Build: <short git hash>[-dirty]`. After `git pull`:
turn Analyze off, unregister the add-on, restart Blender, register again and
check the Build stamp. Python bytecode cache lives under
`dev/tools/scaffold_graph_debug/__pycache__/`; delete it if Blender appears to
run stale code.

To unregister:

```python
scaffold_graph_debug.unregister()
```
