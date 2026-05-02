# CFTUV Reference Rules

This folder contains SCAFFOLD-side reference notes for CFTUV migration.

The CFTUV source oracle lives in:

```text
dev/tools/CFTUV/
  *.py
  docs/*.md
```

Do not import from `dev/tools/CFTUV/`.
Do not run files from `dev/tools/CFTUV/` as SCAFFOLD code.
Do not edit CFTUV reference files during SCAFFOLD implementation tasks.
Do not read CFTUV source in ordinary SCAFFOLD sessions.

Read CFTUV source only when:

- the user explicitly asks for CFTUV migration analysis;
- the routed task is `cftuv_algorithm_card` or `cftuv_migration`;
- the Task Card names exact CFTUV files to inspect.

When analyzing CFTUV, `scaffold_explorer` must output an Algorithm Card.
Do not copy implementation into SCAFFOLD directly.
