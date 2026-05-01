# CFTUV Lessons for SCAFFOLD

CFTUV proved user value and algorithms. SCAFFOLD preserves that value while
reducing the architectural cost of extension.

Migration is by discovered invariants, not by classes, roles, or solve branches.

## Transfer table

| CFTUV idea | SCAFFOLD destination | Status |
|---|---|---|
| Chain-first strongest-frontier | Layer 5 runtime frontier | Planned (G5) |
| Structured `FrontierRank` | Layer 5 runtime rank object | Planned (G5) |
| `FrameRole.STRAIGHTEN` | RuntimePlacementAuthority owned by constraints | Planned (G5) |
| `BandSpineData` | G4 BandFeatureCandidate + G5 BandSpineParametrization | Planned (G4/G5) |
| `PatchShapeClass` | G4 FeatureCandidate model | Planned (G4) |
| Sawtooth FREE-to-axis promotion | Directional geometry evidence / relation evidence | Partial in G2/G3 direction refinement |
| Pin policy extraction | G5 PinPolicyResolver | Planned (G5) |
| P7 skeleton solve | Late G5 axis-family skeleton solve | Planned (G5) |
| `ChainUse` | `PatchChain` + directional evidence / future graph-use view | Implemented/partial in G1/G3 |

## Anti-transfer table

Do not transfer these CFTUV concepts directly into SCAFFOLD:

| CFTUV pattern | SCAFFOLD policy |
|---|---|
| `WALL` / `FLOOR` / `SLOPE` as topology facts | Forbidden in Layer 1/2/3 primary contracts |
| `H_FRAME` / `V_FRAME` / `FREE` as core chain roles | Replaced by direction evidence and later runtime frame decisions |
| `STRAIGHTEN` as analysis role | Replaced by late RuntimePlacementAuthority |
| Shape class as final decision | Replaced by FeatureCandidate -> FeatureInstance resolution |
| Stitching rules hidden inside solve code | Replaced by explicit FeatureConstraint records |
| Patch-first solve order | Replaced by chain-first frontier in G5 |
| Runtime mutating analysis results | Forbidden by frozen lower-layer snapshots |
| Direct CFTUV source copy | Replaced by bridge: behavior invariant -> SCAFFOLD artifact |

## Core migration rule

Each transfer must pass through this path:

```text
CFTUV heuristic / behavior
  -> behavior invariant
  -> SCAFFOLD layer owner
  -> evidence / candidate / constraint / runtime artifact
  -> tests or compact report
  -> implementation
```

Never transfer a CFTUV class name as a SCAFFOLD architecture decision just because
it worked in CFTUV.

## Layer destinations

Use this destination map:

| Behavior kind | SCAFFOLD destination |
|---|---|
| measured geometry | G2 raw facts |
| derived structural relation | G3 relation evidence |
| shape possibility | G4 FeatureCandidate |
| accepted shape interpretation | G4 FeatureInstance |
| solve requirement | G4 FeatureConstraint |
| placement behavior | G5 runtime artifact |
| UV write-back | G5 `uv_transfer` boundary |
| visual/manual validation | Blender inspection / report layer |

## Practical examples

### BAND

Do not transfer `PatchShapeClass.BAND` as a final label.

Transfer:

```text
opposite rails + caps + stable station domain
  -> BandFeatureCandidate
  -> FeatureConstraints
  -> BandSpineParametrization runtime artifact
```

### STRAIGHTEN

Do not transfer `FrameRole.STRAIGHTEN` into G1/G2/G3.

Transfer:

```text
this chain has enough authority to become straight in runtime placement
  -> RuntimePlacementAuthority owned by constraints
```

### Sawtooth

Do not promote FREE chains to H/V in analysis.

Transfer:

```text
polyline has strong chord/PCA direction despite local sawtooth turns
  -> directional geometry evidence
  -> relation confidence / future feature evidence
```
