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

0. **Reporting protocol (token economy).** Every executed card produces:
   (a) `reports/summary.json` — flat key->number/boolean dict, <= 25 keys,
   with the card's acceptance numbers and guard-compliance booleans;
   (b) an ARCHITECT SUMMARY block at the end of the agent's reply,
   <= 15 lines: commit hash, acceptance pass/fail per item (one line
   each), anomalies, open questions. Verbose JSON/MD dumps stay on disk
   for targeted queries — the Architect reads summary.json and the
   block by default and deep-dives only on anomaly. The user pastes
   only the ARCHITECT SUMMARY block, never full agent logs. Blender
   runs print the same block (<= 15 lines) to the console for
   copy-paste.

1. **Evidence moratorium.** Do not add new Layer 3 evidence record types or
   relation kinds. New distinctions must wait until the tracer (Slice E)
   shows they are consumed. Exception: ConnectedDirectionFamily v0 (Slice D),
   which is explicitly planned here. Second exception, approved by the user
   (2026-11-13): PatchChainShapeRelation v0 (Slice W).
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
   Candidate cleanup in Slice F. RESOLVED by Slice N2: node crossings pick
   the hinge Chain through their node.
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

### Task Card E2 — Spike v2: real mesh in Blender (DONE, verdict below)

Spike v2 ran on a real wall mesh (walls.004, walls with window openings).
Structural pipeline executed end-to-end; the resulting layout was unusable:
fragments with partially aligned rails, islands strewn horizontally.
Reference CFTUV run on the same mesh produced clean aligned strips.
Root causes identified by extracting CFTUV behavior
(docs/migration/cftuv_frontier_algorithm_cards.md):

```text
1. Spike has no skeleton solve: CFTUV's visual quality comes from a global
   LSQ pass over junction row/col-graphs (P7) AFTER placement. (Card 4)
2. Spike ignores inner boundary loops: window/door holes are first-class
   skeleton citizens in CFTUV; spike dumped their vertices into fallback
   projection. (Card 5)
3. Spike has no anchor-based frontier: lexicographic choice + arithmetic
   mean collapse vs CFTUV's 7-tier FrontierRank + anchors. (Cards 1-2)
4. No global texel scale / cross-island row alignment. (Card 6)
```

## Slice G — Port CFTUV placement invariants into spike v3 (validate before contracting)

Strategy: keep porting in the spike until walls.004 looks right, THEN write
G5 contracts from validated behavior. Order chosen so each card is visible
on the real mesh.

### Anti-CFTUV guards (binding for every Slice G card)

CFTUV is a behavior reference for four ideas only: first-frontier,
continuity, cascading growth, rigid skeleton. SCAFFOLD must not regress
into CFTUV's shapes:

```text
1. The spike is condemned-by-design. G4 PASS triggers writing Layer 5
   contracts and a fresh implementation from those contracts; the spike
   is then archived/deleted, never promoted or imported. No file outside
   dev/tools/tracer_spike/ may import from it at any point.
2. No stored roles. H/V, WALL/FLOOR/SLOPE, frame roles must not appear in
   spike data models either - island-local AXIS_A/AXIS_B projections are
   computed views over ConnectedDirectionFamily, recomputed per run.
3. Solve never feeds back. The spike consumes Pass 0/1 snapshots
   read-only; any "the relation layer should have told me X" goes into
   the consumption report, becoming a Layer 3 slice, not a spike-local
   re-derivation that ossifies.
4. Skeleton scope is the whole selection, not the patch: row/col
   components are built over all ScaffoldNodes across islands (CFTUV's
   quilt-global rows generalized to mesh/shell level via families).
5. Decision rules that CFTUV hid inside solve branches (semantic pair
   scores, stitch preferences) are Level B and belong to the future
   Layer 4 grammar -> FeatureConstraint channel (DD-26). The spike may
   hardcode ONE simple default but must label it LEVEL_B_PLACEHOLDER in
   code and report, so contracts later claim it explicitly.
6. One file per concept inside the spike too; per-file hard cap ~600
   lines, spike total soft cap ~3000. Skeleton solve (G2) and the
   frontier (G3) live in their own modules. Amended after G1: the
   original ~1500 total was hit by run_tracer_spike.py (1118) +
   blender_run.py (582); raised consciously with a per-file cap instead
   of silently eroded - the guarded failure mode is a single growing
   monolith, not total volume. The spike death clause (guard 1) is
   unchanged.
```

### Task Card G1 — Island-local axis roles + inner loops (spike)

Project ConnectedDirectionFamily members onto two island-local axis roles
(the H/V replacement, per Card 1/4 mapping); place inner boundary loops
chain-by-chain like outer loops (Card 5). Spike-only.

### Task Card G2 — Skeleton solve v0 (spike)

P7 Card 4 in SCAFFOLD terms: union-find row/col graphs over ScaffoldNodes
through axis-classified families; one variable per component; length
equations with orientation_sign; gauge fixing; numpy dense lstsq; write
canonical coords; linear chain rebuild. Sibling equivalence deferred to G4.
Spike-only.

### Task Card G3 — Anchor frontier v0 (spike)

Replace lexicographic placement with anchor discovery + a reduced
FrontierRank (viability, role, ingress, length). Card 1-2. Spike-only.

### Task Card G3.3 — FINAL spike card: transport-consistent unfolded frame (hard stop after)

Revised after user verification: walls.013 has NO sloped geometry - all
faces are flat rectangles, so the trapezoid hypothesis is dead. The
diagonal UV drift with residual A=1.55 is orientation-sign inconsistency
across T-junctions and perpendicular wings: axis classification and
equation signs must be computed in the island's UNFOLDED frame (parallel
transport composed along the stitch tree from crossing-record signed
dihedrals), not from world directions or naive sign propagation over the
branchy family graph. Card adds the axis-parallel invariant (endpoint
UVs of an axis chain differ only along its own axis) as the permanent
bug catcher, keeps the P7 spread/UNCONSTRAINED safety, and remains the
last spike iteration: after it, G4 verdict and Layer 5 contract drafting
regardless of outcome.

### G4 VERDICT (issued from headless proof, spike frozen)

Root cause of the persistent diagonal drift on walls.013 — PROVEN on the
bevel fixture without further Blender runs: granularity mismatch. The
rail atom is the directional RUN, but skeleton equations connect the
endpoint ScaffoldNodes of whole coalesced Chains (skeleton_solve.py
_axis_chain_rows): a three-side border chain (runs 0.9/1.0/0.9 across
two axes) contributes contradictory equations about ONE node pair, and
mid-chain corner vertices are not graph nodes at all. Symmetric
fixtures cancel the contradiction; real multi-face patches (f0/f3 with
windows) do not -> lstsq smears -> diagonals. This is the DD-30 deferred
refinement debt coming due: L1 coalescing stays correct (DD-29), the
missing piece is a Layer 3 entity exposing run-endpoint junction nodes.

Spike disposition: FROZEN per guard 1. Structural mission complete:
island assembly, defect gate, T-junction interior set, unfolded frame,
selection-wide grids are validated; the one remaining gap is named and
proven. Next slice (H) builds it in core, not in the spike.

## Status update (Slice I / H, 2026-06-12)

- I1/I2/I3 overlay slices DONE (family colors, geodesic rail prototype,
  per-use double lines, build stamp). Artist validation found and named
  three prototype bugs (rim leak through seam endpoints, per-chain
  instead of per-use coloring, missing SEAM_SELF cut) — folded into the
  DD-45 contract and H2a acceptance; the prototype assembly is
  superseded by core family v1.
- H1 RunEndpointJunction v0: DONE, merged.
- User approved DD-44/DD-45; G0 bumped to v1.4. H2a authorized: core
  family v1 (occurrence-aware geodesic continuation), extruded_cross
  core fixture, overlay recolored from core, stash resolution.
- H3 / G5a Layer 5 v0: DONE, merged to main. Implemented
  `scaffold_core/layer_5_runtime/` with island assembly, selection-wide
  skeleton solve, pinned UV output, and the `Write UV (G5a)` debug-panel
  button. Current `uv_transfer.py` is operator-free: it writes UVs and pin
  flags only; the artist runs Blender `U > Unwrap` manually for conformal
  fill. Validated captures include two-seam cylinder / artist Cylinder
  (68 pins, residual about 4e-15, zero diagnostics), extruded_cross and
  l_corridor_tunnel. `artist_cross_band` remains a diagnosed partial
  degradation case rather than a silent success.
- Architecture correction (2026-06-13): the multiseam cylinder collapse is
  not a reason to add more orientation/sign traversal heuristics inside
  G5a. Investigation showed that node identity and the scalar least-squares
  solver are not the architectural root; the missing substrate is a
  direction-stable ordered rail/trace contract. Any "fix" that makes
  `_solve_axis` infer rail order, loop signs, branch choices or transport
  consistency locally is a Layer 5 substitute for future ScaffoldTrace /
  ScaffoldRail work and is out of scope. The current xfail stays pinned as
  a known limitation until Slice J defines and implements the Layer 3
  contract G5a should consume.

## Slice H — Run-endpoint junctions + Layer 5 contracts (status)

H1: Layer 3 run-endpoint junction evidence (rail-atom nodes: corner
    vertices interior to coalesced chains, derived from
    ChainDirectionalRun segments; closes the remaining OQ-11 chain-vs-
    run tension). Canonical fixture: the bevel wall multi-run border.
H2: G5 contract drafts from accumulated consumption reports and spike
    invariants (skeleton node := ScaffoldNode UNION run endpoints;
    axis-parallel invariant; UNCONSTRAINED exclusion; T-junction
    interior set; SEAM_SELF split; degradation with diagnostics).
    Architect drafts, user approves phase start.

## Slice J — ScaffoldTrace / ScaffoldRail contract before widening G5a

Purpose: move direction-stable ordered rail/trace semantics into Layer 3
before attempting to solve multiseam looped bands in Layer 5. This slice
exists specifically to prevent CFTUV-style runtime heuristics from
reappearing inside `scaffold_core/layer_5_runtime/`.

Draft artifact: `docs/architecture/scaffold_rail_trace_contract_draft.md`.
It is not a G0 amendment until the user approves it.

Architectural guard for all Slice J cards:

```text
- G5a may consume ordered rail/trace evidence after it exists.
- G5a must not infer rail order, loop signs, branch choices or
  transport-consistent rail orientation by local BFS/greedy traversal.
- Branches and loops preserve ambiguity unless the ScaffoldRail contract
  explicitly resolves them.
- No UV, pins, texel policy, packing, WORLD_UP or H/V semantics in Layer 3.
```

### Task Card J1 — ScaffoldRail / ScaffoldTrace DD draft and consumer contract

Status: DONE as draft (`docs/architecture/scaffold_rail_trace_contract_draft.md`);
awaiting Architect/user approval before any implementation card.

```text
You are a disposable Architect-support session executing one docs-only
Task Card for SCAFFOLD. Base on branch main.

READ FIRST
  1. AGENTS.md
  2. G0.md sections defining ScaffoldTrace, ScaffoldCircuit, ScaffoldRail,
     ConnectedDirectionFamily, RunEndpointJunction and DD-37/DD-43/DD-44/DD-45
  3. docs/phases/G5a_skeleton_runtime.md
  4. docs/plans/uv_tracer_revision_plan.md -> Slice J
  5. scaffold_core/tests/test_layer_5_runtime.py ->
     test_multiseam_cylinder_open_band_should_solve_xfail

TASK CARD: J1 - ScaffoldRail / ScaffoldTrace contract draft

GOAL
  Draft the contract that will let G5a consume ordered, direction-stable
  rails instead of deriving them locally. This is a docs-only contract
  preparation card; do NOT implement rail evidence and do NOT change
  layer_5_runtime solve behavior.

CONTRACT CONTENT TO DRAFT
  1. ScaffoldTrace: an ordered connected sequence over existing Layer 3
     graph atoms (ScaffoldNode and RunEndpointJunction) and existing
     directional evidence members. It is not Layer 1 identity and does
     not mutate PatchChain / ScaffoldEdge grouping.
  2. ScaffoldRail: a direction-stable ScaffoldTrace usable by Layer 5 as
     a conditional axis input. It carries ordered member evidence ids,
     endpoint node ids, per-member orientation sign in the transported
     rail frame, branch/loop ambiguity records, crossing provenance and
     confidence.
  3. Loop policy: closed/looped families are not linearly ordered by
     greedy traversal. The contract must state what remains ambiguous,
     what is eligible to become an open rail after island cuts, and what
     becomes a consistency check instead of a sign source.
  4. Branch policy: valence > 2 never silently picks a trace. It emits
     branch ambiguity unless an explicit future rule resolves it.
  5. Consumer API: G5a may consume ScaffoldRail order/orientation when
     present; when absent or ambiguous it must diagnose/degrade, not
     reconstruct the missing rail in Layer 5.
  6. Non-goals: no UV, pins, feature grammar, packing, WORLD_UP, H/V,
     wall/floor labels, or runtime solve behavior in the Layer 3 contract.

ACCEPTANCE
  1. docs/plans/uv_tracer_revision_plan.md contains the drafted DD text
     or points to a new docs/architecture draft file if the text is too
     large for the plan.
  2. docs/phases/G5a_skeleton_runtime.md states that multiseam rail-loop
     collapse is blocked on ScaffoldRail/Trace and must not be fixed by
     Layer 5 traversal heuristics.
  3. The xfail comment for artist_cyl_multiseam names the missing
     ScaffoldRail/Trace substrate, not a node-identity bug.
  4. No production code behavior changes. `python -m pytest
     scaffold_core/tests/test_layer_5_runtime.py` stays green.

ALLOWED FILES
  docs/plans/uv_tracer_revision_plan.md
  docs/phases/G5a_skeleton_runtime.md
  docs/architecture/scaffold_rail_trace_contract_draft.md (new, optional)
  scaffold_core/tests/test_layer_5_runtime.py (comment / xfail text only)

STOP CONDITIONS
  - Any urge to modify scaffold_core/layer_3_relations or
    scaffold_core/layer_5_runtime behavior -> stop and report.
  - Any urge to edit G0.md directly -> stop; draft the amendment text in
    docs only for user approval.
  - Any rule requires choosing a branch trace at valence > 2 -> preserve
    ambiguity and report the unresolved policy.

Run `python -m pytest scaffold_core/tests/test_layer_5_runtime.py`.
Commit message: "Draft ScaffoldRail contract gate for multiseam G5a".
```

### Task Card J2 — ScaffoldTrace / ScaffoldRail v0 implementation

Status: DONE. Implemented as Layer 3 evidence view in
`scaffold_core/layer_3_relations/scaffold_rails.py`.

Result:

```text
- ScaffoldTrace v0 orders ConnectedDirectionFamily members through existing
  ScaffoldNode / RunEndpointJunction atoms where an unambiguous path exists.
- ScaffoldRail v0 exposes ordered members, ordered trace nodes, transported
  orientation signs for open non-branching traces, crossing provenance,
  branch records, loop ambiguity records, diagnostics and confidence.
- Closed loops are not opened by the builder. They are explicit
  non-consumable loop rails until a later cut-context / consumer slice opens
  them.
- Branches and occurrence-collapsed open endpoints preserve ambiguity; no
  Layer 5 traversal heuristic was added.
```

Acceptance run:

```text
python -m pytest scaffold_core/tests
```

Commit message: "Implement ScaffoldTrace and ScaffoldRail v0".

## Sidecar K — Scaffold Graph Viewer QA tool

This is development tooling only. It lives outside `scaffold_core/` and must
consume exported JSON rather than recreate Scaffold relations.

### Task Card K1 — Flat topological graph viewer

Status: DONE. Implemented in `dev/tools/scaffold_graph_viewer/`.

Result:

```text
- Static web viewer for raw full inspection JSON or
  scaffold_graph_viewer_payload_v1 wrapper payloads.
- Displays ScaffoldNode / RunEndpointJunction atoms, ScaffoldEdges,
  ConnectedDirectionFamily members, ScaffoldTrace members and ScaffoldRail
  members in a flat topological graph.
- Loop/coincident endpoint aliases are display-only visual nodes with a
  canonical_id back to the real graph atom.
- Side inspector exposes raw properties; layer toggles and id search support
  QA without adding viewer-side Scaffold logic.
- Export scripts exist for in-repo fixtures and active Blender mesh snapshots.
```

Guard:

```text
The viewer must not construct rails, choose branches, open loops, compute UVs,
or introduce new core identities. Missing information stays visible as missing
or ambiguous.
```

### Task Card G4 — walls.004 validation gate

User reruns Blender spike v3 on walls.004 after G1-G3. Pass criteria:
rails straight, rows aligned, windows preserved, islands comparable to the
CFTUV reference. Only after PASS: draft G5 phase-start contracts
(FeatureConstraint-free skeleton solve + frontier as Layer 5 modules) from
the validated spike behavior.

First visible end-to-end UV result. Validates the pinned-skeleton +
conformal-fill split on real geometry. The user runs and validates this
inside Blender (Tier 3); agents only prepare the script.

```text
GOAL
  dev/tools/tracer_spike/blender_run.py — a script the user runs from
  Blender's Text Editor or `blender --python`, which:
  1. reads the active object's selected faces via
     scaffold_core.layer_0_source.blender_io.read_source_mesh_from_blender;
  2. runs Pass 0 / Pass 1;
  3. runs the (typed, post-F1) tracer frontier to get islands + skeleton
     UVs + pinned flags;
  4. writes skeleton UVs into the active UV layer, sets pin flags on
     those loops, offsets islands so they do not overlap;
  5. calls bpy.ops.uv.unwrap (conformal) so Blender fills the interior
     between pinned rails;
  6. prints a compact per-island report (patches, stitched/blocked
     seams with angle-defect reasons, rails, pinned counts) to console
     and saves it next to the script.

RULES
  - bpy usage stays inside dev/tools/tracer_spike/blender_run.py;
    scaffold_core/ untouched (blender_io is the existing read boundary);
  - no operator/addon UI, no bl_info: a plain runnable script;
  - mesh editing stays Blender's: the script writes UVs and pins only.

EXPECTATION MANAGEMENT (write into the report header)
  v2 diagnoses reality gaps; it does not produce final-quality UVs.
  Known limits: crude rail collapse math from spike v0, conservative
  splits on asymmetric curved bevels, no scale/texel policy, naive
  island offsets, interior quality depends on Blender's solver.

USER VALIDATION CHECKLIST (manual, in Blender)
  - select wall faces with seams marked, run script;
  - UV editor: rails are straight lines, pins visible on rails;
  - seams the gate stitched are interior straight stitches;
  - cap-like patches are separate islands;
  - report any crash/wrong island with the console dump.

STOP CONDITIONS
  - any urge to modify scaffold_core -> report instead;
  - pinned unwrap API mismatch with target Blender version -> document
    the version used and the call that works.
```

---

## Slice L — Cap-rim direction-family leak (measured multiseam root cause)

Status: L1 APPROVED by the user and DONE (2026-09). The corner-node gap is
deferred to a future patch-normal filter.

Finding. The `artist_cyl_multiseam` collapse is a Layer 3
ConnectedDirectionFamily leak, not a missing Layer 5 rail consumer:

```text
- One 68-member family holds the top rim, bottom rim and both cap
  perimeters (DD-45 requires distinct rim families; DD-43 requires cap and
  side families to stay separate).
- Leak path: SHARED_CHAIN transport rotates a direction about the CHORD of
  the shared chain. A curved cap-rim chain is not a rigid hinge. On a
  5-segment strip the middle rim run is parallel to the chord, so rotation is
  the identity, the transported normal gate passes (normal_dot 0.995) and the
  run crosses into the cap. SAME_PATCH_SHARED_CHAIN_BRIDGE (a raw
  world-direction parallel test inside one patch) then welds top and bottom
  rim runs of the same strip.
- Even-segment strips and the in-repo fixtures pass by accident: either no
  rim run is chord-parallel, or a full-ring band patch has a degenerate
  averaged normal, which makes the PatchAdjacency dihedral 0 and the raw
  normal gate rejects the cap crossing.
- With cap crossings blocked, the unchanged G5a solve pins 76 band vertices
  on two straight rows with zero diagnostics (residual 8.8e-7 = float32
  capture noise).
```

Second, independent leak (does not break any solve today):

```text
- A vertical seam run transported through a 90-degree rim-corner
  ScaffoldNode lands on a cap perimeter run. Node crossings are
  intentionally not normal-gated (DD-43 ring flow), so side and cap join one
  family. Reproduced by the capped hex prism with 2+4 strips.
```

Evidence pinned in tests:

```text
scaffold_core/tests/fixtures/capped_prism.py
test_direction_families.py::test_capped_odd_strip_prism_keeps_rims_and_caps_separate
test_direction_families.py::test_artist_multiseam_cylinder_rims_stay_distinct_across_six_strips
test_direction_families.py::test_capped_uneven_strip_prism_keeps_cap_and_side_families_separate
  (strict xfail: deferred corner-node gap)
test_layer_5_runtime.py::test_capped_odd_strip_prism_band_unwraps_to_an_exact_rectangle
test_layer_5_runtime.py::test_artist_multiseam_cylinder_open_band_unwraps_to_an_exact_rectangle
```

The artist_cross_band partial degradation is a different cause: its rim
families are already correct and the transport rule below does not change it.
Measured 2026-09: the 12-face side band solves cleanly (20 pins, zero
diagnostics); both 5-face planar cross end patches get 0 pins with 5
contradictory equations per axis. Their perimeter families are corner-split
singletons (DD-45), and Layer 5 `_orientation_signs` gives every singleton run
sign +1 in its own loop direction. Candidate next slice: supply per-run
orientation in the island frame from Layer 3 (ScaffoldRail consumer) instead
of widening Layer 5 sign heuristics. Needs an Architect/user decision.

### Task Card L1 — Straight-hinge rule for SHARED_CHAIN transport (DONE)

Rule, implemented in `layer_3_relations/direction_families.py`
(`SHARED_CHAIN_HINGE_MAX_RUNS`, recorded in family evidence data):

```text
SHARED_CHAIN crossings transport a direction only when both PatchChains of
the shared chain carry exactly one directional run (a straight hinge).
A curved multi-run shared chain has no single rotation axis, so it does not
transport direction families.
```

Result: the multiseam capture and the odd-strip prism unwrap to exact
rectangles (two pinned rows, aligned columns, zero diagnostics); corridor
folds, beveled corner, two-seam cylinder, extruded_cross, tube_with_cap and
artist_cyl32 are unchanged. The second (corner-node) gap is not addressed by
this rule.

User decisions (2026-09):

```text
- Straight end-patch edges (a box lid) may keep transporting like a corridor
  ceiling for now. Separating such end patches is a future filter.
- The corner-node gap stays a strict xfail. Its future fix is a filter based
  on the patch normal. Scaffold must not introduce cap/wall patch semantics
  for it: such roles are conditional, not core facts.
```

### Task Card L2 — A family never revisits a patch (DONE, user-directed)

User direction (2026-09): top and bottom rims must never be glued into one
family; find an approach.

Measured on the artist `buildings.blend` (Tier 3, 13 seamed objects): the
same-patch world-direction bridge was only part of the glue. On real walls
nearly every edge is a seam, so every face is its own patch, and families also
glued opposite sides through box-like corners (window reveals, wall tops). At a
cube corner the three geodesic continuations are symmetric; no local,
semantics-free rule can prefer one of them.

Rule, implemented in `layer_3_relations/direction_families.py`:

```text
1. SAME_PATCH_SHARED_CHAIN_BRIDGE is removed. Parallel runs are never merged
   by direction comparison alone.
2. IN_PATCH_GEODESIC crossings first form continuous in-patch segments.
3. Other crossings merge in deterministic priority: SHARED_CHAIN (two uses of
   the same source edges) before SCAFFOLD_NODE (inferred geodesic between
   different Chains), then by transported direction dot and ids.
4. A merge that would put two separate segments of one patch into one family
   is blocked. Blocked counts are recorded per family as
   blocked_patch_revisit_crossings evidence.
5. Guard diagnostic FAMILY_SPANS_OPPOSITE_PATCH_SIDES flags any family holding
   two distinct parallel lines of one patch from different in-patch segments.
```

Shared-chain-first was chosen by measurement: node-first pinned 723 vertices
on the 13 objects, shared-first 964, against 841 before L2.

| Object | opposite-side glue | largest family | pinned | Layer 5 diagnostics |
|---|---|---|---|---|
| walls / walls.003 | 708 to 0 | 3057 to 21 | 169 to 210 | 61 to 1187 |
| walls.004 (selection) | 9 to 0 | 20 to 5 | 156 to 156 | 10 to 18 |
| walls.009 | 350 to 0 | 1582 to 16 | 213 to 161 | 35 to 875 |
| walls.010 | 152 to 0 | 582 to 10 | 32 to 104 | 4 to 121 |
| all 13 objects | 1973 to 0 | | 841 to 964 | |

Axis-parallel violations and seam-length mismatches stay 0 before and after.
Layer 5 diagnostic counts are not comparable one to one: before L2 they were
one "contradictory equations" summary per axis, now they are mostly one
"axis bipartition conflict -> OBLIQUE" line per family.

Fixture expectation change (conflicts with G0 DD-43 text, G0 is read-only for
agents; proposed amendment for the user to apply):

```text
DD-43 canonical fixture expectations, replace:
  l_corridor_tunnel_seamed_folds: one length family across floor, wall and
  ceiling; one width family;
  beveled_wall_corner: one horizontal family across wall A, chamfer and wall
  B; one vertical family;
with:
  l_corridor_tunnel_seamed_folds: one width (profile) family across floor,
  wall and ceiling; one length rail per fold line (floor+wall, wall+ceiling);
  beveled_wall_corner: one horizontal family across wall A, chamfer and wall
  B; one vertical rail per fold line (wall A+chamfer, chamfer+wall B);
and add:
  A ConnectedDirectionFamily visits each patch at most once as one continuous
  in-patch segment; opposite sides of a patch never share a family.
```

Follow-up (2026-11, landed with Slice N): L2 also changed the debug-overlay
rails of beveled_wall_corner. Before L2 its SPINE was the two fold lines glued
through the chamfer's opposite sides, and the outer verticals were PARALLEL to
it. `dev/tools/scaffold_graph_debug/test_overlay_v2.py::test_beveled_corner_has_horizontal_spine_and_vertical_ribs`
kept that expectation (two PARALLEL rails) and failed on main from 196f9dd on,
unnoticed because verification ran only `scaffold_core/tests`. The test now
expects the horizontal SPINE, one PARALLEL (the opposite horizontal side) and
four vertical RIBs, one per fold line and outer edge; verification runs the
full suite from the repository root. (Slice AC removed the debug add-on's
own SPINE/PARALLEL/RIB rails and this test with them.)

### Task Card M1 — UV write stays inside the solved faces (DONE, bug fix)

Tier 3 found that `uv_transfer.write_pinned_uvs` wrote UVs and pins onto
faces outside the solved selection that shared a pinned vertex, and cleared
pins on every other loop of the mesh. On walls.004 with its stored 55-face
selection the old writer changed 343 loops outside the selection. The minimal
patch skips faces without a solved patch; `foreign_loops_changed` is now 0 on
all 13 objects.

## Slice N — Consistent patch -> line -> island structure (DONE, 2026-09)

User decisions (2026-09):

```text
- Target of this stage: a consistent structure on the levels patch -> line
  -> island, which a later slice turns into an unwrap along the rails. The
  final unwrap is a test tool here, not a quality target.
- Approved: the whole Layer 5 slice (island lines, axes and orientation from
  the island frame, _node_map repair, structural metrics in Tier 3) and both
  Layer 3 repairs below.
- G0: delegated to the agent. Applied: DD-43 repair text (L1, L2, node
  crossing provenance) and a DD-45 clarification -> G0 v1.5. DD-46/DD-47 stay
  a draft: rails are not yet reconciled with island lines (loop opening by
  island cuts).
```

Root cause of the "axis bipartition conflict -> OBLIQUE" flood: two
level mismatches, measured on the 13 seamed buildings.blend objects.

```text
1. Layer 5 used global ConnectedDirectionFamilies inside an island, but a
   family also transports across seams the island leaves cut. Restricting
   families alone removed 3522 -> 897 conflicts.
2. Layer 5 derived axes from 3D perpendicularity at nodes (frame-free),
   although the G5a module contract names the island's unfolded frame. In
   a folded island (wall + reveals, box unfoldings) 3D angles are not layout
   angles. Restricting perpendicularity to same-patch pairs alone left
   3147 conflicts; both together removed all of them.
```

### Task Card N1 — DD-45 continuation independent of edge order (DONE, G3 repair)

`direction_families._pair_endpoint_vertex_ids` mixed endpoint samples in the
run's own orientation with LOCAL_SEGMENT samples in the PatchChain loop
orientation, so the geodesic angle check also saw the far ends of both runs
and dropped the continuation. `_can_attempt_in_patch_geodesic` also demanded
END meeting START, although runs of different Chains keep their own
source-edge orientation. A straight patch side split by a T-vertex (walls.005
f2) became two families in 3 of 4 edge orientations. Repair: only samples at
the junction count, and roles are not compared (DD-45 decides by the angle).
Fixture: `scaffold_core/tests/fixtures/t_vertex_wall.py`, all four edge
orders. buildings: in-patch geodesic crossings 44 -> 72, families 4790 ->
4762, opposite-side families stay 0.

### Task Card N2 — Node crossings name their hinge (DONE, G3 repair)

`_node_crossings` looked up one PatchAdjacency per patch pair (last one wins,
D2 review note 4). On the two-seam tube and the artist_cyl32 band both
crossings at the stitched seam named the other seam. Repair: pick the
adjacency whose Chain passes through the node; without a hinge through the
node there is no transport axis and no crossing (never the case on the
in-repo fixtures and the buildings captures). Test: every node crossing of
the two-seam tube names a Chain through its node.

### Task Card N3 — Island lines and the unfolded island frame (DONE)

`layer_5_runtime/skeleton.py`:

```text
- Island lines: a family keeps only crossings inside one patch or through a
  hinge stitched in the island (N2 makes the recorded hinge exact). A family
  that crosses a cut seam splits into several island lines.
- Rigid frame: when no island patch is curved (face-fan normals within ~5
  degrees of the patch normal), each patch is rotated into the root plane
  along the stitch tree (rotation about the hinge Chain by the angle between
  patch normals). The frame crosses only straight hinges (the Layer 3 L1 rule:
  every use of the Chain carries one directional run) or joins of coplanar
  patches, which take no rotation; warped n-gons (boundary runs out of the
  patch plane) and patches behind a bent hinge stay outside with "patch
  outside the rigid island frame".
- Axes and orientation in the frame: AXIS_A follows the longest island line,
  AXIS_B = root normal x AXIS_A, so islands are not mirrored. Every framed run
  gets its role and sign from its unfolded direction; a line whose members
  disagree degrades to OBLIQUE with "island line not straight in the unfolded
  frame". The head-to-tail/co-orientation sign heuristics and the 3D
  bipartition are no longer used in framed islands.
- Curved islands (cylinder bands, strips) keep the provisional frame-free
  derivation over island lines.
- _node_map finds chain ends by the PatchChain end vertices, not by segment
  index: a closed rim cut by a SEAM_SELF starts its segments at an arbitrary
  ring vertex (artist_cross_band joined the seam sides and split the rim at
  the wrong vertex). When both PatchChain ends sit on one source vertex, the
  run's own seam side is the occurrence whose face fan holds the face on the
  run's end edge. The Layer 1 orientation sign of such closed Chains cannot
  be trusted there: it put each rim end on the opposite side, and the band's
  bottom row came out as the mirror of the top row (9 of 10 columns off,
  residual 5e-15, zero diagnostics) before and after the segment fix. Now
  every column lines up.
- New validation output node_frame_mismatches: solve nodes whose occurrences
  sit apart in the rigid frame (Layer 5 node identity vs the frame).
- Dead duplicate definitions and unused helpers removed from skeleton.py.
```

Tier 3 (`buildings_seamed.json` rewritten) now records structure metrics:
rigid_islands, island_lines, axis_runs, oblique_runs, bipartition_conflicts,
lines_not_straight, patches_outside_frame, node_frame_mismatches.

| Object | pinned | L5 diagnostics | rigid/islands | axis/oblique runs | lines not straight | outside frame |
|---|---|---|---|---|---|---|
| walls / walls.003 | 210 to 2215 | 1187 / 1189 to 11 | 8/8 | 3521/31 | 2 | 3 |
| walls.004 | 156 to 188 | 18 to 2 | 27/27 | 224/0 | 0 | 0 |
| walls.005 | 31 to 55 | 13 to 0 | 1/1 | 53/2 | 0 | 0 |
| walls.006 | 20 to 20 | 7 to 0 | 1/1 | 20/0 | 0 | 0 |
| walls.007 | 8 to 196 | 150 to 2 | 1/1 | 201/0 | 0 | 0 |
| walls.009 | 161 to 1486 | 875 to 6 | 3/3 | 1790/29 | 0 | 4 |
| walls.010 | 104 to 477 | 121 to 3 | 3/3 | 704/4 | 1 | 0 |
| all 13 objects | 964 to 6924 | 3561 to 36 | 60/62 | 10117/97 | 5 | 10 |

Node/frame mismatches, axis-parallel violations, seam-length mismatches,
opposite-side families and foreign loops are 0 on all 13 objects. Framed
islands no longer run the frame-free bipartition, so its 3522 conflicts are
gone by construction; in framed islands the frame's own degradation signals
replace them (5 lines not straight, 10 patches outside the frame, 97 OBLIQUE
runs). Check against the exact rigid unfolding: every walls.004 island with
pins (26 of 27) coincides with it up to a rigid motion (pairwise distances
within 8e-6); larger islands differ by the deferred component gauge and by
the straightening of slightly slanted runs. In-repo fixtures: the fully seamed
box went from 0 pins (16 OBLIQUE runs, bipartition conflicts) to 24 pins with
every face counterclockwise in UV and exact face areas.

Reviewer gate (mandatory, independent agent): PASS WITH FIXES. Fixed before
landing: the mirrored artist_cross_band band (seam side by face fan), the
node-crossing fallback (now no crossing), vacuous or missing tests (bent hinge
pair, not-straight line, node/frame detector, band columns; each of the four
matching code mutations is now caught by exactly its test), doc numbers, one
straight-hinge definition shared with Layer 3. Re-review: PASS; its two
optional pins were added too (nearly coplanar bent join, node crossing
without a hinge through its node).

Structural signals the new metrics expose (inputs for later slices, not
regressions):

```text
- lines not straight: a Layer 3 line runs through a curved run. Node
  crossings test straightness on the local segment at the node, while the
  run chord bends away (walls.010 arch run f90:1:0:0, 31 degrees). This is
  the OQ-11 curved-chain remainder.
- patches outside the frame: single n-gons folded around a corner (walls.009
  f715, an L-shaped reveal with an L-shaped hinge) and the patches the stitch
  tree reaches only through them.
```

Deferred, unwrap level (the concrete unwrap along rails is a later stage):

```text
- gauge: disconnected skeleton components of one island get arbitrary
  offsets (lstsq pins only the first node); the rigid frame knows their
  placement.
- RESIDUAL_TOLERANCE is absolute (1e-5). artist_cross_band end patches close
  their loops only to 0.004, so every equation is dropped as contradictory.
  This refutes the old hypothesis that their 0 pins come from singleton
  orientation signs: exact signs from the frame leave the same 5
  contradictions per axis.
- RESOLVED by Task Card M2 below: uv_transfer._pinned_for fell back to
  another patch's pin of the same source vertex, and pins.PinnedVertex was
  keyed by (source vertex, patch), so the two seam-side occurrences of a
  SEAM_SELF band collapsed into one pin (found by the Slice N reviewer;
  pre-existing).
- island assembly: the Level A spanning tree accepts self-overlapping
  unfoldings (walls.007 facade and back side over each other).
```

### Task Card M2 — Pins keep their own vertex occurrence (DONE, bug fix)

One root cause for both deferred findings: pin identity was the source vertex
per patch, not the topology vertex occurrence (DD-37). On the one-seam tube and
artist_cross_band the solve gives two UVs per seam vertex (one per seam side),
but only one pin survived and the write put it on both sides' loops; the
tube's written seam column came out sheared. The G5a claim that duplicated
seam occurrences keep both UVs was false until this card.

Minimal patch, no traversal heuristic:

```text
- skeleton._node_map also returns the occurrence it already picks for each
  run end (IslandSkeleton.vertex_by_run_end): a chain end sits on its
  PatchChain end occurrence (Slice N face-fan rule for closed rims); at a
  mid-chain vertex the same face-fan rule applies: the occurrence whose fan
  holds the faces on the run's own edges, so a boundary pinch keeps one
  occurrence per pass. A seam cutting a mid-chain vertex puts both sides'
  faces on the run's seam edge and the run end does not name its side: it
  stays unpinned with a diagnostic (no such vertex in the in-repo fixtures,
  the captures or the 13 buildings objects).
- pins: PinnedVertex.vertex_id; pins are keyed by (occurrence, patch);
  SolveResult.vertex_by_face_corner maps (face, source vertex) to the
  corner's own occurrence from the Layer 2 patch-side face fans.
- uv_transfer: a loop takes only the pin of its own corner occurrence in
  its own patch. The fallback to another patch's pin is gone; a loop
  without its own pin stays unpinned for U > Unwrap, as pins.py already
  requires for vertices without both axis coordinates.
```

Tests (fail before the patch): the one-seam tube keeps both seam-side pins
as two straight columns; the real write boundary on a fake BMesh (Object and
Edit Mode) unrolls the tube exactly, leaves the artist_cyl32 caps (islands
without pins, 64 rim loops) unpinned and, on a hand-built solve output,
never gives a loop another patch's pin of the same island; a kinked
self-seam leaves its seam-cut mid-chain vertex unpinned with 4 diagnostics;
a pinched grid keeps its pin on both boundary passes of the pinch vertex.

Reviewer gate (independent agent): WARNING, non-blocking. Fixed before
landing: a first "single occurrence per patch" rule for mid-chain vertices
dropped the correct pins of a seamless boundary pinch under a misleading
"seam-cut" diagnostic; the face-fan rule above restores them. Added: the
hand-built same-island write test, because every in-repo fallback crossed
islands and a same-island-only fallback survived the suite (now caught).

Tier 3 (`buildings_seamed.json` rewritten, 9 fields):

| Object | before -> after |
|---|---|
| Cube | pinned 40 -> 42: the second side of a SEAM_SELF band keeps its own pins; 2 loops move to their own side, written loops stay 72 |
| walls, walls.003 | written/pinned loops 3407 -> 3104 each |
| walls.009 | written/pinned loops 2084 -> 2008 |
| walls.010 | written/pinned loops 744 -> 720 |

A per-corner replay of the old and new lookups on captures of the 13 objects
accounts for every difference. The 706 loops no longer written (303 + 303 +
76 + 24; the Slice N review recorded 669, not reproduced at this head) are
all fallback loops: each
corner's own solve node lacks an axis coordinate, and the fallback gave it
the pin of another patch's node in the same island. The other 9595 written
loops are unchanged, and no loop gains a pin. Axis violations, seam
mismatches, node/frame mismatches, opposite-side families and foreign loops
stay 0.

## Slice O — ScaffoldRail over island lines (DONE, 2026-11)

User decisions (2026-11-06):

```text
- Approved: the whole slice. Rail stations and the island cut view in
  Layer 3; rail checks in Layer 5; Tier 3 metrics.
- Approved: fix the fold-back node crossing found while measuring, first, as
  a G3 repair under Minimal Patch Protocol (Task Card O1).
- G0: DD-46/DD-47 are decided after the slice. The user approved the final
  text after the slice; it is applied as G0 v1.6 with the O1 rule in DD-43.
```

Starting point on the 13 seamed buildings objects (PR #21 head): only 233 of
4762 rails were consumable. 4071 carried diagnostics, because rail v0 chained
members through every crossing. A SHARED_CHAIN crossing joins the two uses of
one hinge Chain, which cover the same source edges, so v0 put them one after
the other. There was no node between them (4107 `non_node_crossing`), and
3913 rails ended at the node where they began
(`coincident_open_trace_endpoints`). Rings stayed closed loop rails with no
way to open them at an island cut.

### Task Card O1 — Node crossings never fold back (DONE, G3 repair)

`direction_families._node_crossings` compared the transported run directions
by absolute dot product. So it also accepted two runs that leave the node the
same way after unfolding about the hinge. That happens where a patch wraps
270 degrees around a corner node (walls.003 v142, hinge e2692): a wall's
bottom and the neighbouring wall's notch bottom became one family, and a line
through them doubled back. Repair: `_leaves_node_the_same_way` rejects the
pair when the transported away-from-node directions point the same way. The
run end at the node comes from the node vertex, not from the endpoint
sample's role, which may follow the PatchChain traversal against the run
direction (a first attempt that used the role broke the l-corridor length
rails).

- Fixture: `scaffold_core/tests/fixtures/reflex_corner.py` (an L-shaped wall
  with a notch and a second wall hinged into it).
- Test: `test_node_crossing_never_folds_back_over_a_reflex_patch_corner`; the
  fixture also joined the opposite-sides sweep.
- buildings: 75 fold-back node crossings -> 0; families 4762 -> 4821; island
  lines 7606 -> 7646 (walls, walls.003, walls.010). Pins, Layer 5 diagnostics
  and OBLIQUE runs are unchanged: both runs of a fold-back already took the
  same axis in the frame.
- The strict corner-node xfail stays xfailed. It is a real through
  continuation, not a fold-back.

### Task Card O2 — Rails ordered through hinge stations (DONE, Layer 3)

`scaffold_rails.py` v1 (`scaffold_trace_rail_v1`):

```text
- Stations: members joined by SHARED_CHAIN crossings (the uses of one hinge).
  Other crossings link two stations at their trace node, deduplicated by
  (station, node). crossing_inside_station and non_node_crossing remain
  diagnostics.
- Branch records sit on stations (more than two links) and on trace nodes
  touched by more than two stations, never on the two uses of one hinge. A
  closed loop is a cycle of stations.
- Order and signs: walk the stations from the smallest leaf. Each member's
  sign comes from the trace nodes of the links before and after its station;
  a single station orients its uses against its first member.
- Stations are explicit: ScaffoldTrace, ScaffoldRail and the cut segments
  carry ordered_station_member_ids; in a consumable rail or an ordered
  segment station i is the step between trace nodes i and i + 1, so no
  consumer regroups the uses of a hinge itself (added after the reviewer
  gate). Branched, looped or unordered views list stations by station id.
- Unchanged: one trace and one rail per family, the consumable rule, and the
  coincident-endpoint and missing-member diagnostics. Branched and closed
  rails keep family order with zero signs.
- Dropped from v0: the multiple_crossings diagnostic (duplicate crossings
  between two stations at one node merge into one link; at two nodes they
  form a closed loop of two stations) and copying the family's member-level
  branch_records into the rail (branches are counted on stations now).
```

Tests: `test_fold_line_rail_is_one_station_of_both_hinge_uses` (beveled
corner) and `test_rail_orders_hinge_stations_through_their_node` (T-vertex
wall: two stations linked at w1, each one step between consecutive trace
nodes). All Slice J rail tests stay green.

### Task Card O3 — Rail cut by a given structural cut (DONE, Layer 3)

`cut_scaffold_rail(family, member_endpoints, member_ids, kept_chain_ids)`
returns `ScaffoldRailSegment` values. It is a pure function and is not stored
in `RelationSnapshot`.

- A crossing survives when both of its members are kept and it either stays
  inside one patch or passes a kept Chain.
- Each connected piece is ordered through its stations, so a loop opens
  exactly where the caller cut it.
- A branch, or a loop the cut leaves closed, stays unordered with a
  `branch:` or `closed_loop` diagnostic.

Tests:

- `test_cut_rail_opens_a_loop_only_where_the_cut_is` (two-seam tube): both
  seams kept -> closed loop; one -> one ordered segment; none -> two ordered
  halves.
- `test_cut_rail_keeps_a_branch_unordered` (a station with three links).
- `test_cut_rail_keeps_a_rail_that_returns_to_its_own_node_unordered` and
  `test_cut_rail_names_the_branch_where_a_cut_hinge_parts_its_uses` (the
  T-vertex wall with its right hinge cut): the trace-node branch rule. In
  real data a link node is an endpoint of both stations, so this rule, not
  the station rule, is the one that decides.

### Task Card O4 — Layer 5 checks the island rails (DONE)

`skeleton._island_rail_segments` cuts every family's rail by the island: its
runs and `island.stitched_chain_ids`, the tree edges only, so non-tree seams
stay cut. `_island_rail_conflicts` checks two things:

- every island line with more than one run is exactly one segment;
- in a framed island, rail sign times frame sign is constant over the axis
  runs of an ordered segment.

Outputs: `IslandSkeleton.rail_segments`, `IslandSkeleton.rail_frame_conflicts`
and `SolveResult.rail_frame_conflicts`. The solve itself is unchanged; it does
not consume rail order yet.

Tests:

- `test_island_cut_opens_the_ring_rails_of_a_two_seam_tube`
- `test_artist_multiseam_band_rims_open_into_ordered_island_rails`: both rims
  are closed loop rails across the six strips, and the band island orders each.
- `test_reflex_corner_island_rails_agree_with_the_unfolded_frame`
- `test_island_rail_conflicts_name_rails_against_the_frame_and_split_lines`
- `test_framed_island_reports_an_island_rail_against_its_frame`: wiring of
  the frame check; one sign per ordered island rail is flipped on its way
  out of the cut view, since after O1 no real rail runs against the frame.
- The artist walls invariant test now also requires zero conflicts and
  ordered island rails.

In a prototype run before O1, the rail/frame check found 29 rails running
against the frame; O1 removed all of them.

### Task Card O5 — Tier 3 island rail metrics (DONE)

`blender_smoke` records `island_rails` (segments with more than one run),
`unordered_island_rails` (table column `unord`) and `rail_frame_conflicts`.
`buildings_seamed.json` was rewritten and confirmed identical on a rerun.

| Metric, 13 seamed objects | PR #21 head | Slice O |
|---|---|---|
| fold-back node crossings | 75 | 0 |
| families = rails | 4762 | 4821 |
| consumable rails | 233 | 4301 |
| rails with diagnostics | 4071 | 2 |
| island lines | 7606 | 7646 |
| island rails (more than one run) / ordered | - | 2094 / 2090 |
| rail/frame conflicts | - | 0 |
| pins / L5 diagnostics / OBLIQUE runs | 6926 / 36 / 97 | unchanged |

Largest per-object gains in consumable rails: 61 -> 1515 (walls, walls.003),
47 -> 783 (walls.009), 16 -> 307 (walls.010) and 8 -> 92 (walls.007). The 520
non-consumable rails are:

- 486 single-member rails;
- 22 closed loops;
- 10 branched rails;
- 2 rails on Cube with coincident open endpoints: a rim cut by a SEAM_SELF
  starts and ends at one ScaffoldNode. The island cut orders both.

Axis violations, seam mismatches, node/frame mismatches, opposite-side
families and foreign loops stay 0.

Reviewer gate (independent agent): PASS WITH FIXES, nothing blocking. It
confirmed that UVs, pins and diagnostics are identical before and after the
slice on every fixture and capture. Of the mutations of O1-O4 logic it
tried, only two survived the suite (the trace-node branch threshold and the
frame check wiring); they are the second and third items below. Fixed
before landing:

```text
- The rail did not name its stations, and the draft DD-46 sentence "a trace
  never puts the two uses of one hinge one after the other" contradicted
  the stored order. Stations are now explicit (O2 above), and DD-46 says
  that the uses are listed together as one step.
- The trace-node branch rule had no test (changing its threshold left the
  suite green), and the station-rule test used an impossible input (a link
  at a node that is not an endpoint of its station). Both rules now have
  realistic tests (O3 above).
- The frame check ran only in a unit test; a wiring test now covers it
  (O4 above).
- Plan notes: the v0 behaviours dropped by v1, and the pending G0 note for
  the O1 rule (decision 6).
```

Each of the five matching mutations (both branch rules off, stations out of
rail order, stations split into single members, the frame check unwired)
is caught by exactly the new or updated tests. Re-review of the fixes:
PASS. Stations are consistent on all 672 rails and traces and 771 island
segments of the fixtures and captures. Its last notes were applied: tests
for station order in an unordered segment and for the serialized trace
stations, and the one-step-per-station guarantee is stated for consumable
rails and ordered segments only.

Structure signals and deferred items (inputs for later slices, not
regressions):

```text
- 4 island rails stay unordered as branches (walls and walls.003 at v1544,
  walls.009 at v869, walls.010 at v119): more than two stations of one
  family meet at one node. Branch resolution is open (DD-47 draft, question 4).
- Island lines and the Layer 3 cut apply the same rule twice. The check
  proves they agree (0 disagreements); a later slice may take the island
  lines from the cut directly.
- The absolute transport check in _node_crossings still reads the tangent at
  the endpoint sample's role. For a curved run this can be the far end. No
  measured effect; the fold-back test already uses the node vertex.
- Unchanged from Slice N: 5 island lines through curved runs (OQ-11),
  10 patches outside the frame, the corner-node xfail, the unwrap-level
  gauge and tolerance items.
```

## Slice P — Rigid seams first in the island tree (DONE, 2026-11)

User decisions (2026-11-06):

```text
- Next slice after Slice O: patches outside the rigid island frame, starting
  with a case analysis and a proposed rule.
- Approved after the analysis: the rule "rigid seams first" in Layer 5
  island assembly.
```

Case analysis (13 seamed buildings objects, after Slice O). 10 patches outside
the rigid frame carried 60 of the 97 OBLIQUE runs:

```text
- 5 are warped n-gons: one face folded 90 degrees around a corner (walls
  and walls.003 f1415 and f1352, walls.009 f715). They have no rigid
  unfolding and stay outside the frame (28 OBLIQUE runs).
- 5 are planar (walls and walls.003 f712; walls.009 f218, f664, f233). The
  longest-seam-first tree reached them only through a warped n-gon, often
  over its long L-shaped (bent) hinge. Each of them has a short straight
  seam to a framed patch, and the tree had left that seam cut.
```

Rule: the island tree takes the rigid seams first, then the other accepted
seams, longest first inside each group. A rigid seam is a straight hinge (the
Layer 3 straight-hinge rule) or a coplanar join between two planar, unwarped
patches.

- The Level A gate and the seams it accepts are unchanged, so the islands
  are the same; only which accepted seams become tree edges changes.
- Semantic stitch preferences stay a Layer 4 placeholder.

Implementation:

- `layer_5_runtime/islands.py` now owns `SeamRigidity`, `seam_rigidity` and
  `is_rigid_seam`. They hold patch planarity, warp and straight hinges, moved
  from `skeleton.py`.
- The island tree and the rigid frame (`skeleton._unfolded_frame`) use the
  same predicate, so the tree never prefers a seam the frame cannot cross.
- The frame rule itself is unchanged.

Test: `test_rigid_seams_enter_the_island_tree_first`, on the T-vertex wall
with a warped floor_a. Every seam there is one edge long, so floor_b used to
hang off floor_a and both fell out of the frame. Now the straight hinge e_w12
joins floor_b to the wall, floor_b enters the frame, and only floor_a stays
outside. Each of these mutations is caught:

- no rigid rank;
- the rank reversed;
- warp ignored;
- the frame entering a warped child;
- coplanar joins never rigid.

Tier 3 (`buildings_seamed.json` rewritten and confirmed identical on a rerun):

| Metric, 13 seamed objects | Slice O | Slice P |
|---|---|---|
| patches outside the frame | 10 | 5 |
| OBLIQUE runs | 97 | 65 |
| axis runs | 10117 | 10149 |
| pins | 6926 | 6957 |
| Layer 5 diagnostics | 36 | 31 |
| written loops | 9597 | 9652 |
| island lines / island rails | 7646 / 2094 | 7643 / 2097 |

Changes by object:

- walls, walls.003: outside 3 -> 2, OBLIQUE 31 -> 23, pins +8.
- walls.009: outside 4 -> 1, OBLIQUE 29 -> 13, pins +15.

Four accepted seams swap between stitched and cut, which adds one cut edge on
each of walls, walls.003 and walls.009. Islands (62), rigid frames (60),
unordered island rails (4) and lines not straight (5) are unchanged. Axis
violations, seam mismatches, node/frame mismatches, rail/frame conflicts,
opposite-side families and foreign loops stay 0. The in-repo captures do not
change.

Reviewer gate (independent agent, Slice P with G0 v1.6): PASS WITH FIXES,
nothing blocking.

- Fixed, G0 v1.6 wording:
  - DD-33: traces and rails are separate views over direction families
    and run-endpoint junctions, not over ScaffoldGraph;
  - DD-46: a member's vertices are the occurrences of its endpoint
    samples by sample role (PatchChain traversal, not trace direction);
  - DD-47: a loop opens at a cut the rail builder does not own (island
    assembly is Layer 5, not a lower layer);
  - OQ-11: only circuit construction stays unresolved.
- Fixed, docs: a planar patch joins the frame only over a path of rigid
  seams to the frame root (G5a, handoff).
- Fixed, tests: the sort key is now `islands._tree_edge_priority`.
  - Unit tests cover `is_rigid_seam` (straight hinge, coplanar join with a
    non-unit normal, bent hinge, a warped or non-planar patch on either
    side) and the priority (rigid first with the warped patch second,
    longest first, id tiebreak).
  - 13 mutations, each caught.
- W1: the DD-47 consumer rule forbids Layer 5 to rebuild rail signs by
  local propagation, but islands without a rigid frame still run the
  provisional frame-free derivation (`skeleton._orientation_signs`),
  which does. User decision (2026-11-07): G0 v1.6 DD-47 records this as a
  provisional exception; plan Slice Q removes it.
- Re-review: PASS. One optional note: an island made only of warped
  n-gons also has no rigid frame, so "(a curved island)" in the
  exception is narrower than the code; the user-approved text is kept.

Remaining after Slice P (inputs for later slices):

```text
- 5 warped n-gons (28 OBLIQUE runs): a face folded around a corner has no
  rigid unfolding. Later options: user split marks (OQ-11) or a per-face
  local frame.
```

## Slice Q — Layer 5 on rails (DONE, 2026-11)

User decision (2026-11-07): next after Slice P, "Layer 5 on rails". The
slice starts with a measurement and brings its rule for approval.

Measurement (`scratchpad` probe over the island tree after Slice P):

```text
13 seamed buildings objects:
- island lines 7643, Layer 3 cut segments 7643; every line, single-run
  lines included, is exactly one segment; every run has a line.
- 4 unordered segments (walls, walls.003, walls.009, walls.010), all in
  islands with a rigid frame.
- 2 islands without a rigid frame (Cube, walls.012), 13 lines, all with an
  ordered segment whose sign agrees with the provisional sign.
In-repo captures (scaffold_core/tests/data):
- 532 lines = 532 segments, 0 unordered.
- 3 islands without a rigid frame (artist_cross_band, artist_cyl32,
  artist_cyl_multiseam), 24 lines; on one line of each the rail sign is the
  whole-line opposite of the provisional sign, nowhere do they disagree
  inside a line.
```

Rule (approved by the user, 2026-11-07):

1. Island lines are the pieces of the Layer 3 rail cut by the island;
   Layer 5's own family split (`skeleton._island_lines`) is removed. A line
   id stays the family id plus the smallest member id of its piece.
   (2026-11-15, plan Slice AK: in an island without a rigid frame the lines
   of the two sides of a stitched Chain over the same segments are then
   joined into one, which keeps the id of its longest part.)
2. An island without a rigid frame takes its in-line run signs from its
   ordered island rails; `skeleton._orientation_signs` (head-to-tail walk)
   is removed. A run on an unordered island rail stays unsigned with the
   diagnostic `unordered island rail: <line> -> unsigned` and adds no length
   equation.
3. The DD-47 provisional exception is removed (G0 v1.6, user-approved).

Stays in Layer 5, because it is not rail order and rails do not supply it:
the frame-free axis bipartition by local orthogonality and the
co-orientation of parallel lines through their cross runs.

Tests:

- `test_frame_free_island_takes_lines_and_in_line_signs_from_its_rails`
  (one rail sign flipped on the way out of the cut view; the island must
  follow it, and every line is its segment);
- `test_unordered_island_rail_stays_unsigned_in_a_frame_free_island`
  (diagnostic, no sign, fewer equations).

- `test_unordered_single_run_rail_stays_unsigned_in_a_frame_free_island`
  (added after review: a single-run piece no longer takes a silent +1).

Reviewer gate (independent agent): PASS. Notes fixed: G5a says an unsigned
run keeps its axis role; a single-run unordered piece is tested. DD-47 now
says that axis bipartition and cross-rail co-orientation stay with Layer 5
(user-approved, 2026-11-07).

Mutations: 7 of 8 caught. The survivor drops the "signed runs only" guard
of the co-orientation flip. It is equivalent: an unsigned line never links,
so it is never flipped.

Results: solve output (frame, roles, final signs, lines, coordinates,
diagnostics) is identical before and after on all 101 islands of the 13
buildings captures and the in-repo captures. On the three in-repo
frame-free islands where a rail runs opposite to the old walk, the
co-orientation restores the same final signs. Tier 3: baseline identical
(13 objects, 0 errors).

---

## Slice R — warp measured at the patch scale (DONE, 2026-11, bug fix)

Measurement of the 5 warped n-gons left after Slice P (13 seamed buildings
objects) found two cases, each a single-face patch:

- walls/f1415, walls.003/f1411, walls.009/f715: a hexagon folded 90 degrees
  around a box corner (half on the top face, half on the side face). Its
  runs climb 0.88 m out of the average plane on a 1.4 m patch. This is real
  warp in the source mesh; the patch stays outside the frame with its
  diagnostic. Unfolding a face along an inner fold that is not an edge is
  not attempted.
- walls/f1352, walls.003/f1348 (and walls.012/f0, not counted above because
  that island had no frame at all): a 12 x 8 m face with one vertex 1 cm off
  its plane. The 2 cm edge to that vertex points 63 degrees out of the plane,
  and `islands._warped_patch_ids` judged warp by run direction alone.

Fix (Minimal Patch Protocol, `islands._warped_patch_ids` only): a run warps
its patch when its climb out of the patch plane (|direction . normal| times
run length) exceeds the planar tolerance times the patch scale (square root
of the area). The tolerance constant is unchanged.

Test: `test_warp_is_measured_at_the_patch_scale_not_by_one_short_edge`
(fails when the scale is the run length again, i.e. the old rule).

Results: 98 of 101 islands (buildings and in-repo captures) are unchanged.
walls.012 now has a rigid frame and solves (pins 0 -> 9, its 5
contradictory equations are gone); walls and walls.003 island 6: OBLIQUE
runs 6 -> 2. Tier 3 totals: patches outside the frame 5 -> 3, OBLIQUE runs
65 -> 58, pins 6957 -> 6966, Layer 5 diagnostics 31 -> 28, rigid islands
60 -> 61 of 62 (Cube stays frame-free). Baseline updated.

## Slice S — snap angle and drift tolerance (DONE, 2026-11, user-approved)

Measurement after Slice R (13 seamed buildings objects): 20 contradictory-
equation diagnostics on 6 objects; any residual above an absolute 1e-5
dropped whole components, so 2057 of 6801 solve nodes lost a coordinate
(the main walls island dropped 316 of 1715 AXIS_A equations). Two causes:

- in the rigid unfolded frame a run took an axis within 23 degrees
  (AXIS_CLASS_MIN_COS = 0.92). Cross runs tilted that far glued nodes up to
  3 m apart into one column, and tilted runs carried their full length as
  an axis length. A 32-gon cap snapped its 0, 11.25 and 22.5 degree edges
  and became a square;
- with the snap angle tight, columns still spread up to 10 cm: the source
  meshes drift by millimetres to centimetres over tens of metres.

Options measured (solve nodes with both axes / OBLIQUE / contradictions):
current 4744 / 58 / 20; tolerance only 6516 / 58 / 9; 5 degrees plus
tolerance 6578 / 86 / 9; 1 degree plus tolerance 6738 / 268 / 2 (absolute
3 cm tolerance standing in for the relative one).

Rule (chosen by the user, 2026-11-07, "5 degrees + tolerance"):

1. In the rigid frame a run takes an axis only within the planar tolerance
   angle (`AXIS_CLASS_MIN_COS = PLANAR_PATCH_MIN_NORMAL_DOT`, about 5
   degrees); steeper runs stay OBLIQUE.
2. The solve absorbs drift of 1 mm per metre of the island's span along the
   axis (`RESIDUAL_TOLERANCE_PER_SPAN`); larger residuals stay
   contradictions with their diagnostic, as before.
   (2026-11-15, plan Slice AK, decision 18: for an island without a rigid
   frame the span is the larger of its two axis spans, on both axes; the
   constant is unchanged. A rigid-frame island shares its frame drift with
   the jog check since Slice U; a strip island keeps each axis' own span.)

Tests: `test_rigid_frame_gives_an_axis_only_within_the_planar_tolerance_angle`,
`test_solve_absorbs_modelling_drift_relative_to_the_island_span`. Mutations:
the old snap angle, the absolute tolerance and a 10x looser span tolerance
are each caught.

Results (Tier 3, baseline updated): pins 6966 -> 10104, Layer 5 diagnostics
28 -> 18, contradictions 20 -> 5 (walls, walls.003, walls.004, walls.007,
walls.010), OBLIQUE runs 58 -> 102, island lines not straight in the frame
5 -> 10; invariants stay 0. In-repo captures: artist_cross_band end patches
now solve (the known limitation of Slice N); cylinder caps keep only their
axis-parallel edges on axes, so a round cap stays round.

## Slice T — jogs: runs that leave their axis by more than drift (DONE, 2026-11)

Measurement after Slice S: the 5 remaining contradictions (walls, walls.003,
walls.004, walls.007, walls.010) each come from one cross run 1.6 to 4.6
degrees off its axis, inside the 5 degree snap angle, that moves its column
in the rigid frame by 5 to 40 cm, more than the island's drift tolerance
(walls.004/f14: 1.8 m run, 5 cm across, drift 8.7 mm). Snapped, it
contradicts the rest of the column and the solve drops whole components.

Rule (follows from the Slice S drift tolerance): in the rigid frame a run
whose offset across its axis (length times the sine of its angle to the
nearest axis) exceeds the island's drift (1 mm per metre of the frame
extent) is a jog. It alone goes OBLIQUE; the other members of its line keep
their axis, so the line keeps two straight halves instead of a contradiction.
The diagnostic `island line jogs in the unfolded frame: <run> -> OBLIQUE`
names it when its line keeps an axis; a line of such runs is simply
OBLIQUE. A tried variant that degraded the whole line raised OBLIQUE runs
to 148 and lost lines in walls.004.

Tests: `test_a_run_that_leaves_its_axis_by_more_than_drift_is_a_jog_of_its_line`;
`test_artist_walls_captures_keep_g5a_invariants` now asserts no
contradictory equation. Mutations caught: no drift passed in, whole-line
degradation, jog diagnostic on an oblique line.

Results (Tier 3, baseline updated): contradictions 5 -> 0, island lines not
straight in the frame 10 -> 0, jogs 17, pins 10104 -> 10176, OBLIQUE runs
102 -> 113, Layer 5 diagnostics 18 -> 20 (17 jogs and the 3 folded
hexagons); invariants stay 0.

## Slice U — island assembly without self-overlap (DONE, 2026-11, user-approved)

Measurement after Slice T (13 seamed buildings objects plus in-repo captures):
the rigid unfolding of 9 of 61 framed islands lies over itself. In the main
walls island (582 patches) 2406 patch pairs overlap. The Level A gate checks
developability only; niche and ledge reveals unfold about their opening into
the same opening and onto the wall (artist_walls_006: reveals f1 and f2 into
one opening, f3 onto the wall). Each hinge unfolds correctly, the overlap is
global.

Rule (option "gate + frame", chosen by the user 2026-11-08):

1. Overlap gate: each island part with a rigid frame keeps its patches'
   placement and face triangles (ear clipping, so a concave n-gon keeps its
   notch empty). A rigid stitch between two rigid parts unfolds the smaller
   part about the seam into the larger part's plane and stays cut ("would
   overlap the island") when a triangle overlaps; touching does not count.
2. A non-rigid seam between two rigid parts stays cut ("frame cannot cross
   between rigid parts"); otherwise the part behind it hangs outside the
   frame. A part without rigid patches (curved, warped) joins freely.
3. One unfolding for the gate and the frame: `islands.unfold_rotation`
   (the rotation math moved from skeleton.py to islands.py).
4. In a rigid frame the solve takes the same drift as the jog check (1 mm
   per metre of the frame extent). Small islands made by the gate exposed
   the difference: a long thin island (walls.010, 8.5 x 0.5 m) let a 4.6 mm
   jog pass the check while the solve measured drift along the 0.5 m axis.

Options measured (islands / pins / OBLIQUE / patches outside the frame):
before 62 / 10176 / 113 / 3; gate only 352 / 9995 / 258 / 15; gate + frame
355 / 10058 / 194 / 3, then 10112 pins with the shared drift. A tried axis
seed by coverage did not help (the oblique small islands are real slanted
parts, such as a 6 m sloped beam with small square details).

Tests: `test_niche_reveals_that_would_overlap_the_wall_stay_cut`,
`test_overlap_gate_triangulates_concave_faces_and_ignores_touching_triangles`,
`test_framed_solve_uses_the_frame_drift_shared_with_the_jog_check`;
`test_bent_hinge_between_tilted_patches_stays_cut_between_two_rigid_islands`
replaces the old outside-the-frame expectation. Mutations caught: no
overlap check, non-rigid join between rigid parts, fan triangulation,
touching counted as overlap, drift ignored by the solve. The call-site
wiring of the shared drift is guarded by the Tier 3 baseline (without it 3
contradictions return).

Results (Tier 3, baseline updated): islands 62 -> 355 (354 framed), pins
10176 -> 10112, OBLIQUE runs 113 -> 194, Layer 5 diagnostics 20 -> 28 (25
jogs, 3 folded hexagons), contradictions 0; overlap between patches of one
island 0 (one patch, walls/f302, overlaps itself inside its own faces);
invariants stay 0. Cross-island axis agreement now matters: 2470 of 4821
families span more than one island (none did before).

## Slice W — chain shape per patch side (Stages A and B DONE, 2026-11)

Origin (user review, 2026-11-13): an arch with bevels
(`Decor_Roof_Left_lod00.003`) compared with the CFTUV result. CFTUV
structures all five patches; Scaffold solved one. CFTUV judges a boundary
chain as a whole and per patch: a chain that lies in a plane and bends only
along the patch normal is an axis chain for that patch. The user's direction:
fix the layers below UV first; Layer 5 is not the priority while they cannot
describe shape.

Contract and measurements: `docs/architecture/chain_shape_contract_draft.md`
(approved by the user, 2026-11-13). G0 v1.7 DD-48.

Measurement (probes `chain_shape_probe*.py`, now
`dev/tools/blender_smoke/probes/chain_shape.py`):

```text
- every non-straight chain on properly seamed meshes is planar (0.00%);
- tilt of the chain plane against its patch faces: buildings 40 edges at
  0-10 degrees and 1001 at 80-90, none between; a ring on a cone 41-44;
- surface turn = 3D turn x sin(tilt): median error 0.00, p95 <= 0.15, max
  about 1 degree; larger only on warped single-face patches;
- surface turns at interior chain vertices (13 buildings, 7 in-repo
  captures, the arch, walls.001 and pCylinder of buildings3_3) cluster at
  0-3 (1560), 6-30 (238) and 80-100 (743) degrees, with 12 at 3-6, 46
  between 30 and 80 and 18 above 100: corner threshold 42, between a
  regular 9-gon (40) and an 8-gon (45);
- the one-run chord shortcut on a non-straight chain: 12 sides on buildings,
  all stepped in the surface, all 12 end as Layer 5 defects (10 of 25 jogs,
  2 OBLIQUE).
```

Stage A (this slice, no behaviour change):

- Layer 2: `ChainGeometryFacts.plane_normal`, `plane_deviation`,
  `chord_deviation`; `PatchChainGeometryFacts` per use (side face and normal
  per chain segment, tilt range).
- Layer 3: `PatchChainShapeRelation` v0 per use and piece
  (`layer_3_relations/patch_chain_shape.py`): SURFACE_LINE, SURFACE_CURVE or
  UNRESOLVED; diagnostics `PATCH_CHAIN_SHAPE_LAW_MISMATCH` and
  `PATCH_CHAIN_SHAPE_OCCURRENCE_UNRESOLVED`.
- Inspection counts, Tier 3 metrics `shape_lines`, `shape_curves`,
  `shape_unresolved`, `shape_law_mismatches`, a debug overlay layer
  `ScaffoldGraph_ChainShape`.
- Fixtures: `artist_arch_bevel.json` (the user's arch),
  `fixtures/chain_shape_surfaces.py` (cone or cylinder band with a cap,
  stepped seam, warped pentagon).

Results (replay of captures; existing outputs hash identically before and
after on 25 captures: 13 buildings, 4 of buildings3_3, 8 in-repo; the
reviewer re-checked 21 of them against an export of HEAD, byte-identical):

| Set | lines | curves | unresolved | multi-segment lines, one family / split |
|---|---|---|---|---|
| 13 buildings | 10192 | 11 | 3 | 468 / 0 |
| 8 in-repo captures | 579 | 20 | 0 | 50 / 0 |

The 3 unresolved pieces on buildings are the single-face patches with a 1 cm
sliver vertex (walls f1352, walls.003 f1348, walls.012 f0). Arch: each arc is
one SURFACE_LINE on its rim side and one SURFACE_CURVE on the front face; the
foot chain is one SURFACE_LINE for the front face and five cornered pieces
for the foot cap. Tier 3 baseline: four new fields per object and the new
diagnostic code on three objects; nothing else moved. Shape builder cost on
walls: 0.07 s of 4.4 s.

Tests: the suite goes from 338 to 375 passed. Mutations caught: corner
threshold at 20, 40 and 60 degrees, line tolerance replaced or zeroed, tilt
from the other side's faces, law check skipped, pieces not cut at corners,
and the reviewer's 15.

Reviewer gate (independent agent): PASS WITH FIXES, nothing blocking.

- Fixed, code: a closed Chain is read from the use's own start vertex (a
  use that starts elsewhere was one UNRESOLVED piece: artist_cross_band
  f1); the corner threshold moved from 40 to 42 degrees, off the exact
  turn of a regular 9-gon; the record's segment order is documented.
- Fixed, tests: 7 surviving mutations (a vertex with several face fans,
  is_planar, the signed turning total, a closed spatial chain, the
  overlay's SEAM_SELF sides) are now caught.
- Fixed, docs: DD-48 and the contract draft say what the code does (the
  law check runs at interior vertices of a piece, not at corners; a
  spatial piece still gets a kind and only records is_planar); the turn
  histogram names its set.

### Stage B — the chord shortcut per patch side (DONE, 2026-11)

Rule (user-approved, option i): a zigzag Chain keeps its one chord-directed
run only for a PatchChain use where the whole Chain is one SURFACE_LINE
piece; every other use gets the split runs. G0 v1.8 DD-30.

Implementation: `chain_refinement.py` decides per use from the shape
relations, which are now built before the runs and have this one reader. A
kept chord run keeps its id; split runs beside a kept chord run are
`directional_run:{chain}:split:{i}`.

Results (capture replays, before -> after):

| | 13 buildings | 8 in-repo captures |
|---|---|---|
| directional runs | 6068 -> 6094 | 585 -> 595 |
| families | 4821 -> 4847 | 490 -> 498 |
| pins | 10112 -> 10138 | 743 -> 725 |
| OBLIQUE runs | 194 -> 188 | 162 -> 172 |
| island diagnostics | 28 -> 18 | 18 -> 13 |
| jogs | 25 -> 15 | 2 -> 2 |

Islands, contradictions (0), unordered island rails and the four invariants
are unchanged. Affected on buildings: 7 distinct border chains (walls f331,
f424, f438, f748, f1215; walls.010 f76, f90), 12 with the walls.003
duplicates. Their 12 chord runs became 38 runs, 32 of them on an axis. Six
stay OBLIQUE without a diagnostic: three diagonal 0.32 m segments 18 degrees
off axis, and three 8.4 m segments 0.57 degrees off axis (inside the snap
angle, past the drift).

DD-43's straight-hinge rule loses nothing on real captures: no shared Chain
there gets several runs on both uses. On the synthetic stepped seam each step
is now two single-patch families instead of one two-use station.

Known Layer 5 regression on the arch (`artist_arch_bevel.json`): pins 57 ->
39, OBLIQUE 44 -> 54. Layer 3 is more faithful there (the foot chain is one
line for the front face and five cornered runs for the foot caps; the
SHARED_CHAIN crossing that joined front and cap is gone), but all three arch
islands are frame-free, and the axis bipartition now leaves one rim arc
OBLIQUE. The frame-free branch is the subject of the next slices.

Tier 3: walls, walls.003 and walls.010 change (diagnostics 11 -> 7, 11 -> 7,
2 -> 0; pins +11, +11, +4); the other ten objects are identical. Tests: 375
-> 394 passed.

Reviewer gate (independent agent): PASS WITH FIXES, nothing blocking. The
reviewer replayed 21 captures against an export of HEAD: directional evidence
changed on exactly 14 uses (the 12 on buildings and the two arch foot caps);
every other use is identical in id, run, direction, length and segments.

- Fixed, tests: the early return for a Chain whose split is one run was not
  pinned; a test now covers a straight Chain with a side that is not one
  surface line.
- Found, existed before, not fixed in this stage:
  1. the frame-free axis bipartition links lines by raw 3D perpendicularity
     even across a fold between two patches, and an OBLIQUE line keeps
     propagating. This is the mechanism of the arch regression. A trial with
     edges only between runs of one patch gave the arch 74 pins and 32
     OBLIQUE runs and left the cylinder captures unchanged;
  2. the AXIS_A seed breaks ties by line id, which holds the family number
     as text, so renumbering families can turn an untouched island by 180
     degrees (walls.003 island:84);
  3. the runs of a Chain are ordered by id as text, so a Chain with 11 or
     more runs has evidence indices out of run order.

Later stages:

```text
C  a surface curve record instead of N single-run families. Amends DD-45,
   closes the curved-chain part of OQ-11.
D  a multi-segment surface line as one run with stations; placement of
   curves; band recognition (Layer 4).
```

## Slice X — right corners decide the axes of frame-free islands (DONE, 2026-11)

Autonomous mode (decision 14). Origin: the Stage B reviewer traced the arch
regression to `skeleton._bipartition_families`. In an island without a rigid
frame it called two lines orthogonal when two of their runs met at a solve
node with raw 3D |dot| <= 0.4, even across a fold between two patches, and a
line made OBLIQUE by a conflict kept propagating an axis.

Rule: Layer 3 `RunCornerRelation` v0 (G0 v1.9 DD-49) records the corner
between two run ends on one patch surface, from the same pairing and angle
as DD-45: STRAIGHT, RIGHT (90 or 270 degrees) or OTHER. Layer 5 links two
island lines only through a RIGHT corner between two runs of the island; an
OBLIQUE line passes no axis on.

Results (capture replays, before -> after; all 508 framed islands identical):

| Set | frame-free islands | pins | frame-free axis runs | bipartition conflicts |
|---|---|---|---|---|
| 8 in-repo captures | 6 | 725 -> 753 | 215 -> 230 | 11 -> 0 |
| 13 buildings | 1 | 10138 -> 10138 | 22 -> 22 | 0 -> 0 |
| 4 reference meshes | 6 | 3614 -> 3634 | 92 -> 103 | 11 -> 0 |

Arch: island 0 (rim + foot cap) axis length 4.58 -> 8.37 of 9.69, pins 5 ->
37; island 1 5.49 -> 6.04 of 7.26; both rim arcs share one axis and the end
chains take the other. Tier 3 on buildings: baseline identical. Tests 400
-> 420.

Losses, checked by the reviewer against the reference:

- arch islands 0 and 1 each lose one CORRECT axis line on the flat foot cap
  (f123:0:2 and f125:0:2, 0.9 m of reference axis length). Its right corner
  links it only to a short run that bevel jogs separate from the seeded
  line, so that group of lines is never reached. Known gap: parallel lines
  split by a jog inside one patch have no relation yet;
- arch island 2 loses one run of a curved chain at a 99.4 degree corner, and
  collumn loses alternating axes along a chain the reference lays as one
  line (8 pins). Both were wrong before.

Reviewer gate (independent agent): PASS, nothing blocking. All 25 captures
replayed against an export of HEAD: every Layer 3 field that existed is
identical, so the refactor of the in-patch pairing changed no family; every
framed island is identical. 9 own mutations, 8 caught, 1 equivalent.

Found, existed before, not fixed in this slice:

1. `_co_orient_axis_families` still compares raw 3D directions and emits
   false "rail co-orientation conflict" diagnostics across a fold (signs and
   UVs stayed correct in the reviewer's case);
2. the stop "an OBLIQUE line passes no axis on" depends on the order of the
   walk: a line degraded after it was popped keeps the axes it handed out;
3. at a pinch vertex (one loop visits a vertex twice) no corner is recorded.

## Reference scene and the parity scoreboard (2026-11)

The user's reference: four production meshes unwrapped by CFTUV with good
results (`buildings3_3.blend`: Arc, building_walls, collumn, Main_wall; Arc
and collumn with Straighten Strips on). Goal (decision 14): similar
structures, not coordinates.

`dev/tools/cftuv_parity/` holds the reference UVs and captures and
`parity.py`, which replays Scaffold without Blender and scores structure
per PatchChain use: line recall (reference straight axis lines that Scaffold
also has), false lines, pin coverage, relative axis agreement inside a
patch, structured patches. Island orientation, island composition and
packing are not scored.

| Mesh | recall after W-B | after X | pin coverage after W-B | after X |
|---|---|---|---|---|
| Arc | 29% | 67% | 30% | 60% |
| building_walls | 97% | 97% | 90% | 90% |
| collumn | 0% | 0% | 6% | 0% |
| Main_wall | 54% | 54% | 58% | 58% |

What the gaps are:

```text
Arc             the front face (69 faces) is a flat ring with bevels; the
                reference lays it as a straight strip (Straighten Strips).
                It is not developable; it needs a strip feature (Layer 4).
collumn         a profiled half column. The reference lays its body
                (352 faces, not developable) and its flat back face as
                rectangles: arcs on one axis, profile chains on the other.
                Strip feature again; the back face also needs a zigzag
                profile chain taken as a line (CFTUV's frame tolerance).
building_walls  remaining misses are a few single-face patches with jogs
                and pins along multi-segment chains (Scaffold pins run
                ends only).
Main_wall       2219 triangles, 2 patches: 491 of its 803 seam edges lie on
                the mesh border and the interior seams are slits with dead
                ends. Both patches are not developable. The reference itself
                is weakly structured there (292 pinned loops). Needs work on
                slit seams inside a patch; left for last.
```

A face-by-face rigid unfolding was measured and not built: of the non-planar
reference patches only the two arch rims unfold without contradiction, and
Slice X already gives them their axes.

## Slice Y — Layer 4 v0: the strip feature (DONE, 2026-11)

Autonomous mode (decision 14, which allows opening Layer 4). The reference
lays the arch front face and the column body as straight rectangles (CFTUV
Straighten Strips). Neither is developable, so no fact of the surface makes
them straight: it is a choice of parametrization, and G0 routes such choices
through Layer 4 and a FeatureConstraint.

Measurement before the rule (`strip_probe.py`, 2509 patches of the
reference, buildings and in-repo sets): "one loop of four uses, an island by
itself, a bent opposite pair, not already a rectangle" matches the arch
front face and the column body and nothing else.

Implementation: `scaffold_core/layer_4_features/` (candidates, instances,
the STRAIGHT_STRIP constraint), `run_pass_2_features`, the strip layout in
`skeleton.py` (frame value STRIP, `_solve_axis` takes a per-run length).
Option `straighten_strips`, off by default; tool switches in parity.py, the
smoke runner (`--straighten-strips`) and the debug add-on. G0 v1.10 DD-50,
phase doc `docs/phases/G4a_strip_feature.md`, AGENTS phase amended.

Results, parity scoreboard with the option on for Arc and collumn:

| Mesh | recall after X | after Y | pin coverage after X | after Y |
|---|---|---|---|---|
| Arc | 67% | 96% | 60% | 85% |
| collumn | 0% | 51% | 0% | 54% |
| building_walls | 97% | 97% | 90% | 90% |
| Main_wall | 54% | 54% | 58% | 58% |

Arch front face: a 2.90 x 0.44 rectangle, 29 pins, residual 9e-16. Column
body: 6.54 x 2.88, 68 pins. With the option off, and with the default Pass 2,
all 25 captures hash identically to HEAD. Tier 3 on buildings: baseline
identical. Tests 420 -> 451.

With the option on, 6 more instances are ACCEPTED but sit in larger islands
(the column's flat back face, one patch of building_walls, 4 one-face arch
soffits of the buildings walls): the constraint is not applied and the island
gets a diagnostic.

A copy of the reference scene with Scaffold's result in a second UV layer is
written by `dev/tools/cftuv_parity/write_scaffold_layer.py`. Looking at it
showed what the scoreboard does not measure:

```text
- Main_wall: Scaffold's pins are geometrically inconsistent and Blender's
  unwrap is badly distorted around them. The axis solve fixes the gauge of
  one connected group of equations only; nodes of other groups get arbitrary
  coordinates and are still pinned. A correctness defect of Layer 5.
- collumn body: the long sides bow inward, because a run of several
  segments pins only its two ends (CFTUV pins every vertex of a frame chain).
- an island without pins comes out of Blender's unwrap at an arbitrary
  scale; the comparison tool has to restore its density.
```

Reviewer gate (independent agent): PASS WITH FIXES, nothing blocking. The
option-off identity was re-checked by hashes on 25 captures against an export
of HEAD: zero differences, also with the default Pass 2. Both intended
rectangles close, are not mirrored and pin only their own patch. 16 own
mutations: 11 caught, 5 survived and are covered now.

- Fixed, rule: "bent" means the Chain is more than 1% longer than its chord.
  Before, any vertex off the line counted, and a flat wall with an arched
  top was accepted (building_walls f240, f249).
- Fixed, Layer 5: a constraint is applied only when its four uses close the
  loop in the given order. A reversed order gave a mirrored rectangle and a
  swapped one a collapsed island, both without a diagnostic.
- Fixed, tests: the one-loop rule, "exactly one piece", a side without runs,
  frozen Layer 4 records.

## Slice Z — consistent and complete pins (DONE, 2026-11)

Autonomous mode (decision 14). Found by rendering the result copy of the
reference scene, not by a metric: large islands of building_walls were torn
around clumps of pins.

Measurement (`floating_pins_probe.py`): the axis solve fixed the gauge of one
node. Equation groups that no equation connects to it (the loop of a window
hole: no chain joins it to the outer loop of its patch) kept arbitrary
coordinates and were still pinned: 772 of 2625 pinned nodes on the reference
meshes, 2161 of 7327 on the 13 buildings captures, up to 150 m from their
place in the island frame. The defect is older than this session; every
earlier pin count included these pins.

Rules:

1. Every connected group of equations has its own gauge.
2. Island with a rigid frame: every group is anchored to the frame, so that
   the mean solved coordinate of its nodes equals the mean of their frame
   coordinate on that axis. A component with an equation on one axis only
   takes its frame coordinate on the other axis. A node that the frame alone
   would place on both axes stays unpinned.
3. Island without a frame, and strip islands: only the largest group keeps
   its coordinates; the others are unpinned, with one diagnostic per axis.
4. Stations: an axis run pins its inner source vertices at their arc-length
   points between its two end pins (CFTUV pins every vertex of a frame
   chain). A vertex without a single occurrence on the run's side is skipped
   and counted by a diagnostic.

`layer_5_runtime/axis_solve.py` is new: the solver moved out of `skeleton.py`
together with the change.

Results (capture replays, before -> after):

| | 8 in-repo | 13 buildings | 4 reference |
|---|---|---|---|
| framed pins beyond drift from their frame position | 43 -> 0 | 2161 -> 0 | 800 -> 28 |
| largest distance from the frame | 36 m -> 3 mm | 152 m -> 5.8 cm | 135 m -> 5.7 cm |
| pins | 753 -> 829 | 10138 -> 11112 | 3728 -> 4122 |
| of them stations | 44 | 948 | 373 |

Roles, islands, the four invariants, contradictions and diagnostics are
unchanged, and every equation group moved by one translation per axis (the
reviewer checked 1965 groups). The remaining 28 are in building_walls
island:1 and inside its main group: runs up to 5 degrees off their axis put
their full length on the axis, up to 1.85 times the drift. A snap question,
not a gauge one.

Parity, pin coverage: Arc 85 -> 97%, building_walls 90 -> 99%, collumn 54 ->
73%, Main_wall 58 -> 88%. Tier 3: only pin and written-loop counts change;
baseline updated. Tests 451 -> 470.

Scoreboard additions (dev tool): `shape`/`torn` and `ishape`/`itorn`, the
agreement of pairwise distances between common pins inside a patch and inside
one Scaffold island x one reference island; `dump_layers.py` and
`render_layers.py` draw the reference and the Scaffold UV layer side by side.

Reviewer gate (independent agent): PASS WITH FIXES, nothing blocking. On 25
captures everything except the new pins is identical to HEAD; 1365 stations
checked against an independent edge walk; 16 own mutations, 12 caught, 2
equivalent, 2 gaps now covered (the contradiction path in a framed island,
a station with two candidate occurrences). Also fixed: no stations on a run
whose two ends are one node; a dead branch removed.

What the pictures show after this slice:

```text
building_walls  the six largest islands are clean, openings in place.
Main_wall       still distorted. Frame-free, not developable, one equation
                group; the cause is not found yet.
collumn         the body is a 6.54 x 2.88 m rectangle (width by arc length);
                the reference lays it about 0.83 m wide (it seems to take the
                chord between the two sides). Same structure, another
                proportion: the user's call.
```

`ishape` on building_walls stays at 78%. The reviewer traced the largest
island: every patch fits the reference exactly, but Scaffold joins walls
across horizontal ledge patches that the reference cut off into their own
islands, so a part of the island is turned by 180 degrees against the rest.
It is another stitch tree, valid as an unfolding. Whether walls and ledges
may share an island is the grouping filter of decision 14, not a pin defect.

## Slice AA — loop direction and the corner turn law (DONE, 2026-11)

Autonomous mode (decision 14). Started from two visible defects of the
reference scene: Main_wall is twisted, and the column's flat back face is
not straightened.

Root causes, all below Layer 5:

```text
Layer 2  a one-edge Chain took its vertex run from the source edge's own
         vertex order. For half of all one-edge chains (930 of 1883 on the
         reference meshes, 2595 of 5072 on the 13 buildings) the run, and
         every Layer 3 run and evidence built from it, ran against the
         Layer 1 Chain. START and END of an evidence were not the loop
         direction. Fixed: the run starts at the Chain's start vertex.
Layer 2  the corner angle of a face was acos of its two edge directions:
         a reflex corner of an n-gon was read as 90 degrees instead of 270.
         Fixed: a corner that turns against the face winding is reflex.
Layer 1  a use of a closed Chain that starts elsewhere than the Chain (a
         ring met by a seam), or whose ends are two occurrences of one
         vertex, got orientation +1 by default. Fixed: the cyclic edge
         order decides.
```

Effect of the three fixes alone on 25 captures (strips off and on):
families, rails, shape relations, islands, frames, roles, lines, the pinned
set and all diagnostics are unchanged. Run directions change, and pin
coordinates by a flip of both axes of an island. Layer 3 corners are
corrected: at HEAD 7004 corners had no arriving and leaving run, now none;
Main_wall drops 230 spurious corners (1009 -> 779) that wrong START/END
roles had paired; on the wall meshes 49 corners change kind OTHER -> RIGHT
and 4 RIGHT -> OTHER (reflex angles); the stitch gate's reason changes on
3 chains without changing any stitch. Every PatchChain use now follows the winding of its side face (3
did not), and the LOCAL_SEGMENT fallback of endpoint samples, which had
covered the reversed runs, now fires only for a closed chain used from a
seam.

The law the fixes expose (G0 DD-51): at a RIGHT corner the END run arrives
and the START run leaves along the loop, so in a layout that is not mirrored
a convex corner turns left and a reflex corner turns right. Measured on
solved islands:

| | corners checked | against the law | mirrored islands |
|---|---|---|---|
| rigid frame, before the fixes | 5218 of 9990 readable | 1559 | 74 |
| rigid frame, after the fixes | 13969 | 0 | 0 |
| no frame, after the fixes, old sign rule | 81 | 3 | 3 |
| no frame, new sign rule | 81 | 0 | 0 |

(The first row is the 13 buildings only; with the old directions 4772
corners there did not even have an arriving and a leaving run.)

Layer 5 change: in an island without a rigid frame the lines of one axis
were co-oriented through single cross runs by comparing raw 3D directions;
lines without such a link kept an arbitrary sign. On Main_wall 14 of 40
pins had the wrong vertical sign (each off by twice the length of one
vertical run), and three islands came out mirrored. Now every RIGHT corner
between two signed runs of different axes fixes the product of their two
lines' signs, and the signs spread from the longest line. A line that two
corners orient differently loses its signs with a diagnostic. No 3D
direction is compared.

Results:

```text
structure   digest of 25 captures, strips off and on: the pinned set, roles,
            islands, frames, lines and diagnostics are identical; only pin
            coordinates of artist_arch_bevel, Arc and Main_wall change.
corner law  0 corners against and 0 mirrored islands on all 25 captures.
Main_wall   parity shape and ishape 84% -> 100% (torn 1/2 -> 0/2); turn
            11/20 with one mirrored island -> 20/20.
Arc         turn 8/13 with one mirrored island -> 13/13 (the shape score
            does not see mirroring).
solve_axis  its 3D-dot normalization flipped 28 equations before and flips
            none now (12788 comparisons).
Tier 3      13 buildings objects, 0 errors; the only differences are the two
            new metrics (corners_against_law, mirrored_islands), both 0;
            baseline updated.
```

Seven synthetic fixtures also broke the law under the old rule (extruded
cross, folded sheets, tubes); no test had checked handedness.

Tests 470 -> 513.

A face that crosses itself or is strongly folded has no usable winding:
read by it, its corners would sum far from (n - 2) * pi (a bow-tie quad on
building_walls: 720 degrees). Such a face keeps the plain angle reading,
chosen by which reading is closer to that sum.

Reviewer gate (independent agent): PASS WITH FIXES, nothing blocking. Own
scripts confirm the law (13969 corners, 0 against, also by an independent
3D check against the fan normal) and, against the CFTUV UVs by a
similarity fit, that Arc island 0 and Main_wall island 0 were exact mirrors
and Main_wall island 1 was twisted, and that all three now fit with zero
error. 17 own mutations: 15 caught, 2 equivalent or trivial. Fixes applied:
the fallback for self-crossing faces above; a diagnostic for a signed axis
line that right corners do not tie to the island's longest line (none on
the 25 captures); the statement about corners in this section, which had
said they do not change.

Left alone, noted for later:

```text
solve_axis still normalizes equations between the same two cross components
  by a raw 3D dot.
_segments_follow_chain (Layer 2) and _patch_chain_reverses_source_path
  (Layer 3) compensated for the reversed runs and are now always trivially
  true / false for open chains.
Main_wall: the stepped bottom of the +X wall stays OBLIQUE (3 cm chamfers
  make 225 degree corners, kind OTHER, which break the right-corner walk);
  632 run ends on seam-cut mid-chain vertices stay unpinned.
```

## Slice AB — a straightened strip leaves its island (DONE, 2026-11)

Autonomous mode (decision 14). The flat back face of the reference column
is an accepted strip (two long sides that bend in the face plane, two short
straight ends), but island assembly stitched it to the two caps across the
short ends, so its constraint was not applied: 16 pins, a bowed side, caps
without pins. CFTUV lays it as a rectangle with all 46 corners pinned and
keeps the caps apart with 2 pins each.

Rule (Layer 5 island assembly, G0 DD-50): a patch with a STRAIGHT_STRIP
constraint is not stitched when every seam its stitch gate accepts is a
straight hinge. Straightening only rescales a straight side; it would deform
a neighbour stitched along a bent side, so such a strip stays stitched and
not applied, as before. With the option off nothing changes.

Before Slice AA this could not work: the run of the back face's one-edge end
ran against the loop, so the strip's uses did not close.

Results (25 captures; with the option off every output is identical):

```text
collumn    the back face leaves: islands 2 -> 4 (2 strip islands), pins
           92 -> 126: 46 on the back face (the reference pins the same 46)
           and 2 on each cap (the reference: 2 each). Parity: line recall
           51% -> 100%, pin coverage 73% -> 100%.
walls.009  one two-face patch (f539) leaves a wall island of 120 patches
           (stitched across two straight sides, its bent sides on the mesh
           border): pins 2004 -> 2006. It was the only link to a part of 10
           patches, which becomes an island of its own (109 + 10 + the
           strip) with the same pins and shape; no new diagnostics.
others     unchanged. The L-shaped faces of the wall meshes have a bent
           side among their stitch candidates and stay stitched.
corner law 0 corners against, 0 mirrored islands.
Tier 3     strips off: baseline identical; strips on: 13 objects, 0 errors.
```

The column's shape score stays low (53%): Scaffold lays the body 2.88 m
wide (arc length) and the back face 1.21 m, the reference lays both 0.83 m
wide and on top of each other. Same structure, another proportion: the
user's call.

A strip that leaves separates what was joined only through it: the caps
of the column, and the part of walls.009 above. That follows from the
rule; a check "leaving must not disconnect the island" would also keep the
column's back face stitched.

Open question for the user (Layer 4 acceptance, not this slice): f539 is a
trapezoid, its straight opposite pair is 3.38 and 2.08 m long. DD-50 v0
accepts it because its other pair is bent; straightening stretches each
straight side by about 24%. A limit on how much a straight opposite pair
may differ would suppress it (the column's back face differs by 10%).

Tests 513 -> 515.

Reviewer gate (independent agent): PASS WITH FIXES, nothing blocking. Off:
identical to main on 25 captures. On: only collumn and walls.009 change;
the corner law holds. 9 own mutations: 6 caught, 2 equivalent, 1 gap, now
covered by an assert on the gate's own refusal reason. The walls.009
split and the trapezoid question above come from the review.

## Slice AC — structure debugger (DONE, 2026-11)

Asked by the user: the CFTUV debugger (Grease Pencil patches and each
patch's own copy of its chains) was enough to judge a structure by eye; the
Scaffold add-on had more modes and the user could not tell which were
right. Wanted: the CFTUV elements, plus the large skeleton structure, plus
patch sides and patch types as far as the algorithm determines them.

Inventory of the old add-on: it ran Passes 0 and 1 only and showed nothing
of Layer 4 or Layer 5. Half of its modes were its own logic: SPINE /
PARALLEL / RIB rail roles from raw 3D directions (no such thing in the
core), and a copy of the stitch gate with another tolerance whose
green/red was not the Layer 5 decision. Toggles did nothing until Rebuild.

Now (`dev/tools/scaffold_graph_debug/`): Analyze runs Passes 0-2 and the
Layer 5 solve once and draws fixed layers from records only; eye toggles
and a line thickness slider act at once.

```text
Structure   Patches (fill per patch); Boundary / Holes (loops);
            Chains: every PatchChain use, one stroke per run, on its own
            patch's side of the edge, coloured by the island axis of the
            run (two colours) or grey (OBLIQUE); Labels
Skeleton    Islands by frame kind (rigid frame / frame-free / strip);
            Lines (runs of one island line share a colour); Nodes; Pins;
            Seams (Layer 5 StitchDecision: stitched or cut)
Patches     Sides (PatchChainShapeRelation: line / curve / unresolved);
            Corners (RunCornerRelation: right convex / right reflex /
            other); Types (Layer 4: strip, strip waiting for the option,
            rectangle, four-sided without a bent pair, other)
Layer 3     Families, Junctions
```

The two chain colours are the two axes of an island. They carry no world
meaning and are not related between islands: there is no orientation
filter yet. A use is drawn on its side of an edge by the winding rule of
G0 DD-51 (the face whose vertex cycle runs along the use owns it), with no
heuristic.

Removed: `rail_assembly.py`, `seam_verdicts.py`, `pair_checks.py`, the v1
renderer, `dev/tools/scaffold_graph_grease_pencil.py` and their tests. The
add-on computes display offsets and nothing else.

Layer 4, one change: `resolve_strip` grades the shape before the option,
so with the option off a candidate is still "already a rectangle" or "no
bent opposite pair", and "option off" marks exactly the candidates the
option accepts. Layer 5 reads only constraints: the solve is identical on
12 captures with the option off and on (reviewer), Tier 3 baseline
identical. Only the inspection report's `suppressed_by_reason` with the
option off changes.

`write_debug_scene.py` writes a .blend with the overlays headless (the
visible checkpoint: `E:/temp/buildings3_3_scaffold_debug.blend`).

What the debugger shows about the core (not fixed here): see "Seen in the
Slice AC debugger" in `docs/agent_handoff.md`.

Tests 515 -> 575.

## Slice AD — a right corner turned over one bridge run (DONE, 2026-11)

Started as "axes for the window holes of Main_wall" (seen in the Slice AC
debugger). Measured first:

```text
holes        the 78 inner loops are glass outlines at the bottom of window
             reveals; the reveals are faces of the facade's own patch
             (the facade-level window outline is interior fold edges)
geometry     both patches are piecewise planar with straight folds but not
             developable: saddle defects up to 35 degrees at the bevelled
             reveal corners; holonomy around 56 of 78 holes is 41-73 deg
ties         no Layer 3 record ties a hole to the outer loop: every hole
             family has one run; a whole-patch unfolding does not close
             (gaps up to 1.8 m)
reference    CFTUV pins no hole: all 66 pins are on the outer loops; hole
             runs are axis-aligned in its UV only through Blender's unwrap
census       Main_wall is the only frame-free island with an inner loop on
             52 captures; in rigid frames 1773 of 1784 hole runs have axes
```

User decision (AskUserQuestion, 2026-11-13): "as in the reference" - the
holes of such islands stay out of the skeleton; take the real gap on
Main_wall instead, the outer loops.

That gap: door notches whose corners are chamfered by a 0.028 m run. Each
chamfer meets its neighbours at 225 degree corners (kind OTHER), so the
right-corner walk stopped there: 12 OUTER runs OBLIQUE (6 chamfers, 3 notch
tops, a 3-line piece of 40.6 m cut off from the seed), 58 pins against the
reference's 66, and lines outside the seed's component were OBLIQUE with no
diagnostic.

Principle: a directional run is straight on its patch surface, so the
boundary turns only at corners. For three consecutive runs A, C, B the turn
from A to B is the sum of the two corner turns; when it is a right angle, A
and B are at a right angle exactly as at a RIGHT corner, and C's direction
against both is known. No length threshold.

```text
Layer 3   RunBridgedCornerRelation v0 (G0 DD-52), built from RunCornerRelations
          of kind OTHER; 34 records on 52 captures (17 in rigid frames, unused)
Layer 5   frame-free islands only: the bipartition and the line orientation
          read it like a RIGHT corner; an OBLIQUE bridge is laid by one
          vector equation per axis; a line the corners never reach gets a
          diagnostic
tools     parity and Tier 3 check the corner turn law at bridged corners;
          the debugger's Corners layer marks them
```

Main_wall, before -> after: OUTER runs AXIS_A / AXIS_B / OBLIQUE 24 / 12 /
12 -> 28 / 14 / 6 (the six chamfers, laid by vectors); pins 58 -> 68 (all
66 reference pins covered; 2 more on the notch top of patch f0, which the
reference pins on the other two notches but not there); parity pin
coverage 88% -> 100%; turn law 20/20 -> 31/31; no UNCONSTRAINED. The f1
outer loop now closes, and the mesh's outline misses closure by 11.3 mm
(real geometry); the solve spreads it, 0.4 mm on the worst run, inside the
drift. Line recall stays 54%: the missing lines are the window holes.

On 50 capture x option runs nothing else changes in roles, signs, pins or
coordinates; rigid-frame and strip islands are identical; the Tier 3
baseline is identical. Diagnostics grow only by the new "island line not
reached by right corners" (Main_wall +1047, Arc and artist_arch_bevel +39,
collumn +48 with strips off).

Known limit (pinned by a test): within the DD-45 tolerance a bridged corner
whose turns miss the right angle by a few degrees is laid as exactly
right, like a RIGHT corner; a miss above the drift gives UNCONSTRAINED with
a diagnostic.

Left alone: `skeleton.py` is past 1000 lines; the frame-free block
(bipartition, line orientation, bridge vectors, unreached lines) is the
natural module to split out.

Tests 575 -> 599.

## Slices AE-1 and AE-2 — bevel strips and junctions (DONE, 2026-11)

Asked by the user: classify bevel geometry at patch level, so that there is
structure inside such patches. Input as the user stated it: a Bevel was
applied; its faces are bounded by seams and cut by seams into strips and
corner junctions, each its own patch; shapes may be curved or noisy.

Measured first (26 generated meshes with ground truth from Blender's Face
Strength attribute; the session "Unbevel" was asked how it finds strips):

```text
by straight sides and corner angles     exact on 1 case of 26
by mesh structure (quad ladder)         exact wherever a strip ends at a
                                        junction, a border or is a ring:
                                        curved, on a cylinder, 20% noise,
                                        multi-segment, short
cannot by structure                     strips that meet at a miter without
                                        junction faces (same topology as a
                                        window reveal); triangulated bevels
"band" as a patch kind                  rejected: on building_walls 398 of
                                        610 patches are single quads
```

User decisions (AskUserQuestion, 2026-11-13): the kinds are set by the
Blender mark where it exists and by a strict structural rule without it; a
plain ladder is a Layer 3 record, not a kind. The user's example mesh
rounded_wall_noise_top (258 faces, 9 strips, 6 junctions, marks and seams
as described) is test data.

AE-1: Layer 0 reads the Face Strength mark; Layer 3 PatchQuadLadderRelation
v0 (G0 DD-53); debugger group Ladders. AE-2: Layer 4 kinds BEVEL_STRIP and
BEVEL_JUNCTION (G0 DD-54); debugger group Bevels. Records only: no
constraint, Layer 5 unchanged (digest on 50 capture runs identical, Tier 3
baseline identical).

```text
case                              by mark          by structure
user's rounded_wall_noise_top     9 / 9, 6 / 6     9 / 9, 6 / 6
cubes (1, 3 segments), short edge all              all
windows, arch, ring, cylinder,    all              none (known limit)
  border strip, inner-arc miter
triangulated window               strips, no       none
                                  direction
other captures (no bevels)        -                none, except one one-quad
                                                   strip with a triangle cap
                                                   on walls (same topology
                                                   as a one-segment bevel)
```

First version of the structural rule called an n-gon-capped cylinder cut
into wall pieces a bevelled prism (6 strips, 2 junctions). Two conditions
from the definition removed it: a strip's rail neighbours are not strips,
and a junction joins at least one strip.

The AE-2 reviewer then showed that with non-quad main surfaces the rule
turned every main surface into a junction (a cube with triangulated main
faces): a one-segment strip has two end-strict readings, and the rule
counted the ends of both. Rule B is now a fixpoint from decided readings
(G0 DD-54): a strip with one end-strict reading is decided, junctions are
found from decided ends, junctions decide the undecided strips beside
them. Result: the four exact cases stay exact, the triangulated-main
cubes give nothing, and what remains is the topology-only false positive
(a quad band capped by non-quad patches: the top of an open slab; one
single-quad strip on the building captures, not in the repo). Rule B
records are candidates and are drawn on their own debugger layers.

Each strip keeps what the user's future filters need (horizontal, vertical,
under a ceiling, outer or inner corner for decals): rails, the neighbour
patches on each rail, the corner kind.

Reviewer gates (independent agents): AE-1 PASS WITH FIXES (an own
brute-force finder agreed with the relation on 953 patches of 25 captures
and about 3600 random synthetic patches; fixes: two test gaps, a red suite
caused by the architect adding the user's case after the test run). AE-2
PASS WITH FIXES (an own implementation of both rules agreed with the code
everywhere; it found the non-quad-main defect of rule B, a Rule A limit on
partial bevels and five test gaps; 21 mutations). The fixpoint form of rule
B was written after that gate: it has the worker's mutation checks (10 of
11 killed, 1 equivalent) and an id-permutation test, and no second
independent review yet.

Tests 599 -> 786.

## Slice AF — bevel strips laid from their ladder; a strip is curved on the surface (DONE, 2026-11)

Target: the user's rounded_wall_noise_top (a curved wall with a noisy top,
9 bevel strips, 6 junction triangles). The user: this mesh must unwrap
well; its own UV is the reference, except the top patch.

Measured first: with strips off the wall band was already the exact
development (0.02% of its length off the reference), but six of nine bevel
strips had no axis and one pin, and came out of Blender's unwrap curved and
at an arbitrary scale (area 0.12 to 10.6 of true); with strips on, the STRIP
rule took both walls for strips and rectified them (the noisy top 0.26 m
off).

User decisions (AskUserQuestion, 2026-11-13): bevel strips as separate
straight islands; a strip is only a patch whose long sides are curved on
the surface; the flat curved bottom patch waits for a "band" kind.

```text
Layer 4  STRIP: accepted only when both uses of the longer opposite pair
         are not one surface line (G0 DD-50); is_bent is gone.
         BEVEL_STRIP by mark -> STRAIGHT_LADDER constraint (G0 DD-54),
         option straighten_bevel_strips, on by default.
Layer 2  the length of every source edge (the constraint reads lengths
         only from Layer 2).
Layer 5  a ladder patch is laid from the constraint: frame LADDER, every
         boundary vertex pinned; it is an island by itself (provisional).
files    layer_4_features/bevels.py and layer_5_runtime/frame_free.py split
         out, no behaviour change.
```

rounded_wall_noise_top, strips off, before -> after: islands 3 -> 20
(LADDER 9, UNFOLDED 8, FRAME_FREE 3); pins 94 -> 243; solver diagnostics
151 -> 57; area of every patch after Blender's unwrap 0.12-10.6 -> 0.99-1.15
of true (the top, without pins, aside); with strips on the walls keep their
exact development. Each pinned vertex of a strip is within 6e-15 of the
constraint; no island is mirrored (39 of 39 corners with the law).

STRIP verdicts that change (strips on), all captures: the two walls of the
user's mesh, the trapezoid f539 of walls.009 (the open question of Slice AB
is closed by this rule), and mitred or inner-arc bevel strips of the test
cases, which the ladder lays when marked. The four references, Arc and
collumn solves included, are unchanged; Tier 3 baseline identical.

A step back, stated: a fully triangulated bevel gets no layout (no ladder
reading, no longer a STRIP), and its strips stay stitched into the main
island, which loses its rigid frame (h_rect_s2_tri, strips on: 72 -> 36
pins, equal to strips off).

Reviewer gate (independent agent): PASS WITH FIXES. It recomputed every
number from geometry (2e-16 against the constraint), proved from the code
that a ladder island cannot be mirrored, reproduced the verdict list with
its own implementation, 17 of 18 mutations caught. Fixes: Layer 4 measured
edge lengths from Layer 0 positions (now a Layer 2 fact), two files past
the size rule split, four test gaps, two unreachable guards removed. It
also reviewed the fixpoint form of rule B from Slice AE-2: equal to DD-54
but for one sentence (now corrected), independent of ids on ten meshes.

The user's reaction to the result: too many small islands; bevels are a
consequence of the main patches and must lie with them. See "DIRECTION SET
BY THE USER" in `docs/agent_handoff.md`: the island rule of this slice is
provisional.

Tests 786 -> 900 (with Slice AG-1).

## Slice AG-1 — index lookups in Layers 1-3 (DONE, 2026-11)

From an external audit of the architecture (the user: take what has real
value). Seven scans repeated per element replaced by indexes built once.
No output changes: 4408 field hashes equal on 38 captures x 2 options
(worker), 17630 equal on 318 inputs including shuffled ids and 120 random
meshes (reviewer, PASS). building_walls tiled 8 times: Layer 1 24.0 -> 0.73
s, Layer 2 25.1 -> 3.26 s, pass 1 135.8 -> 15.1 s; growth near linear.

Not done from the audit: removing the Layer 3 records nothing reads,
Layer 5 speed, an order of failure in the axis solve. Deferred: the
`confidence` fields, a direction field inside a patch, an own relaxation.

## Slice AH — quilts: a user filter with the world vertical, each quilt laid as one chart (DONE, 2026-11)

Target: the user's rounded_wall_noise_top after Slice AF (20 small
islands; the user: too many). Commits 4e0c667, 0b4006f and eb3d99c (the
review fixes); G0 v1.16 DD-55.

The user's direction (see "DIRECTION SET BY THE USER" in
`docs/agent_handoff.md`): by default everything connected is one quilt,
decided from structure; only a user filter splits ("these are walls, that
is a floor or a ceiling"); the user's seams always stay as markup. A
quilt is a set of patches that lie together in UV as one chart, known as
data before any unwrap; a Layer 5 island is a quilt. The user authorised
the G0 amendment.

```text
user_filters  new stage scaffold_core/user_filters/, pass 3
              (run_pass_3_filters, PipelineContext.filter_snapshot), after
              Layer 4 and before Layer 5. Option FilterOptions(world_up=None,
              horizontal_angle_degrees=45.0); world_up is a direction in the
              mesh's own space. With world_up None it emits nothing.
              A patch is HORIZONTAL when acos(|n . up|) <= the angle (n: the
              Layer 2 patch normal), else VERTICAL; no usable normal (face
              area vectors that cancel: Layer 2 area_vector_length at most
              1e-3 of the Layer 2 area) is VERTICAL with a diagnostic. The
              stage reads Layers 1-4, no Layer 0 data.
              A bevel strip by mark (DD-54 rule A) is HORIZONTAL when a rail
              neighbour that is not a bevel by mark is HORIZONTAL; without
              rail neighbours (no ladder reading) every adjacent patch that
              is not a bevel by mark is read the same way; with none, its own
              normal. A junction by mark takes the majority class of its
              strips, a tie is HORIZONTAL. Structural candidates are ordinary
              patches here.
              SeamDirective: SPLIT on a seam between two different patches of
              different classes; JOIN on a seam between two different patches
              of one class when at least one is a bevel by mark.
Layer 5       islands.py: a SPLIT seam is never stitched; a JOIN seam is
              stitched without the angle gate. Tree order: rigid seams, the
              other seams (more edges first), the JOIN seams (longer 3D
              length first, PatchAdjacency.shared_length to 9 significant
              digits, so the key does not depend on the mesh's scale), then
              id.
              uv_cut_chain_ids / SolveResult.uv_cut_source_edge_ids: every
              seam the tree did not stitch, counted by edge sides, so a slit
              seam inside one patch and a SEAM_SELF Chain are cuts.
              A ladder patch with a JOIN lies in its quilt; its
              STRAIGHT_LADDER constraint is not applied there.
write         uv_transfer.write_quilt_uvs: refuses first when the target is
              not visible, a solved face is hidden or another object is in
              Edit Mode; pins, then the solved faces' seam flags set to the
              UV cut set for the call, Blender's conformal unwrap (each quilt
              one chart), charts with fewer than two pins rescaled to their
              3D area; seams, the exact vertex, edge and face selection
              flags, mode and object selection restored. write_pinned_uvs is
              unchanged.
Layer 0       the Face Strength mark is read from the edit BMesh face layer
              in Edit Mode (the attribute data is empty there).
Layer 2       GEOMETRY_FACE_NEAR_ZERO_AREA (DEGRADED): face area at most
              1e-6 of its perimeter squared. New raw fact
              PatchGeometryFacts.area_vector_length: the length of the sum
              of the patch's triangle area vectors.
guard         test_forbidden_imports.py keeps the vertical and the patch
              classes out of every other package; the unused constant
              WORLD_UP is removed from scaffold_core/constants.py.
tools         debug panel: Split vertical from horizontal, Up axis, Angle
              (on, +Z, 45) and the operator "Write UV and unwrap quilts";
              write_debug_scene.py and write_scaffold_layer.py default to the
              filter on (+Z); the smoke tool and parity.py default to off.
              Tools turn a world axis into the object's own space.
```

Why 3D length orders the JOIN seams: most JOIN seams are one or two edges,
so an edge count ties them and the id chose where a ring of joined patches
opens. Measured: the user's mesh gave 85, 136 or 137 pins depending on its
vertex numbering; with the 3D length 137 in every numbering.

Results:

- With the filter off every output is identical to the run without pass 3
  (islands, decisions, pins, vertex UVs, diagnostics on 38 captures, with
  strips on and off). Tier 3 default baseline identical.
- rounded_wall_noise_top, filter +Z: 3 quilts whose patch sets equal the
  reference layout's; 137 pins; after Blender's fill 0 overlaps and 0
  flipped faces; mean corner angle error 4.74 degrees on main, 4.41 now.
  The wall ring opens at f94|f211; the reference opens at f94|f110, the
  same strip on its other rail. No structural fact was found that prefers
  one of the two.
- Bevel test cases, mean corner angle error main / now: f_rect_inarc
  14.73 / 2.20; b_rect_s2 10.50 / 0.00; c_arch_s2 4.81 / 1.60 (strip widths
  1.07, 1.06, 1.06 of true); e_arch_s2_n20 4.88 / 1.59 (widths 1.05, 1.11,
  1.00; 10 pins); g_short 3.07 / 1.62; d_cyl_s2 8.70 / 9.19 (pins 64 to 16).
- building_walls with the filter: quilts 106 -> 294; parity `ishape` 78% ->
  87%.
- Main_wall (filter off, written from Object Mode): the UV cut set went
  from 12 to 312 edges with the slit-seam rule; after the quilt write flipped faces 152 -> 98, mean corner angle
  error 6.62 -> 2.86 degrees.
- GEOMETRY_FACE_NEAR_ZERO_AREA fires once over every capture: g_short face
  f30, 0.53 long and 6e-8 wide, which the layout correctly lays as a line.
- write_quilt_uvs headless on Blender 4.5 and 4.3.2: 13 objects, no crash,
  0 seam flags changed; 0 vertex, edge or face selection flags changed in
  vertex, edge and face select modes, with partial selections and with a
  forced unwrap failure. One hidden solved face changed 444 of 968 loops of
  the visible faces, hence the refusal.
- The no-usable-normal ratio over 2720 patches of all captures: no patch
  changes side of the threshold with the Layer 2 fact; the lowest ratios
  are a closed tube at 0, artist_cross_band f1 at 1.79e-4, then d_cyl_s2
  f0 at 0.065.
- Scale: 38 captures scaled by 0.001 and by 1000 with +Z give the same
  classes, directives, set of stitch decisions, islands and JOIN order.

Stated limits:

- A ladder strip inside a quilt is not laid by its ladder. Its runs go
  through the quilt's line layout. On the user's mesh the bottom quilt's
  strip f36 is sheared: its two rails are each laid at their own length
  (6.86 and 6.97), so cross edges of length 0.074 are pinned 3% to 62% too
  long. On the arch cases the strips have no pins and get their width
  from Blender's fill. On d_cyl_s2 pins drop from 64 to 16. A trial that
  added the ladder's equations to the quilt solve was measured and
  rejected: one width and one length for a strip contradict the exact wall
  lengths, and the wall quilt lost all its pins. (Addressed by Slice AI:
  f36 is kept together in its quilt, shear 0.10 m to 0; a strip that
  develops gets no ladder at all.)
- A quilt without a rigid frame lays only the right-corner component that
  holds its longest line; the other components stay without axes. The top
  quilt of the user's mesh has one line and no pins (a pin needs both
  axes).
- A ring of JOIN seams of equal 3D length still opens by id (g_short: ten
  seams of equal length). On symmetric meshes (cube, ring) that is
  harmless.
- Found by the study, older than this slice: with the filter off the
  island sets themselves depend on vertex numbering on some meshes
  (b_rect_s2, b_ring_s1, f_rect_inarc, h_rect_s2_tri, m_rect_s2_trimain,
  several walls objects), from the edge-count tie-break in the first two
  groups and the order-dependent overlap gate. Using 3D length everywhere
  would change the output without the filter and the Tier 3 baseline: a
  separate slice.
- Policies the user has not decided: a junction tie is HORIZONTAL; a patch
  without a usable normal is VERTICAL; arch soffits are HORIZONTAL and
  split from their walls; JOIN seams enter the tree after the other seams
  (the order "between the rigid and the other seams" was measured: no
  clear winner).
- Charts are not placed or packed: quilts overlap each other in UV.
- `world_up` is in the mesh's own space; a non-uniform object scale is not
  handled by the tools.
- write_quilt_uvs was not tested in the interactive UI, undo was not
  verified, and the bmesh select history (the active element) was not
  measured. It refuses a hidden target or hidden solved faces instead of
  laying them.
- Nothing decides the orientation of a quilt in UV: on the user's mesh
  the wall quilt lies upside down against the reference (straight edge
  up, noisy edge down). A natural home is the user-filter stage, which
  owns the vertical.
- Older than this slice: Layer 2's absolute `EPSILON = 1e-9`
  (`layer_2_geometry/measures.py`) makes some lower-layer facts depend on
  the mesh's scale (at 0.001 the sliver face of g_short gets zero area and
  a zero normal), which changes the order of seams outside the JOIN group
  and the pins at that scale.

Study beside the slice: the user's "straighten shell" prototype (outside
the repo), a UV relaxer in pure numpy: per polygon, rigid shape matching
towards the flat 3D shape, plus straight-line constraints on tagged
chains. Measured on the user's mesh with Scaffold's pins and lines as its
inputs. As a fill it beats Blender's conformal unwrap on a chart without
pins (edge length error 6.5% -> 2.9%, area error 11.3% -> 3.8%) and
slightly on pinned charts. Its line constraints add nothing today: every
vertex of every skeleton line is already pinned (0 unpinned on the
user's mesh's pinned quilts and on the 297 quilts of `walls`).
Straightening the remaining sides has no axis from structure (0 of 31
pieces), and without an axis it breaks the layout (edge error 40%, 13
flipped faces on the top quilt). A start without Blender's unwrap works on
two of three quilts. Conclusion: a candidate to replace Blender's fill;
automatic straightening needs a Layer 4 kind ("band") that declares the
axis. `scaffold_core` has no numpy today; adopting it is a separate
decision.

Reviewer gate (independent agent) on 4e0c667: PASS WITH FIXES. Fixes
applied: the writer no longer touches other objects; slit seams are
cuts; a strip without rails is classed by its adjacent patches; the
vertical is a direction in the mesh's own space; the degenerate normal
test is relative; the guard test; six test gaps; the smoke checks. 15 mutants of the fixes,
all caught.

Second independent review, of 0b4006f and eb3d99c: PASS WITH FIXES. It
confirmed by measurement the cut set against the user's rule on 38
captures, the classes and directives against an independent
implementation and under 8 id permutations, the rescale (186 pinned charts
bit-identical; rescaled charts end at scale 1.0 and no pinned loop moves)
and filter-off equality with main. Fixes applied: the exact selection
restore, the refusals (hidden target, hidden solved face, another object
in Edit Mode), the JOIN key to significant digits, a test for the bevel
exclusion among rail neighbours (a strip whose rail neighbours are all
bevels falls back to its adjacent patches), the Layer 2 fact
area_vector_length in place of a Layer 0 read.

Checks: 963 passed, 4 skipped, 1 xfailed (full suite from the repo root).
Tier 3 default baseline identical (13 objects). `--unwrap-quilts` smoke run
0 errors on Blender 4.5 and 4.3.2; it also fails when a vertex, edge or
face selection flag of the target mesh changes.

Next (proposed, not started): a ladder strip inside a quilt. The rail it
shares with a neighbour takes the neighbour's stations; the free rail
copies them through the ladder's profile lines; the width comes from the
ladder; the strip has no length equations of its own. Also open: the
orientation of a quilt in UV (which way is up), naturally in the
user-filter stage. (The ladder strip inside a quilt is done as Slice AI.)

## Slice AI — a strip that unfolds straight is not straightened; in a quilt the ladder keeps the rails together (DONE, 2026-11)

Target: the bevel strips after Slice AH. Commits db9f7dc (smoke),
db9d9da (the slice) and e0e0cd5 (the review fixes); G0 v1.17 DD-54.

Measured first, two problems:

- A bevel strip confirmed by the mark that already unfolds with straight
  rails (a planar mitred strip; a rounded bevel of several segments that
  is a piece of a cylinder) was squared off into a rectangle by its
  ladder layout. Lone mitred strips had 25 to 66 degrees of corner angle
  error.
- Inside a quilt nothing read the ladder, so the two rails of a strip were
  each laid at their own length and the strip sheared (the user's mesh,
  bottom quilt, strip f36: cross edges 3% to 62% too long).

Three variants were measured. The user's decision (2026-11-14): "a strip
that develops is left alone, and in a quilt the rails are kept together".
Rejected, with their numbers:

- "rails together only" (every marked strip keeps its ladder): the corner
  strip f94 of the user's wall quilt went from 0.0 to 7.3 degrees of
  corner angle error;
- "the strip leads its neighbours" (the ladder gives the strip its axes
  and drags the neighbour): the user's mesh 4.41 to 5.43 degrees, strip
  f35 4.8 to 18.5, the cylinder case's strip next to a disc cap 1.7 to
  22.3.

```text
Layer 4  bevels.py::ladder_constraints: a strip by mark whose two rails
         are each one use whose PatchChainShapeRelation on the strip's own
         side is exactly one SURFACE_LINE emits no STRAIGHT_LADDER. Reason
         "both rails are straight on its surface: it unfolds straight as
         it is", FEATURE_BEVEL_STRIP_NOT_LAID at INFO (the other reasons
         stay WARNING). The principle is DD-50's: a patch that unfolds
         straight without distortion is not straightened. The gate does
         not establish that a strip develops (a conical bevel develops, as
         a curved band, and is straightened); it establishes that the
         strip unfolds with straight rails. The test is the rail shape,
         not planarity: 33 strips in the captures have two straight rails
         and are not planar (cylinder pieces that unfold exactly into
         straight strips); no strip is planar with a rail that is not a
         line. One straight rail and one
         that is not: the strip still emits. Bevel records and rules A and
         B unchanged.
Layer 5  new module quilt_ladders.py, called from skeleton.py after line
         orientation and from pins.py after the stations. Only a quilt
         without a rigid frame reads a ladder (a rigid frame holds planar
         patches, each unfolded exactly; a strip outside the frame is not
         laid and gets a diagnostic). The ladder gives no axis and no
         sign. A strip is read when exactly one rail is stitched in the
         quilt, the quilt lays that rail (its longest run, tie by id, has
         an axis and a sign: the rail axis) and the free rail has no run on
         the across axis; every run end of the strip must be on the ladder.
         Read: the free rail's runs on the rail axis lose their signs (no
         length equation); each free-rail vertex takes the along-rail
         coordinate of its profile-line partner on the stitched rail and,
         across, lies on the line between its rail's two corners (one
         corner pinned: on that corner's row); a vertex whose partner or
         both corners have no pin is unpinned and counted; a run-end pin is
         never moved. Width: one stitched end wholly on the across axis
         gives the free end its length; no end stitched: both ends take the
         constraint's width; both stitched: no change.
         After the solve a strip read whose quilt pins none of its run
         ends loses its ties.
         Outcome per strip in a quilt: kept together, both rails stitched,
         its quilt has a rigid frame (quiet); no rail stitched, its
         stitched rail is not laid on an axis, its free rail has a run on
         the across axis, a run end is not on the ladder, it meets the
         conditions but its quilt pins none of its vertices, its patch is
         outside the quilt's rigid frame, not laid (diagnostics).
         Reads only the FeatureConstraint, the island's stitched Chains and
         the Layer 1 use-to-Chain mapping.
         (2026-11-15, plan Slice AK: the stitched rail is read in pieces
         where the axis of its signed runs changes; the rail axis, the
         across axis, the ties' corners and the outcomes are per piece;
         "kept together" means read in at least one piece.)
tools    debug add-on report: strips laid by themselves, strips a quilt
         keeps together, strips in a quilt that are not read with the
         reason, strips not laid because they unfold straight. On the
         user's mesh with +Z it reports 1 kept together (f36).
smoke    --unwrap-quilts calls write_quilt_uvs with partial selections in
         vertex, edge and face select modes from Object Mode and Edit Mode,
         a hidden target, a hidden solved face and another object in Edit
         Mode, and compares the state before and after.
```

Results:

- Filter off, against main: 11 of 38 captures change (every bevel case
  with marked strips except b_ring_s1 and h_rect_s2_tri); every other
  capture is identical. Islands: a_cube_s1 26 to 1, a_cube_s3 26 to 14,
  b_rect_s2 7 to 3, m_rect_s2_trimain 7 to 3, c_arch_s2 5 to 2, d_cyl_s2
  9 to 7, e_arch_s2_n20 6 to 3, f_border 3 to 2, f_rect_inarc 7 to 3,
  g_short 32 to 1, the user's mesh 20 to 8. Mean corner angle error after
  Blender's fill, whole object: b_rect 10.50 to 0.00 degrees, m_rect 8.40
  to 0.00, f_rect_inarc 14.73 to 1.48, g_short 3.07 to 0.11, c_arch 4.81
  to 2.42, e_arch 4.88 to 2.52, the user's mesh 4.74 to 4.60, d_cyl 8.80
  to 8.39.
- Filter on (+Z): the only layout change is the user's mesh's bottom
  quilt. Pins 61 before and after; pinned-edge length error against the
  3D mean 0.048 to 0.0077, max 0.624 to 0.084; strip f36 shear 0.10 m to
  0. After the fill the mesh's mean corner angle error goes from 4.41 to
  2.85 degrees and f36's from 24.6 to 5.1. The wall quilt (76 pins) is
  unchanged: its corner strip f94 has straight rails and no constraint.
- Smoke: five deliberately broken writers each fail the `--unwrap-quilts`
  run; the real writer gives 0 errors.

Stated limits:

- Regression, measured: d_cyl_s2 strip f154 now lies unpinned in a
  7-patch island; Blender's fill gives it a width ratio of 3.33.
- A strip is read only when the quilt already lays its stitched rail. On
  the user's mesh f71, f73 and f96 are not read ("its stitched rail is not
  laid on an axis"), and f35 meets the conditions in the top quilt, which
  has no pins at all ("it meets the conditions but its quilt pins none of
  its vertices").
- No capture has a strip outside a rigid frame ("its patch is outside the
  quilt's rigid frame, not laid").
- The gate reads Layer 3's SURFACE_LINE, which is decided per vertex (a
  turn under 0.1 rad at each vertex), so a finely tessellated curved rail
  can read as one surface line and such a strip is left unstraightened.
  On the present captures every strip let through turns at most 0.1
  degree in total and every strip kept turns 18 to 167 degrees
  (reviewer's measurement).
- New fold, measured by the reviewer and the worker (filter +Z, the
  user's mesh, after Blender's fill): the bottom quilt has 10 overlapping
  triangle pairs and 2 self-intersecting faces (f36 face 98, f111 face
  123), where before the slice it had none. Cause: the stitched rail of
  f36 turns a corner around f111 over a 1.4 mm bridge run that is
  OBLIQUE; the stitched-rail vertex on it gets no pin, and Blender's fill
  puts it on the wrong side of its neighbour. Before the slice the sheared
  free rail happened to hold that corner open. Variants measured: not
  tying the profile lines at the turn changes nothing (10 pairs); the
  only variants with 0 overlaps put the shear back (the free rail keeping
  its own lengths: 0 pairs, f36 at 22.4 degrees). Decision: keep the
  slice. The pins are right (pinned-edge error 0.0077 mean); the fold is
  the fill at an unpinned vertex. Laying that corner (a bridged right
  corner over one run, DD-52, and a strip placed around a corner) belongs
  to the band slice. (2026-11-15: resolved by Slice AK. The cause was not
  the unpinned vertex: the two sides of the stitched Chain f36/f111 were
  two island lines, so the bridged corner on f111's side was never laid,
  and the ladder was read along one axis only.)
- With the filter off a strip without a ladder constraint is assembled by
  structure, as before Slice AF. Overlapping triangle pairs after
  Blender's fill, before to after: b_rect_s2 0 to 15 (0.04% of the UV
  area), m_rect_s2_trimain 0 to 15, c_arch_s2 4 to 37 (1.07% to 1.66%),
  e_arch_s2_n20 0 to 30 (1.62%), f_rect_inarc 32 to 86 (0.05% to 0.25%),
  d_cyl_s2 317 to 300. Why the assembly allows it: these strips have
  straight rails but are not planar, so they have no rigid placement; a
  part without rigid patches joins through the angle-defect gate with no
  overlap test, the island then has no rigid frame, and a frame-free
  layout is never checked for overlap (h_rect_s2_tri had the same 15
  pairs before the slice). Patches that lose a rigid frame: a_cube_s3 5,
  b_rect_s2 10, m_rect_s2_trimain 10, f_border 1, the user's mesh 6. Pins
  lost by main patches: a_cube_s1 7, b_rect_s2 16, m_rect_s2_trimain 16,
  g_short 15, the user's mesh 3. Pin count over 6 id permutations, before
  to after: a_cube_s1 88 to 65..81, g_short 110 to 48..75, the user's mesh
  243 to 237..267, b_rect 72 to 34..56, m_rect 72 to 36..46: the tie-by-id
  rules of island assembly, an older defect, now decide more islands.
  With the filter on none of this changes.
- No capture has a ladder strip in a rigid-frame quilt, a strip with
  exactly one straight rail, or a strip in a quilt with no rail stitched;
  these cases are covered by synthetic tests only.
- Copying stations follows the stitched rail: one free-rail edge of f36
  (0.0408 in 3D) is laid at 0.0014 because its partner edge on the
  stitched rail is that short.
- With `straighten_strips` on, a strip that no longer gets a
  STRAIGHT_LADDER could get a STRAIGHT_STRIP if its longer pair were its
  curved ends; no capture has such a strip.

Reviewer gate (independent agent) on db9f7dc and db9d9da: PASS WITH FIXES.
It confirmed every number, the Layer 4 gate against its own measure on
every marked strip, f36's ties against its own placement, the boundaries,
21 of 22 mutants; the smoke's five broken writers each fail the run.
Fixes applied in e0e0cd5: the two new outcomes (nothing pinned, outside
the rigid frame), the gate's reason, a test for a rail of two straight
uses that meet at a bend (it still gets its constraint). The f36 fold is
stated as a limit.

Checks: 986 passed, 4 skipped, 1 xfailed (963 before; full suite from the
repo root). Tier 3 default baseline identical (13 objects); quilt smoke 0
errors. 11 mutants of the new code, all killed, before the review. The 29
tests that asserted Slice AF's "every marked strip is laid from its
ladder" were rewritten to keep what they pinned.

Next (approved by the user): the band. A design study with a prototype
(session scratchpad, not in the repo) found:

- It needs no new FeatureKind: it is the STRIP feature (DD-50) with a
  different reading of "four sides". A side is a maximal sequence of runs
  of the patch's one loop between corners that are nearer to RIGHT than
  to STRAIGHT (a turn above 45 degrees; the bridge run of a bridged corner
  is a corner by itself). A band has exactly four sides, and both long
  sides turn on the surface by more than 0.1 rad in total (the
  accumulated turn, not the turn per vertex).
- Why today's rule misses the user's bottom patch f111: its loop has
  three uses, not four, and its outer side turns 90 degrees in total at
  about 5 degrees per vertex, under the per-vertex limit, so it counts as
  one SURFACE_LINE.
- Census over 2720 patches: no building patch is accepted; every strip
  STRIP accepts today is kept (arch soffit, column body, the cylinder's
  strips); one new accept, f111; today's false accepts go away (four
  one-face L-shaped wall faces, and the column's back face f355, which is
  laid today with 37.7 degrees of error). The user's reference lays f111
  the same way (both long sides 6.53 m, against 6.23 and 6.86 in 3D).
- In the bottom quilt with the band (prototype, filter on,
  `straighten_strips` on): pins 61 to 107, fit to the user's reference
  RMS 0.0247 to 0.0175, overlapping faces 3 to 0. It needs three additions
  in Layer 5: the band seeds the quilt's axes; a strip whose stitched rail
  turns a corner is placed by offset from its partners; a 1% length
  tolerance carried by the constraint.
- Known problems: the noisy top patch f0 reads as four sides by no
  structural rule found (its left end has two corners of about 105 to 107
  degrees with a short run between them, which is not a bridged right
  angle), so the top quilt would stay as it is; the cylinder case gets
  worse with the filter on (1.24 to 6.18 degrees) if a band is
  straightened inside a quilt. With `straighten_strips` off the prototype
  changes nothing on any capture.
- Open decisions for the user: straighten a band inside a quilt or only
  alone; which option it sits behind and its default; what to do about
  f0.
- Direction from the user (2026-11-14), for the band slice: a finely
  curved chain or rail may ignore sawtooth noise and count as straight;
  in general each concrete case has to be looked at.
- The coordinating agent's reading (not the user's): sawtooth turns
  alternate in sign and cancel (net turn about zero), while the turns of
  a smooth fine arc have one sign and add up, so the accumulated signed
  turn separates them. The band slice introduces that measure, and both
  rules (the band and the Slice AI gate) should move to it. Before a
  threshold goes into code, the concrete rails are shown to the user
  (largest turn per vertex, net turn, absolute turn, with pictures of the
  disputed ones: the noisy top f0, the column's seam profile, strip f73).
- The band slice also takes the corner of f36 around f111 (see the
  stated limits above).
- What happened (note of 2026-11-15): the band was not built as
  described. A study before the next slice ("band as a sweep", see the
  Slice AJ entry) found that the quad-ladder reading gives no rails for
  f0, f111 or Arc f16, and the user's decisions of 2026-11-15 turned the
  slice into Slice AJ: the STRIP rule reads a rail pair (two curved
  sides that bend the same way), the column's back face f355 is no strip,
  a curved end is left to the fill, and a surface line is also straight in
  total (an accumulated turn of at most 15 degrees, the measure proposed
  above). Saw teeth were deferred by the user. The four-side reading by
  corners, f111 as a band (it already lies straight in the bottom quilt
  with the filter on), f0 and the corner of f36 were not taken; the
  corner of f36 is the first open item of Slice AJ (done as Slice AK).

## Slice AJ — a strip's rails are two curved sides that bend the same way; mirrored sides are no strip; a curved end is left to the fill; a surface line is straight in total (DONE, 2026-11)

Target: the STRIP rule (G0 DD-50) and the surface line (G0 DD-48) after
Slice AI. Commit 77fd542; G0 v1.18 DD-48, DD-50, DD-54.

Measured first:

- With `straighten_strips` on, the STRIP rule took the LONGER opposite
  pair as the long sides and accepted when both were not one surface
  line. The flat back wall of the half column (`collumn|f355`: one n-gon
  face between two mirrored profile curves) was accepted and laid as a
  rectangle: 46 pins, 37.71 degrees of mean corner angle error after
  Blender's fill. The column body (`collumn|f1`) was accepted with its
  profile seams (6.541 / 6.541) as long sides and its real rails, the two
  arcs (2.820 / 2.931), as ends; it came out as a full rectangle (76 pins,
  3.98 degrees, edge error 0.096).
- f1's bottom arc turns 36.5 degrees in total on f1's surface, at most
  3.86 per vertex (15 inner vertices), and Layer 3 called it one
  SURFACE_LINE, because a line was decided per vertex only (the limit
  Slice AI stated).

The user's decisions (2026-11-15):

- f355 must not be recognised as a strip and must not be straightened;
  in it only the top and bottom chains are straight.
- For f1 the user laid the arcs and the rings straight by hand; the side
  profile seams are curved and in principle need not be straightened
  (the user straightened them by hand only because it looks nice).
- The user's definition of a strip (2026-11-14): two curved chains of
  close curvature that go the same way, plus two caps of equal length.
  Arcs are never straightened by themselves, only as sides of a patch
  recognised as a strip.
- "Saw teeth" (straightness that tolerates small ripple by relative
  amplitude) is deferred to a late stage.
- The user reminded the rule: find the root cause, do not treat
  symptoms; the rest was left to the agent's judgement.

```text
Layer 2  ChainGeometryFacts.chord_area_vector (measures.py,
         polyline_chord_area_vector): the area vector of the chain closed
         by its chord, a Newell sum about the mean of its points along
         source_vertex_run (a closed ring gives its own area). None when
         its length is at most COLLINEAR_SINE (1e-6) times the squared
         chain length: a numeric zero test, no shape threshold. It needs
         no plane estimate and flips when the chain is walked the other
         way.
Layer 3  PatchChainShapeRelation (DD-48, patch_chain_shape.py): a piece is
         SURFACE_LINE only when every interior surface turn is within
         GEODESIC_STRAIGHT_TOLERANCE AND its accumulated turn (the largest
         absolute partial sum of its signed vertex surface turns along the
         piece; a zigzag stays small, a slow arc grows) is at most
         SURFACE_LINE_MAX_ACCUMULATED_TURN = 15 degrees; otherwise
         SURFACE_CURVE. The evidence data records accumulated_turn and the
         bound.
Layer 4  STRIP rule (DD-50, build.py): the grades already a rectangle and
         long sides straight on the surface (on the longer pair) stay. One
         grade is added after them and before "option off": a RAIL PAIR is
         an opposite pair whose two uses are both not one surface line and
         whose chord area vectors, each oriented by its use as it walks
         the loop, point opposite ways. Opposite sides of a loop are walked
         in opposite directions, so two sides that bend the same way in
         space have opposite vectors; mirrored sides have the same one. A
         side without a vector (collinear, or no net bow) is no rail. No
         rail pair: SUPPRESSED, new reason NO_RAIL_PAIR = "no curved
         opposite sides bend the same way (mirrored or unlike)". Exactly
         one rail pair holds the rails whatever its length; when both pairs
         are rail pairs the longer holds them (pair 0 on an exact tie). No
         floor on the bend and no bound on how alike the two sides are: no
         case on the captures and buildings needs one (the least alike
         accepted pair is u_rounded f96).
         FeatureConstraint (STRAIGHT_STRIP) gains rail_pair (0: loop
         positions 0 and 2, 1: positions 1 and 3) and
         free_end_patch_chain_ids (the end uses that are not one surface
         line); patch_chain_ids and target_lengths keep their meaning.
Layer 5  skeleton.py, pins.py: the rail pair is AXIS_A (without one, the
         pair with the longer target as before). A free end keeps only its
         two end points (the rail ends, tied across); its inner vertices
         get no coordinate, no pin and no stations
         (IslandSkeleton.fill_run_ids). An end that is one surface line is
         laid straight as before.
tools    the debug overlay draws a strip's free-end runs as unlaid; the
         reason NO_RAIL_PAIR maps to the "four-sided" type; the CFTUV
         parity tool counts a use with a free-end run as NOT_LINE with
         reason FREE_END.
```

The measurement behind the Layer 3 bound: over the 801 SURFACE_LINE pieces
with inner vertices on all captures and the buildings, the accumulated
turn is at most 1.91 degrees on the buildings and 5.48 on Main_wall (hole
rims, two inner vertices each); the next values are collumn f1's bottom
ring at 36.5 and u_rounded_wall_noise_top f111's rail at 90.0; 15 sits in
that gap. Exactly those two pieces change kind; no directional run, pin,
frame, bevel-ladder gate verdict or diagnostic moves; the Tier 3 baseline
is identical.

Results:

- Verdicts against HEAD over every capture and the buildings, in three
  option sets (default; strips on; strips on with bevels off): only
  `collumn|f355` changes (strips on: ACCEPTED to NO_RAIL_PAIR; default:
  OPTION_OFF to NO_RAIL_PAIR). `collumn|f1` stays accepted; its rails are
  now the two arcs and the profile seams are free ends.
- Column after Blender 4.5's conformal fill, strips on: f1 34 pins, 3.59
  degrees, edge error 0.087, 0 flips, 0 overlaps (before: 76 pins, 3.98,
  0.096). f355 is an ordinary patch in an UNFOLDED-frame island with both
  caps: 16 pins, 3.90 degrees, edge error 0.020; it keeps its profile
  shape and its top and bottom are straight; identical to HEAD with the
  option off (before, with the option on: 46 pins, 37.71 degrees).
- Default options: every output identical to HEAD on all captures, the
  buildings and the user's mesh, except the two Layer 3 pieces that change
  kind and f355's suppression reason. Arc and its layout are unchanged
  with the option on.
- With strips on and the bevel option off, the marked strips c_arch_s2
  f26, e_arch_s2_n20 f26, d_cyl_s2 f112 and f114 lose 2 pins each: the
  inner vertex of each 2-segment profile end, now a free end. With the
  bevel option on (the default) they are laid by their ladders,
  unchanged.
- CFTUV parity for `collumn` (the reference lays f355 and f1 as full
  rectangles, which the user's decision now contradicts): recall 100% to
  16%, pin coverage 100% to 40%, shape 53% to 49%. Arc unchanged (96%,
  97%, 100%).

Stated limits:

- A wrong reading of the bend is possible only where the bow of a side is
  below its noise.
- An inflected (S-shaped) side is read by its net bow; an exactly
  symmetric S has none and is no rail.
- A cornered side counts as curved (as before): a planar band with a
  right-angle corner inside each long side is still accepted and
  straightened with the option on (measured on a synthetic L band: 23.6
  degrees after the fill against 0.0 unstraightened). The four one-face
  building patches the option accepts are unchanged. Cutting such sides
  at their corners is not done.
- The rule covers only patches with one loop of exactly four PatchChain
  uses. The noisy top `u_rounded_wall_noise_top|f0` (five uses because of
  a 6 cm chamfer; 30 triangles inside) and `f111` are not candidates.
- The rails of a strip with free ends lie at equal UV length (the mean of
  the two 3D lengths) and at a distance equal to the mean end length, as
  before; with free ends the interior rings of the column come out nearly
  straight, not exactly (only the two arcs are pinned).
- `straighten_strips` is still off by default.
- The fold at the corner of strip f36 (Slice AI stated limit) is
  unchanged.

Also studied before the slice (session scratchpad, not in the repo):

- "Band as a sweep" (`ai\band3\`, report in README_band3.txt and
  partA.txt): the hypothesis that the quad-ladder reading (DD-53) gives a
  band its rails was FALSE for the cases that matter. Of the named bands
  only collumn f1 has a reading; `f0` has 49 quads, 30 triangles and one
  5-gon; `f111` is 29 triangles and one quad; Arc f16 has 7 triangles
  forming an interior pole. 3D sweep measures alone cannot tell a band
  from a wall that develops (u_rounded f211 reads as a sweep in 3D); the
  developed-surface test is still needed. Two separate questions remain:
  station correspondence (topology: a ladder reading, a face strip, or
  the mark) and whether to straighten (geometry, or the user's intent).
  For f0 and Arc f16 no structural fact was found for either.
- `f111` already lies straight in the bottom quilt with the filter on
  (through its neighbours); `f0`'s quilt has no pins.
- The user's hand tool (a numpy prototype outside the repo; operator
  "Straight, Snap to U/V") straightens edges the user selects, including
  interior edges that are not seams. Where structure is silent (f0, Arc
  f16, exactly straight interior rings), a user-selected set of edges is
  a possible future input of the same kind as the Face Strength mark and
  the vertical filter. Open proposal for the user: NOT decided, NOT
  approved.
- Saw teeth, deferred by the user: the measured facts of the case sheet
  (`ai\band\cases2\`) stay valid for when it is taken up: relative
  amplitude has a natural gap between 0.93% and 2.03%.

Reviewer gate (independent agent), round one: PASS WITH FIXES. It
reproduced the numbers, proved the default output identical to HEAD,
checked the verdicts under mirroring, rotation with scale, flipped winding
and id permutations (no difference), and ran 13 mutants plus two (one that
mattered survived: removing the station skip; now caught by a new test).
Its main finding: the first version read the bend sign from Layer 2's
plane estimate (a signed turn in the chain's plane), which fails under
out-of-plane noise: a mirrored wall with noise of 5% of a segment was
ACCEPTED in 2 of 4 seeds, and u_rounded f35 was wrongly rejected. The
chord area vector replaced it; a test now holds a noisy mirrored wall at
NO_RAIL_PAIR and a noisy real strip accepted at 5% and 10% noise over
four seeds. Second round, on the fixes: PASS. It confirmed
the claims with its own whole-state dump (default output identical to HEAD
except the two Layer 3 pieces and f355's reason; f35 identical in every
option set), repeated the invariance checks on the new fact, measured that
the smallest curved strip side lies about 400 times above the numeric zero
test, and caught all six mutants of the fixes. A wrong ACCEPT of a mirrored
wall is still constructible only when the noise reaches about the bow of
the side (bow 0.1 of the side's length: from one segment of in-plane
noise; at a bow of 0.4 never, up to two segments). Not tested, no case in
the data: a curved SEAM_SELF Chain on two opposite sides would be a rail
pair by construction, and Layer 4 does not guard Layer 2's degraded
edge-order fallback.

Seen on the checkpoint scene and not changed by this slice: the back wall
f355 lies in its true shape but turned by about 1 degree. Its rigid frame
takes its axis from the longest line, one of the two tapering shaft runs
(5.517 long, 1.03 degrees off the wall's own vertical), so the top and
bottom chains are OBLIQUE and the mirror shaft run is OBLIQUE and has no
pins. This is the open question of the orientation of a quilt, on one
patch.

Checks: `python -m pytest` 1020 passed, 4 skipped, 1 xfailed (986
before; full suite from the repo root). Tier 3 on buildings: baseline
identical, 13 objects.

Next, open items in this order:

1. The fold at the corner of strip f36 around f111 (Slice AI stated
   limit; unchanged). DONE as Slice AK (2026-11-15).
2. Quilt orientation.
3. The user-selected-edges proposal (above): awaiting the user.
4. Saw teeth: deferred by the user.
5. The older open items already listed in this plan stay (among them,
   from Slice AI: d_cyl_s2 f154, strips not read in their quilts, the
   filter-off overlaps and the tie-by-id rules of island assembly; from
   Slice AH: the four open policies; from Slice AF: the scale of charts
   with fewer than two pins).

## Slice AK — in a quilt the two sides of a stitched Chain are one line; a ladder strip is read in pieces where its rail turns; the drift of a frame-free island is per metre of the island (DONE, 2026-11)

Target: the fold at the corner of strip f36 around f111 (the Slice AI
stated limit, the first open item of Slice AJ). Commit 46e5a35; G0 v1.19 DD-47, DD-52, DD-54, DD-55.

The user's decision (2026-11-15): this defect is the next slice ("the fold
at f36"), and the rule holds: find the root cause, do not treat the
symptom. No other decision was asked of the user. One thing in the slice
touches an earlier user-approved rule, the drift tolerance of plan Slice
S: its constant (1 mm per metre) is unchanged, but for islands without a
rigid frame it is now measured against the larger of the island's two axis
spans instead of the span along the solved axis (decision 18).

Measured first: the user's mesh `u_rounded_wall_noise_top`, user filter on
(`world_up` +Z), quilts laid by `uv_transfer.write_quilt_uvs`. After
Blender's fill the bottom quilt (the flat band f111 with the marked bevel
strips f36, f73, f95 and three junctions) had 10 overlapping triangle
pairs (5 face pairs) and 2 self-intersecting faces (f36 face 98, f111 face
123) where strip f36 wraps around f111's corner. Slice AI recorded it as a
stated limit and blamed one unpinned vertex.

The cause (study in the session scratchpad `ak_study\`, NOTES.txt, not in
the repo):

- Layer 3 is right. On f111's side the corner is a recognised
  RunBridgedCornerRelation: 135.00 + 135.02 - 180 = 90.02 degrees over the
  1.4 mm edge e312 (v208-v210), the near-collapsed inner side of f36's
  mitre face f98 (its other side, e314, is 40.8 mm). On f36's own surface
  there is no right corner there: 212.65 + 212.20 = 244.85 where 270 is
  needed, 25.15 short, which is the angle defect (12.35 + 12.79).
  Loosening that tolerance would have been a symptom fix.
- In the frame-free bottom quilt the runs of f111 along the stitched Chain
  f36/f111 formed one island line and the runs of f36 over the same
  segments and nodes another. Nothing said they are one UV line, although
  in a quilt a stitched Chain has one UV per vertex. The quilt's axes
  started from f36's free rail and spread only through f36's own right
  corners; all 29 runs of f111 stayed OBLIQUE, the bridged corner was never
  laid, and the whole leg of f36 past the corner had no place (v210, v157
  on the stitched rail; v211, v158 on the free rail), not one vertex.
- The Layer 4 ladder of f36 runs straight through its mitre on one axis
  (22 profile lines over 7.368), and `quilt_ladders.py` read a strip along
  one laid axis only.
- With the lines joined the solve reaches f95, whose two long sides are
  0.4218 and 0.4207 against f111's ends 0.4207 and 0.4198: measurements of
  one distance that differ by up to 2 mm. The frame-free residual
  tolerance was 1 mm per metre of the span along the solved axis: 0.42 mm
  across a 0.42 m band, so the equations were contradictory and pins fell
  from 40 to 11.

```text
Layer 5  frame_free.join_stitched_lines (island level, frame-free islands
         only; skeleton.py runs the rail signs first, then the join, then
         the bipartition and the orientation): within one island, two
         signed runs of two different uses of a stitched Chain with
         identical segment_indices become one line; their relative
         orientation is o_a * o_b * s_a * s_b (the uses' orientation signs
         and the run signs, DD-51), joined by a union-find with parity.
         Runs that overlap only in part are not joined (a partial overlap
         may hide a corner on one side). A pair that contradicts lines
         already joined keeps the line's earlier orientation and gets the
         diagnostic "stitched Chain sides disagree on their line
         orientation: ... -> one line, it keeps the orientation it had". A
         joined line keeps the id and orientation of its longest part
         (tie: the smallest id) and counts its stitched Chain once; a line
         Layer 3 itself built across both sides of a seam is counted as
         before. It reads Layer 3 run fields and the island's stitched
         Chains only; no walk. It does not run in an island with a rigid
         frame. The rail/line check compares the rail pieces with the
         lines cut from them, before the join.
Layer 5  quilt_ladders.py: a ladder strip in a quilt is read in pieces. A
         signed axis run of the stitched rail holds the profile lines
         between its two ends; a line held on exactly one axis is in a
         piece, a line held on both axes (a plain right corner) or on none
         is in no piece; neighbouring lines share a piece only when one
         run holds both. Within a piece the Slice AI rule is unchanged
         (rail axis and across axis per piece; the ties' corners are the
         free-rail vertices of the piece's first and last line). A
         free-rail run that spans two pieces (a mitre) keeps its sign and
         role. Lines on no piece are not tied, and a strip that ends read
         gets the diagnostic "ladder strip in a quilt read in pieces, N
         profile lines on no piece -> not tied". Outcomes: "kept together"
         now means read in at least one piece; "its stitched rail is not
         laid on an axis" now means no piece at all; "its free rail has a
         run on the across axis" refers to the across axis of the piece
         the run lies in. Every strip still gets exactly one outcome.
Layer 5  skeleton._island_drift, axis_solve.py (refactor: _axis_equations,
         axis_span): for an island without a rigid frame that is not a
         STRAIGHT_STRIP island, the residual tolerance of both axes is
         RESIDUAL_TOLERANCE_PER_SPAN (1e-3, unchanged) times the larger of
         the two axis spans. Rigid-frame islands keep the drift they share
         with the jog check (plan Slice U); strip islands keep each axis'
         own span. Argument: the model puts each line exactly on its axis
         while a real line may run off it by the drift; the error this
         leaves in the cross coordinate grows with the line's length, so
         equations across a long thin island disagree in proportion to its
         length, not its width.
tests    test_layer_5_runtime.py: the join (parity, partial overlap not
         joined, an arc seam fixture whose two sides really are two
         families, the chamfer fixture's far-side bridged corner with a
         stand-in for Layer 3, which the test says), the drift per metre of
         the island (1 mm of noise absorbed on a 10 x 0.3 m band, a 5 cm
         taper still a contradiction, paired negative on the old span);
         test_layer_5_quilt_ladders.py: the pieces of a stitched rail, a
         strip read in two pieces with its rails together in each, the
         across-axis outcome per piece, f36 of the user's mesh; the debug
         report test counts f73 as kept together.
```

Measured before changing the drift (all 34 captures including the 13
building captures, filter off and +Z; 48 and 42 islands without a frame):
with the join and the pieces off exactly one axis changes verdict,
e_arch_s2_n20 +Z island 1 (f1/f3, a band 9.60 x 0.31 m), AXIS_B: 4
equations, residual 0.566 mm on widths 0.3106 against 0.3117 (0.18%),
tolerance 0.311 mm to 9.6 mm, pins 10 to 36. With the join and the pieces
on also u_rounded +Z island 2, AXIS_B: residual 0.713 mm on 0.4218
(0.17%), tolerance 0.572 mm to 7.01 mm. Both are noise: e_arch_s2_n20's
generator adds up to 1 cm of random offset per vertex; on the user's mesh
the widths 0.4218 and 0.4207 lie 72 mm apart (15 mm per metre) while over
the next 7 m the width changes 0.9 mm (0.13 mm per metre). A real taper (5
cm on a 0.3 m band) stays a contradiction (test). The reviewer's smallest
case the new form absorbs and the old rejected: a 10 x 0.3 m band whose two
widths differ by up to about 9 mm (rails converging about 0.05 degrees);
both widths are then laid at their mean.

Results:

- User's mesh, +Z, bottom quilt after Blender 4.5's fill, before to now:
  overlapping triangle pairs 10 to 0; self-intersecting faces 2 to 0;
  flips 0 to 0; pinned source vertices 40 to 61; f36 shear between its
  rails, mean / max, 1.68 / 35.57 to 0.01 / 0.13 degrees; f73 4.34 / 22.24
  to 0.55 / 2.02; mean corner angle error 4.00 to 5.28 degrees (max 101.93
  to 31.64); pinned-edge error 0.0071 to 0.0335. Per patch (angle error,
  pinned-edge error, pins): f111 4.08 to 5.20, 0 to 0.0461, 18 to 29; f36
  5.08 to 5.33, 0.0086 to 0.0288, 40 to 44; f73 2.94 to 6.86 (max 3.99 to
  23.91), 0 to 0.0269, 0 to 16; f95 0 to 0.43, 0 to 0.0009, 1 to 4;
  junctions f28, f30, f31 angle 0 to 0, f30 and f31 0 to 2 pins each. The
  other two quilts of the mesh are identical.
- Where the cost comes from: f111 is a band of two straight parts and a
  rounded corner between them (its f36 side 6.86 m, its f73 side 6.23 m;
  it turns about 81 degrees) and is now laid straight along f36; its inner
  side is three lines and the curved middle (5 runs, 2.89 m in 3D) stays
  OBLIQUE and is stretched by the fill to 3.52 m, which shows as a bulge;
  f73's largest errors sit where its tied pieces meet that untied middle
  (4 of its 10 profile lines are on no piece); f36's free mitre edge
  v209-v211 (40.8 mm) is laid at 106.6 mm.
- For comparison, the user's own layout of that quilt (UV layer `UVMap`):
  f36 also turns 90 degrees with f111's corner and is not cut there; the
  mitre is kept short (32 mm) and the leg past the corner is pinched (4.8
  mm wide against 72 mm); it has 4 overlapping pairs, one
  self-intersecting face, one flip, a mean angle error of 4.39 degrees and
  f36 shear 7.0 mean / 34 max.
- Full-state comparison against HEAD (every pin UV, role, sign, outcome,
  tie, diagnostic) on every capture, the 13 buildings and the user's mesh.
  Filter off (the default): pins, roles, outcomes and ties identical
  everywhere; the only differences are signs on OBLIQUE runs (which give
  no equations) and fewer "not reached" diagnostics on b_ring_s1, d_cyl_s2,
  e_arch_s2_n20 and f_rect_inarc.
- +Z: every moved HEAD pin set is a pure translation (no rotation).
  a_cube_s3 both quilts 52 to 60 pin records (after the fill the four
  octant junctions f0, f14, f28, f42 go from 3.87 to 4.64-4.80 degrees mean
  and 9 to 16 max: their arc sides are now one line with the straight strip
  rails they are stitched to, so the arcs are laid straight; the octant has
  78.5 degrees of angle excess); c_arch_s2 quilt 41 to 43, f26 kept
  together; e_arch_s2_n20 f1/f3 0 to 26 pin records (after the fill angle
  error 0.00 to 1.16, pinned-edge error mean 4.6 mm, max 19 mm: the pins
  impose a straight band on a noisy one), its f22 quilt 0 to 3, f26 "its
  quilt pins none of its vertices"; u_rounded bottom quilt as above, f73
  kept together; d_cyl_s2, b_ring_s1, f_rect_inarc only OBLIQUE signs and
  diagnostics.
- Buildings: no difference; the Tier 3 seamed run baseline is identical
  (13 objects); the quilt smoke as HEAD apart from timing and residual.
- The cause is general: with +Z, 15 stitched Chains in frame-free quilts
  had one side on an axis and the other OBLIQUE (a_cube_s3 8, u_rounded 3,
  e_arch_s2_n20 3, c_arch_s2 1); with the filter off none; buildings none
  (no frame-free islands).

Stated limits:

- The cost above: the quilt's mean angle error and pinned-edge error rise
  because the band is now really laid straight; the curved middle of
  f111's inner side is not laid (OBLIQUE) and bulges; f73's largest angle
  error is about 24 degrees there; f36's mitre edge is stretched 2.6
  times.
- The ladder still gives the quilt no axis (Slice AI's decision): the
  middle of f73 is not read.
- As the seed of the bipartition and orientation, the length of a line
  counts a joined line's stitched Chain once but a line Layer 3 built
  across a seam twice, as before. Counting once everywhere was measured
  and moves three captures (b_rect_s2, h_rect_s2_tri, m_rect_s2_trimain
  lose 12 pins each because another component becomes the seed). Not
  changed in this slice.
- A frame-free quilt still lays only the right-corner component that holds
  its longest line, and is not tested for overlap.
- The new drift absorbs a width disagreement of up to 1 mm per metre of the
  island's length: a band 10 m long may have its two end widths differ by
  about 9 mm and be laid at their mean.
- Only runs over identical segments join; a seam whose two sides are cut
  differently (one side takes the DD-30 chord shortcut) stays two lines.
- The top quilt of the user's mesh (noisy f0) still has no pins; saw teeth
  stay deferred by the user.
- The chamfer test's join case in a small fixture rests on a stand-in for
  Layer 3; the real case is the user's mesh capture.

Reviewer gate (independent agent), round one: PASS WITH FIXES. It
reproduced the tests, Tier 3, the quilt smoke and the user's quilt numbers
with its own dump and metrics; confirmed the parity of the join (15 tests
catch its removal), that nothing is walked, that the pieces come only from
the roles, and that the drift argument is sound; checked mirror, rotation,
scale and id renaming on four meshes (no difference: the slice adds no id
dependence); ran ten mutants (two survive with identical output on all
data). Findings fixed: partial segment overlaps were joined (a constructed
forced stitch lost all 10 pins of an island); a joined line summed both
sides' lengths and took the smallest id, so five frame-free islands of
a_cube_s3 came out turned with the filter off (the worker's first
comparison counted pins and missed it); two diagnostic texts that could be
untrue; strip islands' drift had changed without being part of the
decision; a test rested on a stand-in for Layer 3 (a fixture whose arc
seam really has two families was added; the chamfer test keeps its
stand-in and says why). Second round, on the fixes: PASS
with one test added. It confirmed with its own dump of every pin UV that
with the filter off every capture and the buildings equal HEAD (the only
differences are signs on OBLIQUE runs and fewer "not reached"
diagnostics) and that with +Z every moved pin set is a pure translation;
it caught the mutants of the fixes. Two of them (the smallest id instead
of the longest part; both sides of a joined line counted) were caught
only by a unit test and bring back the turned islands of a_cube_s3: an
integration test on that capture now catches both.

Limits it asked to be stated:

- The seed bias is inherited, not added: a 1.0 m seam that Layer 3 built
  as one line on both sides counts 2.0 and beats a 1.5 m joined line. The
  seed matters at all because `bipartition_families` gives axes only to
  the corner component of the seed line; seeding every corner component
  is the follow-up, not another way of counting.
- An exact length tie between the parts of a joined line is the normal
  case (96 joins on the captures) and is decided by id; flipping the tie
  changes no pin, role or outcome on any capture, only the label of
  OBLIQUE lines.
- e_arch_s2_n20 with +Z, island f1/f3: under a renaming of vertex and
  face ids it comes out turned by 180 degrees. HEAD's existing seed
  tie-break by id causes it; it is visible now because the island has
  pins.
- A STRAIGHT_STRIP island's drift decides nothing (its runs are scaled to
  the constraint's targets, so its equations leave no residual); no test
  pins it.

Checks: `python -m pytest` 1028 passed, 4 skipped, 1 xfailed (1020 before;
full suite from the repo root). Tier 3 on buildings: baseline identical, 13
objects; quilt smoke as HEAD apart from timing and residual.

Next, open items in this order:

1. The curved middle of a band in a quilt (f111's inner side, f73's
   untied lines): the ladder gives the quilt no axis.
   (2026-11-15: done by Slice AL; see that entry.)
2. Quilt orientation (also the one-patch case of the column's back wall,
   Slice AJ).
3. The user-selected-edges proposal (Slice AJ): awaiting the user.
4. Saw teeth: deferred by the user.
5. A frame-free quilt is not tested for overlap.
6. The older open items already listed in this plan stay (among them,
   from Slice AI: d_cyl_s2 f154, strips not read in their quilts, the
   filter-off overlaps and the tie-by-id rules of island assembly; from
   Slice AH: the four open policies; from Slice AF: the scale of charts
   with fewer than two pins).

## Slice AL — in a quilt the mark makes a ladder strip's stitched rail one line; that line gives no length, its nodes are stations by 3D length (DONE, 2026-11)

Correction (note of 2026-11-15) to the Slice AK entry above, which stays
as written; measured in the study of this slice:

- f111 turns 90.0 degrees, not about 81, and is not two straight parts
  with a rounded corner. Its outer side (f36's side, v79 to v208, 6.864 m)
  is one uniform arc along its whole length: 16 vertices turn 5.29 to
  5.30 degrees each in plan, the two next to its ends 2.65. Its inner
  side (f73's side, v157 to v160, 6.233 m) has near-straight ends (v164,
  v178 6.51; v162, v180 4.86) and a curved middle (8.55, 10.77, 12.36,
  12.36, 10.77, 8.55). The 3D width is 0.42 m at the ends, 0.45 at the
  shoulders and 0.346 in the middle; the sides differ by 0.631 m.
- The stretch of the middle was not a bulge chosen by the fill. The pins
  fixed the inner side's ends at the outer side's along coordinates and
  its straight parts at their 3D length (1.671 m each), so the five middle
  runs had to cover 6.8647 - 2 x 1.671 = 3.522 m for 2.889 m in 3D. The
  fill spread it unevenly (per edge 1.335, 1.177, 1.087, 1.174, 1.334)
  and laid a zigzag of up to 0.036 m across (largest at v170).
- f73's largest corner angle error, 23.9 degrees, is not where its tied
  pieces meet the middle. It is on its end faces f75 and f91, whose 3D
  corners are 66 and 114 degrees (skewed rungs) and which
  the ladder lays at 90. It is the same in every variant measured, with
  the whole of f73 tied, and this slice does not remove it.
- f73 has 12 profile lines, not 10; 4 of the 12 were on no piece.

Target: the curved middle of band f111 in the bottom quilt of the user's
mesh `u_rounded_wall_noise_top` with the user filter on (`world_up` +Z),
the first open item of Slice AK. Commit d3d766f;
G0 v1.20 DD-47, DD-52, DD-54, DD-55.

The user chose this slice on 2026-11-15 ("the bulge of band f111"). The
rule was chosen by the architect among the study's measured variants
(B4 with the corner cut, below), because it reproduces the user's own
layout of that quilt: the outer side keeps its length, the inner side is
stretched evenly along its whole length, both are straight. This is plan
decision 19, taken by the architect inside the slice the user chose; the
user may reverse it.

Measured first (study in the session scratchpad `al_study\`, NOTES.txt,
not in the repo; Blender 4.5 on a copy of the user's scene):

- At HEAD the quilt is frame-free. f111's outer side is one island line
  with f36's stitched rail (19 runs, 6.864 m, AXIS_A, joined by Slice
  AK); f111's inner side is seven lines: F137 (v160 to v176, 1.671 m) and
  F143 (v166 to v157, 1.671 m) on AXIS_A through the right corners at
  v159 and v157, and F138 to F142 (one run each, 0.575 to 0.580 m) that
  no right corner reaches, OBLIQUE. v174, v172, v170 and v168 get no
  coordinate. f73's rails follow: its free rail is tied only on its two
  straight parts.
- The user's own layout (UV layer `UVMap`, ratios normalised by its
  median UV/3D scale 0.2391): f111 is straight (the outer side deviates at
  most 0.008 from its chord over 6.84, the inner side at most 0.006). The
  outer side keeps its length (0.999; per edge 0.96 to 1.025, no trend).
  The inner side takes all of the difference, along its whole length, not
  only in the round: 1.095 overall, per edge 1.036 to 1.124 (the middle
  five 1.109). The width in UV is nearly constant, 0.426 to 0.446 (3D
  0.346 to 0.453). After-fill metrics of that layout: corner angle error
  mean / max 4.39 / 52.1 degrees, f111 2.67 / 12.8, f36 4.23 / 40.6, f73
  4.30 / 11.4; 4 overlapping triangle pairs, 1 self-intersecting face, 1
  flip. No CFTUV reference exists for this mesh. The user did not
  straighten the noisy top quilt fully (f35 keeps about 55 of its 84
  degrees of round).

The cause:

- The straightness of a marked ladder strip's stitched rail in a quilt
  came only from Layer 3 families. A family continues at a run-end
  junction when the junction turns at most GEODESIC_STRAIGHT_TOLERANCE
  (0.1 rad = 5.73 degrees) there, judged per junction, with no bound on
  the accumulated turn.
- Outer side, per vertex (on f111 | on f36): 5.29 to 5.30 | 3.74 to 3.76 at
  all 16 turning vertices, all under 5.73: one family on each side, one
  line, a 90-degree arc laid straight.
- Inner side, v164 to v178 (on f111 | on f73): 6.51 | 4.61, 8.55 | 6.05,
  10.77 | 7.62, 12.36 | 8.76, 12.36 | 8.76, 10.77 | 7.62, 8.55 | 6.05,
  6.51 | 4.61. On f111 each breaks the family; on f73 v164 and v178
  continue and the six middle ones break. With the stitched-side join
  that gives the seven lines above, five of them reached by no right
  corner.
- Both sides turn 90 degrees; only the subdivision differs (16 vertices
  against 8). The user's mark (STRAIGHT_LADDER) says the rail is straight,
  but nothing made it one line. Layer 3's own PatchChainShapeRelation
  (DD-48) records both sides as SURFACE_CURVE (90.0 and 128.5 degrees on
  f111's and f36's sides), but no family or line reads it.

Variants measured (study; bottom quilt after Blender 4.5's fill; pins are
pinned source vertices, angle error mean / max in degrees, inner and
outer side UV/3D):

| variant | pins | overlaps | self-x | angle error | pinned-edge | f111 | outer | inner |
|---|---|---|---|---|---|---|---|---|
| user's layout | - | 4 | 1 | 4.39 / 52.1 | - | 2.67 / 12.8 | 0.999 | 1.095 |
| HEAD | 61 | 0 | 0 | 5.28 / 31.6 | 0.0335 | 5.20 / 23.3 | 1.000 | 1.103 (uneven) |
| A: one line, lengths kept | 0 | 10 | 2 | 1.68 / 97.1 | - | 2.06 / 97.1 | 0.996 | 0.999 |
| B1: lines no corner reached give no length | 69 | 0 | 0 | 5.67 / 33.9 | 0.0584 | 6.21 / 23.3 | 1.000 | 1.101 (1.219 on the middle) |
| B2: weighted, hard straight parts | 69 | 0 | 0 | 4.39 / 34.4 | 0.0526 | 2.95 / 10.8 | 0.940 | 1.031 |
| B3u: plain least squares | 69 | 6 | 0 | 5.53 / 133.5 | 0.3244 | 5.23 / 133.5 | 0.953 | 1.033 |
| B3w: least squares 1/length | 69 | 0 | 0 | 4.47 / 32.8 | 0.0484 | 3.14 / 10.2 | 0.955 | 1.048 |
| B4: a line the mark made gives no length | 69 | 0 | 0 | 4.49 / 33.9 | 0.0468 | 3.20 / 8.4 | 1.000 | 1.101 |

A: the cycle of 19 outer runs and the bridge against 9 inner runs
disagrees by 0.631 m, every AXIS_A equation is contradictory and the
quilt pins nothing (the pre-AK fold). B2 and B3w exempt the marked line
from the drift tolerance; on the noisy top quilt that exemption pins 55
vertices at 9.48 degrees mean. B4 changes nothing in the top quilt. A
second cut at DD-48 surface corners (one vertex turning at least 42
degrees) would separate f35's mitre in the top quilt, but it needs a
DD-48 amendment (PatchChainShapeRelation has one reader by contract) and
changes nothing in the bottom quilt; it was not built.

The rule (Layer 5, islands without a rigid frame only):

```text
Layer 5  quilt_ladders.stitched_rail_uses: for each strip of a frame-free
         quilt that read_quilt_ladders could read (every run end of its
         patch on the ladder, exactly one rail stitched), the stitched uses
         of its stitched rail whose Chain the quilt stitches; the free rail
         is never named. It lives here because this module is Layer 5's
         only reader of the FeatureConstraint. The module rule now says
         the ladder chooses no axis and no sign, but its mark makes the
         stitched rail one line.
Layer 5  frame_free.join_marked_rails (rule 1), after join_stitched_lines,
         before the bipartition: the signed runs of each such use, ordered
         by their first Chain segment (Layer 3 segment indices) and
         rotated to the run that starts at one of the use's ends (Layer 1
         PatchChain start and end vertex), are joined pairwise when the
         next run starts where this one ends walking the Chain forward
         (orientation signs), that vertex is not a use end, and no right
         corner Layer 3 records between runs of the rail's Chain, on any
         use of it in the island, sits there: a RIGHT RunCornerRelation,
         or either end of the bridge of a RunBridgedCornerRelation. A
         closed use cut by a SEAM_SELF is never joined across its cut. The
         union-find with parity is shared with join_stitched_lines
         (_join_lines, factored out; join_stitched_lines behaves as
         before). One MarkedRail (frozen dataclass) per stretch: patch,
         Chain, line, runs in the use's order, line count (how many lines
         the join made one), name "<patch> (<first source>..<last
         source>)".
Layer 5  skeleton._join_marked_rails (rule 2): the joins of an island are
         made together or not at all. They run into a scratch list of
         diagnostics, then one bipartition of the joined lines, seeded by
         the line lengths from before the joins (a joined line counts as
         its longest part). If any line comes out OBLIQUE (a conflict),
         the island keeps its lines, signs and lengths as after
         join_stitched_lines, the bipartition of those lines runs with its
         own diagnostics, and one diagnostic says "ladder strips in a
         quilt, stitched rails not made one line: with the rails joined
         the quilt's right corners hold a line on both axes, the lines
         are kept as they were: <patches>".
Layer 5  frame_free.unmeasured_runs (rule 3): the runs whose Chain is a
         rail's Chain and whose line the mark made from several lines
         (every use of the Chain in the island). axis_solve.solve_axis,
         axis_span and _axis_equations take unmeasured_run_ids: such a run
         adds no equation and keeps its role, so its line still joins its
         nodes on the cross axis; skeleton._island_drift leaves them out
         of the spans. Other runs on the joined line, and a rail that
         already was one line, keep their length equations. New field
         IslandSkeleton.unmeasured_run_ids.
Layer 5  frame_free.station_marked_rails (rule 4), after the solve: walking
         a stretch, a run-end node without an along coordinate between two
         laid nodes takes the value between them in proportion to the 3D
         length (the runs' lengths); a node with laid nodes on one side
         only gets none. One diagnostic per stretch: "ladder strip in a
         quilt, stitched rail made one line from N lines, no length
         equation, L m in 3D laid at X m: <name>", "..., its ends not both
         laid: <name>" or "..., no stations: fewer than two of its nodes
         are laid: <name>". Then quilt_ladders.py reads the strip as
         before (rule 5). No outcome text changed.
tests    test_layer_5_quilt_ladders.py, on the user's mesh: f73's stitched
         rail is one line from 7 ("6.2331 m in 3D laid at 6.8648 m"),
         read in one piece with all 12 profile lines tied, v174 to v168 on
         the inner row at stations whose ratio to 3D length is one value
         (1.101), only the rail Chain's runs unmeasured (f95's side on the
         same line keeps its length), the outer arc's 17 runs at their 3D
         length, the top quilt still without pins; f71 and f96 keep their
         outcomes, the top quilt's joins are not made and the diagnostic
         names f35, f71, f96. Synthetic bump band (a rail Layer 3 cuts
         into 5 lines): one line, no length, stations by 3D length, one
         piece, one named diagnostic; the free rail is not joined; fewer
         than two laid nodes give no stations (paired positive); the
         mirrored case loses exactly p1_0 and p1_1 against the solve
         without the joins (the stated limit); a rail that already is one
         line keeps its lengths; a right corner cuts the join; both rails
         stitched: no join, no diagnostic; a run beside the rail on its
         line keeps its length and its pin; the parity of the rail's two
         sides; a closed rail (the cut ring lifted off its frame) is never
         joined across its cut; on d_cyl_s2 with +Z the joined rails of
         f112 and f114 are longer than any line before the join and every
         run keeps its axis role. A unit test of the stations (both use
         directions, all three diagnostic texts). Changed: the f36 test
         (61 -> 69 pinned source vertices; pinned edges 137 -> 167, mean
         bound 0.035 -> 0.05, second largest 0.25 -> 0.19).
fixtures make_marked_ladder_strip_source(..., beyond_a=None): the far side
         of the row beyond rail A.
```

Results:

- User's mesh, +Z, bottom quilt after Blender 4.5's fill (HEAD -> now;
  the user's layout in brackets where measured): pinned source vertices
  61 -> 69 (pin occurrences 99 -> 111, none lost); overlapping triangle
  pairs, self-intersecting faces, flips 0 -> 0 (4, 1, 1); corner angle
  error mean / max 5.28 / 31.6 -> 4.49 / 33.9 degrees (4.39 / 52.1); f111
  5.20 / 23.3 -> 3.20 / 8.4 (2.67 / 12.8); f36 5.33 / 31.6 -> 5.33 /
  33.9; f73 6.86 / 23.9 -> 6.82 / 23.9; f95 0.43 -> 0.43; f73 shear
  between its rails 0.55 / 2.02 -> 0.00 / 0.00; pinned-edge error 0.0335
  -> 0.0468 (study's B4, whose pins this slice reproduces; round two of
  the worker moves them by at most 4e-5). f111's outer side 1.000 -> 1.000
  (0.999); its inner side per edge 1.000 x 3, 1.335, 1.177, 1.087, 1.174,
  1.334, 1.000 x 3 -> 1.101 on every edge (1.036 to 1.124, 1.095
  overall); its largest deviation across 0.036 -> 0.000 m.
- Diagnostic of the slice there: "ladder strip in a quilt, stitched rail
  made one line from 7 lines, no length equation, 6.2331 m in 3D laid at
  6.8648 m: patch:seed:f73 (v160..v157)".
- The other two quilts of the mesh: the wall quilt is identical; the top
  quilt keeps its Layer 3 lines (0 pins, angle error 3.96 / 58.4) and
  gains only the diagnostic that its joins are not made (f35, f71, f96).
- Full-state comparison against HEAD (every pin UV, role, sign, line,
  outcome, tie and diagnostic) on all 34 captures (the in-repo captures,
  the parity references and the 13 building captures), filter off and +Z:
  filter off identical everywhere. +Z: only d_cyl_s2 and the user's mesh
  change. d_cyl_s2: diagnostics only, two "not reached" lines fewer and
  for each of f112 and f114 "... from 2 lines, no length equation, 0.7488
  m in 3D, no stations: fewer than two of its nodes are laid"; no role
  and no pin. User's mesh: in the bottom quilt 10 roles OBLIQUE -> AXIS_A
  (f111:0:1 runs 2 to 6, f73:0:0 runs 2 to 6), 5 "not reached" and the
  pieces diagnostic gone, the f73 diagnostic added; the moved pins are
  the inner row (v162 to v167 and v176 to v181 along by up to 0.169 m, the
  stations at 1.101), the rows of v156 to v161 and v210/v211 across by at
  most 0.29 mm (v157 and v160 now on one AXIS_B row; AXIS_B residual
  0.000713 -> 0.000778, review round one) and a translation of 4e-5 in u. Ties of f73 8 ->
  12. The top quilt as above.
- Census (study): with +Z 9 ladder strips lie in frame-free quilts
  (u_rounded 5, d_cyl_s2 2, c_arch_s2 1, e_arch_s2_n20 1), with the
  filter off none.
- Buildings: no difference; the Tier 3 seamed baseline is identical (13
  objects); the quilt smoke (+Z, `--unwrap-quilts`) equals HEAD apart
  from timing.

Stated limits:

- The coupling with Layer 3. The band is straight, and which side keeps
  its length is decided, only because the other side of the band is one
  Layer 3 line: 5.29 degrees per junction against the tolerance of 5.73.
  With a family stopped after 15 degrees of accumulated turn (emulated in
  Layer 5 in the study, re-run by the worker and the reviewer; DD-48
  lines have that bound since Slice AJ, families do not) the bottom quilt
  has 14 pinned source vertices and folds after the fill as before Slice
  AK (10 overlapping triangle pairs, 2 self-intersecting faces) at HEAD,
  and 0 pinned source vertices with the same fold after this slice:
  f36's outer side is then a line the mark made too, and neither side
  has a length. A rule for which side leads the length, independent of
  that, is the first open item.
- Rule 3 is unconditional: where nothing in the quilt ties the joined
  rail's two ends the slice pins less than HEAD did (the mirrored case
  loses p1_0 and p1_1; a test names them). On the 34 captures no pin HEAD
  had is lost.
- All or nothing per island: one strip on a noisy surface (f71 on the
  top patch f0) undoes the joins of the whole quilt; the top quilt is as
  at HEAD (0 pins) except the diagnostic. The fallback fires on any line
  the joined bipartition degrades to OBLIQUE, also one the Layer 3 lines
  would have had without the joins; on the 34 captures it fires only in
  the user's top quilt, which at HEAD has no conflict.
- A mitre for which Layer 3 records no right or bridged corner (f35's on
  the noisy top patch f0) does not cut the join. Measured by the reviewer
  before the fallback existed: with only the rail's Chain unmeasured the
  top quilt gains 7 pins and 28 ties and f35 and f96 change outcome, laid
  through f35's mitre. The top quilt stays unread; saw teeth and noise
  are deferred by the user.
- The bottom quilt's largest corner angle error rises from 31.6 to 33.9
  degrees: f36's mitre quad f98, corner v208 (3D 106.3, UV 140.2; HEAD's
  maximum was on the same face at v211/v210, v208 was 28.7). The
  reviewer's explanation: f111's inner side is one line, so v157 and v160
  share one AXIS_B row (HEAD: two rows 0.35 mm apart); the AXIS_B cycle
  through f95 (0.4218) and f111's end (0.4207) closes with one freedom
  less, and the unweighted least squares puts 0.2 mm of that 1.1 mm width
  disagreement on the 1.4 mm bridge run (bridge vector (0.00096, 0.00096)
  -> (0.00097, 0.00116), about 5 degrees at v208). Follow-up: spread drift
  in proportion to run length.
- The inner side is laid 10.1% longer than in 3D on every edge (6.8648 m
  for 6.2331 m; the user's layout 9.5%), so the quilt's pinned-edge error
  rises from 0.0335 to 0.0468 (pinned edges 137 -> 167).
- f73's 24 degrees on its end faces f75 and f91 stay (skewed rungs laid
  at 90 by the ladder).
- If the two uses of the rail's Chain are cut into runs differently (a
  per-use run refinement or a DD-30 chord shortcut on one side), the
  neighbour's extra run ends are nodes of no stretch and get no station.
  Not present on the captures and not constructed.
- Tests: on the synthetic folded strip a join across the right corner
  makes the joined bipartition conflict, so the fallback would hide a
  missing cut; the cut is caught by a second synthetic case where no
  conflict arises (rail A turns the right corner at one vertex, the free
  rail over three) and by the tests on the user's mesh capture (f36's
  mitre). The test of the fallback on lines that conflict without the
  joins rests on a stand-in (the bipartition is patched to degrade a
  line): no capture has such an island. Two mutants survive with no case
  changing: the drift span counting the unmeasured runs, and the check
  against a use's own end (it acts only when no run of the use starts at
  a use end; not constructed).

Reviewer gate (independent agent), round one: PASS WITH FIXES. It
reproduced the tests, Tier 3, the quilt smoke and the after-fill numbers
of the bottom quilt with its own dump and metrics; confirmed that
join_stitched_lines is unchanged by the refactor (the slice with the mark
join off equals HEAD on all 34 captures in every field), that nothing is
walked, that "on either use" holds (the bridged corner of f36's mitre is
only on f111's side) and that the FeatureConstraint keeps one reader;
checked mirror, rotation with scale, flipped winding and id renaming on
five meshes; ran fifteen mutants (four survived). Findings fixed in round
two:

- F1: the slice made the top quilt depend on ids and winding (f71's joined
  line met right corners of both axes, and the bipartition degraded
  whichever line it reached second in id order; under a flip or a
  renaming f35 and f71 were read and 5 pin occurrences appeared). Fixed by
  rule 2 (all or nothing); the worker's invariance re-run on the user's
  mesh now matches the base under mirror, rotation with scale, flip and
  renaming for both quilts.
- F2: on a closed rail the join crossed the use's own end (runs ordered
  from segment 0, an arbitrary ring vertex). Fixed: runs ordered from the
  use's start, never paired at a use end; test on the lifted cut ring.
- F3: rule 3 reached runs beyond the rail's Chain on the joined line
  (f95's side on the user's mesh; a constructed junction run lost its
  pin). Fixed: only the runs of the rail's Chain are unmeasured; test.
- F4: G0 and AGENTS.md contradicted the code; this documentation.
- F5: diagnostics: "not laid" on a rail the quilt lays, two diagnostics
  for one stretch, stretches not named. Fixed: one diagnostic per
  stretch, named by its first and last source vertex.
- F6: tests were added for the surviving mutants that join both rails
  and flip the join's parity, and for the wrapped use of F2; the
  drift-span mutant still survives.
- Point c: a joined line could become the longest line and move the seed
  (d_cyl_s2's roles shifted). Fixed: the seed is chosen by the lengths
  before the joins; test on d_cyl_s2.
- Point b: the loss on the mirrored case is stated as a limit and pinned
  by a test.

Second round, on the fixes: PASS WITH FIXES (small). With its own dump and
metrics it confirmed: filter off identical on all 34 captures; with +Z the
user's top quilt equals HEAD except the one fallback diagnostic; the
bottom quilt has 99 to 111 pin occurrences on 69 source vertices, none
lost, every pin within 4e-5 of round one, and after the fill 0 overlaps,
angle error 4.49 / 33.9 (f111 3.20 / 8.4) and the inner side at 1.101 on
every edge; d_cyl_s2 +Z changes no pin, role or outcome (its line
partition goes 12 to 11 per island and 4 runs per island are unmeasured);
nothing else changes. The fallback fires only on a line the bipartition
degraded for a conflict (a line no corner reaches is absent, not OBLIQUE)
and does not depend on BFS order. Under mirroring, rotation with scale,
flipped winding and id renaming on four meshes the slice adds no
dependence (the order of patch names in the fallback text follows ids;
lengths in diagnostics scale). The seed is HEAD's by construction. Ten
mutants of the fixes are caught; the two survivors are stated above.

Its findings were fixed in a third pass and checked by the architect (full
suite; whole-state dump identical to round two except the reworded text):

- A synthetic corner-cut test that the fallback cannot hide: added; it
  fails without the cut.
- The fallback diagnostic blamed the joins also when the lines conflict
  without them: reworded to say only what is observed; a test added (on a
  stand-in, see the limits).
- The use-end check keeps a comment naming the case it guards.

Not re-run in round two: the split emulation and Blender fills of the
transformed meshes (invariance was checked on the solver output).

Checks: `python -m pytest` 1044 passed, 4 skipped, 1 xfailed (1028 before;
full suite from the repo root). Tier 3 on buildings: baseline
identical, 13 objects; quilt smoke as HEAD apart from timing. Checkpoint
scene in the session scratchpad (`al_impl\rounded_wall_scaffold_al.blend`,
UV layer `Scaffold` beside the user's untouched `UVMap`; pictures in
`al_impl\png\`).

Next, open items in this order:

1. Which side of a straightened band leads its length, and the
   accumulated-turn bound for Layer 3 families (the coupling above).
   (Note of 2026-11-23: the length rule is answered by Slice AM: a line
   the mark made keeps its length unless it contradicts, and of
   contradicting lines the shorter yields, so the longest leads; the
   Layer 3 bound itself stays open.)
2. Drift spread in proportion to run length.
3. Quilt orientation (also the column's back wall).
4. Seeding every right-corner component of a frame-free quilt.
5. The user-selected-edges proposal: awaiting the user.
6. Saw teeth: deferred by the user.
7. A frame-free quilt is not tested for overlap.
8. The older open items already listed in this plan stay.

## Slice AM — the solve takes signs as given; a line the mark made keeps its length unless it contradicts (DONE, 2026-11)

Correction (note of 2026-11-23) to the Slice AL entry above, which stays
as written; measured in the sign study of this slice (`am_sign\`):

- The 5 degrees that the 1.4 mm bridge run takes are not on f98. They sit
  on face f123 at v208 and v210 (5.24 and 5.23 degrees; 0.05 and 0.03
  with the drift spread by run length).
- The 33.9 degrees on f36's mitre face f98 at v208 are mostly the shear
  of the straight layout. With the drift spread by run length f98:v208
  goes to 28.7 degrees and f98:v210 rises from 26.4 to 31.6, so the
  quilt's largest error falls only from 33.9 to 31.6: about 2 degrees of
  it are drift.

Target: items В and Б of an external code review that the user relayed
(В: a 3D dot product decides signs inside the solve; Б: a contradiction
should be localised to its cycle). Commit 8868656; G0 v1.21 DD-47,
DD-52, DD-54.

The user opened this slice on 2026-11-23: "start the next slice with
measuring items В and Б of the review". What to build was chosen by the
architect from the measurements (plan decision 20, taken inside the
slice the user opened; the user may reverse it): a line the mark made
keeps its length unless it contradicts, and of contradicting lines the
shorter yields, so the longest line keeps its length. Reason: that is
what the user's own layout of the bottom quilt does (UV layer `UVMap`:
outer side 0.999 of its 3D length, inner side 1.095 evenly), and it
leaves that quilt exactly as Slice AL laid it.

Data of every whole-state comparison in this entry: 38 captures, 13
bevel cases (the user's `u_rounded_wall_noise_top` among them), 8 in-repo
`tests/data/artist_*.json`, 4 parity references (Arc, building_walls,
collumn, Main_wall) and 13 building captures of `E:\buildings.blend`
(`run_smoke --seamed --capture-dir`, read-only), each with the filter off
and with `world_up` +Z (76 runs).

Measured first (two studies in the session scratchpad, `am_sign\` and
`am_cycles\`, NOTES.txt, not in the repo):

- The dot step (`axis_solve._axis_equations`). Equations between the same
  two cross components had their signs normalised to the first one's by
  the dot product of their 3D run directions. Pairs that met an earlier
  equation on the same components: framed 6456 (off) / 5809 (+Z),
  frame-free quilts 169 / 222, frame-free single patches 2 / 3, strips
  1 / 1. Flipped: 0 everywhere; every frame-free cosine is at least 0.8.
  In framed and strip islands the step is provably inert (a framed sign
  is the sign of the frame direction against its axis with |cos| at
  least 0.996; a strip's direction is its sign times the unit axis). It
  is live only in frame-free islands, where it compares raw 3D
  directions (against DD-47). It dates from Layer 5 v0 (commit 7699316,
  2026-06-13), when an unsigned run took +1; since then an unsigned run
  adds no equation. Removing it is bit-identical on all 76 runs.
- The case where it acts: a flat band (radii 1 to 3 m) between two marked
  ladder strips, both stitched rails made one line by the mark, so the
  band's two end runs join the same two rows with a cosine of cos(bend).
  At 100, 120 and 180 degrees the step flips one end run: "AXIS_A: 2
  contradictory equations", 0 pins, both strips "pins none of its
  vertices". At 80 degrees it flips nothing.
- The gauge (item А): 5639 equation groups; the largest has 89
  components and 178 equations (bld_walls island 0, AXIS_A). The largest
  coordinate difference to a reference solve (numpy least squares with
  the gauge eliminated, checked against exact rationals) is 6.7e-13; the
  condition number of the reduced incidence matrix is at most 83; no
  verdict changes. On the largest capture `solve_axis` takes 0.22 s of
  the 17.6 s of `run_skeleton_solve` (1.3%), `build_islands` 15.9 s (93%).
- Drift spread in proportion to run length (weights 1/length, a bridge
  1/its run length): every verdict is unchanged; pins move by up to 4.6
  mm on the buildings (walls, walls.003, building_walls; in-island), so
  the Tier 3 baseline would change; on the bottom quilt after the fill
  f123's 5.2 degrees go, and the largest error falls from 33.9 to 31.6
  (the correction above); on e_arch_s2_n20 the quilt maximum falls from
  2.64 to 2.38 degrees but some corners get worse (f19:v21 0.36 -> 0.77).
  Three tests fail under it (two are verdict changes on synthetic
  fixtures). Not built.
- Census of accumulated turn. Directional runs (17640 uses): the largest
  first-to-last 3D angle is 9.70 degrees and the largest accumulated
  surface turn 9.48 (u_rounded f0:0:0:20, 1.165 m); no run turns more
  than 15 degrees, so the per-segment gate of runs is no accident on the
  data. Island lines turning more than 15 degrees on a patch side are
  found only on c_arch_s2 and e_arch_s2_n20 +Z (through the Slice AK
  join: straight on f22, 62.8 / 57.9 degrees on f26), d_cyl_s2 +Z,
  ref_collumn, and u_rounded (f111's sides 90.0 and 86.1, f36 63.7 and
  56.2, f73 61.0, the top quilt's f35, f71, f96); none on the buildings,
  cubes, rects, rings, walls, Arc or Main_wall.
- Emulation of families stopped after 15 degrees of accumulated turn
  (in Layer 5: each ordered island rail segment cut greedily from its
  first station where the accumulated surface turn passes 15 degrees;
  measurement only, not a Layer 3 change). Against the code before this
  slice it cuts 4 families on all data (u_rounded 3, collumn 1) and
  changes only the user's bottom quilt: 69 pinned source vertices (111
  occurrences) -> 0, and after the fill 10 overlapping triangle pairs and
  2 self-intersecting faces (the fold before Slice AK). Two causes: both
  band sides become lines the mark made, so neither has a length; and
  the drift, which left those runs out of its spans, shrinks from 7.01 to
  0.57 mm, so f95's 1.07 mm width noise becomes an AXIS_B contradiction.
- Contradictions as cycles (item Б). 3784 solves, 15055 independent
  cycles. The code before this slice reports contradictory equations in
  exactly one solve: e_arch_s2_n20 +Z island 2 AXIS_B (tolerance 4.41
  mm), the 2-cycle of f46's two ends (0.2406 against 0.2612 m, 20.6 mm).
  It drops 7 of its 8 equations and 2 components, and the island keeps 3
  pin occurrences; removing only that cycle's two equations gives 44 pin
  occurrences on 24 source vertices (f26 kept together, 9 ties) and
  changes nothing else. A cycle test free of subdivision (1 mm per metre
  of the cycle's own length) would fail 297 cycles, mostly rigid building
  frames (5 cm over 6.8 m).
- Who leads the length, candidates on the user's bottom quilt with a
  mark-made line keeping its lengths (the 0.6317 m cycle of 27 AXIS_A
  equations: the bridge run, f111's 9 inner and 17 outer runs). After
  Blender 4.5's fill:

| candidate | pins (occurrences) | overlaps | self-x | flips | angle error | outer / inner |
|---|---|---|---|---|---|---|
| user's UVMap | - | 4 | 1 | 1 | 4.39 / 52.1 | 0.999 / 1.095 |
| before this slice | 69 (111) | 0 | 0 | 0 | 4.49 / 33.9 | 1.000 / 1.101 |
| before this slice + emulation | 0 | 10 | 2 | 0 | 1.68 / 97.1 | fold |
| shorter yields, bridges hard (built) | 69 (111) | 0 | 0 | 0 | 4.49 / 33.9 | 1.000 / 1.101 |
| the same + emulation | 69 (111) | 0 | 0 | 0 | 4.49 / 33.9 | 1.000 / 1.101 |
| bridges last | 69 (111) | 25 | 2 | 2 | 13.9 / 134.9 | 1.086 / 1.000 |
| disagreement shared by length | 69 (111) | 0 | 0 | 0 | 4.50 / 36.8 | 0.955 / 1.048 |
| side stitched to more hard runs leads | 33 (57) | 0 | 0 | 0 | 3.54 / 33.9 | 0.956 / 1.046 |

  "Bridges last" puts the 0.63 m into the 1.4 mm bridge run (laid 463
  times its length). Pure length order is the same, the bridge being the
  shortest run.

The cause (item Г of the review, measured): runs and families are gated
per junction (DD-45, 5.73 degrees) with no bound on the accumulated
turn. Runs never turn more than 9.7 degrees on the data; families do (the
lines above). Since Slice AL which side of a straightened band keeps its
length rested on that accident: f111's outer side is one Layer 3 line
(5.29 degrees per junction, 90 in total) and its inner side seven. The
bound itself (open item 1) needs a rule for who leads the length first;
this slice gives it.

The rule (Layer 5 only):

```text
Layer 5  axis_solve._axis_equations: the dot step is gone. Each own-axis
         run adds its sign times its length between the components of its
         START and END, the sign used as given (rails, stitched and mark
         joins, corner orientation, frame or strip layout). direction_of is
         removed from solve_axis, axis_span and _axis_equations (no other
         reader), with the import of dot / normalize; skeleton._strip_layout
         no longer builds directions and _STRIP_AXIS_UNIT is gone. The
         framed branch keeps its own direction_of for its roles and signs.
         axis_span lost unmeasured_run_ids. New field
         AxisSolve.contradiction_by_run: the run of each contradictory
         equation -> its largest residual, before the contradictory
         components are dropped.
Layer 5  frame_free.marked_lines (replaces unmeasured_runs): one MarkedLine
         (chain_id, line_id, run_ids, length) per rail Chain and joined
         line the mark made from several lines. run_ids are the soft runs
         (every run of that Chain on that line, on every use of the Chain
         in the island); length is the 3D rail length, the summed run
         lengths of its stretches on the strip's own stitched use (the
         largest such sum over uses), never read from the other side.
         marked_line_groups: sorted by length; a line within
         MARKED_LINE_TIE = 1e-9 (relative) of a group's shortest line joins
         that group. MarkedYield(fewer, left, others): the effect of a
         yield at its step (fewer contradictory equations among the other
         runs, how many left at that step, how many other lines yielded
         with it); a later yield does not refresh it.
Layer 5  skeleton._solve_axis_yielding, for each axis: solve with every soft
         run measured. While the kept solve has contradictory equations
         and marked lines with a signed run on this axis have not yielded,
         try candidates: each group alone, shortest first, then the
         shortest k groups together for k = 2 .. n (every group is tried
         alone before any two together; a set of several groups is always
         the shortest k). A candidate yields when
         the solve without its soft runs' length equations has no
         contradiction, or strictly fewer contradictory equations among
         the runs that are not its own soft runs (counted by run) than the
         kept solve. On a yield the trial restarts from the shortest group
         left; if no candidate helps, the kept solve stands as solve_axis
         reports it. Only the kept solve's diagnostics are appended. With
         no marked line it is one solve_axis call. A round with m groups
         left makes at most 2m - 1 trials and every yield takes at least
         one group, so an axis with n groups takes at most 1 + n^2 solves.
Layer 5  skeleton._island_skeleton: the drift is taken once by _island_drift
         with every signed run (the soft runs too), before any yield.
         IslandSkeleton.unmeasured_run_ids holds the soft runs of the lines
         that yielded. The seed and the all-or-nothing fallback of Slice AL
         are unchanged.
Layer 5  frame_free.station_marked_rails(rails, yielded, ...): stations only
         for a rail whose line yielded; one diagnostic per stretch,
         H = "ladder strip in a quilt, stitched rail made one line from N
         lines, L m in 3D": "H, keeps its length: <name>"; "H, gives no
         length equation, its line has no signed run on an axis: <name>";
         "H, yields its length: without its length equations the other
         runs of its axis have <effect>" or "H, yields its length together
         with K other line(s) the mark made: without their length
         equations the other runs of its axis have <effect>", effect "no
         contradictory equation" or "F fewer contradictory equations (M
         left at that step)", then ", laid at X m (+D m): <name>", ", its
         ends not both laid: <name>" or ", no stations: fewer than two of
         its nodes are laid: <name>".
Layer 5  quilt_ladders.py: module rule only.
tests    test_layer_5_runtime.py (solver level): equation signs are the run
         signs, never turned by 3D directions (paired: opposite signs
         contradict); the shorter of two contradicting marked lines yields
         whatever their ids; equal lengths yield together (paired: 1e-8
         apart, one yields); the drift does not shrink when marked lines
         yield; a marked line against a line Layer 3 holds yields and a
         hard contradiction stays; a disagreement seen only on a hard run
         still lets the marked line yield; a hard contradiction smeared
         onto a marked line leaves it its length (the result equals
         solve_axis); a marked line off the disagreeing loop keeps its
         length; after a yield the shorter lines are tried again (and the
         notes are the step's: B MarkedYield(1, 2, 0), "(2 left at that
         step)", although the final axis has no contradiction); two
         marked lines against one hard line yield together when neither
         alone helps (10.0 / 10.3 / 10.6 m); of three that contradict the
         two shorter yield; the stated limit F2 (a marked line beside a
         hard taper keeps its length); a contradiction carried by a bridge
         offset; the tie anchor; a yield that leaves a hard contradiction
         says how many fewer and how many left.
         test_layer_5_quilt_ladders.py (meshes): a band between two marked
         strips is laid whole with the longer rail leading (90, 100, 120,
         180 degrees); who yields does not depend on ids or on a mirror
         (inner first, mirrored, both); the bump 0.20 strip whose
         disagreement shows only on hard runs still yields; the island
         drift counts the runs of the lines the mark made (band 180, 1 cm
         wider at its last end: drift 6.7 mm with the marked arcs, 2.4
         without; paired 1.5 cm: contradiction); a marked line is as long
         as its longest stitched rail use whatever the order; two marked
         rails against a seam Layer 3 holds yield together and the seam
         leads (the mesh case of F1: a band of radii 10 / 20 / 30 m bent 8
         degrees in 10 segments, split along its length by a seam at
         radius 20, its inner and outer rails moved out 5 cm at the odd
         interior vertices so Layer 3 cuts them into several lines; no
         contradiction, all three arcs at the seam's 3D length 2.7925 m,
         both rails "together with 1 other line the mark made", 11 profile
         lines tied on each strip). Changed by
         design: the f73 text; the bump 0.30 rail yields (laid at 5.0000);
         the rail nothing contradicts keeps its 5.0881 m and is laid
         straight at 3D stations; the mirrored case no longer loses p1_0
         and p1_1; the closed marked ring is OBLIQUE ("no signed run on an
         axis"); the seed test checks the join by its diagnostic.
fixtures make_marked_band_source(degrees, segments, inner_first, mirrored,
         end_widening): a flat band of radii 1 and 3 m between two marked
         ladder strips (10 to 11.25 degrees per segment, so the band ends
         are right corners). make_marked_split_band_source(degrees,
         segments, radii, wobble): the split band above.
         Test filters that look for the solve's contradiction text match
         "contradictory equations ->" (the yield text now contains
         "contradictory equation").
```

Results:

- Full state against the code before the slice (every pin UV and flag,
  role, sign, line, coordinate, unconstrained set, equation count,
  ladder outcome, tie, unmeasured set, bridge vector, diagnostic and
  corner-law count) on the 38 captures: filter off identical everywhere.
  +Z: two runs differ. The user's bottom quilt changes only the text of
  f73's diagnostic, now "ladder strip in a quilt, stitched rail made one
  line from 7 lines, 6.2331 m in 3D, yields its length: without its
  length equations the other runs of its axis have no contradictory
  equation, laid at 6.8648 m (+0.6317 m): patch:seed:f73 (v160..v157)";
  its 69 pinned source
  vertices (111 occurrences) are bit-identical and its equation counts
  equal. d_cyl_s2 islands 1 and 2: the unmeasured set goes from 4 runs to
  none (its joined lines are OBLIQUE and give no equation either way) and
  the diagnostic reads "... 0.7488 m in 3D, gives no length equation, its
  line has no signed run on an axis: ...". The reviewer counted 33858
  pinned vertices, bitwise identical.
- The drift of the bottom quilt taken with every run is 6.6 mm (7.0 mm
  with the inner runs left out, as in Slice AL); verdicts and pins are
  the same.
- Emulation of bounded families, with this slice: the bottom quilt keeps
  69 pinned source vertices (111 occurrences); after Blender 4.5's fill
  0 overlapping triangle pairs, 0 self-intersecting faces, 0 flips,
  angle error 4.49 / 33.92 degrees, outer side 0.9999, inner side 1.1012
  on every edge: identical to the slice without the emulation and to
  Slice AL without it. Other effects of the emulation: 13 runs of f36's
  free rail OBLIQUE (pieces; no pin moves), f36's outer rail a line the
  mark made ("from 2 lines, 6.8638 m in 3D, keeps its length"), and the
  emulation's own diagnostics on u_rounded (filter off) and collumn.
- Synthetic bands between two marked strips (+Z): 90 degrees in 8
  segments 8 pins (junctions only) -> 44, 18 of 18 ties; 100 / 120 / 180
  degrees (10 / 12 / 18 segments) 0 pins ("AXIS_A: 2 contradictory
  equations") -> 52 / 60 / 84, ties 22 / 26 / 38 (every profile line).
  The outer rail is laid at its 3D length (4.7048 m, ratio 1.000000), the
  inner rail (1.5683 m) at 4.7048 m, ratio 3.000000 on every edge. Who
  yields is the same with the inner strip first, mirrored, and both.
- The bump strip with the straight 5 m far side (a Layer 3 line), bump
  height -> rail length -> laid length of the rail and the far side:

| bump | rail (3D) | Slice AL | this slice |
|---|---|---|---|
| 0.30 | 5.0881 m | 5.0000 | yields, 5.0000 |
| 0.20 | 5.0396 m | 5.0000 | yields, 5.0000 |
| 0.15 | 5.0224 m | 5.0000 | yields, 5.0000 |
| 0.145 | 5.0209 m | 5.0000 | keeps its length, both 5.0060 |
| 0.12 | 5.0143 m | 5.0000 | keeps its length, both 5.0041 |
| 0.10 | one Layer 3 line | 5.0029 | 5.0029 |

  Under the drift the disagreement is spread over the rail and the far
  side (about 1.2 mm per metre, the island's drift) where Slice AL laid
  them exactly; no pin on the captures moves for this reason.
- Buildings: the Tier 3 seamed baseline is identical (13 objects, 0
  errors); the quilt smoke (+Z, `--unwrap-quilts`) differs from the code
  before the slice only in timing.

Stated limits:

- A line the mark made keeps its length on trust where nothing
  contradicts it (review F3). A rail that turns through a mitre for
  which Layer 3 records no corner is laid straight at its 3D length:
  the user's top quilt with only f35's rail joined (the reviewer's
  filter of `stitched_rail_uses`; not reached today) gets 54 pins with
  pinned edges at 0.275 to 2.046 of their 3D length (78 edges; f35
  v120-v121 0.275, v121-v124 1.626, f97/f105 2.046), where Slice AL's rule
  gives 5 pins at 0.91 to 1.44; with f35 and f96 joined 56 pins and 2
  contradictory AXIS_B equations. Today the all-or-nothing fallback hides
  it (with f35, f71 and f96 the quilt keeps its Layer 3 lines, 0 pins,
  as before). Not filled in Blender.
- A line the mark made beside a hard contradiction it does not cause
  keeps its length even when far off (review F2; solver level: a hard
  taper of 10.00 / 10.03 m over a 10 mm drift and a marked line of 11.0 m
  through a node x: without the line the taper still has 2 contradictory
  equations, so the line keeps its length, 1 m wrong, and x's components
  are UNCONSTRAINED; Slice AL laid them). A test pins it.
- Under the drift a line the mark made keeps its length and the drift is
  spread over it and its neighbours (review F4; the bump table above).
- "Shortest yields" stretches the inner rail of a bend to the outer one
  (ratio 3.000 on the synthetic bands, 1.101 on the user's mesh). If the
  texture should follow the inner edge, or the longer rail is long by
  noise (a sawtooth outer edge), the leader is wrong.
- The trial is greedy per axis and a yield is never given back. The
  effect test counts contradictory equations, not their size: a yield
  that removes one large contradiction but lets the smear flag one more
  small equation elsewhere is refused. Cost: a round with m groups left
  makes at most 2m - 1 trials and every yield takes at least one group,
  so an axis with n groups of lines the mark made takes at most 1 + n^2
  solves (five marked lines against one hard line: 13 solves). On the
  data the shortest line always yields alone on its first trial (2
  solves on that axis, 1 on the other) and no set of several groups is
  ever tried; at most 2 marked lines per quilt; no timing change in the
  smoke. The largest count in the reviewer's fuzz was 11 solves per axis.
- Several lines the mark made between the same rows yield together when
  no single one helps, and the line Layer 3 holds leads: on the split
  band (radii 10 / 20 / 30 m, a seam Layer 3 holds at radius 20) both
  marked rails are laid at the seam's 2.7925 m (4.2087 m and 1.4503 m in
  3D). With today's Layer 3 such a loop needs the hard line to be one
  Layer 3 line (at most 15 degrees in total) and the rails to be cut
  into several lines by a wobble, not by the bend.
- In the reviewer's fuzz (3000 random column graphs, 1 to 4 marked lines)
  the fuzz counts 16 trials as worse than Slice AL. 10 of them have a hard
  contradiction in both (the F2 limit above; a user can meet it, noisy
  quilts such as the top patch f0 have hard contradictions). 6 have no
  contradiction in either and differ in which equation group is largest
  (the frame-free gauge keeps only the largest): in 4 of them this slice
  lays more columns, in 2 it lays 2 where Slice AL laid 3. None ends in a
  contradiction where Slice AL had none; renaming and reordering never
  change who yields; not seen on data.
- The emulation of bounded families is a Layer 5 stand-in for a Layer 3
  change; it cuts greedily from a rail's start.
- Test limits: ties, the restart, a contradiction carried by a bridge
  equation and the length over uses are tested at solver or unit level
  only; the island drift has a mesh test on one band, and the case of
  two marked lines yielding together has the split-band mesh test. Of
  the worker's 20 mutants of round three (run on the two test files of
  the slice) none survives; two survived until a test was added for each
  (the drift taken without the soft runs, and the count of fewer
  contradictory equations). Of the reviewer's 15 mutants of round two
  (full suite) 13 are killed; left_is_after is equivalent always (the
  yielding set's own runs are never among its trial's contradictions),
  note_final (the note refreshed from the final solve) is now caught by
  the restart test, which pins the step's note (B's "2 left"); that
  mutant was not re-run.
- The checkpoint scenes now live in
  `dev/tools/blender_smoke/reports/checkpoints/` (git-ignored), because
  the session's temp scratchpad was emptied by a system cleanup on
  2026-11-18 (the study harnesses of Slices AK and AL were found empty).

Also measured, not built (open items, with their numbers):

1. The accumulated-turn bound for Layer 3 families itself: a G3 contract
   change. The census and the emulation above say what it would cost: on
   the 38 captures nothing but the user's bottom quilt, which this slice
   now keeps. The emulation cuts greedily from a rail's start, so where a
   uniform arc is cut needs its own design; the Slice AK stitched-side
   join is a second path the bound does not reach (c_arch_s2,
   e_arch_s2_n20).
2. A rail the mark made that turns through a mitre Layer 3 records no
   corner for keeps its 3D length (the first stated limit; review F3).
3. Localising a real contradiction to its loop: on all data one solve
   (e_arch_s2_n20 +Z island 2) would gain 41 pin occurrences (3 -> 44),
   nothing else changes. "Bridges last" fails (the 1.4 mm bridge would
   absorb 0.63 m). This slice did not take the cycle-basis verdict: a
   per-cycle verdict depends on the chosen spanning forest, so the least
   squares verdict is kept as the single arbiter, and the cycles are used
   for the analysis.
4. Drift spread in proportion to run length: verdicts unchanged, the 5
   degrees at face f123 gone, the quilt's largest error 33.9 -> 31.6
   degrees, building pins move up to 4.6 mm (the Tier 3 baseline would
   change), some corners of e_arch_s2_n20 worse.
5. The gauge by penalty is no practical problem (largest group 89
   components, 6.7e-13 from an exact solve); the solve is 1.3% of the run
   time on the largest capture, `build_islands` 93%.

### External review, 2026-11-23

The user relayed an external code review on 2026-11-23. Its items and
what was found for each:

| item | claim | found |
|---|---|---|
| А | the gauge by penalty and the conditioning of the solve | measured: no change needed (largest group 89 components, 6.7e-13 from an exact solve, condition number at most 83) |
| Б | contradictions should be localised to their cycle | the cycle frame is adopted for the analysis; localisation is open (open item 3), the least-squares verdict stays the arbiter |
| В | a 3D dot product decides signs inside the solve | true; it flipped nothing on the data but broke bands bent more than 90 degrees between two marked strips; removed in this slice |
| Г | runs and families "creep": they turn without an accumulated bound | true: the gates are per junction with no accumulated bound; runs turn at most 9.7 degrees on the data, families up to 90; the per-vertex gate is a recorded earlier decision (OQ-11, DD-45); the bound is open item 1 |
| Д | one Z4 relation instead of two passes for axes and signs | not built; a candidate to do with quilt orientation |
| Е | accumulated drift of the unfolded frame | not measured |
| - | a Rust port | not now: the model still changes every slice |
| - | sliding line constraints in an own relaxer instead of point pins | the destination after the structure; the "straight, length unknown" of Slices AL and AM is a hand-made case of it |

Reviewer gate (independent agent), round one: PASS WITH FIXES. It
reproduced every claim on data with its own dump and compare (tests,
Tier 3, the quilt smoke, the full state on 38 captures x 2, the bands,
the emulation with its own trees and the after-fill numbers), confirmed
that the dot step was inert in framed and strip islands and flipped
nothing on data (instrumented: 2 flips on each band of 100 degrees or
more), checked termination, order and id independence (fuzz, and
mirror, rotation with scale, flipped winding and renaming on the bands,
the user's mesh, d_cyl_s2 and artist_walls_005) and ran 15 mutants.
Findings:

- F1 (major): with two or more marked lines in parallel on one
  contradictory loop no single yield helps, so none yielded (H 10.0 /
  A 10.3 / B 10.6: 0 columns laid; Slice AL laid them; fuzz 208 trials
  worse than Slice AL, 158 new contradictions). Fixed: the shortest k
  groups together are tried after the single ones; fuzz 16 / 0, at most
  11 solves in the fuzz; full state on all data unchanged. Solver-level
  tests, and since round two a mesh test (below).
- F2, F3, F4 (medium): stated limits above; no code.
- F5 (minor): the yield diagnostic said more than was observed. Fixed:
  it states the effect.
- F6 (minor): surviving mutants (the island drift, a contradiction on a
  bridge equation, the tie anchor, MarkedLine.length). Tests added;
  MarkedLine.length kept as the largest over uses, with a test.

Round two, on the fixes: PASS WITH FIXES (small). With its own scripts
and copies it reproduced the suite (1069 passed), Tier 3 (baseline
identical, 13 objects) and the quilt smoke (as HEAD apart from timing),
the full state against HEAD on 38 captures x 2 (filter off identical;
+Z only the f73 text and d_cyl_s2 islands 1 and 2; all 33858 pins
identical), the bands (44 / 52 / 60 / 84 pins, ties 18 / 22 / 26 / 38,
ratios 1.000000 and 3.000000), the emulation fill (69 pinned source
vertices, 0 overlaps, self-intersections and flips, outer 0.9999, inner
1.1012) and the fuzz (16 worse than Slice AL: 10 the stated F2 limit, 6
a different largest equation group, 4 of those better and 2 worse; 0
new contradictions; 0 id-dependent). The candidate-set loop is the rule
as stated and independent of order and ids, ties inside sets of several
groups included. On real data the shortest line always yields alone in
2 solves and no set of several groups is ever tried (the bands; f73 on
the user's bottom quilt, MarkedYield(35, 0, 0); under the emulation f73
yields alone and f36 keeps its length). Findings, closed by the worker's
round four and checked by the architect:

- R2-1 (major): a mesh does put three lines on one loop (two the mark
  made, one Layer 3 holds): the split band of radii 10 / 20 / 30 m with a
  seam Layer 3 holds. The round-one code laid 0 pins on it ("AXIS_B: 32
  contradictory equations"), this round 63, as Slice AL. Closed: it is
  now the mesh-level test of F1; both marked rails yield together and
  the seam leads at 2.7925 m. The claim "no mesh can" is withdrawn.
- R2-2 (minor): the yield note is taken at the step of the yield and
  never refreshed, so a text could say "(2 left)" when the final axis has
  no contradiction, and "fewer" counts only the other runs. Closed: the
  text says "the other runs of its axis have ..." and "(M left at that
  step)"; the restart test pins the notes.
- R2-3 (minor): a docstring sentence and a test comment said the longest
  line never yields alone before every shorter one was tried with it.
  Replaced with what the code does: each group is tried alone before any
  two together, and sets of several groups are always the shortest k.
  The bound 1 + n^2 is stated.

Mutants of round two: 15 on the full suite, 13 killed; left_is_after is
equivalent always, note_final was a missing test (now pinned, R2-2). Not
run by the reviewer: invariance transforms and a Blender fill of the
split band, the worker's probe_three*.py, dumps of the killed mutants.
The worker's whole-state compare of round four against round three: one
run differs, only the f73 text.

Checks after the fixes (the architect): `python -m pytest` 1070 passed,
4 skipped, 1 xfailed (1044 before; full suite from the repo root). Tier 3
on buildings: baseline identical, 13 objects; quilt smoke as before apart
from timing.
Checkpoint scenes in `dev/tools/blender_smoke/reports/checkpoints/am/`
(git-ignored): `bands_am.blend` (band_coarse90, band_bend120, band_u180
side by side, UV layers `Scaffold_before` and `Scaffold`; picture
`png/bands_before_after.png`: 8 / 0 / 0 pins before, 44 / 60 / 84 now)
and `rounded_wall_scaffold_am.blend` (the user's scene copied, every face
UV and pin of the `Scaffold` layer bit-identical to the Slice AL
checkpoint; picture `png/quilt_am_bottom.png`).

Next, open items in this order:

1. The accumulated-turn bound for Layer 3 families (and directional
   runs).
2. Cutting a rail the mark made at a mitre Layer 3 does not record (with
   noise and saw teeth, deferred by the user).
3. Localising a real contradiction to its loop.
4. Drift spread in proportion to run length.
5. Quilt orientation, with the Z4 formulation as a candidate, and seeding
   every right-corner component of a frame-free quilt.
6. The user-selected-edges proposal: awaiting the user.
7. Saw teeth: deferred by the user.
8. A frame-free quilt is not tested for overlap.
9. `build_islands` takes 93% of the skeleton solve time on the largest
   building.
10. The older open items already listed in this plan stay.

## Decisions the user must approve before the relevant slice

```text
1. Slice D: G0 amendment for ConnectedDirectionFamily — APPROVED
   (DD-43, G0 v1.3). AlignmentClass demotion remains a separate future
   approval.
2. Slice E: spike home dev/tools/tracer_spike/ — APPROVED; no phase
   exception required.
3. Slice F: G0 restructuring (constitution vs status split) — PENDING.
4. Slice L: SHARED_CHAIN straight-hinge transport rule (Task Card L1) as a
   G3 repair of DD-43 — APPROVED and DONE.
5. Slice L: end-patch separation (box lids, corner-node gap) — DEFERRED by
   the user to a future patch-normal filter; no cap/wall semantics.
6. Slice J/O: DD-46/DD-47 (ScaffoldTrace/ScaffoldRail v1) and the Slice O1
   fold-back rule in DD-43 — APPROVED by the user after Slice O and APPLIED
   as G0 v1.6 (2026-11-06). Background (loop and branch policy, fixtures,
   answers to the open questions) stays in
   docs/architecture/scaffold_rail_trace_contract_draft.md.
7. Slice L2: G0 DD-43 fixture-expectation amendment (one rail per fold line;
   no patch revisit) — APPLIED to G0 v1.5 by the agent under explicit user
   delegation (2026-09).
8. Slice N: Layer 5 island lines, axes and orientation in the island frame;
   Layer 3 DD-45 continuation and node-crossing provenance repairs —
   APPROVED and DONE.
9. Next level after patch -> line -> island: ScaffoldRail over island lines
   with loop opening by island cuts — CHOSEN by the user (2026-11-06) and
   DONE as Slice O, including the O1 fold-back repair.
10. Next after Slice O: patches outside the rigid island frame — CHOSEN by
   the user (2026-11-06). The rule "rigid seams first" in the island tree
   was APPROVED after the case analysis and is DONE as Slice P (outside
   patches 10 -> 5, OBLIQUE runs 97 -> 65).
11. Next, open (measured on the 13 seamed objects after Slice P):
   - 5 warped n-gons (28 OBLIQUE runs); after Slice R (bug fix) 3 remain,
     all one hexagon folded around a box corner (source mesh warp);
   - 12 OBLIQUE runs on 5 lines through curved runs (OQ-11);
   - island assembly without self-overlap (walls.007); DONE as Slice U
     (overlap gate, user-approved);
   - the solve consuming island rail order: 2 islands have no rigid frame
     (Cube, walls.012); their provisional signs agree with the island
     rails on both multi-run lines, and on all 6 in the in-repo artist
     captures;
   - island lines taken from the Layer 3 cut;
   - branch resolution for the 4 unordered island rails;
   - 21 contradictory-equation diagnostics (unwrap level); after Slice S
     (user-approved snap angle and drift tolerance) 5 remain; after Slice T
     (jogs) none remain.
   Cross-island axis agreement has nothing to agree yet: no family spans
   two islands on those objects.
   CHOSEN by the user (2026-11-07) as Slice Q, "Layer 5 on rails":
   island lines come from the Layer 3 rail cut, and islands without a
   rigid frame take their in-line run signs from the ordered island
   segments; branches and uncut loops degrade with a diagnostic. It
   removes the DD-47 provisional exception. Rule APPROVED after the
   measurement and DONE. The other items stay open.
12. Next after Slice U, chosen by the user (2026-11-13): chain shape per
   patch side (Slice W). Stage A (facts and evidence, no behaviour change)
   APPROVED and DONE with G0 v1.7 DD-48. Stage B rule APPROVED ("one run
   only for a side where the chain is a surface line") and DONE (G0 v1.8
   DD-30). Stages C and D: see decision 14.
13. Slice V (seam turns and island orientation, rule "longest seam first"
   APPROVED 2026-11-10) is implemented and PARKED by the user on the local
   branch claude/slice-v-seam-turns (commit 99db1a4, not pushed): plan,
   handoff and phase docs and the reviewer gate are still missing.
14. Autonomous mode (user, 2026-11-13). Goal: a result structurally similar
   to the CFTUV reference scene (Arc, building_walls, collumn, Main_wall of
   buildings3_3.blend; Arc and collumn were unwrapped with Straighten
   Strips). Similar structures, not positions or coordinates. The agent may
   merge its own slices after tests, Tier 3 and the reviewer gate; may amend
   G0 and Layer 5, with the wording shown in the PR; may open Layer 4 and a
   world-orientation filter if a similar result needs them, with the phase
   amendment in AGENTS.md. The user's view of that filter: a post-filter of
   user options (what is up, which way a trim runs, which patches stitch
   into one quilt), never an input of Layers 1-3.
15. Quilts (user direction, 2026-11-13): by default everything connected is
   one quilt, decided from structure; only a user filter splits; the
   user's seams stay as markup. DONE as Slice AH with the first filter
   (vertical apart from horizontal, a bevel with its surfaces), G0 v1.16
   DD-55, amendment authorised by the user. Open for the user: the four
   policies listed in Slice AH (junction tie, no usable normal, arch
   soffits, JOIN group order) and the next slice (a ladder strip inside a
   quilt; DONE as Slice AI).
16. Bevel strips (user decision, 2026-11-14, among three measured
   variants): "a strip that develops is left alone, and in a quilt the
   rails are kept together". DONE as Slice AI, G0 v1.17 DD-54 (the gate
   built reads "both rails straight on its surface": the strip unfolds
   straight as it is). Next slice
   APPROVED by the user: the band (the STRIP feature with sides split at
   corners nearer to RIGHT than to STRAIGHT; see the Slice AI entry). Open
   for the user: straighten a band inside a quilt or only alone, its
   option and default, and the noisy top patch f0. (2026-11-15: the band
   was not built as described; the next slice became Slice AJ, decision
   17.)
17. Strips (user decisions, 2026-11-15): the column's flat back face
   f355 (two mirrored profile curves) is no strip and is not
   straightened; the column body's profile seams need not be
   straightened; a strip is two curved chains of close curvature that go
   the same way plus two caps (the user's definition of 2026-11-14), and
   an arc is straightened only as a side of a strip; saw teeth are
   deferred to a late stage. DONE as Slice AJ, G0 v1.18 DD-48, DD-50
   (amendment authorised by the user). Open for the user: the
   user-selected-edges proposal (an input of the same kind as the Face
   Strength mark; not decided, not approved).
18. Slice AK (the user's choice of defect, 2026-11-15: "the fold at f36";
   find the root cause, do not treat the symptom). Inside that slice the
   agent changed what the drift tolerance of plan Slice S (user-approved,
   2026-11-07) is measured against for islands without a rigid frame: the
   larger of the island's two axis spans, on both axes, instead of the
   span along the solved axis. The constant (1 mm per metre,
   RESIDUAL_TOLERANCE_PER_SPAN = 1e-3) is unchanged; islands with a rigid
   frame (drift shared with the jog check, Slice U) and strip islands
   (each axis' own span) are unchanged. Decided by the agent, shown to the
   user in the report and in the PR; G0 v1.19 DD-52. The user may reverse
   it: on the measured data only e_arch_s2_n20 +Z island 1 and u_rounded
   +Z island 2 change verdict on one axis each.
19. Slice AL (the user's choice of slice, 2026-11-15: "the bulge of band
   f111"). Inside it the architect chose the rule among the study's
   measured variants (B4 with the corner cut): in a quilt without a rigid
   frame the stitched rail of a marked ladder strip is one line between
   right corners, a rail the mark made from several lines gives no length
   equation on its Chain, and its nodes are stations by 3D length between
   the nodes the quilt lays. Reason: it reproduces the user's own layout
   of that quilt (UV layer UVMap: outer side 0.999 of its 3D length,
   inner side 1.095 evenly along its whole length, both straight; the
   slice gives 1.000 and 1.101). Decided by the architect, shown to the
   user in the report and in the PR; G0 v1.20 DD-47, DD-54. The user may
   reverse it. It leaves open which side of a band leads its length
   (Slice AL, Next item 1).
20. Slice AM (opened by the user on 2026-11-23 after an external code
   review they relayed: "start the next slice with measuring items В and Б
   of the review"). Inside it the architect chose what to build from the
   measurements: the axis solve takes signs as given (the 3D dot step is
   removed), and in a quilt without a rigid frame a line the mark made
   from several lines keeps its rail lengths unless they contradict; of
   contradicting marked lines the shorter yields first (then the
   shortest k together), so the longest line keeps its length; the drift
   is taken once with every run. Reason: the user's own layout of the
   bottom quilt keeps the longer side (UV layer UVMap: outer side 0.999,
   inner side 1.095 evenly), and the rule leaves that quilt exactly as
   Slice AL laid it, also with Layer 3 families bounded at 15 degrees of
   accumulated turn (emulated). Decided by the architect, shown to the
   user in the report and in the PR; G0 v1.21 DD-47, DD-52, DD-54. The
   user may reverse it. Localising contradictions to their loop, drift by
   run length and the Layer 3 bound itself were measured and not built
   (Slice AM, Next items 1, 3, 4).
```
