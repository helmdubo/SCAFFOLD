"""
Layer: tests

Rules:
- PatchChain orientation tests only.
- Tests may import Scaffold Core but must not define production logic.
"""

from __future__ import annotations

import pytest

from scaffold_core.ids import PatchChainId
from scaffold_core.layer_1_topology.build import build_topology_snapshot
from scaffold_core.layer_1_topology.queries import patch_chain_vertices
from scaffold_core.tests.fixtures.seam_self import make_seam_self_model
from scaffold_core.tests.test_layer_5_runtime import DATA, _load_capture


def test_patch_chain_orientation_sign_controls_start_and_end_vertices() -> None:
    model = make_seam_self_model()

    forward_start, forward_end = patch_chain_vertices(model, next(iter(model.patch_chains)))
    reverse_use_id = tuple(model.patch_chains.keys())[1]
    reverse_start, reverse_end = patch_chain_vertices(model, reverse_use_id)

    assert forward_start == reverse_end
    assert forward_end == reverse_start


@pytest.mark.parametrize("capture", sorted(path.name for path in DATA.glob("*.json")))
def test_every_patch_chain_use_walks_its_first_edge_with_its_side_face(capture) -> None:
    source = _load_capture(capture)
    model = build_topology_snapshot(source)

    checked, against = _side_face_winding(source, model)

    assert checked
    assert against == []


def test_closed_chains_used_from_a_seam_follow_the_cyclic_edge_order() -> None:
    # A ring met by a seam (the use starts elsewhere than the Chain) and a
    # Chain whose two ends are two occurrences of one source vertex.
    source = _load_capture("artist_cross_band.json")
    model = build_topology_snapshot(source)
    ring_use = model.patch_chains[PatchChainId("patch_chain:patch:seed:f4:0:0")]
    seam_closed_use = model.patch_chains[PatchChainId("patch_chain:patch:seed:f1:0:2")]

    ring = model.chains[ring_use.chain_id]
    assert ring_use.start_vertex_id == ring_use.end_vertex_id
    assert ring_use.start_vertex_id not in (ring.start_vertex_id, ring.end_vertex_id)
    seam_closed = model.chains[seam_closed_use.chain_id]
    assert seam_closed.start_vertex_id == seam_closed.end_vertex_id
    assert seam_closed_use.start_vertex_id != seam_closed_use.end_vertex_id
    assert ring_use.orientation_sign == seam_closed_use.orientation_sign == -1
    checked, against = _side_face_winding(source, model, (ring_use.id, seam_closed_use.id))
    assert checked == 2
    assert against == []


def _side_face_winding(source, model, use_ids=None):
    """Uses whose first edge has one side face in the patch, and those walked against it."""

    patch_of_face = {face_id: patch.id for patch in model.patches.values() for face_id in patch.source_face_ids}
    checked = 0
    against = []
    for use in model.patch_chains.values():
        if use_ids is not None and use.id not in use_ids:
            continue
        chain = model.chains[use.chain_id]
        walk = [model.vertices[chain.start_vertex_id].source_vertex_ids[0]]
        for edge_id in chain.source_edge_ids:
            first, second = source.edges[edge_id].vertex_ids
            walk.append(second if first == walk[-1] else first)
        edges = list(chain.source_edge_ids)
        if use.orientation_sign < 0:
            walk.reverse()
            edges.reverse()
        if walk[0] == walk[-1]:  # a ring: the use starts at its own start vertex
            start = walk.index(model.vertices[use.start_vertex_id].source_vertex_ids[0])
            walk = walk[start:-1] + walk[:start + 1]
            edges = edges[start:] + edges[:start]
        side_faces = [
            face_id for face_id, face in source.faces.items()
            if edges[0] in face.edge_ids and patch_of_face.get(face_id) == use.patch_id
        ]
        if len(side_faces) != 1:
            continue  # both sides of the edge are in the patch (a seam inside it)
        ids = source.faces[side_faces[0]].vertex_ids
        checked += 1
        if not any(ids[i] == walk[0] and ids[(i + 1) % len(ids)] == walk[1] for i in range(len(ids))):
            against.append(use.id)
    return checked, against
