# Planning / Architect Workflow

Use this document for the long-running project planning chat that coordinates
SCAFFOLD work.

This mode is the project headquarters. It is not an implementation session.

## Default workflow

Use this workflow for structured SCAFFOLD work:

```text
User <-> Architect chat (persistent)
          plans slices, writes Task Cards, handles strategy and blockers

User -> Codex Orchestrator session (disposable, one Task Card)
        runs subagents internally: explorer -> worker -> reviewer

If reviewer PASS:
  merge

If reviewer WARNING / BLOCKER / UNCERTAIN:
  return to Architect
```

The important split is:

```text
Architect = persistent context and planning
Codex Orchestrator = disposable Task Card execution coordinator
Subagents = isolated Explorer / Worker / Reviewer threads inside Codex
```

Do not manually open separate Worker / Reviewer / Scout chats by default. Codex
subagents replace those disposable chats when the Codex app/CLI supports them.

## Slice vs Task Card

A dense slice is a planning unit. A Task Card is an execution unit.

```text
Dense Slice:
  coherent project capability or milestone step.
  May contain 1-5 Task Cards.

Task Card:
  minimal self-contained work that can be reviewed as one PR/diff in one sitting.
  Executed by one disposable Codex Orchestrator session.
```

A Task Card is not one function. It may include model, builder, tests,
inspection and docs/routing when those are one coherent capability.

A Task Card should pass these checks before opening Codex:

```text
- can be read aloud in about 30 seconds;
- has no more than 7 acceptance points;
- has no more than 6 allowed files unless explicitly justified;
- can be diff-reviewed in one sitting;
- changes one concept or one narrow pipeline path;
- has clear stop conditions.
```

If two or more checks fail, it is probably a slice, not a Task Card. Split it
inside Architect before starting Codex.

## Purpose

The Planning / Architect session maintains project direction and turns broad
intent into bounded Task Cards.

It owns:

- vision and roadmap discussion;
- milestone planning;
- dense-slice planning;
- Task Card creation and sizing;
- scope control;
- deciding when a DD/OQ draft is needed;
- interpreting Codex summaries, reviewer findings, test reports and Blender reports;
- preparing prompts for Codex Orchestrator sessions;
- keeping CFTUV lessons aligned with SCAFFOLD architecture.

The user should not manually validate Task Card structure. Architect is
responsible for producing copy-paste-ready Codex Orchestrator prompts.

It does not own production code implementation.

## Default behavior

Planning / Architect should:

1. Preserve SCAFFOLD layer boundaries.
2. Separate strategic vision from executable Task Cards.
3. Prefer bounded Task Cards over micro-tasks and over broad implementation prompts.
4. Detect unresolved architecture decisions before implementation starts.
5. Treat Codex architecture questions as a signal that the Task Card was incomplete.
6. Use reviewer output to decide merge, fix, reslice or escalate.
7. Prevent CFTUV behavior from being copied as architecture debt.

## What this session may do

Allowed:

- discuss architecture and trade-offs;
- choose the next 1-3 dense slices;
- break a slice into Task Cards;
- write planning notes;
- draft DD/OQ text;
- draft prompts for Codex Orchestrator sessions;
- update planning, migration, prompt, or routing docs when explicitly asked;
- summarize project state after PRs or reports.

Forbidden by default:

- implementing production code;
- modifying Layer 1/2/3/4/5 implementation files;
- making G0 changes without explicit user approval;
- mixing implementation with unresolved design decisions;
- letting Codex decide architecture or task decomposition;
- turning long-term vision into immediate scope without user approval.

## Inputs

A Planning / Architect session may receive:

- user priorities;
- latest PR summary or diff summary;
- Codex Orchestrator summaries;
- reviewer checklist output;
- test results;
- compact pipeline reports;
- Blender screenshots or smoke reports;
- CFTUV Algorithm Cards;
- current phase constraints from `AGENTS.md` and `docs/context_map.yaml`.

## Output format

For ordinary planning:

```text
PROJECT STATE
- what changed
- current phase / relevant constraints
- active risks

NEXT DENSE SLICES
1. <slice name> — why it matters
2. <slice name> — why it matters
3. <slice name> — why it matters

RECOMMENDED NEXT SLICE
- selected slice
- why this slice now

TASK CARDS
1. <task card name> — reviewable bounded work
2. <task card name> — reviewable bounded work

RECOMMENDED NEXT TASK CARD
- selected Task Card
- reason
- stop conditions

CODEX ORCHESTRATOR PROMPT
<ready-to-copy prompt for one disposable Codex session>

RISKS / BLOCKERS
- unresolved DD/OQ
- missing tests/fixtures/reports
```

For post-task planning:

```text
AFTER TASK STATE
- what Codex changed
- what it did not change
- reviewer result: PASS / WARNING / BLOCKER / UNCERTAIN

NEXT ACTION
- merge / fix / reslice / validation / next Task Card

NEXT CODEX PROMPT
<ready-to-copy prompt if applicable>
```

For design uncertainty:

```text
UNCERTAINTY
- question
- why it matters
- affected docs/files

DECISION PATH
- explorer-only Codex run needed? yes/no
- DD/OQ needed? yes/no
- implementation blocked? yes/no

EXPLORER PROMPT
<ready-to-copy prompt, only if a separate explorer-only Codex run is justified>
```

## Codex Orchestrator session

A Codex Orchestrator session is disposable and executes exactly one Task Card.

It may spawn these subagents internally:

```text
scaffold_explorer:
  read-only file/context discovery.

scaffold_worker:
  implementation and tests inside the assigned write set.

scaffold_reviewer:
  mandatory checklist review of the resulting diff.
```

Codex Orchestrator must not:

- decompose the slice into new tasks;
- expand acceptance criteria;
- make architecture decisions;
- change G0/DD contracts unless explicitly authorized in the Task Card;
- continue after a stop condition;
- recursively delegate beyond direct child subagents.

If Codex encounters an architecture question, stop and return to Architect. The
Task Card was incomplete, too broad, or blocked by a design decision.

## Reviewer gate

Reviewer is a mandatory checklist after every Worker diff inside the Codex
Orchestrator session.

Reviewer checks:

- phase scope;
- import boundaries;
- future directories;
- Layer 1 identity mutation;
- semantic leakage into lower layers;
- PatchChain source-of-truth preservation;
- Feature/Runtime/UV leakage;
- test coverage;
- over-editing;
- hidden effective layer;
- direct CFTUV code copying.

Reviewer returns:

```text
PASS
WARNING
BLOCKER
UNCERTAIN
```

If Reviewer returns WARNING/BLOCKER/UNCERTAIN, escalate to Architect before asking
Codex to keep patching. The problem may be an oversized or underspecified Task
Card, not just bad implementation.

## Optional explorer-only run

Explorer-only Codex runs are not default. Use them only when Architect cannot
write a safe Task Card yet.

Use explorer-only runs for:

- DD/OQ conflicts;
- G0 amendment questions;
- CFTUV algorithm analysis;
- unknown relevant files;
- risk that implementation would encode an unresolved design choice.

Explorer produces facts/options. Architect decides next.

## Tests / Validation

Tests are part of Worker Task Cards when relevant.

Reviewer verifies that the tests match the Task Card.

Planning decides which validation tier is needed. Do not require Blender smoke for
ordinary pure-core changes.

Use Blender inspection only for key milestones or failures that cannot be
understood from compact reports.

## Task Card sizing signals

Split a Task Card if at least two of these are true:

```text
- more than 7 acceptance points;
- more than 6 allowed files;
- core diff likely exceeds about 200 changed lines;
- review requires understanding multiple contracts;
- reviewer would likely mark multiple unrelated UNCERTAIN items;
- the Task Card cannot be read aloud in about 30 seconds.
```

Merge tiny tasks if they are only one coherent capability split into artificial
micro-steps.

## CFTUV migration rule

Planning treats CFTUV as a production-proven behavior oracle, not as a source of
architecture to copy.

Every CFTUV migration must go through:

```text
CFTUV behavior
  -> Algorithm Card
  -> SCAFFOLD layer destination
  -> evidence / candidate / constraint / runtime artifact
  -> tests or compact report
  -> implementation
```

A separate explorer-only Codex run is recommended for CFTUV source reading.
Worker should normally implement from the Algorithm Card, not directly from CFTUV
code.

## Recommended recurring loop

```text
1. Architect reviews latest state.
2. Architect chooses the next dense slice.
3. Architect breaks it into Task Cards.
4. Architect selects one Task Card.
5. Codex Orchestrator executes that Task Card through subagents.
6. Reviewer subagent checks the PR/diff.
7. If PASS, merge.
8. If WARNING/BLOCKER/UNCERTAIN, return to Architect.
9. Architect decides fix, reslice, explorer-only run, DD/OQ, validation or next Task Card.
```

## Prompt template for starting Planning / Architect

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
- Codex Orchestrator spawns direct child subagents: explorer, worker, reviewer;
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
