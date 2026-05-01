# Codex Prompt Library

Copy these prompts into Codex Chat and replace the placeholders.

Keep prompts short. Persistent rules live in `AGENTS.md`, `docs/context_map.yaml`,
and the routed docs.

## Dense slice implementation

```text
Read AGENTS.md and docs/context_map.yaml route: <route>.

Dense slice:
  <name>

Goal:
  <one capability>

Allowed:
  <current phase dirs or explicit files>

Forbidden:
  <hard forbidden concepts>

Stop if:
  - you need a G0 amendment;
  - you need future-phase directories;
  - you need Layer 4/5 during G3;
  - you need to mutate PatchChain identity;
  - you need hidden semantic promotion;
  - you need to copy CFTUV solve code directly.

Deliver:
  - implementation;
  - tests;
  - inspection/report update if relevant.

Final:
  PATCH SUMMARY
  TESTS RUN
  ARCHITECTURE CHECK
  RISKS / FOLLOW-UP
```

## Scout / no-code architecture check

```text
No code.

Read AGENTS.md and docs/context_map.yaml route: <route>.

Question:
  <architectural question>

Output:
  CURRENT CONTRACT
  RELEVANT FILES
  RISKS / STOP CONDITIONS
  OPTIONS
  RECOMMENDATION
  NEXT SLICE
```

## Diff review

```text
Review the last diff only.

Read AGENTS.md and docs/context_map.yaml route: <route>.

Findings first.
Focus only on:
- phase/scope violations;
- forbidden imports;
- future-phase directory creation;
- Layer 4/5 leakage;
- PatchChain identity mutation;
- hidden semantic promotion;
- missing tests;
- over-editing;
- CFTUV code copied without bridge mapping.

Do not propose broad redesign unless required by a blocking issue.
```

## Bug fix / regression

```text
Read AGENTS.md and docs/context_map.yaml route: bug_fix.
Follow docs/agent_rules/minimal_patch_protocol.md.

Bug:
  <symptom>

Expected:
  <expected behavior>

Observed:
  <actual behavior>

Before editing:
  identify exact file/function/line range, root cause, minimal patch strategy.

Do not refactor.
Do not rename.
Do not reformat unrelated code.
```

## Tests-only task

```text
Read AGENTS.md and docs/context_map.yaml route: testing.

Tests-only task:
  <behavior to lock down>

Allowed:
  scaffold_core/tests/**
  fixture files only if needed

Forbidden:
  production code changes
  docs changes unless route missing

Final:
  TESTS ADDED
  EXPECTED FAILURE OR PASS STATE
  NOTES
```

## Inspection/report task

```text
Read AGENTS.md and docs/context_map.yaml route: <route>.

Goal:
  Add compact inspection/report output for <entity>.

Rules:
  - no new core semantics;
  - no Blender dependency;
  - no future-layer concepts;
  - report should be compact and agent-readable.

Final:
  CHANGED FILES
  REPORT FIELDS
  TESTS RUN
  RISKS
```

## Blender smoke validation

```text
Read AGENTS.md and docs/context_map.yaml route: blender_regression.

Validation task:
  <fixture/operator/check>

Rules:
  - do not duplicate Scaffold Core logic in Blender scripts;
  - produce compact JSON/text report and optional screenshots;
  - do not dump full mesh data into chat;
  - do not write UV outside the G5 uv_transfer boundary.

Final:
  COMMANDS
  REPORT SUMMARY
  ARTIFACTS
  FAILURES
```

## CFTUV algorithm scout

```text
No SCAFFOLD code.

Read AGENTS.md and docs/context_map.yaml route: cftuv_algorithm_scout.
Read only these CFTUV reference files:
- <exact file>
- <exact file>

Goal:
  Extract the behavior invariant for <CFTUV behavior>.

Output an Algorithm Card:
  CFTUV behavior
  Source files inspected
  Behavior invariant
  SCAFFOLD layer destination
  Required evidence/candidate/constraint/runtime artifact
  Test or compact report expectation
  What NOT to copy
```

## Implement from CFTUV Algorithm Card

```text
Read AGENTS.md and docs/context_map.yaml route: <route>.
Read the provided Algorithm Card.
Do not read CFTUV source unless explicitly allowed.

Dense slice:
  <name>

Goal:
  Implement the SCAFFOLD-side version of the invariant using SCAFFOLD layer contracts.

Forbidden:
  - direct CFTUV code copy;
  - CFTUV class/role names as SCAFFOLD architecture;
  - hidden runtime promotion;
  - future-phase concepts outside current phase.

Final:
  PATCH SUMMARY
  TESTS RUN
  ARCHITECTURE CHECK
  RISKS / FOLLOW-UP
```

## Docs/routing update

```text
Read AGENTS.md and docs/context_map.yaml.

Docs/routing task:
  <new doc/route/policy>

Allowed:
  docs/**
  AGENTS.md if explicitly needed

Forbidden:
  core code changes
  G0.md edits unless explicitly approved

Final:
  DOCS CHANGED
  ROUTES ADDED
  RISKS
```
