"""
Layer: tests

Rules:
- Chain shape Stage B tests only: the chord shortcut of a zigzag Chain is taken per PatchChain use.
- Every "no longer one run" case is paired with a "still one run" case.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_2_geometry.build import build_geometry_facts
from scaffold_core.layer_3_relations import chain_refinement
from scaffold_core.layer_3_relations.chain_refinement import (
    build_chain_directional_runs,
    build_patch_chain_directional_evidence,
)
from scaffold_core.layer_3_relations.model import PatchChainShapeKind
from scaffold_core.layer_3_relations.patch_chain_shape import build_patch_chain_shape_relations
from scaffold_core.layer_5_runtime.pins import run_skeleton_solve
from scaffold_core.pipeline.passes import run_pass_0, run_pass_1_relations
from scaffold_core.tests.fixtures.chain_shape_surfaces import (
    make_folded_strip_with_cap_source,
    make_stepped_seam_source,
)
from scaffold_core.tests.test_layer_5_runtime import DATA, _load_capture
from scaffold_core.tests.test_patch_chain_shape import (
    ARCH_FOOT_CAPS,
    ARCH_FOOT_FRONT,
    ARCH_FRONT_ARCS,
    ARCH_RIM_ARCS,
    _canonical_sources,
)

AXES = ("AXIS_A", "AXIS_B")
JOG = "island line jogs in the unfolded frame"
STEPPED_CHAIN = "chain:e1_2_2_2:e1_1_1_2:e0_1_1_1"
STRAIGHT_CHAIN = "chain:e2_1_3_1:e1_1_2_1:e0_1_1_1"
FOLDED_CHAIN = "chain:e_p0_0_p1_0:e_p1_0_p2_0:e_p2_0_p3_0"
FOLDED_STRIP_USE = "patch_chain:patch:seed:f_strip0:0:0"
FOLDED_CAP_USE = "patch_chain:patch:seed:f_cap:0:1"
ARCH_FOOT_CHAINS = ("chain:e158:e139:e120:e128:e59", "chain:e44:e21:e108:e123:e146")


def _context(source):
    return run_pass_1_relations(run_pass_0(source))


def _evidence_of_use(relations, patch_chain_id: str) -> list:
    return sorted(
        (item for item in relations.patch_chain_directional_evidence if str(item.patch_chain_id) == patch_chain_id),
        key=lambda item: item.id,
    )


def _evidence_of_chain(relations, chain_id: str) -> dict[str, list]:
    uses: dict[str, list] = {}
    for item in relations.patch_chain_directional_evidence:
        if str(item.parent_chain_id) == chain_id:
            uses.setdefault(str(item.patch_chain_id), []).append(item)
    return {use: sorted(items, key=lambda item: item.id) for use, items in uses.items()}


def _runs_of_chain(relations, chain_id: str) -> list:
    return [run for run in relations.chain_directional_runs if str(run.parent_chain_id) == chain_id]


def _old_shortcut(monkeypatch) -> None:
    """Disable the per-side decision: every use keeps the chord run (main before Stage B)."""

    monkeypatch.setattr(chain_refinement, "_use_keeps_chord_run", lambda pieces, chord_run: True)


def _assert_runs_referenced_exactly(relations) -> None:
    referenced = {item.directional_run_id for item in relations.patch_chain_directional_evidence}
    assert {run.id for run in relations.chain_directional_runs} == referenced


# --- stepped seam between two coplanar patches ----------------------------------------------

def test_stepped_seam_is_three_axis_runs_on_both_sides_and_no_jog() -> None:
    context = _context(make_stepped_seam_source(stepped=True))
    relations = context.relation_snapshot

    uses = _evidence_of_chain(relations, STEPPED_CHAIN)
    assert len(uses) == 2
    for items in uses.values():
        assert [item.segment_indices for item in items] == [(0,), (1,), (2,)]
        assert [item.directional_run_id for item in items] == [f"directional_run:{STEPPED_CHAIN}:{index}" for index in range(3)]
    _assert_runs_referenced_exactly(relations)

    solve = run_skeleton_solve(context)
    roles = {run_id: role for skeleton in solve.skeletons for run_id, role in skeleton.axis_role_by_run.items()}
    assert all(roles[item.id] in AXES for items in uses.values() for item in items)
    assert not any(diagnostic.startswith(JOG) for diagnostic in solve.diagnostics)


def test_stepped_seam_was_one_chord_run_under_the_old_shortcut(monkeypatch) -> None:
    _old_shortcut(monkeypatch)
    relations = _context(make_stepped_seam_source(stepped=True)).relation_snapshot

    for items in _evidence_of_chain(relations, STEPPED_CHAIN).values():
        assert [item.segment_indices for item in items] == [(0, 1, 2)]


def test_straight_seam_stays_one_chord_run_with_unchanged_id_and_direction() -> None:
    source = make_stepped_seam_source(stepped=False)
    context = _context(source)
    relations = context.relation_snapshot

    (run,) = _runs_of_chain(relations, STRAIGHT_CHAIN)
    assert run.id == f"directional_run:{STRAIGHT_CHAIN}:0"
    assert run.segment_indices == (0, 1, 2)
    assert run.direction == context.geometry_facts.chain_facts[run.parent_chain_id].chord_direction
    for patch_chain_id, items in _evidence_of_chain(relations, STRAIGHT_CHAIN).items():
        assert [item.id for item in items] == [f"patch_chain_directional_evidence:{patch_chain_id}:0"]
        assert items[0].directional_run_id == run.id


# --- arch with bevels (artist capture) -------------------------------------------------------

@pytest.fixture(scope="module")
def arch_relations():
    return _context(_load_capture("artist_arch_bevel.json")).relation_snapshot


def test_arch_foot_chain_is_one_chord_run_on_the_front_face(arch_relations) -> None:
    for patch_chain_id in ARCH_FOOT_FRONT:
        (item,) = _evidence_of_use(arch_relations, patch_chain_id)
        run = next(run for run in arch_relations.chain_directional_runs if run.id == item.directional_run_id)
        assert item.id == f"patch_chain_directional_evidence:{patch_chain_id}:0"
        assert run.id == f"directional_run:{run.parent_chain_id}:0"
        assert item.segment_indices == (0, 1, 2, 3, 4)


def test_arch_foot_chain_is_split_at_its_corners_on_the_foot_caps(arch_relations) -> None:
    for patch_chain_id in ARCH_FOOT_CAPS:
        items = _evidence_of_use(arch_relations, patch_chain_id)
        assert [item.segment_indices for item in items] == [(0,), (1,), (2,), (3,), (4,)]
        assert [item.id for item in items] == [
            f"patch_chain_directional_evidence:{patch_chain_id}:{index}" for index in range(5)
        ]
        assert all(":split:" in item.directional_run_id for item in items)
    for chain_id in ARCH_FOOT_CHAINS:
        # One chord run for the front use plus five split runs for the cap use.
        assert len(_runs_of_chain(arch_relations, chain_id)) == 6
    _assert_runs_referenced_exactly(arch_relations)


def test_arch_rim_and_front_arcs_keep_their_run_counts(arch_relations) -> None:
    for patch_chain_id, segment_count in ARCH_RIM_ARCS.items():
        assert len(_evidence_of_use(arch_relations, patch_chain_id)) == segment_count
    for patch_chain_id, (segment_count, _, _) in ARCH_FRONT_ARCS.items():
        assert len(_evidence_of_use(arch_relations, patch_chain_id)) == segment_count


def test_arch_foot_chain_no_longer_joins_front_and_cap_in_one_family(arch_relations, monkeypatch) -> None:
    def families_with_front_and_cap(relations) -> int:
        count = 0
        for family in relations.connected_direction_families:
            members = " ".join(family.member_directional_evidence_ids)
            if any(use in members for use in ARCH_FOOT_FRONT) and any(use in members for use in ARCH_FOOT_CAPS):
                count += 1
        return count

    assert families_with_front_and_cap(arch_relations) == 0
    _old_shortcut(monkeypatch)
    assert families_with_front_and_cap(_context(_load_capture("artist_arch_bevel.json")).relation_snapshot) == 2


# --- strip folded like a bevel profile, flat end cap -------------------------------------------

def test_folded_strip_cross_chain_is_one_run_for_the_strip_and_cornered_for_the_cap() -> None:
    context = _context(make_folded_strip_with_cap_source())
    relations = context.relation_snapshot

    (strip_item,) = _evidence_of_use(relations, FOLDED_STRIP_USE)
    assert strip_item.directional_run_id == f"directional_run:{FOLDED_CHAIN}:0"
    assert strip_item.segment_indices == (0, 1, 2)
    strip_run = next(run for run in relations.chain_directional_runs if run.id == strip_item.directional_run_id)
    assert strip_run.direction == context.geometry_facts.chain_facts[strip_run.parent_chain_id].chord_direction

    cap_items = _evidence_of_use(relations, FOLDED_CAP_USE)
    assert [item.segment_indices for item in cap_items] == [(0,), (1,), (2,)]
    assert [item.directional_run_id for item in cap_items] == [
        f"directional_run:{FOLDED_CHAIN}:split:{index}" for index in range(3)
    ]
    _assert_runs_referenced_exactly(relations)

    solve = run_skeleton_solve(context)
    roles = {run_id: role for skeleton in solve.skeletons for run_id, role in skeleton.axis_role_by_run.items()}
    assert all(roles[item.id] in AXES for item in cap_items)


# --- the decision reads one use's own pieces ------------------------------------------------

def _folded_builders():
    source = make_folded_strip_with_cap_source()
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    relations, _ = build_patch_chain_shape_relations(topology, geometry)
    return topology, geometry, relations


def _strip_segments_with(pieces_of_strip) -> list[tuple[int, ...]]:
    topology, geometry, relations = _folded_builders()
    relations = tuple(piece for piece in relations if str(piece.patch_chain_id) != FOLDED_STRIP_USE) + pieces_of_strip(
        tuple(piece for piece in relations if str(piece.patch_chain_id) == FOLDED_STRIP_USE)
    )
    runs = build_chain_directional_runs(topology, geometry, relations)
    evidence = build_patch_chain_directional_evidence(topology, runs, relations)
    return [item.segment_indices for item in evidence if str(item.patch_chain_id) == FOLDED_STRIP_USE]


def test_one_surface_line_piece_keeps_the_chord_run() -> None:
    assert _strip_segments_with(lambda pieces: pieces) == [(0, 1, 2)]


@pytest.mark.parametrize("kind", (PatchChainShapeKind.UNRESOLVED, PatchChainShapeKind.SURFACE_CURVE))
def test_a_piece_that_is_not_a_surface_line_gets_split_runs(kind) -> None:
    assert _strip_segments_with(lambda pieces: tuple(replace(piece, kind=kind) for piece in pieces)) == [
        (0,),
        (1,),
        (2,),
    ]


def test_several_surface_line_pieces_get_split_runs() -> None:
    def two_pieces(pieces):
        (piece,) = pieces
        return (
            replace(piece, id=piece.id + ":a", segment_indices=(0, 1)),
            replace(piece, id=piece.id + ":b", segment_indices=(2,)),
        )

    assert _strip_segments_with(two_pieces) == [(0,), (1,), (2,)]


def test_a_use_without_a_shape_record_gets_split_runs() -> None:
    assert _strip_segments_with(lambda pieces: ()) == [(0,), (1,), (2,)]


@pytest.mark.parametrize(
    ("source", "chain_id"),
    ((make_folded_strip_with_cap_source(), FOLDED_CHAIN), (make_stepped_seam_source(stepped=False), STRAIGHT_CHAIN)),
)
def test_a_kept_chord_run_carries_the_layer_2_chord_direction(source, chain_id) -> None:
    # A chord direction a hair off the segment sum tells the two apart; real
    # meshes differ from the sum in float noise only.
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    facts = next(item for key, item in geometry.chain_facts.items() if str(key) == chain_id)
    chord = facts.chord_direction
    nudged = (chord[0], chord[1] + 1.0e-9, chord[2])
    geometry = replace(geometry, chain_facts={**geometry.chain_facts, facts.chain_id: replace(facts, chord_direction=nudged)})
    relations, _ = build_patch_chain_shape_relations(topology, geometry)

    runs = build_chain_directional_runs(topology, geometry, relations)

    assert next(run for run in runs if run.id == f"directional_run:{chain_id}:0").direction == nudged


# --- everything the rule does not touch is identical ---------------------------------------

AFFECTED_CHAINS_BY_SOURCE = {
    "blender:Decor_Roof_Left_lod00.003:Decor_Roof_Left_lod00.003": set(ARCH_FOOT_CHAINS),
    "stepped_seam": {STEPPED_CHAIN},
}


def _guard_sources():
    return [_load_capture(path.name) for path in sorted(DATA.glob("*.json"))] + _canonical_sources()


def test_chains_outside_the_rule_are_identical_to_the_old_shortcut(monkeypatch) -> None:
    sources = _guard_sources()
    assert len(sources) >= 18
    new = [_context(source) for source in sources]
    new_solves = [run_skeleton_solve(context) for context in new]

    _old_shortcut(monkeypatch)
    for source, context, solve in zip(sources, new, new_solves):
        old = _context(source)
        relations, old_relations = context.relation_snapshot, old.relation_snapshot
        affected = AFFECTED_CHAINS_BY_SOURCE.get(str(source.id), set())
        changed = {
            str(run.parent_chain_id)
            for run in relations.chain_directional_runs + old_relations.chain_directional_runs
            if (run in relations.chain_directional_runs) != (run in old_relations.chain_directional_runs)
        }
        assert changed == affected, source.id
        if not affected:
            assert relations == old_relations, source.id
            assert solve == run_skeleton_solve(old), source.id
            continue
        assert [run for run in relations.chain_directional_runs if str(run.parent_chain_id) not in affected] == [
            run for run in old_relations.chain_directional_runs if str(run.parent_chain_id) not in affected
        ]
        assert [
            item for item in relations.patch_chain_directional_evidence if str(item.parent_chain_id) not in affected
        ] == [
            item for item in old_relations.patch_chain_directional_evidence if str(item.parent_chain_id) not in affected
        ]


def test_in_repo_walls_captures_have_no_affected_chain_and_keep_their_jogs() -> None:
    jogs = {}
    for path in sorted(DATA.glob("artist_walls_*.json")):
        solve = run_skeleton_solve(_context(_load_capture(path.name)))
        jogs[path.stem] = sum(1 for diagnostic in solve.diagnostics if diagnostic.startswith(JOG))
    # No in-repo walls capture holds a zigzag chain that bends in its own
    # surface; the two jogs on walls_004 are elsewhere and stay (main: same).
    assert jogs == {
        "artist_walls_004_selection": 2,
        "artist_walls_005": 0,
        "artist_walls_006": 0,
        "artist_walls_007": 0,
    }


def _unresolved(piece):
    return (replace(piece, kind=PatchChainShapeKind.UNRESOLVED),)


def _two_pieces(piece):
    return (
        replace(piece, id=piece.id + ":a", segment_indices=(0, 1)),
        replace(piece, id=piece.id + ":b", segment_indices=(2,)),
    )


@pytest.mark.parametrize("reshape", (_unresolved, _two_pieces))
def test_a_straight_chain_stays_one_chord_run_whatever_one_side_says(reshape) -> None:
    source = make_stepped_seam_source(stepped=False)
    topology = build_topology_snapshot(source)
    geometry = build_geometry_facts(source, topology)
    relations, _ = build_patch_chain_shape_relations(topology, geometry)
    seam_pieces = [piece for piece in relations if str(piece.chain_id) == STRAIGHT_CHAIN]
    forced_use = sorted(str(piece.patch_chain_id) for piece in seam_pieces)[0]
    (forced_piece,) = [piece for piece in seam_pieces if str(piece.patch_chain_id) == forced_use]
    relations = tuple(piece for piece in relations if piece is not forced_piece) + reshape(forced_piece)

    runs = build_chain_directional_runs(topology, geometry, relations)
    evidence = build_patch_chain_directional_evidence(topology, runs, relations)

    (run,) = [run for run in runs if str(run.parent_chain_id) == STRAIGHT_CHAIN]
    assert run.id == f"directional_run:{STRAIGHT_CHAIN}:0"
    assert run.direction == geometry.chain_facts[run.parent_chain_id].chord_direction
    seam_evidence = [item for item in evidence if str(item.parent_chain_id) == STRAIGHT_CHAIN]
    assert len({str(item.patch_chain_id) for item in seam_evidence}) == 2
    assert all(item.directional_run_id == run.id for item in seam_evidence)
    assert not any(":split:" in item.id for item in runs)
