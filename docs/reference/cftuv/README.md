# CFTUV Reference

Optional location for selected CFTUV source files used as migration reference.

Preferred layout:

```text
docs/reference/cftuv/
  AGENTS.md
  README.md
  source/
    structural_tokens.py
    shape_classify.py
    band_spine.py
    solve_frontier.py
    solve_pin_policy.py
    solve_skeleton.py
```

Copy only files needed for a specific migration analysis. Keeping the full CFTUV
repository here is possible but discouraged because it increases the chance that
agents read too much or copy code directly.

For most work, keep CFTUV as a sibling checkout and point Scout agents to exact
files instead.
