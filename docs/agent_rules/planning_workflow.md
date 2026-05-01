# Planning / Architect Workflow

Use this document for the long-running project planning chat that coordinates
SCAFFOLD work.

This mode is the project headquarters. It is not an implementation session.

## Default simplified workflow

Use this reduced chat model by default:

```text
1. Main Planning / Architect chat
   Long-running project headquarters.
   Owns roadmap, dense-slice selection, scope control and Codex prompts.

2. Codex Work chat
   One short-lived chat per dense slice.
   May combine inspect -> plan -> implement -> tests -> inspection/report.
```

Use extra chats only when needed:

```text
Optional Scout chat:
  Use only for unresolved architecture questions, DD/OQ conflicts or CFTUV
  algorithm analysis that must be separated from implementation.

Optional Reviewer chat:
  Use only for high-risk diffs: G0/DD changes, new layer contracts,
  ScaffoldGraph/Feature/Runtime work, large diffs or uncertain implementation.

Optional Blender Validation chat:
  Use only for milestone visual checks or failures that compact reports cannot
  explain.
```

Do not create separate chats for Model, Builder, Tests, Inspection and
Docs/routing by default. Those are usually one Codex Work dense slice.

## Purpose

The Planning / Architect session maintains project direction and turns broad
intent into bounded Codex work.

It owns:

- vision and roadmap discussion;
- milestone planning;
- dense-slice selection;
- scope control;
- deciding when a separate Scout session is needed;
- deciding when a separate Reviewer session is needed;
- deciding when a DD/OQ draft is needed;
- interpreting Codex Work summaries, test reports and Blender reports;
- preparing prompts for Codex Work sessions;
- keeping CFTUV lessons aligned with SCAFFOLD architecture.

It does not own production code implementation.

## Default behavior

Planning / Architect should:

1. Preserve SCAFFOLD layer boundaries.
2. Prefer dense bounded slices over micro-task planning for greenfield work.
3. Use the two-chat workflow unless risk justifies a separate Scout/Reviewer.
4. Separate strategic vision from executable next slices.
5. Detect unresolved architecture decisions before implementation starts.
6. Keep the user focused on the next useful step.
7. Produce Codex-ready prompts when a slice is selected.
8. Prevent CFTUV behavior from being copied as architecture debt.

## What this session may do

Allowed:

- discuss architecture and trade-offs;
- choose the next 1-3 dense slices;
- write planning notes;
- draft DD/OQ text;
- draft prompts for Codex Work / optional Scout / optional Reviewer sessions;
- update planning, migration, prompt, or routing docs when explicitly asked;
- summarize project state after PRs or reports.

Forbidden by default:

- implementing production code;
- modifying Layer 1/2/3/4/5 implementation files;
- making G0 changes without explicit user approval;
- mixing implementation with unresolved design decisions;
- turning long-term vision into immediate scope without user approval.

## Inputs

A Planning / Architect session may receive:

- user priorities;
- latest PR summary or diff summary;
- Codex Work summaries;
- optional Scout reports;
- optional Reviewer findings;
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
- reason
- stop conditions

CODEX WORK PROMPT
<ready-to-copy prompt for the next Codex Work chat>

RISKS / BLOCKERS
- unresolved DD/OQ
- missing tests/fixtures/reports
```

For post-slice planning:

```text
AFTER SLICE STATE
- what the slice changed
- what it did not change
- whether roadmap changed

NEXT ACTION
- merge / follow-up / optional reviewer / validation / next slice

NEXT CODEX WORK PROMPT
<ready-to-copy prompt if applicable>
```

For design uncertainty:

```text
UNCERTAINTY
- question
- why it matters
- affected docs/files

DECISION PATH
- separate Scout needed? yes/no
- DD/OQ needed? yes/no
- implementation blocked? yes/no

SCOUT PROMPT
<ready-to-copy prompt, only if a separate Scout is justified>
```

## Relationship to other session modes

### Codex Work

Planning writes the dense-slice prompt. Codex Work performs the slice.

A Codex Work chat may combine:

```text
inspect -> short plan -> implement -> tests -> inspection/report -> summary
```

A dense slice should have:

- one capability;
- one layer owner or narrow pipeline path;
- explicit forbidden scope;
- stop conditions;
- tests or report output.

### Optional Scout

Planning asks a separate Scout only when the contract is unclear.

Use separate Scout when:

- a DD/OQ conflict may exist;
- a G0 amendment may be needed;
- CFTUV behavior needs isolated analysis;
- relevant files must be located before a risky implementation.

Scout returns information. Planning decides what to do with it.

### Optional Reviewer

Planning may start a separate Reviewer session after high-risk implementation.

Reviewer checks the diff. Reviewer does not redesign unless the diff reveals a
blocking architecture issue.

Ordinary dense slices may use Codex Work self-check plus tests instead of a
separate Reviewer chat.

### Tests / Validation

Planning decides which validation tier is needed.

Do not require Blender smoke for ordinary pure-core changes.

### Blender Inspection

Planning uses Blender inspection only for key milestones or failures that cannot
be understood from compact reports.

## Dense slice selection rules

A good next dense slice has:

```text
one new concept
one layer owner
one inspection/report/test output
no unresolved DD blocker
clear stop conditions
```

Examples:

Good:

```text
ScaffoldNode v0 docs/status sync:
  update G3 docs + handoff + AGENTS status + DD note, no implementation code.
```

Good implementation slice:

```text
ScaffoldNode v0:
  model + builder + tests + inspection summary inside G3.
```

Bad:

```text
Make SCAFFOLD support bands like CFTUV.
```

## Stop conditions for Planning

Planning should stop and request Scout/DD work when the next action requires:

- changing `G0.md`;
- resolving DD-34 / PatchChain / ScaffoldEdge semantics;
- adding Layer 4/5 concepts during G3;
- defining a new cross-layer contract;
- changing `WORLD_UP` policy;
- deciding how user-authored seam chains are represented;
- porting CFTUV behavior without an Algorithm Card.

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

A separate Scout is recommended for CFTUV source reading. The Codex Work chat
should normally implement from the Algorithm Card, not directly from CFTUV code.

## Recommended recurring planning loop

```text
1. Review latest state.
2. Identify whether design uncertainty exists.
3. If uncertain, decide whether a separate Scout is worth it.
4. If clear, choose one dense slice.
5. Write Codex Work prompt.
6. Codex Work performs inspect -> implement -> tests -> summary.
7. Decide whether optional Reviewer or Blender validation is needed.
8. Update next slices.
```

## Prompt template for starting Planning / Architect

```text
You are the Planning / Architect session for SCAFFOLD.

Do not implement production code.
Your job:
- maintain roadmap;
- choose next dense slices;
- decide when separate Scout/Reviewer chats are actually needed;
- prepare Codex Work prompts;
- keep G0/current phase boundaries in mind;
- prevent scope creep;
- keep CFTUV migration behavior-first.

Default workflow:
- one long Planning chat;
- one Codex Work chat per dense slice;
- optional Scout/Reviewer/Blender chats only for high-risk cases.

Input:
- latest PR summaries / reviewer notes / test reports / user priorities.

Output:
PROJECT STATE
NEXT DENSE SLICES
RECOMMENDED NEXT SLICE
CODEX WORK PROMPT
RISKS / BLOCKERS
```
