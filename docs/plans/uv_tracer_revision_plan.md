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
- uv_transfer._pinned_for falls back to another patch's pin of the same
  source vertex; on buildings every such loop (669) lands at the other seam
  side's place inside the island.
- pins.PinnedVertex is keyed by (source vertex, patch), so the two seam-side
  occurrences of a SEAM_SELF band collapse into one pin: the solve gives two
  UVs per seam vertex on the one-seam tube and artist_cross_band, the write
  keeps one and puts it on both sides' loops. This contradicts the G5a claim
  that duplicated seam occurrences keep both UVs (found by the Slice N
  reviewer; pre-existing).
- island assembly: the Level A spanning tree accepts self-overlapping
  unfoldings (walls.007 facade and back side over each other).
```

---

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
6. Slice J: DD-46/DD-47 (ScaffoldTrace/ScaffoldRail) G0 amendment text is
   implemented as v0 evidence but not yet approved into G0 — PENDING
   (agent decision under user delegation, 2026-09: keep as draft until rails
   are reconciled with Slice N island lines).
7. Slice L2: G0 DD-43 fixture-expectation amendment (one rail per fold line;
   no patch revisit) — APPLIED to G0 v1.5 by the agent under explicit user
   delegation (2026-09).
8. Slice N: Layer 5 island lines, axes and orientation in the island frame;
   Layer 3 DD-45 continuation and node-crossing provenance repairs —
   APPROVED and DONE.
9. Next, open: which level to consolidate after patch -> line -> island
   (cross-island axis agreement through shared families; ScaffoldRail over
   island lines with loop opening by island cuts; island assembly without
   self-overlap; curved runs inside Layer 3 lines, OQ-11) — PENDING.
```
