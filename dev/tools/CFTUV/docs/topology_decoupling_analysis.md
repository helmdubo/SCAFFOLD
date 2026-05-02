# Analysis: AI Agent Feedback on Decoupling Topology from World Semantics

## Context

Another AI agent reviewed the CFTUV architecture and proposed decoupling
floor/wall/slope from the core topology. This document is my assessment
of that feedback — what's right, what's wrong, and what actually makes
sense to do.

---

## Diagnosis: Largely Correct

The agent's core observation is **accurate**: `patch_type` (WALL/FLOOR/SLOPE)
and `world_facing` (UP/DOWN/SIDE) are already nearly decorative in the
solving path. The data confirms this:

- **frame_role assignment** (`analysis_corners.py:92-133`) is **pure geometry** —
  measures chain direction against `basis_u`/`basis_v`, never checks patch_type
- **Placement logic** (`frontier_eval.py`, `frontier_place.py`, `frontier_state.py`)
  uses frame_role, never patch_type
- **effective_placement_role()** in `frontier_state.py` resolves through
  native H/V → STRAIGHTEN → band_cap_role → FREE, never touching patch_type
- **Total patch_type conditionals in solving**: exactly **2 locations**:
  1. `_semantic_stability_bonus()` in `solve_planning.py:306-315` — scoring weight (returns 0.02 default, non-critical)
  2. `patch_types_compatible()` in `solve_records_domain.py:152-160` — attachment filter (could use structural properties)
- **Total world_facing conditionals in solving**: **0 locations**
- The remaining ~15+ uses are debug visualization and statistics reporting

The agent correctly identifies that Chain → Corner → Junction is already
the real structural backbone, and that patch_type is "historical dispatch
vocabulary, not the real cause of decisions."

---

## Proposed Solution: Over-Engineered and Partially Contradicts Architecture

Here's where the feedback goes wrong. The proposed solution introduces
a large amount of new abstraction that conflicts with explicit CFTUV
architectural invariants.

### Problem 1: New enum/class explosion violates "What NOT To Do"

The agent proposes:
- Expand PatchShapeClass to: SHEET, BAND, RING, HUB, BRANCHING, MIX
- Add new "Chart embedding mode": AXIS_RESOLVED, AXIS_INHERITED, AXIS_AMBIGUOUS, STRAIGHTENABLE, CONFORMAL_ONLY
- Add new "Structural role" layer: continuation, turn, branch, terminal, side, cap, bridge, spine candidate
- Rename H/V to AXIS_A/AXIS_B

But AGENTS.md explicitly states:
> "Do NOT add multi-axis semantic profiles (confidence scores beyond ChainRoleClass)"

The AXIS_RESOLVED/AXIS_INHERITED/AXIS_AMBIGUOUS layer is exactly that — a
multi-axis semantic profile. And SHEET/RING/HUB are shapes that don't exist
in the codebase yet because they haven't been needed, not because of oversight.

### Problem 2: "Constraint-first ownership" contradicts architectural invariants

The agent proposes:
> junction/corner → emits structural constraints → constraints решаются в local chart system

But AGENTS.md explicitly states:
> "Do NOT create constraint classes — stitching rules are code in solve"
> "Corner-derived facts are hints: local refinement only, not independent placement units"
> "Junction remains derived: not a primary runtime entity (future Phase 2)"
> "Drift toward ... corner-based placement is an architectural regression"

The entire "constraint-first" pipeline they propose (corners → relation graph →
constraints → chart system → axes) is the exact architecture the project has
deliberately avoided. It would turn Junction from a diagnostic entity into a
solve-driving entity, which is an explicit regression.

### Problem 3: Renaming H/V to AXIS_A/AXIS_B loses information for no gain

H_FRAME and V_FRAME are defined relative to `basis_u`/`basis_v` — which are
already local patch axes, not world axes. H_FRAME means "aligned with basis_u
direction" and V_FRAME means "aligned with basis_v direction." They're already
chart-local. Renaming them to AXIS_A/AXIS_B would:
- Break all existing code (H/V appears in ~100+ locations)
- Remove mnemonic value (developers lose intuition about which axis is which)
- Gain nothing — the "psychological world binding" the agent worries about
  doesn't exist in the code, only potentially in a reader's head

### Problem 4: The "danger of junction-first" warning is correct but misapplied

The agent correctly warns that junctions alone can't determine global axis
orientation (symmetric cases, rings, isolated patches). But then proposes
a complex pipeline to solve exactly that problem. The current architecture
already handles this better: frame_role is assigned from geometry, scoring
aggregates structural hints, frontier picks the strongest candidate. No
new pipeline needed.

---

## What I Actually Recommend

The actual change needed is **much smaller** than what the agent proposes.
Since patch_type/world_facing are already nearly decorative, the work is:

### Step 1: Replace the 2 solving dependencies with structural alternatives

1. **`_semantic_stability_bonus()`** (`solve_planning.py:306-315`):
   Replace patch_type/world_facing checks with structural properties —
   frame dominance ratio, rectilinearity, or shape class. The function
   already returns a small scoring bonus (0.02-0.06), so any reasonable
   structural metric works.

2. **`patch_types_compatible()`** (`solve_records_domain.py:152-160`):
   Replace same-patch_type check with structural compatibility — e.g.,
   dihedral_convexity range, frame_role continuity between neighbors, or
   shape_class compatibility.

3. **Seed scoring in `frontier_eval.py:550-562`**:
   Replace `semantic_key` checks with structural neighbor properties.

### Step 2: Demote PatchType/WorldFacing to display-only

- Keep the enums (they're useful for human-readable reporting and debug viz)
- Keep `semantic_key` property on PatchNode (useful for debug output)
- Add a comment marking them as "display/reporting layer, not solve input"
- Do NOT delete them — they serve real value in debug.py visualization

### Step 3: Do NOT add new abstraction layers

- No new enums for "chart embedding mode"
- No expansion of PatchShapeClass beyond what's needed (RING/HUB can come
  when there's actual code that needs them, per Phase 2/3 roadmap)
- No constraint classes
- No AXIS_A/AXIS_B renaming
- Keep Junction as diagnostic-only per current roadmap

---

## Summary

| Aspect | Agent's Feedback | My Assessment |
|--------|-----------------|---------------|
| Diagnosis (floor/wall is decorative) | Correct | Agree |
| Chain/Corner/Junction is real core | Correct | Agree |
| Add SHEET/RING/HUB/BRANCHING | Premature | Skip — add when needed |
| Add AXIS_RESOLVED/INHERITED/AMBIGUOUS | Over-engineered | Violates "no multi-axis profiles" |
| Rename H/V to AXIS_A/AXIS_B | Cosmetic | Destructive churn, no real gain |
| Constraint-first ownership | Architecturally wrong | Violates "no constraint classes" |
| Junction as structural truth source | Partially right | Keep as hints, not owner |
| Actual scope of change needed | ~large redesign | ~3 small function rewrites |

The agent did good analysis of the current state but proposed a solution
that's 10x larger than the actual problem. The coupling is already minimal
(2-3 functions). Fix those, mark the rest as display-only, done.

---

## Files to Modify

1. `cftuv/solve_planning.py` — `_semantic_stability_bonus()` (~10 lines)
2. `cftuv/solve_records_domain.py` — `patch_types_compatible()` (~10 lines)
3. `cftuv/frontier_eval.py` — seed scoring section (~15 lines)
4. `cftuv/frontier_score.py` — same-type neighbor check (~5 lines)
5. `cftuv/model.py` — add docstring clarifying PatchType/WorldFacing are display-only

## Verification

- Run existing test suite (if any) to check for regressions
- Verify that patch_type/world_facing are no longer imported in solve_planning,
  solve_records_domain, frontier_eval, frontier_score
- Verify debug.py still works (it should — it reads patch_type from PatchNode,
  which still exists)
- Manual test: UV unwrap a mixed wall/floor/slope mesh, verify output unchanged
