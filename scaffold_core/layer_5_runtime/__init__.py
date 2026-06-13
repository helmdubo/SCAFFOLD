"""
Layer: 5 - Runtime

Rules:
- Consume Layers 0-3 snapshots read-only; never mutate them.
- No stored H/V, WALL/FLOOR/SLOPE or world-axis roles; axis roles are
  recomputed per run from ConnectedDirectionFamily data.
- bpy is allowed only in uv_transfer (the G5 write boundary).
- Degrade with diagnostics; never silently distort.
"""
