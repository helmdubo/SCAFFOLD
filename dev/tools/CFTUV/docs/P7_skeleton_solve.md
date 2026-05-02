# P7 — CFTUV Skeleton Solve (Junction-Based Global Alignment)

> Status: Ready for execution.
> Replaces: `Variant A` row/column snap correction pass from Stage C roadmap.
> Includes: ChainUse first-class IR modernization as Phase S0b (risk-critical, done inline with P7).
> Depends on: existing junction IR, scaffold build, frontier placement telemetry.

---

## Role

You are a Principal Technical Art Engineer agent working on CFTUV for Blender. You are replacing the post-scaffold drift correction pass with a **junction-based global skeleton solve** that reconciles three previously independent concerns in a single constrained least-squares system:

1. Row/column alignment (H chains at same Y, V chains at same X).
2. Chain length ratios (sibling chains — e.g. repeated door openings in a patch — must correct symmetrically).
3. Shared chain identity (a chain used by two patches is one variable, not two).

Previous incremental approaches (row/column snap, closure redistribution, per-pair alignment) solved these concerns sequentially and allowed the grid to slip "somewhere." This plan eliminates the sequence: all three live in one sparse solve over two independent 1D axes.

This plan also consolidates one piece of IR modernization inline: `ChainUse` as a first-class entity (Phase S0b). The rationale is that deferring IR changes that are relevant to the new solver would create architectural debt that next-agent-with-no-context would not see in green tests and would reinforce. Doing it here, under explicit regression coverage, is lower total risk than deferring.

## Reading list (mandatory, in order)

1. `AGENTS.md` — project invariants, IR rules, frontier vs scaffold distinction.
2. `docs/cftuv_architecture.md` — layer model, PatchQuilt, Junction, Chain semantics.
3. `docs/cftuv_reference.md` — chain classification (H/V/FREE after MESH_BORDER resolution), scaffold build, FrontierRuntimePolicy.
4. `cftuv/solve_frontier.py` — current frontier; skeleton solve runs AFTER frontier. Frontier is also the main consumer of per-patch chain orientation that S0b migrates.
5. `cftuv/solve_diagnostics.py` — existing ScaffoldClosureSeamReport, ScaffoldFrameAlignmentReport. These produce the drift measurements we now correct in one pass.
6. `cftuv/model.py` (Junction, Chain, Patch, ContinuationEdge definitions) — types we will augment and the existing cross-patch-use hint we will integrate with.
7. `cftuv/analysis_boundary_loops.py` — where boundary loops are constructed. S0b extends this to produce ChainUse instances during loop construction.
8. `cftuv/analysis_corners.py` — corner detection. One of the consumers to migrate in S0b.

Do not begin implementation until all eight are read and the agent can answer internally:
- Which chain roles participate in the skeleton? (H, V — NOT FREE, NOT MESH_BORDER; MESH_BORDER is resolved upstream.)
- What is a junction's current role in IR? (corner container, valence counter, currently ignored by solver.)
- Where is per-patch chain orientation currently derived? (Distributed; S0b consumer migration list identifies all sites.)
- What does `ContinuationEdge` represent today, and what part of its role does ChainUse absorb vs preserve?

---

## Behavioral constraints

- **Do not modify frontier placement strategy or scaffold build logic.** S0b migrates frontier to ChainUse but must preserve placement sequence byte-identically (verified by telemetry regression). Skeleton solve (S1+) is a post-frontier correction pass.
- **Do not introduce new chain classifications.** Two kinds remain: H/V and FREE. MESH_BORDER is a temporary tag resolved upstream.
- **Do not add a new drift correction heuristic elsewhere.** If the skeleton solve is active and working, existing partial corrections in `solve_frontier.py` and `solve_diagnostics.py` are retired. The plan handles retirement explicitly (Phase S5).
- **Do not use ad-hoc tolerance bucketing for row/column detection.** Row and column membership is topological: connected components of junction-graphs over H-chain edges and V-chain edges respectively. 3D geometry is used only as post-hoc safety check, never as grouping source.
- **Do not implement cotangent Laplacian, graph Laplacian regularization, cycle basis, or Horton's algorithm.** These appear in prior design discussion but are out of scope for P7.
- **Sibling equivalence detection starts minimal.** Phase S3 gives a specific, bounded rule. Broadening the rule is a separate plan.
- **Do not attempt CornerFan (F2) or prev/next (F3) refactoring during P7.** These remain deferred as explicit architectural debt markers (see Backlog and Debt Marking sections below).
- **Do not ship any phase without the regression steps listed in its acceptance section.** S0b in particular requires ≥ 5-mesh snapshot regression before merge.

---

## Overall pipeline placement

```
... frontier build (frontier placement preserved; consumer-only migration in S0b)
      |
      v
[NEW] P7 Skeleton Solve
   ├─ S0:  Facade APIs on Junction and Patch (stable surface)
   ├─ S0b: ChainUse as first-class IR entity (risk-critical migration)
   ├─ S1:  Augment Junction with skeleton fields
   ├─ S2:  Build row-graph, column-graph via union-find
   ├─ S3:  Detect sibling equivalence groups
   ├─ S4:  Assemble + solve two sparse LSQ systems
   ├─ S4:  Write canonical u_col/v_row to Junction
   ├─ S4:  Rebuild chain points from junction UV
   └─ S5:  Pipeline integration, retire legacy correction, diagnostics, debt markers
      |
      v
Conformal solve (unchanged, receives cleaner pins)
```

Entry point for skeleton solve: new function `apply_skeleton_solve(quilt, diagnostics)` in new module `cftuv/solve_skeleton.py`. Called from `solve.py` after frontier completion, before conformal dispatch.

S0 and S0b both modify IR surface. S1–S5 do not modify IR structure — they only add new computation and new junction fields.

---

## Phase S0 — Facade APIs

**Goal.** Expose two read-only façade methods over IR that later phases consume directly. These methods exist permanently — they are the stable external API, not a temporary shim.

**APIs to add.**

1. `Junction.ordered_disk_cycle() -> list[ChainIncidence]`
   - Returns chains incident to the junction in stable circular order.
   - `ChainIncidence` fields: `chain_use` (the ChainUse instance after S0b), `role`, `side` (start or end relative to the ChainUse), `angle` (radians, in junction-local 2D frame from WORLD_UP projection).
   - Implementation: aggregate existing per-patch corner data; sort by `angle`. Compute on demand; no caching unless profiling requires.
   - Read-only.

2. `Patch.iter_boundary_loop_oriented(loop_index: int = 0) -> Iterable[ChainUse]`
   - Iterates ChainUse instances of the specified boundary loop (0 = outer, ≥ 1 = holes) in canonical traversal direction.
   - S0 and S0b ship in the same commit series — the façade final shape is `Iterable[ChainUse]` from the start. A transitional `Iterable[tuple[Chain, int]]` shape exists only if S0b is delayed beyond S0 merge; avoid that split if possible.
   - Read-only.

**Acceptance.**
- `ordered_disk_cycle` returns expected circular order on: synthetic junction with 4 chains (HHVV), 3 chains (HVV T-junction), 5 chains (star), 2 chains (mesh border corner).
- `iter_boundary_loop_oriented` yields ChainUse instances consistent with a documented convention (e.g. for rectangular patch with CCW outer loop, bottom-H chain's ChainUse has axis_sign=+1 in +U direction, top-H has axis_sign=-1). Convention documented in module docstring.
- Sanity test: for every H chain in every patch, `chain_use.axis_sign` matches the sign of `(J_end.world_u - J_start.world_u)`.
- No regression in existing snapshot tests.

**Size.** Small (100–200 LOC including tests).

---

## Phase S0b — ChainUse as first-class IR entity

**Goal.** Introduce `ChainUse` as a dedicated IR object representing a specific usage of a chain by a specific patch. Migrate all consumers of per-patch chain orientation from ad-hoc derivation to direct `ChainUse` access. This is the riskiest phase of P7 and is executed before skeleton solve (S1+) begins, under full regression coverage.

**Rationale.** Per-patch chain orientation and role are currently scattered across frontier placement, corner detection, validation, transfer, debug, and implicitly in ContinuationEdge for cross-patch seams. Before introducing skeleton solve as a new consumer, the truth must live in one object. Otherwise skeleton solve adds another ad-hoc derivation site, worsening the state this phase exists to fix. Deferring ChainUse also creates debt that next-agent-with-no-context will not see in green tests and will reinforce unintentionally — see "Marking architectural debt" section below.

**Data model.**

```python
@dataclass(frozen=True)
class ChainUse:
    chain_id: ChainId                   # back-reference to Chain
    patch_id: PatchId                   # owning patch
    loop_index: int                     # 0 = outer boundary, >= 1 = inner holes
    position_in_loop: int               # ordinal within the loop (0..len(loop)-1)
    axis_sign: Literal[-1, +1]          # +1 if chain.points[0] -> chain.points[-1] matches loop traversal
    role_in_loop: ChainRole             # H, V, or FREE; usually identical to Chain.role
```

`Chain` keeps geometry, classification, topological identity, 3D length.
`ChainUse` keeps per-patch orientation, loop membership, loop position, axis sign.

**Invariants.**

1. Every chain appearing in at least one patch's boundary loop has ≥ 1 ChainUse.
2. Shared chain between P1 and P2 has exactly 2 ChainUse instances (one per patch).
3. MESH_BORDER chain (no neighbor patch) has exactly 1 ChainUse.
4. SEAM_SELF chain has 2 ChainUse instances with same `patch_id` but differing `loop_index` or `position_in_loop`.
5. ChainUse is immutable after construction. Chain.points mutations (e.g. skeleton solve rebuilds) do not alter any ChainUse.
6. For each patch P and loop L: iterating ChainUse instances in ascending `position_in_loop` produces the canonical loop walk used by frontier.
7. For shared chains (invariant 2), the two ChainUse instances have opposite `axis_sign` — they traverse the same edge in opposite directions from the perspective of their respective patches.

**Construction.**

Extend `analysis_boundary_loops.py` loop construction. For each patch P and each of its boundary loops L_i:
- For each chain C appearing at position k in L_i:
  - Derive `axis_sign` from whether C.points natural order matches loop traversal at position k.
  - Derive `role_in_loop` from C.role (verify edge cases: bevel-absorbed, point-contact-downgraded, U-shape SEAM_SELF).
  - Instantiate `ChainUse(chain_id=C.id, patch_id=P.id, loop_index=i, position_in_loop=k, axis_sign=sign, role_in_loop=role)`.
- Attach ChainUse instances to PatchQuilt, indexed by (chain_id, patch_id) for lookup.

**Relationship with ContinuationEdge.**

ContinuationEdge is not removed by S0b. It encodes seam-through-corner continuation semantics that ChainUse does not cover. Migration plan:
- Where ContinuationEdge callers use it purely to recover per-patch orientation, switch them to ChainUse.
- Where ContinuationEdge callers need continuation semantics (which chain continues through which corner across a seam), preserve the existing use.
- Post-S0b audit: if ContinuationEdge has no remaining callers, mark for removal in S5 retirement list. If callers remain, ContinuationEdge stays as-is with no changes.

**Consumer migration list (explicit, agent audits each).**

Each site below is inspected; ad-hoc orientation derivation is replaced with ChainUse access. Agent produces a per-site migration note in the S0b completion report.

1. `solve_frontier.py` — frontier placement queries for per-patch chain orientation. Primary consumer.
2. `analysis_corners.py` — corner detection reads chain role in loop context.
3. `solve_transfer.py` — UV transfer to BMesh reads per-patch chain points in oriented order.
4. `solve_diagnostics.py` — validation re-derivation of orientation.
5. Debug / Grease Pencil visualization sites that iterate loops in patch-local order.
6. Any grep hit for identifiers like `_derive_chain_orientation`, `_chain_direction_in_patch`, `axis_sign`, `loop_walk`, `per_patch_order` — full audit required.

**Acceptance criteria (strict — this is the risk-critical phase).**

1. **Snapshot regression on ≥ 5 production meshes.** All existing CFTUV output (frontier placement sequence, corner detection result, UV transfer output, debug visualization) must be byte-identical or visually identical to pre-S0b output. Divergences must be explained and approved before merge.
2. **Frontier telemetry comparison.** `FrontierTelemetryCollector` output (placement steps, anchor reasoning, stall events) compared step-by-step. Identical.
3. **Unit tests for all 7 ChainUse invariants** against synthetic fixtures: single patch, shared chain, SEAM_SELF, MESH_BORDER, U-shape, bevel-absorbed chain, patch with inner hole.
4. **Consumer migration audit.** Per-site migration notes in completion report. Any site still deriving orientation ad-hoc is flagged as incomplete.
5. **Performance sanity.** PatchQuilt construction time not regressed more than 10% on production meshes.
6. **ContinuationEdge decision documented.** Either kept with stated reasons, or listed in S5 retirement list with justification.

**Rollback strategy.**

If S0b causes regressions that cannot be resolved within a reasonable time budget: revert S0b commit series; P7 continues on a simpler branch with façade-only S0 and ChainUse deferred to post-P7. The façade-only branch is slower overall (skeleton solve S4 re-derives orientation from patch loop each chain) but not blocking. The rollback is clean because S0 façade signatures are designed to accommodate both shapes.

Rollback authority: human approval required. An agent may not unilaterally roll back S0b.

**Size.** Large (1000–1500 LOC including tests). Largest single phase in P7.

---

## Phase S1 — Junction IR augmentation

**Goal.** Add fields that S2+ populate. Assumes S0 and S0b are in place.

**Changes.**

1. In `cftuv/model.py`, add to `Junction`:
   - `row_component_id: int | None = None` — set by S2.
   - `col_component_id: int | None = None` — set by S2.
   - `canonical_u: float | None = None` — set by S4.
   - `canonical_v: float | None = None` — set by S4.
   - `skeleton_flags: SkeletonFlags = SkeletonFlags(0)` — flag bitfield (SINGULAR_SPLIT, PURE_FREE, UNCONSTRAINED_COL, UNCONSTRAINED_ROW).

2. Do not change junction construction in `analysis_junctions.py`. Fields default to None; S2 populates.

3. `Junction.ordered_disk_cycle()` (from S0) already delivers circular-order access. Do not add a second accessor.

**Acceptance.**
- IR roundtrip preserves new fields as None.
- `apply_skeleton_solve` not yet called from pipeline — only module skeleton exists.
- No regression in existing snapshot tests.

**Size.** Small (≤ 100 LOC).

---

## Phase S2 — Row/column graph construction

**Goal.** Build two undirected graphs over junctions. Row-graph edges are H chains; column-graph edges are V chains. Compute connected components via union-find. Populate `row_component_id` and `col_component_id` on every junction. Detect and resolve singular-junction conflicts.

**New module.** `cftuv/solve_skeleton.py`.

**Data structures.**

```python
@dataclass
class SkeletonGraphs:
    row_parent: dict[JunctionId, JunctionId]
    col_parent: dict[JunctionId, JunctionId]
    row_component_members: dict[int, list[JunctionId]]
    col_component_members: dict[int, list[JunctionId]]
    row_component_of_junction: dict[JunctionId, int]
    col_component_of_junction: dict[JunctionId, int]
    singular_unions: list[SingularUnionReport]
```

**Algorithm.**

1. Initialize union-find over all junction IDs for both row and col graphs.
2. For each H chain (role inspected via ChainUse), union its two endpoint junctions in row-graph.
3. For each V chain, union its two endpoint junctions in col-graph.
4. FREE chains are ignored — they do not participate in skeleton graphs.
5. Compute canonical representatives; assign integer `row_component_id`, `col_component_id` to each junction.
6. **Safety pass.** For each row-component:
   - Collect 3D Y coordinates of member junctions.
   - If `max(Y) - min(Y) > SKELETON_ROW_SPREAD_TOLERANCE`, the component is inconsistent.
   - Use `Junction.ordered_disk_cycle()` (S0) to inspect circular incidence at candidate singular junctions. Identify the junction whose removal would minimize spread.
   - Split it: create a phantom junction instance for graph purposes, reassign one of its H-chain endpoints to the phantom, redo union-find for the affected subset.
   - Record action in `singular_unions`.
7. Repeat for col-components with 3D X tolerance.

**Tolerances (in `cftuv/constants.py`).**
- `SKELETON_ROW_SPREAD_TOLERANCE = 0.01` (meters; 1 cm). Tunable.
- `SKELETON_COL_SPREAD_TOLERANCE = 0.01`.

**Singular split policy.**
- Splitting is a last resort. Prefer to report the conflict and fail-open (leave component merged, flag with `UNCONSTRAINED_ROW`) if the split would isolate a well-connected junction.
- Split is considered only for junctions with valence ≥ 5. Valence-3 conflicts indicate upstream classification error, not a candidate for split.
- Every split logged via `SingularUnionReport`.

**Acceptance.**
- Synthetic test: L-shaped wall (two patches, shared V chain). Both patches' junctions at the shared seam share one col_component_id. Row-components match expected floor/ceiling lines.
- Synthetic test: star junction with five H chains, five Y levels within spread tolerance. One row-component, no split.
- Synthetic test: star junction with five H chains across two Y groups outside tolerance. Split invoked, report emitted.
- Real mesh: component counts and member lists printed; manual inspection confirms correctness on `walls_a.007` and 2–3 other production meshes.

**Size.** Medium (300–500 LOC with tests).

---

## Phase S3 — Sibling equivalence detection

**Goal.** Identify groups of H chains (or V chains) that must correct symmetrically. Minimal initial rule; broader rules deferred.

**Rule (initial).**
Two chains `c1`, `c2` are siblings iff:
- Same role (both H or both V).
- Same patch.
- Both endpoints of `c1` are in different row-components than both endpoints of `c2` (ensures they are not trivially the same length via shared variables). Symmetrically for V chains and col-components.
- `|length_3d(c1) - length_3d(c2)| < SKELETON_SIBLING_LENGTH_TOLERANCE`.

**Tolerance.**
- `SKELETON_SIBLING_LENGTH_TOLERANCE = 0.001 * max(length_3d(c1), length_3d(c2))` — relative, 0.1% of the longer chain. Tunable.

**Output.**
- `SiblingGroup(role: Literal["H", "V"], members: list[ChainId], target_length: float)`.

**What the rule deliberately excludes.**
- Cross-patch siblings. Promote to a second rule only if S5 validation shows asymmetric correction across patches on production meshes.
- Length-based grouping without structural context.

**Acceptance.**
- Synthetic test: patch with two identical doorway openings. H-chains at door tops form a sibling group; V-chains at door sides form groups.
- Synthetic test: patch with one door and one window at different heights and widths. No sibling group.

**Size.** Small (100–200 LOC with tests).

---

## Phase S4 — Assembly, solve, write-back

**Goal.** Build two independent sparse systems (U-axis, V-axis), solve each, write canonical positions to junctions, rebuild chain points.

**Variables (U-axis system).**
- One variable per col-component: `u[c]` for `c in col_component_ids`.

**Equations (U-axis system).**
- **(E1) Length equations.** For each H chain `h` from junction `J_a` (col-component `c_a`) to `J_b` (col-component `c_b`), using the ChainUse in the iterating patch:
  `u[c_b] - u[c_a] = chain_use.axis_sign * L_3d(h)`
  `axis_sign` is direct field access — no runtime derivation.
- **(E2) Sibling equivalence.** For each H-chain sibling group `G = [h_1, ..., h_n]`:
  For `k in [2..n]`: `(u[c_b(h_k)] - u[c_a(h_k)]) - (u[c_b(h_1)] - u[c_a(h_1)]) = 0`.
  Soft weight: `SKELETON_SIBLING_WEIGHT = 5.0`. Hard weight for length: `1.0`.
- **(E3) Gauge fixing.** System rank-deficient by 1. Pin one col-component to u=0 — the one containing the seed junction used by frontier. Weight: 10^6.

**V-axis system.** Symmetric over V chains and row-components.

**Sparse assembly.**
- `scipy.sparse.lil_matrix` during build, convert to `csr_matrix` before solve.
- Weight matrix `W` row-wise: multiply row `i` of `A` and entry `i` of `b` by `sqrt(w_i)`.

**Solve.**
- `scipy.sparse.linalg.lsmr(A_weighted, b_weighted)` per axis.
- Log residual norm and iteration count. If residual > `SKELETON_MAX_RESIDUAL_WARN`, warn and continue.

**Write-back.**
- For each junction `J` in row `r`, col `c`: `J.canonical_u = u[c]`, `J.canonical_v = v[r]`.
- Pure-FREE junctions: `canonical_u`/`canonical_v` left as None.

**Chain point rebuild.**
- H/V chain endpoints receive canonical positions. Interior subdivided points interpolated linearly between new endpoints.
- FREE chains rebuilt via existing `_cf_rebuild_chain_points_for_endpoints` with updated endpoints.

**Acceptance.**
- Rectangular single patch with correct frontier placement — skeleton solve returns identity (zero residual).
- Rectangular single patch with injected drift — correction distributes via sibling group or falls on the drifted chain alone.
- L-shape two patches with shared V seam, one patch with injected cross-axis scatter — post-solve, shared junction matches in both patches. Scatter across row-component below residual tolerance.
- Real mesh `walls_a.007`: pre/post metrics. Expected `ScaffoldFrameAlignmentReport.scatter_max` reduction ≥ 90% on affected groups.

**Size.** Medium (400–600 LOC with tests).

---

## Phase S5 — Integration, retirement, diagnostics, debt markers

**Goal.** Hook `apply_skeleton_solve` into pipeline, retire existing partial correction paths, surface skeleton diagnostics, install architectural debt markers for anything deliberately deferred.

**Integration.**
- In `solve.py`, after frontier completion and before conformal dispatch: call `apply_skeleton_solve(quilt, diagnostics_collector)`.
- Guard with feature flag `USE_SKELETON_SOLVE` in `constants.py`. Default True after S4 acceptance passes.

**Retirement list.**
- Partial correction logic in `solve_frontier.py` (ad-hoc scatter averaging in placement).
- Row/column snap attempts anywhere in codebase.
- ContinuationEdge — if S0b audit concluded it has no remaining callers, mark for removal; otherwise leave.
- Mark retiring code with `# RETIRED by P7 skeleton solve, remove after 2 release cycles` rather than deleting immediately.

**Diagnostics.**
- New report `SkeletonSolveReport` with: row/col component counts, singular_unions, sibling_groups, residual norms per axis, pure_free_junctions count, unconstrained_rows/cols counts.
- Surfaced via existing `solve_reporting.py`.

**Holonomy pre-check (optional, diagnostic only).**
- For each independent cycle in patch-graph, compute turn-sign sum.
- If sum is not a multiple of 2π within tolerance, emit `HolonomyReport` flagging the cycle as trim-incompatible.
- Informational, not used for correction.
- Implement only if S4 validation shows residual norms hinting at cyclic incompatibility.

**Debt markers (required — see Debt Marking section below for convention).**
- Install `ARCHITECTURAL_DEBT: F2_CORNERFAN` markers at each site currently reconstructing circular order around junctions (beyond `Junction.ordered_disk_cycle()` itself).
- Install `ARCHITECTURAL_DEBT: F3_LOOP_PREVNEXT` markers at frontier corner-turn sites that walk loops to find prev/next ChainUse.
- Create `docs/architectural_debt.md` with ledger entries for F2 and F3.
- Add "Architectural debt" onboarding paragraph to `AGENTS.md`.

**Acceptance.**
- Feature flag toggles between legacy and new path cleanly.
- At least 3 real production meshes show measurable drift reduction.
- Grease Pencil debug renders skeleton junctions with canonical positions correctly.
- Debt ledger exists, markers are grep-able, AGENTS.md references ledger.

**Size.** Medium (200–300 LOC plus ledger doc and AGENTS.md update).

---

## Non-goals / deferred

Explicitly out of scope for P7.

- Cross-patch sibling equivalence.
- Cotangent weights / geometric regularization.
- Graph Laplacian smoothing.
- QP formulation with box constraints.
- Replacing conformal solve.
- Modifying frontier placement strategy (S0b migrates consumers only; placement logic unchanged).
- CornerFan (F2) and prev/next (F3) refactoring — deferred as marked debt.
- Handling non-manifold junctions beyond valence-5+ split case.

---

## Future IR refactoring (post-P7 backlog)

F1 (ChainUse) is no longer in this backlog — it is delivered as S0b inline with P7.

### At a glance

| ID | What | Primary beneficiary | Rough payoff |
|----|------|--------------------|--------------|
| F2 | `CornerFan` as first-class entity | Corner detection, bevel, singular-junction handling | ~200–400 LOC of scattered circular-order logic consolidated |
| F3 | `prev/next` on `ChainUse` within loop | Frontier, corner-turn reasoning | Low-hundreds LOC, faster loop-neighbor queries |

### Backlog item F2 — CornerFan as first-class entity

- **What.** A dedicated object per junction holding the circularly-ordered disk cycle of incident chains with their sides, angles, and roles. Replaces the on-demand computation in `Junction.ordered_disk_cycle()`.
- **Why not in P7.** Corner detection and bevel absorption are the most heavily debugged modules in CFTUV. Their invariants are fragile and have been iterated on for months. F2 without a second real consumer beyond skeleton solve is premature consolidation — higher risk than payoff at this point.
- **Touches.** `model.py` (new class, field on `Junction`), `analysis_junctions.py`, `analysis_corners.py`, `solve_skeleton.py` (S2 safety valve becomes cleaner).
- **Trigger to execute.** When any of the following is true:
  - Bevel-detection work in `analysis_corners.py` is reopened for an unrelated reason (natural consolidation moment).
  - A third consumer of circularly-ordered disk cycles is introduced beyond skeleton solve and existing corner detection.
  - OUTER/HOLE classification work is reopened.
- **Marker location.** `ARCHITECTURAL_DEBT: F2_CORNERFAN` at each site currently reconstructing circular order. Installed during S5.

### Backlog item F3 — Chain next/prev within boundary loop

- **What.** Explicit prev/next references on `ChainUse` within its boundary loop context. Replaces on-the-fly loop iteration for neighbor queries.
- **Why not in P7.** Skeleton solve gains nothing directly from F3; the primary beneficiary is frontier corner-turn logic. Proper F3 execution should coincide with a dedicated frontier simplification pass.
- **Touches.** `model.py` (fields on `ChainUse`), loop construction in `analysis_boundary_loops.py`, frontier neighbor-query sites.
- **Trigger to execute.** When a frontier simplification or corner-turn cleanup plan is opened. F3 is a companion change, not a standalone motivation.
- **Marker location.** `ARCHITECTURAL_DEBT: F3_LOOP_PREVNEXT` at frontier corner-turn sites and loop-walking neighbor-query sites. Installed during S5.

---

## Marking architectural debt for AI agents

This section codifies a project-wide convention for how deliberate architectural debt is recorded so that future AI agents (who typically start each session without context from prior planning work) will physically encounter the debt at the exact code sites where it lives.

### Problem

AI agents, including Claude Code and similar, are strong at producing new code that matches existing patterns. They are weaker at recognizing that an existing pattern is suboptimal when all tests pass. A design issue documented only in a planning document is invisible during implementation — the agent reads the code, sees green tests, and builds on top of the existing shape. Over time, a pattern that was meant to be temporary spreads to more sites and becomes progressively harder to consolidate.

"Nothing is more permanent than something temporary" is an operational risk, not a platitude. Planning documents alone do not prevent this.

### Convention for CFTUV

**1. In-code markers at every debt site.**

Every location participating in known architectural debt carries a comment of this form:

```python
# ARCHITECTURAL_DEBT: F2_CORNERFAN
# Circular disk-cycle order is recomputed inline here rather than sourced from a
# dedicated CornerFan object. See docs/architectural_debt.md#F2_CORNERFAN for
# trigger conditions and consolidation plan.
```

The ID (`F2_CORNERFAN`) is the grep key. The one-line description tells the agent what is suboptimal. The reference to the ledger tells the agent where to find full context.

**2. Centralized ledger: `docs/architectural_debt.md`.**

One file, enumerating all active debt IDs. For each ID:
- Summary — what the design issue is.
- Affected files and functions.
- Why not resolved immediately (original decision context).
- Trigger conditions — concrete circumstances under which the debt should be paid down.
- Estimated payoff.
- Link to originating planning doc for deeper history if needed.

The ledger is short and read-once. Agents that encounter an in-code marker are directed to the matching section of this file.

**3. Onboarding instruction in `AGENTS.md`.**

A short paragraph near the top of AGENTS.md:

> **Architectural debt.** This codebase contains `ARCHITECTURAL_DEBT: <ID>` markers at sites with known suboptimal design. Before substantially modifying any file containing such a marker, read `docs/architectural_debt.md` and check whether your planned change should trigger debt pay-down. If the change reinforces the debt pattern in a new location, flag this and ask the human whether to consolidate now or install an additional marker.

**4. Initial entries after P7.**

S5 installs markers for F2_CORNERFAN and F3_LOOP_PREVNEXT, and creates corresponding ledger entries. F1 is not an entry because P7 resolves it inline as S0b.

### Limitations and mitigation

The convention relies on agents respecting the marker instruction. This is not guaranteed — an agent instructed "just fix the bug" may skip reading the ledger.

Mitigations:
- The marker convention is cheap (a comment at the code site), so a skipping agent at least produces code adjacent to the marker; the next human review surfaces it.
- Standard project-level agent prompts (in AGENTS.md onboarding) should explicitly include marker-check as a pre-implementation step.
- CI can optionally count `ARCHITECTURAL_DEBT:` markers per PR and surface changes (new markers added, markers removed) in review.
- Over time, agents operated with this pattern in their standard rotation learn to treat markers as mandatory reading.

The convention is imperfect but strictly better than zero in-code signal. Without markers, the only defense against the "temporary becomes permanent" failure mode is human memory, which does not scale across agent-driven workflows.

### Scope

This convention applies project-wide, not just to P7 debt. If future work identifies additional debt sites, add a marker and a ledger entry at the time of identification. Do not wait for a dedicated planning cycle.

---

## Verification summary (pre-merge checklist)

Before merging the full P7:

1. **S0b snapshot regression** — ≥ 5 production meshes, byte-identical or visually identical output to pre-S0b.
2. **S0b frontier telemetry parity** — placement steps, anchor reasoning, stall events identical.
3. All ChainUse invariant unit tests pass.
4. S2/S3/S4 synthetic acceptance tests pass.
5. At least 3 real production meshes show drift reduction with no conformal output regression.
6. `ScaffoldFrameAlignmentReport.scatter_max` improved ≥ 90% on affected groups.
7. `ScaffoldClosureSeamReport.axis_phase_offset_max` improved ≥ 80%.
8. No new frontier stalls (sanity check — frontier logic unchanged).
9. Feature flag `USE_SKELETON_SOLVE=True` produces identity on meshes where legacy path had zero drift.
10. Debt markers F2_CORNERFAN and F3_LOOP_PREVNEXT installed; `docs/architectural_debt.md` exists; AGENTS.md references it.
11. Diagnostic report `SkeletonSolveReport` readable, actionable, consistent with existing report style.

---

## Phase dependency graph

```
S0  (façade APIs)        ── required by ──> S0b, S2, S4
S0b (ChainUse)           ── required by ──> S1, S2, S4, S5
S1  (Junction fields)    ── required by ──> S2, S4
S2  (graphs)             ── required by ──> S3, S4
S3  (siblings)           ── required by ──> S4
S4  (solve)              ── required by ──> S5
S5  (integration, debt)  ── final step
```

S0 and S0b together modify IR. Neither S1 nor anything after it may begin until S0b has passed its regression gate.

S1 may proceed in parallel with S3 design once S0b is complete. S2 implementation begins after S1 lands. S4 requires all prior phases. S5 is strictly last.

---

## Open questions for human review

1. **S0 disk-cycle 2D frame** — WORLD_UP-projected tangent is the natural choice; confirm edge cases for slope patches. Answered in S0 completion report.
2. **S0 loop orientation convention** — CW vs CCW for outer loop. Confirm against existing frontier assumption. Answered in S0 completion report.
3. **ContinuationEdge fate after S0b** — kept, reduced, or retired. Answered in S0b completion report based on consumer audit outcome.
4. **Seed-junction choice for gauge fixing (S4)** — confirm frontier seed junction translates cleanly to seed col-component. Answered in S1 completion report.
5. **Sibling group weight (S4 E2)** — initial 5.0. Tune during S4 acceptance. Final value documented.
6. **Singular split heuristic (S2)** — valence ≥ 5 as first cut. Propose final heuristic after seeing real meshes.

Questions 1–2 must be answered in the S0 completion report. Question 3 in the S0b completion report. Question 4 in the S1 completion report. Questions 5–6 in the S4 completion report.
