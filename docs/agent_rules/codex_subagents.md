# Codex Subagents

Use this document for Codex app/CLI sessions that can spawn subagents.

Codex subagents replace manual disposable Worker / Reviewer / Scout chats. They
do not replace the persistent Planning / Architect chat.

## Default structure

```text
Architect chat (persistent)
  plans slices and writes one Task Card

Codex Orchestrator session (disposable)
  executes exactly one Task Card
  spawns direct child subagents:
    scaffold_explorer
    scaffold_worker
    scaffold_reviewer

Architect chat
  receives consolidated result and decides merge / follow-up / next task
```

Codex only spawns subagents when explicitly asked. The Orchestrator prompt must
name which subagents to spawn and what each one must return.

## Parent / Orchestrator

The Codex parent session coordinates one Task Card.

Responsibilities:

1. Read the Task Card and routed docs.
2. Spawn `scaffold_explorer` when discovery is needed.
3. Spawn `scaffold_worker` only after scope is clear.
4. Spawn `scaffold_reviewer` after the Worker diff exists.
5. Wait for subagent results.
6. Return one consolidated response.

The Orchestrator must not:

- choose the next dense slice;
- split slices into new tasks;
- expand acceptance criteria;
- make architecture decisions;
- silently amend G0/DD contracts;
- keep patching after architecture uncertainty appears;
- recursively delegate to deeper subagents.

If a blocker appears, stop and return it to the Architect.

## scaffold_explorer

Read-only codebase and documentation explorer.

Use for:

- locating relevant files;
- checking current contracts;
- finding stale documentation;
- identifying stop conditions;
- producing Algorithm Cards from CFTUV reference code.

Rules:

- do not edit files;
- do not propose broad refactors unless asked;
- cite files/symbols/sections when possible;
- return risks and stop conditions;
- answer only the assigned question.

Output:

```text
EXPLORER SUMMARY
RELEVANT FILES
FACTS
RISKS / STOP CONDITIONS
RECOMMENDATION
```

## scaffold_worker

Implementation-focused worker.

Use for exactly one assigned Task Card.

Rules:

- edit only the assigned write set;
- do not edit G0/DD unless explicitly authorized;
- do not expand scope;
- do not introduce future-phase directories;
- do not mutate Layer 1 identity from lower-layer work;
- do not copy CFTUV code directly;
- run the tests requested by the Task Card;
- stop on listed stop conditions.

Output:

```text
WORKER SUMMARY
CHANGED FILES
TESTS RUN
RISKS / FOLLOW-UP
```

## scaffold_reviewer

Read-only mandatory checklist reviewer for every Worker diff.

Rules:

- review the diff only;
- findings first;
- severity: PASS / WARNING / BLOCKER / UNCERTAIN;
- include file/line references when possible;
- do not redesign unless a blocking issue requires it;
- do not edit files.

Checklist:

```text
PHASE SCOPE
IMPORT BOUNDARIES
FUTURE DIRECTORIES
LAYER 1 IDENTITY MUTATION
PATCHCHAIN SOURCE OF TRUTH
SEMANTIC LEAKAGE INTO LOWER LAYERS
FEATURE / RUNTIME / UV LEAKAGE
TEST COVERAGE
OVER-EDITING
HIDDEN EFFECTIVE LAYER
CFTUV CODE COPY LEAKAGE
DOCS / STATUS SYNC
```

Output:

```text
REVIEW RESULT: PASS | WARNING | BLOCKER | UNCERTAIN

CHECKLIST
- PHASE SCOPE: PASS/WARNING/BLOCKER/UNCERTAIN — note
- IMPORT BOUNDARIES: PASS/WARNING/BLOCKER/UNCERTAIN — note
...

FINDINGS
1. <severity> <file/line> <issue>

MERGE / ESCALATE RECOMMENDATION
- merge
- fix within Task Card
- return to Architect
- split Task Card
```

## Task Card template

```text
TASK CARD

Name:
  <short name>

Goal:
  <one bounded capability>

Route:
  <docs/context_map.yaml route>

Use subagents:
  - scaffold_explorer: yes/no and exact question
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

Final Orchestrator output:
  EXPLORER SUMMARY
  WORKER SUMMARY
  TESTS RUN
  REVIEW RESULT
  FINAL RECOMMENDATION
```

## Task Card sizing guardrails

A Task Card should be reviewable in one sitting.

Split the card if at least two are true:

```text
- more than 7 acceptance points;
- more than 6 allowed files;
- core diff likely exceeds about 200 changed lines;
- review requires understanding multiple contracts;
- reviewer would likely mark multiple unrelated UNCERTAIN items;
- the Task Card cannot be read aloud in about 30 seconds.
```

## Recommended Codex Orchestrator prompt

```text
Read AGENTS.md and docs/context_map.yaml route: <route>.
Read docs/agent_rules/codex_subagents.md.

You are the Codex Orchestrator for this SCAFFOLD Task Card.
Execute exactly this Task Card. Do not expand scope.

Task Card:
<task card>

Subagent workflow:
1. Spawn scaffold_explorer if the Task Card requests it.
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

## Custom agents

Project-scoped custom agents live in:

```text
.codex/agents/
```

Recommended files:

```text
.codex/agents/scaffold-explorer.toml
.codex/agents/scaffold-worker.toml
.codex/agents/scaffold-reviewer.toml
```

Recommended project config:

```text
.codex/config.toml
```

Keep `agents.max_depth = 1` unless there is a specific reason for recursive
delegation. Recursive delegation increases token use, latency and unpredictability.
