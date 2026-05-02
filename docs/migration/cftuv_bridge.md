# CFTUV to SCAFFOLD Bridge

This document defines how to use CFTUV as an algorithm oracle without copying its
architecture debt into SCAFFOLD.

## Core rule

CFTUV source may be studied. CFTUV implementation must not be copied directly.

A CFTUV behavior can be implemented in SCAFFOLD only after it has been expressed
as:

1. a behavior invariant;
2. a SCAFFOLD layer owner;
3. expected evidence/candidate/constraint/runtime artifacts;
4. tests or compact report fields.

## Repository locations

SCAFFOLD now keeps two different kinds of CFTUV material.

### Migration docs

Migration/process documents live in:

```text
docs/migration/
docs/reference/cftuv/
```

These are SCAFFOLD-side documents: lessons, bridge rules, fixture plans, and
reference notes. They are safe for ordinary planning/migration tasks.

### CFTUV source oracle

CFTUV source/reference code lives in:

```text
dev/tools/CFTUV/
  *.py
  docs/*.md
```

This directory is a read-only algorithm oracle. It is not part of Scaffold Core.
It must not be imported by SCAFFOLD runtime code, tests, or pipeline modules.

Read `dev/tools/CFTUV/` only when a Task Card explicitly asks for CFTUV migration
analysis or an Algorithm Card.

## CFTUV source oracle rules

- Do not import from `dev/tools/CFTUV/` in SCAFFOLD code.
- Do not run files from `dev/tools/CFTUV/` as part of SCAFFOLD tests or pipeline.
- Do not edit CFTUV reference files during SCAFFOLD implementation tasks.
- Do not read CFTUV source in ordinary SCAFFOLD tasks.
- Use `scaffold_explorer` for CFTUV source reading.
- Name exact CFTUV files to inspect whenever possible.
- Produce an Algorithm Card before any SCAFFOLD implementation.

## Bridge stages

### Stage 1 — Observe

Identify the behavior in CFTUV on a real or synthetic fixture.

Examples:

- simple 4-chain BAND to trim strip;
- split-cap BAND;
- sawtooth/decorated chain direction recovery;
- pin policy for connected constrained chains;
- skeleton solve drift correction.

### Stage 2 — Extract invariant

Describe what must remain true without using CFTUV implementation classes as the
design language.

Good:

```text
Two opposite side rails share a station domain; cap chains connect matching
stations; UV U follows station, UV V follows rail-to-rail width.
```

Bad:

```text
Port BandSpineData and STRAIGHTEN roles.
```

### Stage 3 — Map to SCAFFOLD

Choose a destination:

```text
G2 raw fact
G3 relation / evidence
G4 FeatureCandidate
G4 FeatureConstraint
G5 runtime artifact
G5 uv_transfer boundary
Blender validation/report
```

### Stage 4 — Test or report first

Before implementing the behavior, define what must be visible in tests or compact
reports.

Examples:

```text
G3 report: two rail traces, two cap traces, one loop signature.
G4 report: one BandCandidate with rail/cap evidence.
G5 report: valid UV, no flips, rail lines straight, trim span matched.
```

### Stage 5 — Port math only

Pure math may be adapted when the invariant is clear.

Do not copy:

- runtime roles;
- frontier branches;
- pin logic embedded in transfer;
- CFTUV class names as SCAFFOLD architecture;
- hidden solve exceptions.

## Algorithm Card format

A CFTUV Explorer must output this card before any SCAFFOLD implementation:

```text
ALGORITHM CARD

CFTUV behavior:
  <behavior name>

Source files inspected:
  - dev/tools/CFTUV/<file>.py
  - dev/tools/CFTUV/docs/<file>.md

Observed behavior:
  <what CFTUV does from the user's point of view>

Behavior invariant:
  <what must remain true, independent of CFTUV code structure>

SCAFFOLD destination:
  Layer: <G2/G3/G4/G5/Blender validation>
  Artifact: <evidence/candidate/constraint/runtime/report>

Required inputs:
  <existing SCAFFOLD snapshots/relations needed>

Expected tests/report:
  <how to verify behavior>

What NOT to copy:
  <CFTUV roles/classes/branches that must not become architecture>

Open questions:
  <DD/OQ needed before implementation, if any>
```

## Implementer rule

The SCAFFOLD implementer should normally read the Algorithm Card, not the CFTUV
source files.

Read CFTUV source during implementation only when explicitly allowed by the user
or Task Card.

## Mapping table

| CFTUV module/entity | SCAFFOLD destination |
|---|---|
| `PatchGraph` | Layer 1/2/3 snapshots, not one object |
| `BoundaryChain` | `Chain` + `PatchChain` |
| `ChainUse` | `PatchChainDirectionalEvidence` / future graph-use view |
| `FrameRole.H_FRAME/V_FRAME/FREE` | Not transferred to G1/G2/G3 |
| `FrameRole.STRAIGHTEN` | G5 RuntimePlacementAuthority |
| `PatchShapeClass.BAND` | G4 BandFeatureCandidate |
| `ChainRoleClass.SIDE/CAP` | G4 BandFeatureCandidate evidence |
| `structural_tokens.LoopSignature` | G3 boundary/loop signature or G4 feature input |
| `band_spine.BandSpineData` | G5 BandSpineParametrization |
| `solve_pin_policy` | G5 PinPolicyResolver |
| `solve_frontier` | G5 chain-first frontier |
| `solve_skeleton` | G5 axis-family skeleton solve |
| debug/regression snapshots | Blender compact report + screenshots |

## Parallel migration model

Use Codex subagents when possible:

```text
scaffold_explorer:
  reads selected CFTUV files from dev/tools/CFTUV/;
  outputs Algorithm Card;
  writes no SCAFFOLD code.

scaffold_worker:
  reads Algorithm Card;
  implements SCAFFOLD artifact;
  does not copy CFTUV code.

scaffold_reviewer:
  checks the diff for CFTUV code-copy leakage, layer leakage and missing tests.
```

This separation reduces accidental code copying and forces behavior-level design.
