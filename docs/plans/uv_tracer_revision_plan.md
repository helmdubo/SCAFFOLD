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

Each strip keeps what the user's future filters need (horizontal, vertical,
under a ceiling, outer or inner corner for decals): rails, the neighbour
patches on each rail, the corner kind.

Reviewer gates (independent agents): AE-1 PASS WITH FIXES (an own
brute-force finder agreed with the relation on 953 patches of 25 captures
and about 3600 random synthetic patches; fixes: two test gaps, a red suite
caused by the architect adding the user's case after the test run). AE-2:
see the PR.

Tests 599 -> 762.

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
```
