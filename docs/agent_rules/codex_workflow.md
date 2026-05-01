# Codex Workflow

Use this document when a task is intended for Codex app/CLI with subagent support.

The goal is speed without losing Scaffold's layer boundaries. Prefer bounded
Task Cards over manual micro-management and over broad implementation prompts.

## Default workflow

Use this structure for ordinary SCAFFOLD work:

```text
Architect chat (persistent)
  plans dense slices and writes Task Cards

Codex Orchestrator session (disposable, one Task Card)
  spawns subagents internally:
    scaffold_explorer -> scaffold_worker -> scaffold_reviewer

Architect chat
  receives consolidated result and decides merge / follow-up / next task
```

Do not manually open separate Worker / Reviewer / Scout chats by default. Codex
subagents replace those disposable chats.

## Roles

### Planning / Architect

Persistent project planning outside Codex Work.

Owns:

- roadmap and milestone discussion;
- dense-slice selection;
- Task Card creation and sizing;
- scope control;
- deciding whether a DD/OQ is needed;
- preparing Codex Orchestrator prompts;
- interpreting consolidated Codex results.

Architect does not implement production code.

### Codex Orchestrator

Disposable parent session for one Task Card.

Responsibilities:

- read the Task Card and routed docs;
- spawn requested subagents;
- wait for subagent results;
- return one consolidated response.

The Orchestrator must not:

- choose the next dense slice;
- split a slice into new tasks;
- expand acceptance criteria;
- make architecture decisions;
- silently amend G0/DD contracts;
- recursively delegate beyond direct child subagents.

### scaffold_explorer

Read-only discovery subagent.

Use for file discovery, contract checks, stale-doc detection, risk discovery and
CFTUV Algorithm Cards.

### scaffold_worker

Implementation subagent.

Executes only the assigned Task Card. Edits only the assigned write set. Runs the
requested tests when possible.

### scaffold_reviewer

Mandatory read-only checklist reviewer after every Worker diff.

Returns PASS / WARNING / BLOCKER / UNCERTAIN.

## Dense Slice vs Task Card

```text
Dense Slice:
  planning unit owned by Architect.
  May contain 1-5 Task Cards.

Task Card:
  execution unit owned by one Codex Orchestrator session.
  Must be reviewable as one PR/diff in one sitting.
```

A Task Card is not one function. It may include model, builder, tests,
inspection and docs/routing when those are one coherent capability.

Task Card sizing guardrails:

```text
- can be read aloud in about 30 seconds;
- no more than 7 acceptance points;
- no more than 6 allowed files unless explicitly justified;
- diff-reviewable in one sitting;
- changes one concept or one narrow pipeline path;
- has clear stop conditions.
```

If two or more guardrails fail, split the task inside Architect before opening
Codex.

## Stop conditions

Stop and return to Architect if the task requires:

- editing `G0.md` without explicit user approval;
- creating future-phase directories;
- Layer 4/5 concepts during G3;
- redefining or splitting Layer 1 `PatchChain` identity;
- adding hidden semantic role promotion;
- copying CFTUV solve code directly;
- adding UI or Blender logic to core layers;
- adding generic `utils.py`, `helpers.py`, `manager.py`, `service.py`, or `registry.py` modules.

## Minimal Patch vs Task Card

Use `docs/agent_rules/minimal_patch_protocol.md` for:

- bug fixes;
- regressions;
- small corrections;
- repairs to existing working behavior.

Use Task Cards for approved greenfield capabilities, docs/status sync work, or
multi-file changes that are still one coherent reviewable capability.

Minimal Patch Protocol should not be used to artificially split one approved
capability into many manual micro-tasks.

## Prompt style

Keep prompts short. Persistent rules live in:

```text
AGENTS.md
docs/context_map.yaml
routed docs
docs/agent_rules/codex_subagents.md
```

Task prompts should state:

- route to read;
- Task Card name;
- goal;
- requested subagents;
- allowed files;
- forbidden scope;
- acceptance criteria;
- tests;
- stop conditions;
- required consolidated output.

## Codex Orchestrator prompt shape

```text
Read AGENTS.md and docs/context_map.yaml route: <route>.
Read docs/agent_rules/codex_subagents.md.

You are the Codex Orchestrator for this SCAFFOLD Task Card.
Execute exactly this Task Card. Do not expand scope.

Task Card:
<task card>

Subagent workflow:
1. Spawn scaffold_explorer if requested.
2. If explorer reports BLOCKER, stop and summarize.
3. Spawn scaffold_worker to implement only the Task Card.
4. Spawn scaffold_reviewer to review the resulting diff using the SCAFFOLD checklist.
5. Wait for all requested results.
6. Return a consolidated response.

Do not start a second implementation pass if reviewer reports architecture
UNCERTAIN or BLOCKER. Return to Architect instead.
```

## Consolidated response format

```text
EXPLORER SUMMARY
- facts / files / risks, or N/A

WORKER SUMMARY
- changed files
- behavior added

TESTS RUN
- commands and results

REVIEW RESULT
- PASS / WARNING / BLOCKER / UNCERTAIN
- key checklist items

FINAL RECOMMENDATION
- merge
- fix within Task Card
- return to Architect
- split Task Card
```
