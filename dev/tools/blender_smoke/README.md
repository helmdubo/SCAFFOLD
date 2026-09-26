# Scaffold Blender Smoke (Tier 3)

Headless Blender runner for real `.blend` meshes. It exercises the real Layer 0
read boundary (`blender_io`), Pass 0/1, the G5a solve and, optionally, the G5
UV write boundary (`uv_transfer`) inside Blender 4.5. It never saves the
`.blend`.

The tool lives outside `scaffold_core/` and consumes it like the debug add-on.

## Run

From the repository root, with Blender on `$SCAFFOLD_BLENDER`, `/opt/blender/*/blender`,
`C:/Program Files/Blender Foundation/Blender */blender.exe` or `PATH`:

```bash
# token-lean regression check: prints only differences from the baseline
python dev/tools/blender_smoke/run_smoke.py path/to/buildings.blend --seamed --write-uv \
  --baseline dev/tools/blender_smoke/baselines/buildings_seamed.json

# one table row per object
python dev/tools/blender_smoke/run_smoke.py path/to/buildings.blend --objects walls.004,walls.005

# dump SourceMeshSnapshot captures for Blender-free Tier 2 tests
python dev/tools/blender_smoke/run_smoke.py path/to/buildings.blend --objects walls.004 \
  --capture-dir /tmp/captures
```

Options:

```text
--seamed            every mesh object that has at least one UV seam
--objects a,b       explicit object names
--selection file    (default) the face selection stored in the .blend, read in
                    Edit Mode like the artist; objects with no selected faces
                    are read whole in Object Mode
--selection all     every face of each object
--write-uv          write pins through uv_transfer and verify that no loop
                    outside the solved faces changed (foreign_loops_changed)
--baseline PATH     compare stable fields; exit 1 and print only the diffs
--update-baseline   rewrite PATH from this run
```

Full JSON reports go to `dev/tools/blender_smoke/reports/` (git-ignored).

## Keeping agent runs cheap

- Prefer `--baseline`: an unchanged run prints two lines.
- Blender's own stdout is captured and dropped; only `SMOKE` records are parsed.
- For iteration, dump captures once with `--capture-dir` and replay them in
  pure Python; do not relaunch Blender per experiment.
- Commit only small, representative captures to `scaffold_core/tests/data/`.

## Metrics per object

```text
faces, shells, patches, chains       Layer 0/1 scope actually read
families, family_max                 ConnectedDirectionFamily count and size
opposite_side_families               FAMILY_SPANS_OPPOSITE_PATCH_SIDES diagnostics (must be 0)
rails, rails_consumable              ScaffoldRail v0 records
islands, pinned                      G5a assembly and pinned vertices
solve_diagnostics, first_solve_...   Layer 5 degradation diagnostics
axis_violations, seam_mismatches     G5a invariants (must be 0)
residual_max / residual_ok           lstsq residual; only residual_ok is baselined
written_loops, pinned_loops          UV write summary (--write-uv)
foreign_loops_changed                loops outside the solved faces touched (must be 0)
pipeline_codes                       diagnostic code histogram
ms                                   wall time, never baselined
```

Structure metrics (plan Slice N) measure whether patch -> line -> island
agree, not the quality of a final unwrap:

```text
rigid_islands                        islands with a rigid unfolded frame
island_lines                         families split at the seams each island cuts
axis_runs, oblique_runs              runs with / without an island axis
bipartition_conflicts                frame-free axis conflicts (curved islands)
lines_not_straight                   island lines whose members disagree in the frame
patches_outside_frame                warped n-gons and patches behind a bent hinge
node_frame_mismatches                solve nodes whose occurrences sit apart in the frame (must be 0)
```

## Why not a Blender MCP add-on

Blender MCP add-ons (the Blender Lab MCP server, ahujasid/blender-mcp) open a
socket inside a running Blender with a UI event loop on the same machine as the
MCP client. Cloud agent sessions have no such Blender, and MCP responses are
verbose. Direct `blender -b --python` is the same mechanism those servers use
for their headless mode, and it matches the Tier 3 contract in
`docs/agent_rules/testing_rules.md`. For interactive local work, either MCP
add-on can still be used next to this runner.
