# Codex Workflow

Use this document when a task is intended for Codex Chat or another AI coding agent.

The goal is speed without losing Scaffold's layer boundaries. Prefer dense,
bounded work slices over tiny manual steps for approved greenfield work. Prefer
minimal patches for bug fixes and regressions.

## Default two-chat workflow

Use two chats for most work:

```text
1. Main Planning / Architect chat
   Long-running project headquarters.
   Chooses dense slices, controls scope, prepares Codex prompts, interprets results.

2. Codex Work chat
   One chat per dense slice.
   May combine inspect -> plan -> implement -> tests -> inspection summary.
```

Use extra chats only when needed:

```text
Optional Reviewer chat:
  Only for high-risk diffs, architecture changes, G0/DD changes, new layers,
  ScaffoldGraph/Feature/Runtime work, or when the user is unsure.

Optional Scout chat:
  Only for unresolved design questions, DD/OQ conflicts, or CFTUV algorithm
  analysis that should be separated from implementation.

Optional Blender Validation chat:
  Only for milestone visual checks or failures that compact reports cannot explain.
```

Do not create a separate chat for every subtask such as Model, Builder, Tests,
Inspection and Docs. Those are usually one Codex Work dense slice.

## Session modes

These modes describe responsibilities. They do not always require separate chats.

### Planning / Architect

Long-running project planning. Do not implement production code.

Owns:

- roadmap and milestone discussion;
- dense-slice selection;
- scope control;
- deciding whether Scout or Reviewer is needed;
- preparing prompts for Codex Work chats;
- interpreting tests, reports and Blender checks.

### Codex Work

Default implementation chat for one dense slice.

A Codex Work chat may combine:

```text
Scout-lite -> implementation -> tests -> compact inspection/report -> summary
```

Use this combined mode when the slice contract is already clear and no DD/G0
blocker is expected.

### Scout

Read and report. Do not edit files.

Use a separate Scout only for:

- architecture uncertainty;
- design-decision conflicts;
- CFTUV algorithm analysis;
- deciding whether a task needs a new DD/OQ;
- locating relevant files before a risky implementation slice.

Scout output:

```text
CURRENT CONTRACT
RELEVANT FILES
RISKS / STOP CONDITIONS
OPTIONS
RECOMMENDATION
NEXT SLICE
```

### Reviewer

Review a diff only. Do not redesign unless a blocking issue requires it.

Use a separate Reviewer only for high-risk changes. Ordinary dense slices may use
Codex Work self-check plus tests.

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

Usually part of Codex Work.

Own architecture gates, pure Python tests, compact pipeline reports and Blender
smoke reports.

Do not mix validation scripts with Scaffold Core logic.

### Docs / Routing

Usually part of Codex Work when docs/routing are part of the dense slice.

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
ScaffoldNode v0 docs/status sync:
  update G3 docs + handoff + AGENTS status + DD note, no implementation code.
```

Good implementation slice:

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

Use dense slices for explicitly approved greenfield capabilities or docs/status
sync work.

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

One Codex Work session may complete the whole stack when the contract is clear.

Use a separate Scout only when the contract is unclear.

Use a separate Reviewer only when the diff is high-risk.

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

## Codex Work prompt shape

```text
Read AGENTS.md and docs/context_map.yaml route: <route>.

Dense slice:
  <name>

Mode:
  Single Codex Work chat.

Steps:
  1. Inspect relevant files and produce a short plan.
  2. If no blocker, implement the slice.
  3. Run targeted tests.
  4. Report architecture risks and follow-up needs.

Allowed:
  <files/dirs>

Forbidden:
  <hard forbidden concepts>

Stop if:
  <stop conditions>

Final:
  PATCH SUMMARY
  TESTS RUN
  ARCHITECTURE CHECK
  RISKS / FOLLOW-UP
```

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
