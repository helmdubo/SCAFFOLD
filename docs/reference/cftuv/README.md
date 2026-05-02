# CFTUV Reference Docs

This folder contains SCAFFOLD-side reference notes for CFTUV migration.

It is not the CFTUV source-code location.

CFTUV source/reference code lives in:

```text
dev/tools/CFTUV/
  *.py
  docs/*.md
```

Use `dev/tools/CFTUV/` only as a read-only algorithm oracle during explicit
CFTUV migration / Algorithm Card tasks.

Use this folder for lightweight reference notes that help agents understand how
CFTUV should be treated during migration.

Rules:

- ordinary SCAFFOLD tasks should not read `dev/tools/CFTUV/`;
- CFTUV source reading should be done by `scaffold_explorer`;
- SCAFFOLD implementation should normally consume an Algorithm Card, not CFTUV source directly;
- do not import or run CFTUV files from SCAFFOLD code/tests.

Primary migration docs:

```text
docs/migration/cftuv_lessons.md
docs/migration/cftuv_bridge.md
docs/migration/cftuv_parity_fixtures.md
```
