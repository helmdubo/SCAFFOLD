# CFTUV Parity Fixtures

Use CFTUV as a production oracle for SCAFFOLD behavior.

Parity is staged. A fixture may pass G3 structural expectations before G4 feature
recognition or G5 UV runtime exists.

## Fixture stages

| Stage | Expected output |
|---|---|
| G3 | topology/geometry/relation/scaffold graph report |
| G4 | feature candidates, suppressed candidates, feature constraints |
| G5 | UV validity, placement metrics, runtime validation |
| Blender | screenshots / overlay / user visual acceptance |

## Suggested fixture set

| ID | Name | Why it matters | G3 expectation | G4 expectation | G5 expectation |
|---|---|---|---|---|---|
| 01 | simple_rect_wall | Basic rectangular panel | four-side signature | RectPanelCandidate | valid analytic rectangle UV |
| 02 | rect_floor_up_ambiguous | Tests non-wall orientation ambiguity | local axes without H/V leak | RectPanelCandidate with frame ambiguity | user/world hint resolves frame |
| 03 | simple_band_4_chain | Minimal BAND | two rails + two caps | BandCandidate | straight rail UV / trim strip |
| 04 | band_trim_sheet_killer | CFTUV killer feature | stable rail/cap evidence | high-confidence BandCandidate | trim sheet placement parity |
| 05 | band_split_cap | Split cap / non-trivial boundary | trace/cap evidence retained | BandCandidate with split-cap evidence | station mapping survives |
| 06 | sawtooth_free_chain | Decorated chain direction recovery | sawtooth directional evidence | usable feature evidence | stable straightened placement |
| 07 | seam_self_ring | Closed tube/ring seam-self | SEAM_SELF relations, circuit evidence | cable/band candidate later | valid seam-side UV |
| 08 | beveled_arch_strip | Bevel vs band ambiguity | narrow strip trace + adjacency | candidate confidence / rejection reasons | no false destructive unwrap |
| 09 | hole_window_panel | Panel with opening | inner/outer loop reporting | future hole policy | controlled fallback or unsupported report |
| 10 | nonmanifold_warning | Bad production input | diagnostics, no false relation | no candidate or degraded candidate | no unsafe UV write |
| 11 | incomplete_user_seam | User seam not enough | explicit unresolved structure | candidate blocked with reason | user-facing report |
| 12 | prod_case_A | Real production case | expected structural report | expected candidate set | visual parity target |
| 13 | prod_case_B | Real production case | expected structural report | expected candidate set | visual parity target |

## File layout

Suggested layout for future fixtures:

```text
tests/fixtures/cftuv_parity/
  03_simple_band_4_chain/
    notes.md
    fixture.blend
    cftuv_oracle_report.json
    scaffold_expected_G3.json
    scaffold_expected_G4.json
    scaffold_expected_G5.json
    screenshots/
```

Do not add large production meshes directly unless they are intentionally selected
as parity fixtures.

## Compact report policy

Agents should compare compact reports, not full mesh dumps.

Good report fields:

```text
patch_count
patch_chain_count
endpoint_relation_count
loop_corner_count
scaffold_node_count
feature_candidate_count
accepted_feature_count
uv_flip_count
overlap_area
warnings
summary_hash
```

Avoid dumping:

```text
all vertex coordinates
all face indices
full UV arrays
large Blender console logs
```

## Priority order

Start with:

1. `simple_rect_wall`
2. `simple_band_4_chain`
3. `band_trim_sheet_killer`
4. `sawtooth_free_chain`
5. `seam_self_ring`

These provide the fastest signal for CFTUV parity without requiring the full
future feature set.
