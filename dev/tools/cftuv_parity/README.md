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

## What it does not measure

UV coordinates, island orientation (quarter turns are invisible to the axis
score), scale between islands, packing and overlap. Stretch is reported as
information, not scored.

Arc and collumn references were made with CFTUV "Straighten Strips" on: curved
strips are laid as straight rectangles with stretch, so their stretch differs
from 1 by design. building_walls and Main_wall were made without it.

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
