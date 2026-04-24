# Minimal Patch Protocol

Use this protocol for bug fixes, regression fixes and edits to existing working code.

Over-editing is an architecture risk.

Over-editing means fixing the reported issue while unnecessarily rewriting surrounding code: renaming variables, changing formatting, adding unrelated guards, changing control flow, extracting helpers or touching unrelated files.

Minimality is part of correctness.

A patch is not correct if it fixes the bug but unnecessarily changes stable code.

## When this applies

Apply this protocol when the task says or implies:

```text
fix bug
regression
small correction
adapt existing function
change one behavior
repair failing test
```

Do not use this protocol for explicitly approved greenfield implementation tasks.

## Required workflow

### Step 1 — diagnosis only

Before editing, identify:

```text
file
function/class
line range
root cause
minimal patch strategy
expected changed lines
```

Do not edit files during diagnosis.

### Step 2 — patch plan

Propose the smallest patch.

Include:

```text
changed files
changed functions
estimated changed lines
behavior affected
tests to run
```

### Step 3 — apply patch

Apply only the approved minimal patch.

Do not modify anything else.

## Hard constraints

When Minimal Patch Protocol applies:

```text
Do not refactor.
Do not rename variables, functions, classes, or files.
Do not reformat unrelated code.
Do not modernize code style.
Do not add defensive checks unless the bug directly requires them.
Do not change public behavior outside the failing case.
Do not touch unrelated functions.
Do not change imports unless directly necessary.
Do not update docs, README, configs, or tests unless required by the bug.
```

If the fix requires more than 10 changed lines, stop and explain why before editing.

## Output format

Separate patch from notes:

```text
PATCH:
  minimal fix only

NOTES:
  optional suggestions for later cleanup
```

Do not include cleanup suggestions in the patch.

## Reject patch if

```text
changed files > expected files
changed functions > expected functions
changed lines > agreed edit budget
public API changed without explicit approval
formatter changed unrelated blocks
imports changed without direct need
defensive try/except was added without direct need
```

If a useful unrelated improvement is discovered, report it under NOTES and leave code unchanged.
