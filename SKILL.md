# Skill: Anti Over-Editing Coding Protocol

## Purpose

This skill helps AI coding agents avoid, detect, and clean up over-editing.

Over-editing means making changes beyond the actual task:

- rewriting whole functions when a small patch was enough
- adding unnecessary defensive checks
- adding fallback logic without a requirement
- introducing helper functions, flags, configs, abstractions, or wrappers that are not needed
- partially reverting a failed approach but leaving debris behind
- changing nearby code "for cleanliness"
- mixing bug fixes with refactoring
- changing behavior outside the requested scope

This skill is designed for brownfield / existing codebases, especially when the human user is not a professional programmer and relies on AI agents to work safely in a medium or large codebase.

The priority is:

1. Solve the task.
2. Preserve existing behavior.
3. Keep the diff small.
4. Separate research code from production code.
5. Prevent AI-generated debris from entering the main codebase.

---

## Core Principle

Do not optimize for elegant code during a bug fix.

Optimize for:

```text
minimal diff + behavioral preservation + clear intent
```

A correct patch is not just one that works.

A correct patch is one where every changed line can be justified by the original task.

---

## Operating Modes

The agent must distinguish between four modes.

### 1. Tiny Fix Mode

Use when the task is obviously local:

- typo
- one-line bug
- wrong condition
- wrong index
- wrong variable
- small local behavior correction

Rules:

- Touch only the necessary function or block.
- Do not refactor.
- Do not rename.
- Do not reformat unrelated code.
- Do not add helpers or fallback logic unless directly required.

Required output:

- Short explanation.
- Minimal diff.
- Confirmation of changed files/functions.

---

### 2. Normal Coding Mode

Use for ordinary feature work or bug fixing.

Rules:

- Keep changes close to the requested task.
- Do not modify neighboring systems unless required.
- Do not add broad defensive wrappers.
- Do not add new configuration flags unless the task explicitly requires it.
- If a helper function is added, explain why the task requires it.
- If behavior outside the target area changes, explicitly mark it.

Required output after each significant change:

```text
Diff Receipt:
- Changed files:
- Changed functions/classes:
- Added helpers:
- Added fallback/try-except/default behavior:
- Changed public behavior:
- Temporary/debug/experimental code:
- Anything that may need cleanup later:
```

Keep the receipt short.

---

### 3. Research Mode

Use when the solution is uncertain and experimentation is needed.

Allowed:

- prototypes
- temporary helpers
- debug output
- experimental branches
- rough code
- alternative approaches

But research code is not production code.

Rules:

- Mark temporary or experimental code clearly.
- Do not treat exploratory code as final.
- Keep a short session log of failed approaches.
- Do not merge research output directly.

Required output during research:

```text
Research Log:
- Current hypothesis:
- Approach tried:
- What worked:
- What failed:
- Temporary code added:
- Code that must be removed before production:
```

---

### 4. Cleanup / Integration Mode

Use at the end of a coding or research session.

Goal:

Convert messy session output into a clean production patch.

Rules:

- Do not add new features.
- Do not refactor for beauty.
- Do not expand scope.
- Identify what to keep, revert, review, or mark as debt.
- Remove debris from failed approaches.
- Extract the minimal production patch.

Required output:

```text
Session Cleanup Pass:

KEEP:
- Code that directly belongs to the final solution.

REVERT:
- Experimental code that should not remain.
- Helpers, flags, wrappers, fallbacks, debug code, or branches no longer needed.

REVIEW:
- Code that may be valid but changes behavior or needs human decision.

DEBT:
- Code that remains temporarily, with a reason and suggested future cleanup.

Minimal Production Patch:
- Files that truly need to change:
- Functions/classes that truly need to change:
- Expected behavior change:
- Anything intentionally left out:
```

---

## Over-Editing Risk Triggers

Run a deeper audit only if one or more triggers are present:

```text
- More than 1–2 files changed.
- Large diff.
- New helper functions/classes added.
- New config flags/options added.
- New fallback behavior added.
- New try/except blocks added.
- Public API or function signatures changed.
- Existing behavior changed outside the requested task.
- The agent previously made a mistake and partially reverted it.
- The session involved research/prototyping.
- The human user says: "I no longer understand what changed."
- Before merge into main/master/production branch.
```

If no trigger is present, do not perform a full forensic audit.

Use a lightweight check instead.

---

## Lightweight Over-Editing Check

Use this after small or normal changes.

Do not produce a long report.

Answer only:

```text
Quick Over-Editing Check:

1. Did I touch anything outside the task?
2. Did I add helpers/fallbacks/try-except/configs?
3. Did I change public behavior?
4. Can the diff be smaller?
5. Is there any temporary or experimental code left?
```

If all answers are safe, say so briefly.

If something is suspicious, list only the suspicious parts.

---

## Full Over-Editing Forensic Audit

Use only for risky diffs or before merge.

The agent must not edit code during this audit.

The agent must classify changes and explain which ones are not justified by the original task.

### Input Required

```text
Original task:
<what the human asked>

Observed problem:
<bug / feature / goal>

Git diff:
<diff>

Optional session log:
<failed approaches, partial rollbacks, experiments>

Relevant constraints:
<what must not change>
```

### Audit Rules

Classify every meaningful changed block as one of:

```text
GREEN  — directly required by the task
YELLOW — probably useful but not proven
ORANGE — behavior-changing or risky
RED    — likely over-editing / leftover / hidden side effect
GRAY   — cannot determine
```

Also classify by type:

```text
- Direct fix
- Necessary support code
- Test/debug code
- Behavior change
- Defensive wrapper
- Fallback logic
- Refactor/style change
- Dead or unused code
- Suspicious unrelated change
- Partial rollback leftover
- Unknown
```

### Specific Smells to Detect

Look for:

```text
- broad try/except
- silent exception handling
- new fallback branches
- new default values
- compatibility modes
- new config flags
- new helper functions
- pass-through wrappers
- unused imports
- unused functions/classes
- debug scaffolding
- temporary comments
- changed function signatures
- changed public behavior
- changed order of operations
- duplicated logic
- partially reverted code
- code from failed approaches that still remains
```

### Required Audit Output

```text
Over-Editing Forensic Audit:

Executive Summary:
- Overall risk:
- Main concern:
- Recommended action:

Suspicious Changes:
[OE-01]
Risk: RED / ORANGE / YELLOW / GRAY
File:
Function/class:
Type:
Why suspicious:
What requirement justifies it:
Can it be removed:
Recommendation:

Likely Removable Code:
- ...

Behavior Changes:
- ...

Partial Rollback Leftovers:
- ...

Questions for Human Owner:
- ...

Minimal Production Patch Reconstruction:
- What files truly needed changes:
- What functions/classes truly needed changes:
- What could have been left untouched:
```

Keep the report focused.

Do not list every harmless change.

Prioritize RED and ORANGE findings.

---

## Production Patch Extraction

Use this after research mode or messy AI iteration.

Goal:

Build the cleanest version of the final patch.

Prompt behavior:

```text
Extract the minimal production patch from the current session.

Do not preserve experimental scaffolding.
Do not preserve failed approaches.
Do not preserve debug code.
Do not preserve unused helpers.
Do not preserve fallback logic unless required.
Do not preserve new config flags unless required.
Do not refactor unrelated code.

First show what will be kept and what will be removed.
Then produce the patch.
```

Required output:

```text
Production Extraction Plan:

KEEP:
- ...

REMOVE:
- ...

REVIEW BEFORE REMOVAL:
- ...

FINAL PATCH SCOPE:
- Files:
- Functions/classes:
- Behavior changes:
```

Only after this plan should code be edited.

---

## Rules for AI Agents

### Hard Rules

```text
1. Do not refactor unless explicitly asked.
2. Do not rename variables, functions, classes, or files unless required.
3. Do not reformat unrelated code.
4. Do not change neighboring functions unless required.
5. Do not add defensive checks unless the bug directly requires them.
6. Do not add broad try/except.
7. Do not add fallback behavior without explaining the requirement.
8. Do not add config flags for speculative future flexibility.
9. Do not mix bug fixes with cleanup.
10. Do not assume existing AI-generated code is correct just because it exists.
```

### When Adding Any New Helper / Wrapper / Flag

Answer:

```text
Why does this need to exist?
What breaks if it is removed?
Which part of the original task requires it?
Is this production code or research code?
```

If the answer is vague, do not add it.

Suspicious vague justifications include:

```text
- improves robustness
- makes it more flexible
- handles future cases
- cleaner architecture
- safer behavior
- better abstraction
```

These are not sufficient unless tied to a concrete requirement.

---

## Human Attention Budget

The agent must respect the human user's attention.

Do not overload the user with excessive review reports.

Use this escalation ladder:

```text
Tiny fix:
- diff receipt only

Normal change:
- quick over-editing check

Research session:
- session cleanup pass

Before merge or risky diff:
- full forensic audit
```

The agent should never run the full audit after every small iteration unless explicitly requested.

---

## Recommended Commands / Prompts

### Start Coding Session

```text
We are starting a coding session.

Use Anti Over-Editing Coding Protocol.

Mode: Normal Coding / Research / Tiny Fix

Task:
...

Constraints:
- minimal diff
- no refactor
- preserve existing behavior
- separate research code from production code

At the end of each significant change, provide a short Diff Receipt.
```

---

### Quick Check

```text
Run a lightweight over-editing check.

Do not edit code.
Do not produce a long report.

Answer only:
1. Did you touch anything outside the task?
2. Did you add helpers/fallbacks/try-except/configs?
3. Did you change public behavior?
4. Can the diff be smaller?
5. Is temporary or experimental code left?
```

---

### Session Cleanup

```text
We finished a coding/research session.

Run Session Cleanup Pass.

Do not edit code yet.

Classify current changes as:
- KEEP
- REVERT
- REVIEW
- DEBT

Focus only on:
- leftovers from failed approaches
- unnecessary helpers
- unnecessary fallback logic
- debug scaffolding
- temporary code
- behavior changes not required by the original task

Keep the report short and actionable.
```

---

### Extract Production Patch

```text
Extract the minimal production patch from this session.

Do not keep research scaffolding.
Do not keep failed approaches.
Do not keep unused helpers.
Do not keep unnecessary fallback logic.
Do not keep debug code.

First output:
- KEEP
- REMOVE
- REVIEW BEFORE REMOVAL
- FINAL PATCH SCOPE

Then wait for approval before editing.
```

---

### Full Audit Before Merge

```text
Run a full Over-Editing Forensic Audit.

Do not edit code.

Inputs:
- Original task
- Current git diff
- Session log / failed approaches if available

Find only meaningful risks:
- RED
- ORANGE
- important YELLOW

Ignore cosmetic issues unless they hide behavior changes.

Output:
- Executive summary
- Suspicious changes
- Likely removable code
- Behavior changes
- Partial rollback leftovers
- Minimal production patch reconstruction
- Questions for human owner
```

---

## Definition of Done

A task is not done until:

```text
1. The requested behavior works.
2. The diff is as small as reasonably possible.
3. No research/debug scaffolding remains.
4. No failed approach leftovers remain.
5. Any helper/fallback/config has a concrete reason to exist.
6. Behavior changes outside the task are explicitly listed.
7. The human can understand what changed without reading the whole codebase.
```

---

## Final Reminder for the Agent

You are not rewarded for producing more code.

You are rewarded for producing the smallest safe change that solves the actual problem.

When in doubt:

```text
prefer deletion over abstraction
prefer explicit intent over cleverness
prefer small patch over elegant rewrite
prefer asking for scope confirmation over expanding behavior
```
