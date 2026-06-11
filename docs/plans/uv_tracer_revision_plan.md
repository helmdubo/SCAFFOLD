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
5. **Paired acceptance.** Every negative acceptance criterion ("X must not
   be emitted") must ship with a paired positive criterion ("Y must still
   be emitted") backed by an end-to-end fixture test. Lesson from the B1
   regression: the cap/side gate silently disabled legitimate rule A ring
   flow because no in-repo fixture pinned the positive case.

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

Landed via PR #2. See "Current state" above.

## Status update (2026-06)

- Slice B (B1, B2, B3) and Slice C (C1): DONE, merged to main.
- B1 follow-up: the first cap/side fix gated all SurfaceFlowCompatibility
  on compatible normals and silently regressed DD-39 rule A ring flow
  (two-seam tube). Fixed by scoping the normal gate to same-chain pairs;
  the two-seam tube maker and ring-flow baseline test now pin the
  positive case. Origin of standing rule 5.
- D1: DONE — DD-43 approved by user and committed (G0 v1.3).
- User approvals received: DD-43 amendment (Slice D), tracer spike home
  in dev/tools/tracer_spike/ (Slice E, no phase exception needed since
  the spike lives outside scaffold_core as consumer tooling).
- F3 endpoint part is resolved by C1; F1/F2/F3 family-grouping parts
  await D2.
- D2: DONE, merged to main (`d3e7b3e`). Architect review: PASS.
  All five DD-43 fixture expectations verified empirically; parallel
  transport is real (45-degree chamfer crossing rotates wall A's
  direction exactly onto the chamfer chord, tunnel folds transport at
  90 degrees, two-seam ring flow spans both side patches);
  AlignmentClass outputs untouched; no new relation kinds.

D2 review notes — known v0 conservatism, input for the tracer (E1):

```text
1. Isolated single-patch shapes yield only singleton families (lone
   wall quad, single-patch tunnel): the coalesced border chain is one
   ScaffoldEdge, and same-chain node crossings are skipped, so in-patch
   opposite rails are not grouped. The frontier must rely on PatchAxes
   for in-patch rail pairing, or a future in-patch grouping slice.
2. In the bevel fixture the outer vertical border runs of walls A/B stay
   singletons; the vertical family spans only seam-touching evidence.
   Same root cause as (1).
3. The rounded two-segment corner spans all three patches only by
   symmetry: the turning chain's chord coincides with the
   patch-average-normal dihedral. Asymmetric curved strips will
   conservatively split — this is the curved-chain OQ-11 remainder,
   now confirmed empirically. Fails closed, never over-merges.
4. adjacency_by_patch_pair keeps one PatchAdjacency per patch pair;
   pairs sharing two different chains (two-seam tube) keep an arbitrary
   one. Masked by symmetric fixtures; conservative on asymmetric ones.
   Candidate cleanup in Slice F.
5. direction_families digs source_edge_id/segment_index out of
   Evidence.data payloads — the shadow-API smell again; add to the
   Slice F evidence-payload cleanup list.
```

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

### Task Card D1 — DD draft + contract doc (DONE)

DD-43 approved by user and committed as G0 v1.3. Agents implement from
DD-43; they do not edit G0.

### Task Card D2 — ConnectedDirectionFamily v0 implementation

Note on baselines: AlignmentClass stays unchanged in v0 (DD-43), so the
existing KNOWN LIMITATION alignment assertions remain true and are NOT
flipped here. D2 adds family assertions alongside them. The alignment
flips happen only when AlignmentClass is demoted (Slice F or later).

```text
GOAL
  ConnectedDirectionFamily v0 per G0 DD-43: direction families propagated
  along ScaffoldGraph connectivity with signed-dihedral parallel
  transport, as a new Layer 3 evidence view. AlignmentClass untouched.

ACCEPTANCE (fixture expectations are DD-43 verbatim)
  1. detached_parallel_walls: the two walls never share a family.
  2. l_corridor_tunnel_seamed_folds: one length family across floor,
     wall and ceiling; one width family.
  3. beveled_wall_corner: one horizontal family across wall A, chamfer
     and wall B; one vertical family.
  4. tube_with_cap: cap and side families stay separate.
  5. cylinder_tube two-seam variant: top ring family and bottom ring
     family across both side patches.
  6. Same-chain vs different-chain transport gates follow DD-43 (mirror
     the SurfaceFlowCompatibilityEvidence same-chain normal gate).
  7. Families carry provenance: member directional-evidence ids,
     crossing records (shared chain id / node id, signed dihedral),
     confidence. No trace/rail/UV/solve semantics.
  8. Inspection report exposes families behind detail="full".
  9. Existing tests stay green; AlignmentClass outputs unchanged.

ALLOWED FILES
  scaffold_core/layer_3_relations/direction_families.py (new)
  scaffold_core/layer_3_relations/model.py
  scaffold_core/layer_3_relations/build.py
  scaffold_core/pipeline/inspection.py
  scaffold_core/tests/test_direction_families.py (new)
  scaffold_core/tests/test_canonical_fixture_baselines.py (add family
  assertions only; do not flip alignment assertions)

STOP CONDITIONS
  - propagation wants to mutate ScaffoldContinuityComponent -> stop
  - gate logic wants a new relation kind -> stop (moratorium)
  - AlignmentClass consumers need migration -> stop, report
```

### Task Card D3 — Debug overlay channel

Family id as a deterministic color channel in the scaffold graph debug
addon (`dev/tools/scaffold_graph_debug`), same coloring rules as continuity
components (stable pseudo-random by id).

---

## Slice E — Vertical tracer: skeleton frontier to pinned UVs

Purpose: validate which Layer 3 evidence a real consumer actually uses.
This is a spike: deletable consumer tooling, NOT a G5 phase start.

APPROVED home: `dev/tools/tracer_spike/` — outside scaffold_core, a
pipeline consumer like the debug addon. No phase-rule exception is
needed; the spike must not be imported by scaffold_core and must not
move solve logic into the core. The "no Layer 5 during G3" rule stays
fully in force for scaffold_core/.

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

## Slice F — Post-tracer revision (REPLANNED from the E1 consumption report)

E1 verdict: PASS. Structural decisions correct on all five fixtures
(angle-defect stitch gate accepted the two-seam tube fold with defect 0,
blocked cap/side at ~pi/2, detected SEAM_SELF, assembled bevel corner into
one island, kept detached walls apart). Raw UV numbers in the dumps are
crude (mean-collapse, fallback projection) — irrelevant: the consumption
report is the deliverable.

Consumption verdict:

```text
CONSUMER API (read by the frontier):
  connected_direction_families, patch_chain_directional_evidence,
  patch_adjacencies, scaffold_junctions, patch_axes
  + Layer 2: vertex_facts.angle_defect, chain_facts
  + Layer 1 topology.

NEVER READ DIRECTLY (15 RelationSnapshot fields), but most are the
SUBSTRATE direction_families/patch_axes are built from (endpoint
samples, scaffold nodes/edges, incident relations, shared-chain
relations, alignment classes). Substrate is internal, not dead.

TRULY UNCONSUMED (no builder consumes them either):
  chain_continuations (TERMINUS/SPLIT) — retire candidate;
  scaffold_continuity_components — superseded by families for flow
  purposes; only the debug overlay colors by it. Decide: debug-only
  or retire after D3.
```

### Task Card F1 — Typed family consumer API

Direct response to spike improvisations 1, 2, 6, 7.

```text
GOAL
  Promote ConnectedDirectionFamily to a typed consumer contract:
  1. crossing_records become a frozen CrossingRecord dataclass (kind,
     node/chain ids, evidence ids, signed dihedral, transported dots,
     confidence) — no dict shadow API;
  2. rail-order helper: family members in connected rail order
     (crossing-graph walk; leaves chosen deterministically), exposed as
     ordered member ids per family;
  3. explicit member -> (patch_chain_id, scaffold_edge_id, topology
     start/end vertex ids) map so consumers stop reverse-mapping
     through source vertices.

ACCEPTANCE
  1. tracer spike rewritten to consume the typed API with zero dict key
     access and zero source-vertex reverse lookup (spike edit allowed,
     it is the validation consumer);
  2. family outputs byte-identical on all canonical fixtures except the
     new typed/ordered fields;
  3. suite green; inspection serializes the typed records.

ALLOWED FILES
  scaffold_core/layer_3_relations/direction_families.py
  scaffold_core/layer_3_relations/model.py
  scaffold_core/pipeline/inspection.py
  scaffold_core/tests/test_direction_families.py
  dev/tools/tracer_spike/run_tracer_spike.py

STOP CONDITIONS
  - rail order wants to CHOOSE among branches at valence>2 -> preserve
    ambiguity (emit branch records), do not pick a trace.
```

### Task Card F2 — Stitch-gate vertex set DD + fixture

The spike approximated "vertices that become interior" as the two shared
chain ENDPOINTS. Mid-chain vertices of a multi-edge seam also become
interior and are currently unchecked. Needs: DD text defining the exact
vertex set (all vertices of the shared chain, endpoints included only
when their other incident boundary disappears), plus a fixture with a
multi-edge seam whose midpoint vertex has nonzero defect (e.g. a ridge
tent shape) proving the gate blocks it. DD draft by Architect, user
approves; implementation lives in the spike until G5.

### Task Card F3 — Consumer API split DD (G0 amendment, user approval)

Declare in G0 which RelationSnapshot fields are consumer-facing contract
vs builder-internal substrate; retire chain_continuations if no consumer
is found; decide scaffold_continuity_components fate (debug-only vs
retire). Includes the original doc hygiene: DD-41/42 rewritten against
fixtures, DD text deduplication to one canonical home, G0
constitution/status split (pending decision 3).

### Recommended next vertical after F1: spike v2 in Blender

Run the frontier on a real beveled-wall mesh inside Blender: write pins
from the skeleton layout, call the built-in pinned conformal unwrap,
screenshot the UV editor. First visible end-to-end UV result; validates
the pinned-skeleton + conformal-fill split on real geometry.

---

## Decisions the user must approve before the relevant slice

```text
1. Slice D: G0 amendment for ConnectedDirectionFamily — APPROVED
   (DD-43, G0 v1.3). AlignmentClass demotion remains a separate future
   approval.
2. Slice E: spike home dev/tools/tracer_spike/ — APPROVED; no phase
   exception required.
3. Slice F: G0 restructuring (constitution vs status split) — PENDING.
```
