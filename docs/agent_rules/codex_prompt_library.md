# Codex Prompt Library

Copy these prompts into Codex app/CLI and replace the placeholders.

Keep prompts short. Persistent rules live in `AGENTS.md`, `docs/context_map.yaml`,
routed docs and `docs/agent_rules/codex_subagents.md`.

## Architect planning prompt

Use this in the persistent Planning / Architect chat.

```text
You are the Planning / Architect session for SCAFFOLD.

Do not implement production code.
Your job:
- maintain roadmap;
- choose next dense slices;
- break slices into Task Cards;
- ensure each Task Card is reviewable in one sitting;
- prepare Codex Orchestrator prompts;
- keep G0/current phase boundaries in mind;
- prevent scope creep;
- keep CFTUV migration behavior-first.

Default workflow:
- one long Architect chat;
- one disposable Codex Orchestrator session per Task Card;
- Codex Orchestrator spawns direct child subagents: scaffold_explorer, scaffold_worker, scaffold_reviewer;
- reviewer subagent is mandatory after every Worker diff;
- optional explorer-only run only for unresolved design questions.

Input:
- latest PR summaries / reviewer notes / test reports / user priorities.

Output:
PROJECT STATE
NEXT DENSE SLICES
TASK CARDS
RECOMMENDED NEXT TASK CARD
CODEX ORCHESTRATOR PROMPT
RISKS / BLOCKERS
```

## Codex Orchestrator Task Card prompt

Use this in one disposable Codex session for one Task Card.

```text
Read AGENTS.md and docs/context_map.yaml route: <route>.
Read docs/agent_rules/codex_subagents.md.

You are the Codex Orchestrator for this SCAFFOLD Task Card.
Execute exactly this Task Card. Do not expand scope.

TASK CARD

Name:
  <short name>

Goal:
  <one bounded capability>

Use subagents:
  - scaffold_explorer: <yes/no and exact question>
  - scaffold_worker: yes
  - scaffold_reviewer: yes

Allowed files:
  - <path>
  - <path>

Forbidden:
  - <hard no-go>
  - <hard no-go>

Acceptance:
  1. <checkable result>
  2. <checkable result>

Tests:
  - <command>

Stop if:
  - <condition requiring Architect decision>

Subagent workflow:
1. Spawn scaffold_explorer if requested.
2. If explorer reports BLOCKER, stop and summarize.
3. Spawn scaffold_worker to implement only the Task Card.
4. Spawn scaffold_reviewer to review the resulting diff using the SCAFFOLD checklist.
5. Wait for all requested results.
6. Return a consolidated response:
   - explorer summary;
   - worker summary;
   - tests run;
   - reviewer result;
   - final recommendation.

Do not start a second implementation pass if reviewer reports architecture
UNCERTAIN or BLOCKER. Return to Architect instead.
```

## Reviewer checklist-only prompt

Use this only if you need to run a standalone review outside the Orchestrator.

```text
Read AGENTS.md and docs/context_map.yaml route: codex_subagents.
Read docs/agent_rules/codex_subagents.md.

Review the current diff only.
Do not edit files.
Do not redesign unless a blocking issue requires it.
Return the SCAFFOLD reviewer checklist.

Focus on:
- phase/scope violations;
- forbidden imports;
- future-phase directory creation;
- Layer 1 identity mutation;
- PatchChain source-of-truth preservation;
- Layer 4/5 leakage;
- Feature/Runtime/UV leakage;
- hidden semantic promotion;
- missing tests;
- over-editing;
- CFTUV code copied without bridge mapping;
- docs/status sync.

Output:
REVIEW RESULT: PASS | WARNING | BLOCKER | UNCERTAIN
CHECKLIST
FINDINGS
MERGE / ESCALATE RECOMMENDATION
```

## Explorer-only architecture check

Use this when Architect cannot write a safe Task Card yet.

```text
No code.

Read AGENTS.md and docs/context_map.yaml route: <route>.
Read docs/agent_rules/codex_subagents.md.

Use scaffold_explorer only.

Question:
  <architectural question>

Output:
  EXPLORER SUMMARY
  RELEVANT FILES
  FACTS
  RISKS / STOP CONDITIONS
  OPTIONS
  RECOMMENDATION
```

## CFTUV Algorithm Card prompt

```text
No SCAFFOLD code.

Read AGENTS.md and docs/context_map.yaml route: cftuv_algorithm_card.
Read docs/migration/cftuv_bridge.md.
Read only these CFTUV reference files:
- <exact file>
- <exact file>

Use scaffold_explorer only.

Goal:
  Extract the behavior invariant for <CFTUV behavior>.

Output an Algorithm Card:
  CFTUV behavior
  Source files inspected
  Observed behavior
  Behavior invariant
  SCAFFOLD destination
  Required inputs
  Expected tests/report
  What NOT to copy
  Open questions
```

## Bug fix / regression prompt

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

Use scaffold_worker for the smallest patch only.
Use scaffold_reviewer to check the resulting diff.

Do not refactor.
Do not rename.
Do not reformat unrelated code.
```

## Tests-only Task Card

```text
Read AGENTS.md and docs/context_map.yaml route: testing.
Read docs/agent_rules/codex_subagents.md.

TASK CARD

Name:
  <tests-only behavior>

Goal:
  Lock down <behavior> with tests only.

Use subagents:
  - scaffold_explorer: optional, locate existing tests/fixtures
  - scaffold_worker: yes
  - scaffold_reviewer: yes

Allowed files:
  - scaffold_core/tests/**
  - fixture files only if needed

Forbidden:
  - production code changes
  - docs changes unless route missing

Acceptance:
  1. Tests express the intended behavior.
  2. No production code changed.

Final:
  EXPLORER SUMMARY
  WORKER SUMMARY
  TESTS RUN
  REVIEW RESULT
  FINAL RECOMMENDATION
```

## Inspection/report Task Card

```text
Read AGENTS.md and docs/context_map.yaml route: <route>.
Read docs/agent_rules/codex_subagents.md.

TASK CARD

Name:
  Add compact inspection/report output for <entity>

Goal:
  Make <entity> visible in compact or full inspection reports without adding new semantics.

Use subagents:
  - scaffold_explorer: inspect existing report style
  - scaffold_worker: yes
  - scaffold_reviewer: yes

Forbidden:
  - no new core semantics;
  - no Blender dependency;
  - no future-layer concepts;
  - no large dumps.

Acceptance:
  1. Report includes compact agent-readable fields.
  2. Tests cover report output.
  3. No Layer 4/5 leakage.
```

## Blender smoke validation prompt

```text
Read AGENTS.md and docs/context_map.yaml route: blender_regression.
Read docs/agent_rules/codex_subagents.md.

Validation task:
  <fixture/operator/check>

Use subagents:
  - scaffold_explorer: locate validation scripts and fixture expectations
  - scaffold_worker: only if validation script changes are explicitly needed
  - scaffold_reviewer: yes if files changed

Rules:
  - do not duplicate Scaffold Core logic in Blender scripts;
  - produce compact JSON/text report and optional screenshots;
  - do not dump full mesh data into chat;
  - do not write UV outside the G5 uv_transfer boundary.

Final:
  COMMANDS
  REPORT SUMMARY
  ARTIFACTS
  REVIEW RESULT if diff exists
```

## Docs/routing Task Card

```text
Read AGENTS.md and docs/context_map.yaml route: codex_workflow.
Read docs/agent_rules/codex_subagents.md.

TASK CARD

Name:
  <docs/routing update>

Goal:
  <one docs/routing capability>

Use subagents:
  - scaffold_explorer: locate stale docs/routes
  - scaffold_worker: yes
  - scaffold_reviewer: yes

Allowed files:
  - docs/**
  - AGENTS.md if explicitly needed
  - docs/context_map.yaml if explicitly needed

Forbidden:
  - core code changes
  - G0.md edits unless explicitly approved

Acceptance:
  1. Docs/routing are internally consistent.
  2. No production code changed.
```
