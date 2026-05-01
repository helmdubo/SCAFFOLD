# Codex Workflow

Use this document when a task is intended for Codex Chat or another AI coding agent.

The goal is speed without losing Scaffold's layer boundaries. Prefer dense,
bounded work slices over tiny manual steps for approved greenfield work. Prefer
minimal patches for bug fixes and regressions.

## Session modes

### Scout

Read and report. Do not edit files.

Use Scout sessions for:

- architecture uncertainty;
- design-decision conflicts;
- CFTUV algorithm analysis;
- deciding whether a task needs a new DD/OQ;
- locating relevant files before a dense implementation slice.

Scout output:

```text
CURRENT CONTRACT
RELEVANT FILES
RISKS / STOP CONDITIONS
OPTIONS
RECOMMENDATION
NEXT SLICE
```

### Dense Slice Implementer

Implement one approved capability inside the current phase boundary.

A dense slice may touch multiple allowed files when all are required by one
capability, for example:

```text
model -> builder -> tests -> inspection -> docs/routing if needed
```

Dense slices are allowed for greenfield implementation. They are not the same as
bug-fix patches.

Dense slice output:

```text
PATCH SUMMARY
TESTS RUN
ARCHITECTURE CHECK
RISKS / FOLLOW-UP
```

### Reviewer

Review a diff only. Do not redesign unless a blocking issue requires it.

Findings first. Focus on:

- phase/scope violations;
- forbidden imports;
- future-phase directory creation;
- semantic leakage into lower layers;
- PatchChain identity mutation;
- hidden runtime/feature promotion;
- missing tests;
- over-editing;
- direct CFTUV code copying.

### Tests / Validation

Own architecture gates, pure Python tests, compact pipeline reports and Blender
smoke reports.

Do not mix validation scripts with Scaffold Core logic.

### Docs / Routing

Own agent-facing docs, context routes, migration notes and prompt libraries.

Docs/routing changes should not modify core implementation unless explicitly part
of the same dense slice.

### Blender Inspection

Use only for key milestone validation or cases that cannot be represented by pure
Python fixtures.

Blender inspection should produce compact reports or screenshots, not large mesh
dumps.

## Dense slice rules

A dense slice must have:

- one capability;
- one layer owner or one narrow pipeline path;
- explicit forbidden scope;
- stop conditions;
- tests or report output.

Good dense slice:

```text
ScaffoldNode v0:
  model + builder + tests + inspection summary inside G3.
```

Bad dense slice:

```text
Make SCAFFOLD support bands like CFTUV.
```

## Stop conditions

Stop and report instead of patching if the task requires:

- editing `G0.md` without explicit user approval;
- creating future-phase directories;
- Layer 4/5 concepts during G3;
- redefining or splitting Layer 1 `PatchChain` identity;
- adding hidden semantic role promotion;
- copying CFTUV solve code directly;
- adding UI or Blender logic to core layers;
- adding generic `utils.py`, `helpers.py`, `manager.py`, `service.py`, or `registry.py` modules.

## Minimal Patch vs Dense Slice

Use `docs/agent_rules/minimal_patch_protocol.md` for:

- bug fixes;
- regressions;
- small corrections;
- repairs to existing working behavior.

Use dense slices for explicitly approved greenfield capabilities.

Minimal Patch Protocol should not be used to artificially split one approved
greenfield capability into many manual micro-tasks.

## Commit-stack shape inside a dense slice

A dense slice may be internally organized as:

```text
1. Model
2. Builder
3. Tests
4. Inspection/report
5. Docs/routing if needed
```

One Codex Implementer session may complete the whole stack when the contract is
clear.

Use a Scout session first when the contract is not clear.

Use a separate Reviewer session after implementation.

## Prompt style

Keep Codex Chat prompts short. Persistent rules live in:

```text
AGENTS.md
docs/context_map.yaml
routed docs
```

Task prompts should state:

- route to read;
- dense slice name;
- goal;
- allowed scope;
- forbidden scope;
- stop conditions;
- required final summary.

## Final response format for dense slices

```text
PATCH SUMMARY
- changed files
- behavior added

TESTS RUN
- commands and results

ARCHITECTURE CHECK
- phase boundaries
- forbidden imports
- no future layers

RISKS / FOLLOW-UP
- known limitations
- next slice suggestion
```
