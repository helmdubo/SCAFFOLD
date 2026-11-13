# CFTUV parity scoreboard

Measures, per mesh, how much of a reference UV *structure* (made by the older
tool CFTUV) Scaffold reproduces, and where the largest gaps are. It is a dev
tool: it replays Scaffold from SourceMeshSnapshot captures without Blender and
defines no Scaffold relations of its own.

## What it measures

The common frame is Scaffold's PatchChain uses (one side of one Chain in one
Patch). Both tools cut patches by UV seams. For every use the tool builds:

- a reference description from the CFTUV UVs of that patch's own side faces:
  `AXIS_LINE` / `FREE_LINE` / `SHAPED`, U or V axis, pinned vertices, stretch;
- a Scaffold description from the G5a skeleton: `AXIS_LINE` (all runs share one
  axis role and their pinned ends lie on one line of that axis) or `NOT_LINE`,
  plus pinned vertices.

Scores per object (exact definitions and tolerances in the `parity.py`
docstring): line recall, false lines, pin coverage and extra pins, relative
axis agreement (same/different axis within a patch), patch verdicts
(structured = at least 80% of the boundary length is AXIS_LINE), and, as
information only, island counts with split/merged islands. The top gaps list
the patches with the most reference AXIS_LINE length that Scaffold misses and
the dominant reason read from Scaffold's data.

Shape agreement checks WHERE the pins are. For the corners pinned in both
descriptions, every pair's Scaffold distance (times the object scale) must
match the reference distance within max(2% of it, 1% of the group's reference
UV extent); pairwise distances ignore rotation (any angle) and translation.
At most 300 pairs per group, taken as every k-th pair (no randomness). A group
is the common pins of one patch (`shape`, `torn`) or of one Scaffold island
(`ishape`, `itorn`) that lie in one reference UV island; a patch or island the
reference cut into several islands is compared per piece. `shape` is the
pair-weighted share of agreeing pairs; `torn` is "groups below 90% / groups
scored". Fewer than 3 common pins: not scored. The island score is the one that
catches patches placed wrongly against each other inside one island; the gaps
section lists the worst torn patches and islands.

## What it does not measure

Island orientation (quarter turns are invisible to the axis score), scale
between islands, packing and overlap. Stretch is reported as information, not
scored. A strip the reference straightened and Scaffold did not shows as torn.

Arc and collumn references were made with CFTUV "Straighten Strips" on: curved
strips are laid as straight rectangles with stretch, so their stretch differs
from 1 by design. building_walls and Main_wall were made without it.
Scaffold replays each object with the same option (Pass 2
`FeatureOptions.straighten_strips`); the mapping is `STRAIGHTEN_STRIPS` in
`parity.py`, and the table prints it per object (`strips on/off`).

Main_wall's seams are mostly open slits (they do not close regions), so
Scaffold builds 2 patches there and the reference is one connected UV island
cut along those slits.

## Files

- `reference/<name>.uv.json`: reference UVs per face corner (vertex, u, v,
  pin flag), the UV layer name and the reference UV islands.
- `reference/<name>.capture.json`: the SourceMeshSnapshot of the same object
  (same face/vertex/edge indices as Blender).

## Re-extract the reference

Read-only; the scene is never saved:

    "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b reference_scene.blend \
        --python dev/tools/cftuv_parity/extract_reference.py -- \
        dev/tools/cftuv_parity/reference Arc building_walls collumn Main_wall

Captures come from `dev/tools/blender_smoke/run_smoke.py ... --capture-dir DIR`
on the same scene; copy them as `reference/<name>.capture.json`.

## Run

From the repository root:

    python dev/tools/cftuv_parity/parity.py                  # four objects + total
    python dev/tools/cftuv_parity/parity.py --object Arc --detail
    python dev/tools/cftuv_parity/parity.py --json out.json  # numbers for diffing

Tests: `python -m pytest dev/tools/cftuv_parity`.

## Look at a result

`write_scaffold_layer.py` writes Scaffold's UVs as a second UV layer
("Scaffold") into a copy of the scene. To see both layers side by side without
opening Blender's UI, dump them (read-only, the .blend is never saved) and
render PNGs with Pillow:

    "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" -b result.blend \
        --python dev/tools/cftuv_parity/dump_layers.py -- layers.json Arc building_walls collumn Main_wall
    python dev/tools/cftuv_parity/render_layers.py layers.json --out-dir png [--panel 900]

`<object>.png` shows the reference layer (`--left`, default "UVMap") and the
Scaffold layer (`--right`, default "Scaffold"); pinned corners are red. For an
object with more than 30 UV charts, `<object>.charts.png` also shows the 6
largest Scaffold charts by UV area, each fitted to its own cell.

What `ishape` and `itorn` do and do not say. They compare the pins of one
Scaffold island with the reference island that holds them. A low value has two
possible causes: pins at wrong places (the defect Slice Z fixed), or a
different but valid unfolding: Scaffold stitched patches the reference kept in
separate islands, so a part is turned against the rest. On building_walls after
Slice Z the second cause dominates: Scaffold joins walls across horizontal
ledge patches that the reference cut off, and the far wall comes out upside
down. That is a question of which patches to stitch (a future grouping
filter), not of pin positions. Pairwise distances also ignore mirroring. For
pin positions inside Scaffold's own unfolding, check pins against the island
frame instead (see `docs/phases/G5a_skeleton_runtime.md`, invariant 7).
