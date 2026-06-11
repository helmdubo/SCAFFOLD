# UV Tracer & G3 Revision Plan

Status: active plan
Owner: Architect session
Scope: G3 revision slices + first vertical UV tracer
Workflow: `docs/agent_rules/planning_workflow.md` (one Task Card per disposable
agent session; reviewer gate mandatory)

This plan supersedes "next evidence slice" planning. Its goal is to validate
the Layer 3 evidence vocabulary against a real consumer (a skeleton frontier
producing pinned UVs) before any further evidence kinds are added.

---

## Standing rules for all Task Cards in this plan

1. **Evidence moratorium.** Do not add new Layer 3 evidence record types or
   relation kinds. New distinctions must wait until the tracer (Slice E)
   shows they are consumed. Exception: ConnectedDirectionFamily v0 (Slice D),
   which is explicitly planned here.
2. **Fixtures over blend files.** Contracts must be expressed against
   in-repo synthetic fixtures, never against local `.blend` exploratory
   files (no new Cube.001-style references in DD text).
3. **KNOWN LIMITATION tests** in
   `scaffold_core/tests/test_canonical_fixture_baselines.py` document
   current wrong/missing behavior. A slice that fixes the behavior must
   flip the matching test in the same Task Card, not delete it.
4. G0.md remains read-only for agents. Where a slice needs a G0 amendment,
   the Task Card says so and the Architect drafts the amendment for user
   approval first.

---

## Current state (baseline, 2026-06)

Canonical fixture package landed (Slice A below, done):

```text
scaffold_core/tests/fixtures/detached_parallel_walls.py
scaffold_core/tests/fixtures/beveled_wall_corner.py      (single chamfer + rounded 2-segment)
scaffold_core/tests/fixtures/l_corridor_tunnel.py        (single patch + seamed folds)
scaffold_core/tests/fixtures/tube_with_cap.py
scaffold_core/tests/test_canonical_fixture_baselines.py
```

Documented findings from the fixtures (each is a pinned baseline test):

```text
F1. detached_parallel_walls:
    two disconnected walls share AlignmentClasses by world-direction
    coincidence (global greedy clustering in
    layer_3_relations/alignment.py:build_alignment_classes).

F2. beveled_wall_corner:
    the horizontal surface flow around the chamfered corner is fully lost:
    three single-patch horizontal families, zero continuation candidates,
    all continuity components singletons. This is the priority middle-poly
    production case.

F3. l_corridor_tunnel_seamed_folds:
    6 MISSING_ENDPOINT_EVIDENCE pairs at fold nodes; floor+ceiling length
    chains merge by world parallelism while the wall stays separate; all
    continuity components singletons.

F4. tube_with_cap — CONTRACT VIOLATION (DD-39):
    SURFACE_SLIDING_CONTINUATION_CANDIDATE is emitted between the tube top
    ring and the cap rim, and ScaffoldContinuityComponent merges cap with
    side. The planar diamond cap presents dual-axis PatchAxes and slips
    past the cap-like single-axis gate of SurfaceFlowCompatibilityEvidence
    rule B. DD-39 forbids exactly this merge.
```

Target artist scenario (fixed by user):

```text
select faces -> one button -> patches assemble into UV islands by
adjacency/relations; rigid skeleton (rails) is laid out first by a
priority frontier; skeleton vertices are pinned; remaining vertices are
solved by standard conformal unwrap.
```

Stitch-vs-split decision frame (agreed direction, to be encoded gradually):

```text
Level A (Layer 3, hard, geometric):
  developability of the would-be merged region (discrete Gaussian
  curvature / angle defect of vertices that become interior),
  SEAM_SELF always splits (plus equal-length parametrization invariant),
  length compatibility.

Level B (Layer 4/5, soft, semantic):
  when distortion cost is ~0 (e.g. cube walls), geometry cannot decide;
  trim policy, texel orientation and packing decide. Runtime-only labels
  (DD-04/DD-05) may return HERE, never in Layer 1/2/3.
```

---

## Slice A — Canonical fixture package (DONE)

Landed on branch `claude/nifty-bohr-pv623i`. See "Current state" above.

---

## Slice B — Contract repairs and cheap infrastructure

### Task Card B1 — Fix DD-39 cap/side sliding violation (F4)

Why now: an implemented contract is violated; the fix is a gate correction,
not a redesign.

```text
GOAL
  tube_with_cap must not emit SURFACE_SLIDING_CONTINUATION_CANDIDATE
  between side top ring and cap rim; cap and side ScaffoldEdges must stay
  in separate continuity components.

INVESTIGATE FIRST
  why the cap passes the "compatible side/dual-axis, not cap-like
  single-axis" gate (SurfaceFlowCompatibilityEvidence rule B) or the
  SideSurfaceContinuityEvidence consumption path in
  scaffold_core/layer_3_relations/scaffold_graph_relations.py.
  Likely cause: planar diamond cap yields DUAL_ALIGNMENT PatchAxes, so
  "cap-like" cannot be detected from axis count alone. Owner-normal
  divergence between the two edge-end occurrences is the contract-named
  signal (DD-39: "not side-surface continuation when owner normals
  diverge") — prefer strengthening the normal compatibility requirement
  for cross-patch sliding promotion over inventing a new cap heuristic.

ACCEPTANCE
  1. No SURFACE_SLIDING_CONTINUATION_CANDIDATE between patches whose
     owner normals at the shared node diverge below the compatible-normal
     threshold (tube_with_cap case).
  2. test_tube_with_cap_documents_known_cap_side_sliding_violation is
     flipped to assert the contract (0 sliding pairs touching f_cap, no
     2-edge component containing f_cap) and renamed accordingly.
  3. Existing cylinder/cube-path tests stay green.
  4. Minimal patch protocol: no refactor, no renames.

ALLOWED FILES
  scaffold_core/layer_3_relations/scaffold_graph_relations.py
  scaffold_core/layer_3_relations/scaffold_continuity.py (only if needed)
  scaffold_core/tests/test_canonical_fixture_baselines.py

STOP CONDITIONS
  - fix requires changing ScaffoldNode/Edge identity -> return to Architect
  - fix requires a new evidence type -> return to Architect (moratorium)
```

### Task Card B2 — Vertex incidence index

Why now: `incident_patch_chains_for_vertex` scans all patch chains per call
(`patch_chain_incidence.py`); relation building calls it per vertex. This is
O(V*PC) per rebuild and grows quadratically on production meshes.

```text
GOAL
  one-pass vertex -> incident PatchChainIds index built once per Pass 1,
  consumed by incidence queries and continuation building.

ACCEPTANCE
  1. Index is built inside Layer 3 build (single rebuild scope, not a
     persistent cache; DD-16 full-rebuild policy preserved).
  2. incident_patch_chains_for_vertex result order/content unchanged
     (deterministic order test).
  3. build_chain_continuations consumes the index.
  4. No public model entity added.

ALLOWED FILES
  scaffold_core/layer_3_relations/patch_chain_incidence.py
  scaffold_core/layer_3_relations/continuation.py
  scaffold_core/layer_3_relations/build.py
  scaffold_core/tests/test_patch_chain_incidence.py

STOP CONDITIONS
  - index wants to live in Layer 1 -> return to Architect
```

### Task Card B3 — Angle defect as a Layer 2 fact

Why now: discrete Gaussian curvature (angle defect = 2*pi - sum of incident
face corner angles at a vertex; boundary vertices use pi) is the raw
measurement behind the Level A stitch-vs-split gate and distortion
diagnostics. It is a pure measured geometry fact, legal in Layer 2.

```text
GOAL
  per-vertex interior angle sum and angle defect stored as raw G2 facts.

ACCEPTANCE
  1. New fact fields measured in layer_2_geometry (vertex angle sum,
     boundary flag used for the defect baseline).
  2. No semantic interpretation in Layer 2 (no "developable" label —
     numbers only; classification happens later in Layer 3+).
  3. Tests: cube corner vertex defect = pi/2; flat interior vertex
     defect ~ 0; tunnel fold vertices defect ~ 0 (folds are developable).
  4. Inspection report includes the new facts behind detail="full".

ALLOWED FILES
  scaffold_core/layer_2_geometry/measures.py
  scaffold_core/layer_2_geometry/facts.py
  scaffold_core/layer_2_geometry/build.py
  scaffold_core/pipeline/inspection.py
  scaffold_core/tests/test_layer_2_geometry_facts.py

STOP CONDITIONS
  - any enum/label like DEVELOPABLE appears in Layer 2 -> stop
```

---

## Slice C — Endpoint evidence from topology (kills MISSING_ENDPOINT class)

### Task Card C1 — Topology-first endpoint samples

Why: F3 shows fold nodes lose endpoint evidence because samples derive from
the directional-run pipeline, which degrades on closed/turning chains. A
PatchChain end always has a first/last segment tangent in Layer 2 geometry,
so the sample can be built directly from topology + local segment geometry,
with the directional-run path kept as enrichment, not as a prerequisite.

```text
GOAL
  PatchChainEndpointSample exists for every PatchChain end that has at
  least one geometric segment, even when ChainDirectionalRun is UNKNOWN.

ACCEPTANCE
  1. l_corridor_tunnel_seamed_folds: MISSING_ENDPOINT_EVIDENCE count
     drops from 6 to 0 (flip the baseline assertion).
  2. Sample provenance distinguishes RUN_DERIVED vs LOCAL_SEGMENT sources.
  3. No change to PatchChain identity or Layer 1 records (DD-30).
  4. Existing endpoint relation tests stay green.

ALLOWED FILES
  scaffold_core/layer_3_relations/patch_chain_endpoint_samples.py
  scaffold_core/layer_3_relations/build.py
  scaffold_core/tests/test_patch_chain_endpoint_samples.py
  scaffold_core/tests/test_canonical_fixture_baselines.py

STOP CONDITIONS
  - requires new Layer 1 fields -> return to Architect
```

---

## Slice D — ConnectedDirectionFamily v0

Replaces global world-direction clustering as the rail-family source. This is
the agreed resolution direction for OQ-11 connectivity.

Design constraints (Architect-level, encode in the Task Card / DD draft):

```text
- Layer 3 derived evidence view; does not replace AlignmentClass yet
  (AlignmentClass stays until consumers migrate, then is revisited).
- Seed: PatchChainDirectionalEvidence.
- Propagation: across ScaffoldGraph adjacency only (no world comparison
  between non-adjacent patches). Two detached walls can never share a
  family (fixes F1 by construction).
- Transport: direction carried across a shared Chain is rotated by the
  signed dihedral (parallel transport). The tunnel length family becomes
  one family across floor/wall/ceiling (fixes F3 target).
- Gate: transport requires compatible owner normals at the crossing
  (same compatible-normal threshold as incident-edge relations) and
  non-degenerate evidence. Cap/side stays separated (consistent with B1).
- No dihedral threshold: user seams already encode cut intent; dihedral
  modulates HOW direction transports, never WHETHER (user decision).
- Output: family id per PatchChainDirectionalEvidence + per-crossing
  transport records with provenance/confidence.
- Must not choose traces, rails, circuits, UV directions (same
  restrictions as ScaffoldContinuityComponent).
```

### Task Card D1 — DD draft + contract doc (Architect output, user approves)

G0 amendment required (new derived relation + AlignmentClass demotion path).
Architect drafts; user approves; agents do not edit G0.

### Task Card D2 — Implementation + baseline flips

```text
ACCEPTANCE
  1. detached_parallel_walls: walls never share a family (flip F1 test).
  2. l_corridor_tunnel_seamed_folds: one length family across 3 patches
     (flip F3 length test), width family unchanged.
  3. beveled_wall_corner: horizontal chains of wall A + chamfer + wall B
     form one family (flip F2 test); vertical family unchanged.
  4. tube_with_cap: cap and side families stay separate.
  5. cylinder/cube regression tests green.

ALLOWED FILES
  scaffold_core/layer_3_relations/<new module per anti-overengineering
  naming rules — one concept, no utils/helpers>
  scaffold_core/layer_3_relations/model.py
  scaffold_core/layer_3_relations/build.py
  scaffold_core/pipeline/inspection.py
  scaffold_core/tests/ (new test module + baseline flips)
```

### Task Card D3 — Debug overlay channel

Family id as a deterministic color channel in the scaffold graph debug
addon (`dev/tools/scaffold_graph_debug`), same coloring rules as continuity
components (stable pseudo-random by id).

---

## Slice E — Vertical tracer: skeleton frontier to pinned UVs

Purpose: validate which Layer 3 evidence a real consumer actually uses.
This is a spike: branch-isolated, deletable, NOT a G5 phase start.

**Requires explicit user approval to relax the "no Layer 5 during G3" rule
for a spike branch.** The phase rule stays in force for mainline.

```text
SCOPE
  - input: fixtures beveled_wall_corner and l_corridor_tunnel_seamed_folds
    (synthetic path), plus optional Blender smoke on a simple wall mesh.
  - frontier v0: pick the longest ConnectedDirectionFamily as the spine;
    stitch decision Level A only (angle defect budget ~ 0 required);
    SEAM_SELF always splits; lay rails straight with arc-length
    parametrization; no FeatureConstraints, no pin policy, no packing.
  - output: UV coordinates for skeleton vertices + pinned flag; in
    Blender smoke, write pins and call the built-in pinned conformal
    unwrap for interior vertices (uv_transfer boundary file, spike only).
  - deliverable: a compact report listing WHICH relation records the
    frontier consumed and which it never read.

STOP CONDITIONS
  - any urge to add evidence types mid-spike -> note it in the report
    instead of implementing.

EXIT
  Architect reviews the consumption report and plans Slice F.
```

---

## Slice F — Post-tracer revision (plan after Slice E report)

Expected content, to be confirmed by the tracer report:

```text
- prune or merge evidence kinds the frontier never consumed;
- rewrite DD-41/DD-42 against fixture invariants (no blend-file pairs);
- deduplicate DD texts to one canonical home per fact
  (G0 = short normative text; design_decisions.md = full text;
  agent_handoff.md = status);
- split G0 changelog/status entries out of the constitution;
- define confidence semantics from frontier needs, or downgrade to
  ok/degraded.
```

---

## Decisions the user must approve before the relevant slice

```text
1. Slice D: G0 amendment for ConnectedDirectionFamily and the planned
   demotion path of global AlignmentClass.
2. Slice E: temporary spike exception to the "no Layer 5 during G3" rule.
3. Slice F: G0 restructuring (constitution vs status split).
```
