# Bevel test cases

Twelve small meshes bevelled by Blender's Bevel modifier (Face Strength = All),
for the quad ladder relation (`scaffold_core/layer_3_relations/quad_ladders.py`)
and the Layer 0 face strength mark.

Generator: `dev/tools/blender_smoke/build_bevel_cases.py`

```text
blender -b --factory-startup --python dev/tools/blender_smoke/build_bevel_cases.py -- scaffold_core/tests/data/bevel_cases
```

Per case:

- `<case>.capture.json`: the SourceMeshSnapshot read through
  `scaffold_core/layer_0_source/blender_io.py` and written by
  `dev/tools/scaffold_graph_debug/snapshot_io.py` (compacted), with the
  optional `face_strength` map. Seams follow the ground truth: one patch per
  bevel strip run and per junction; other faces are cut where their normals
  turn by more than 30 degrees.
- `<case>.gt.json`: ground truth from Blender's Face Strength per face,
  `[class, component, original element]`: STRIP (Medium), JUNCTION (Weak) or
  OTHER (Strong); the original element is the bevelled edge (strip) or
  vertex (junction) the face came from, -1 for other faces.

| Case | What it is |
|---|---|
| a_cube_s1, a_cube_s3 | cube, all edges, 1 and 3 segments (corner junctions) |
| b_rect_s2 | rectangular window, front rim, 2 segments, cut at the corners |
| b_ring_s1 | the same rim as one closed ring, 1 segment |
| c_arch_s2 | arch window (curved strip), 2 segments |
| d_cyl_s2 | thick tube: top rim ring and the rim of a hole through the wall |
| e_arch_s2_n20 | c_arch_s2 with vertex noise of 20% of the bevel width |
| f_rect_inarc | b_rect_s2 with inner miter Arc: junction patches at the corners |
| f_border | open L sheet: the fold strip runs to the mesh border |
| g_short | prism with one very short side: one-quad strip between junctions |
| h_rect_s2_tri | b_rect_s2, every face triangulated |
| m_rect_s2_trimain | b_rect_s2 with triangulated main surfaces, quad reveals |
| u_rounded_wall_noise_top | real mesh from the user, not generated: a rounded wall with a noisy top, bevels with Face Strength marks, strips and triangle junctions cut by seams (9 strip patches of 1 to 23 faces, 6 junctions, 5 other); ground truth is its own mark |
