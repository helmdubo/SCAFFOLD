"""
Layer: 1 — Topology

Rules:
- Build immutable Layer 1 topology snapshot from Layer 0 source snapshot.
- Build only topology.
- Do not compute Layer 2 geometry facts.
- Do not classify features.
- Do not assign H/V or WorldOrientation roles.
- Do not orchestrate pipeline passes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from scaffold_core.ids import (
    BoundaryLoopId,
    ChainId,
    ChainUseId,
    PatchId,
    ShellId,
    SourceEdgeId,
    SourceFaceId,
    SourceVertexId,
    SurfaceModelId,
    VertexId,
)
from scaffold_core.layer_0_source.marks import SourceMarkKind
from scaffold_core.layer_0_source.snapshot import SourceMeshSnapshot
from scaffold_core.layer_1_topology.model import (
    BoundaryLoop,
    BoundaryLoopKind,
    Chain,
    ChainUse,
    Patch,
    Shell,
    SurfaceModel,
    Vertex,
)


class _BoundaryRunKind(str, Enum):
    BORDER_RUN = "BORDER_RUN"
    PATCH_ADJACENCY_RUN = "PATCH_ADJACENCY_RUN"
    SEAM_SELF_RUN = "SEAM_SELF_RUN"
    NON_MANIFOLD_RUN = "NON_MANIFOLD_RUN"


@dataclass(frozen=True)
class _BoundarySide:
    face_id: SourceFaceId
    edge_id: SourceEdgeId
    edge_index: int
    start_vertex_id: VertexId
    end_vertex_id: VertexId
    run_kind: _BoundaryRunKind


@dataclass(frozen=True)
class _BoundaryRun:
    sides: tuple[_BoundarySide, ...]
    patch_context: tuple[PatchId, ...]
    run_kind: _BoundaryRunKind


def selected_face_ids(source: SourceMeshSnapshot) -> tuple[SourceFaceId, ...]:
    """Return selected faces, or all source faces when no explicit selection exists."""

    return tuple(source.selected_face_ids) or tuple(source.faces.keys())


def selected_edge_incidence(
    source: SourceMeshSnapshot,
    face_ids: tuple[SourceFaceId, ...],
) -> dict[SourceEdgeId, tuple[SourceFaceId, ...]]:
    """Map each source edge to selected faces that use it."""

    selected = set(face_ids)
    incidence: dict[SourceEdgeId, list[SourceFaceId]] = defaultdict(list)
    for face_id in face_ids:
        face = source.faces[face_id]
        for edge_id in face.edge_ids:
            if face_id in selected:
                incidence[edge_id].append(face_id)
    return {edge_id: tuple(edge_face_ids) for edge_id, edge_face_ids in incidence.items()}


def marked_patch_boundary_edge_ids(source: SourceMeshSnapshot) -> set[SourceEdgeId]:
    """Return source edges explicitly marked as G1 Patch boundaries."""

    boundary_edge_ids: set[SourceEdgeId] = set()
    source_edge_ids = set(source.edges)
    for mark in source.marks:
        if mark.target_id not in source_edge_ids or not mark.value:
            continue
        if mark.kind in (SourceMarkKind.SEAM, SourceMarkKind.USER):
            boundary_edge_ids.add(SourceEdgeId(mark.target_id))
    return boundary_edge_ids


def is_patch_boundary_edge(
    edge_id: SourceEdgeId,
    selected_incident_face_ids: tuple[SourceFaceId, ...],
    boundary_mark_edge_ids: set[SourceEdgeId],
) -> bool:
    """Return whether a selected source edge blocks G1 Patch flood fill."""

    if len(selected_incident_face_ids) != 2:
        return True
    return edge_id in boundary_mark_edge_ids


def _edge_connected_face_components(
    source: SourceMeshSnapshot,
    face_ids: tuple[SourceFaceId, ...],
    edge_incidence: dict[SourceEdgeId, tuple[SourceFaceId, ...]],
    boundary_mark_edge_ids: set[SourceEdgeId] | None = None,
) -> tuple[tuple[SourceFaceId, ...], ...]:
    components: list[tuple[SourceFaceId, ...]] = []
    face_order = {face_id: index for index, face_id in enumerate(face_ids)}
    remaining = set(face_ids)

    while remaining:
        start = min(remaining, key=face_order.__getitem__)
        stack = [start]
        component: list[SourceFaceId] = []
        remaining.remove(start)

        while stack:
            face_id = stack.pop()
            component.append(face_id)
            for edge_id in source.faces[face_id].edge_ids:
                incident_face_ids = edge_incidence[edge_id]
                if boundary_mark_edge_ids is not None and is_patch_boundary_edge(
                    edge_id,
                    incident_face_ids,
                    boundary_mark_edge_ids,
                ):
                    continue
                for neighbor_face_id in incident_face_ids:
                    if neighbor_face_id in remaining:
                        remaining.remove(neighbor_face_id)
                        stack.append(neighbor_face_id)

        components.append(tuple(sorted(component, key=face_order.__getitem__)))

    return tuple(components)


def _source_edge_orientation_sign(
    source_edge_vertex_ids: tuple[SourceVertexId, SourceVertexId],
    face_start: SourceVertexId,
    face_end: SourceVertexId,
) -> int:
    if (face_start, face_end) == source_edge_vertex_ids:
        return 1
    if (face_end, face_start) == source_edge_vertex_ids:
        return -1
    return 1


def _order_boundary_cycles(
    sides: tuple[_BoundarySide, ...],
) -> tuple[tuple[tuple[_BoundarySide, ...], bool], ...]:
    cycles: list[tuple[tuple[_BoundarySide, ...], bool]] = []
    remaining = sorted(sides, key=lambda side: (str(side.face_id), side.edge_index, str(side.edge_id)))

    while remaining:
        cycle = [remaining.pop(0)]
        first_start = cycle[0].start_vertex_id
        current_end = cycle[0].end_vertex_id
        closed = current_end == first_start

        while remaining and not closed:
            next_index = next(
                (
                    index
                    for index, candidate in enumerate(remaining)
                    if candidate.start_vertex_id == current_end
                ),
                None,
            )
            if next_index is None:
                break

            next_side = remaining.pop(next_index)
            cycle.append(next_side)
            current_end = next_side.end_vertex_id
            closed = current_end == first_start

        cycles.append((tuple(cycle), closed))

    return tuple(cycles)


def _edge_patch_contexts(
    edge_incidence: dict[SourceEdgeId, tuple[SourceFaceId, ...]],
    face_to_patch_id: dict[SourceFaceId, PatchId],
) -> dict[SourceEdgeId, tuple[PatchId, ...]]:
    contexts: dict[SourceEdgeId, tuple[PatchId, ...]] = {}
    for edge_id, face_ids in edge_incidence.items():
        patch_ids = {face_to_patch_id[face_id] for face_id in face_ids}
        contexts[edge_id] = tuple(sorted(patch_ids, key=str))
    return contexts


def _can_merge_boundary_contexts(
    first: tuple[PatchId, ...],
    second: tuple[PatchId, ...],
    first_kind: _BoundaryRunKind,
    second_kind: _BoundaryRunKind,
) -> bool:
    return first_kind is second_kind and first == second


def _boundary_run_kind(
    edge_id: SourceEdgeId,
    selected_incident_face_ids: tuple[SourceFaceId, ...],
    patch_context: tuple[PatchId, ...],
    boundary_mark_edge_ids: set[SourceEdgeId],
) -> _BoundaryRunKind:
    if len(selected_incident_face_ids) > 2:
        return _BoundaryRunKind.NON_MANIFOLD_RUN
    if len(selected_incident_face_ids) == 1:
        return _BoundaryRunKind.BORDER_RUN
    if edge_id in boundary_mark_edge_ids and len(patch_context) == 1:
        return _BoundaryRunKind.SEAM_SELF_RUN
    return _BoundaryRunKind.PATCH_ADJACENCY_RUN


def _boundary_endpoint_vertex_id(
    face_id: SourceFaceId,
    patch_id: PatchId,
    source_vertex_id: SourceVertexId,
    materialized_vertex_ids: dict[tuple[PatchId, SourceFaceId, SourceVertexId], VertexId],
) -> VertexId:
    return materialized_vertex_ids.get(
        (patch_id, face_id, source_vertex_id),
        VertexId(f"vertex:{source_vertex_id}"),
    )


def _materialized_vertex_ids_by_face(
    source: SourceMeshSnapshot,
    patch_face_ids: dict[PatchId, tuple[SourceFaceId, ...]],
    face_to_patch_id: dict[SourceFaceId, PatchId],
    edge_incidence: dict[SourceEdgeId, tuple[SourceFaceId, ...]],
    boundary_mark_edge_ids: set[SourceEdgeId],
    vertices: dict[VertexId, Vertex],
) -> dict[tuple[PatchId, SourceFaceId, SourceVertexId], VertexId]:
    materialized: dict[tuple[PatchId, SourceFaceId, SourceVertexId], VertexId] = {}
    for patch_id, face_ids in patch_face_ids.items():
        faces_by_vertex: dict[SourceVertexId, list[SourceFaceId]] = defaultdict(list)
        for face_id in face_ids:
            for source_vertex_id in source.faces[face_id].vertex_ids:
                faces_by_vertex[source_vertex_id].append(face_id)

        for source_vertex_id, vertex_face_ids in faces_by_vertex.items():
            face_set = set(vertex_face_ids)
            if len(face_set) <= 1:
                continue

            parents = {face_id: face_id for face_id in face_set}

            def find(face_id: SourceFaceId) -> SourceFaceId:
                while parents[face_id] != face_id:
                    parents[face_id] = parents[parents[face_id]]
                    face_id = parents[face_id]
                return face_id

            def union(first: SourceFaceId, second: SourceFaceId) -> None:
                first_root = find(first)
                second_root = find(second)
                if first_root != second_root:
                    parents[second_root] = first_root

            for edge_id, source_edge in source.edges.items():
                if source_vertex_id not in source_edge.vertex_ids:
                    continue
                if is_patch_boundary_edge(
                    edge_id,
                    edge_incidence.get(edge_id, ()),
                    boundary_mark_edge_ids,
                ):
                    continue
                incident_patch_face_ids = [
                    incident_face_id
                    for incident_face_id in edge_incidence.get(edge_id, ())
                    if incident_face_id in face_set
                    and face_to_patch_id[incident_face_id] == patch_id
                ]
                for incident_face_id in incident_patch_face_ids[1:]:
                    union(incident_patch_face_ids[0], incident_face_id)

            components: dict[SourceFaceId, list[SourceFaceId]] = defaultdict(list)
            for vertex_face_id in face_set:
                components[find(vertex_face_id)].append(vertex_face_id)
            if len(components) <= 1:
                continue

            sorted_components = sorted(
                (tuple(sorted(component, key=str)) for component in components.values()),
                key=lambda component: str(component[0]),
            )
            for component_index, component in enumerate(sorted_components):
                vertex_id = VertexId(f"vertex:{source_vertex_id}:use:{patch_id}:{component_index}")
                vertices.setdefault(
                    vertex_id,
                    Vertex(
                        id=vertex_id,
                        source_vertex_ids=(source_vertex_id,),
                    ),
                )
                for component_face_id in component:
                    materialized[(patch_id, component_face_id, source_vertex_id)] = vertex_id

    return materialized


def _run_start_vertex_id(run: _BoundaryRun) -> VertexId:
    return run.sides[0].start_vertex_id


def _run_end_vertex_id(run: _BoundaryRun) -> VertexId:
    return run.sides[-1].end_vertex_id


def _coalesce_boundary_runs(
    cycle: tuple[_BoundarySide, ...],
    edge_patch_contexts: dict[SourceEdgeId, tuple[PatchId, ...]],
) -> tuple[_BoundaryRun, ...]:
    if not cycle:
        return ()

    runs: list[_BoundaryRun] = []
    current_sides = [cycle[0]]
    current_context = edge_patch_contexts[cycle[0].edge_id]
    current_kind = cycle[0].run_kind

    for side in cycle[1:]:
        side_context = edge_patch_contexts[side.edge_id]
        if _can_merge_boundary_contexts(current_context, side_context, current_kind, side.run_kind):
            current_sides.append(side)
            continue
        runs.append(_BoundaryRun(
            sides=tuple(current_sides),
            patch_context=current_context,
            run_kind=current_kind,
        ))
        current_sides = [side]
        current_context = side_context
        current_kind = side.run_kind

    runs.append(_BoundaryRun(
        sides=tuple(current_sides),
        patch_context=current_context,
        run_kind=current_kind,
    ))

    if len(runs) == 1:
        return tuple(runs)

    if _can_merge_boundary_contexts(
        runs[-1].patch_context,
        runs[0].patch_context,
        runs[-1].run_kind,
        runs[0].run_kind,
    ):
        runs[0] = _BoundaryRun(
            sides=runs[-1].sides + runs[0].sides,
            patch_context=runs[0].patch_context,
            run_kind=runs[0].run_kind,
        )
        runs.pop()

    return tuple(runs)


def _run_source_edge_ids(run: _BoundaryRun) -> tuple[SourceEdgeId, ...]:
    return tuple(side.edge_id for side in run.sides)


def _chain_lookup_key_for_run(run: _BoundaryRun) -> tuple[SourceEdgeId, ...]:
    return tuple(sorted(_run_source_edge_ids(run), key=str))


def _chain_id_for_source_edge_ids(source_edge_ids: tuple[SourceEdgeId, ...]) -> ChainId:
    return ChainId("chain:" + ":".join(str(edge_id) for edge_id in source_edge_ids))


def _matches_cyclic_order(
    candidate: tuple[SourceEdgeId, ...],
    reference: tuple[SourceEdgeId, ...],
) -> bool:
    if len(candidate) != len(reference):
        return False
    if not candidate:
        return True
    doubled_reference = reference + reference
    return any(
        candidate == doubled_reference[index:index + len(candidate)]
        for index in range(len(reference))
    )


def _orientation_sign_for_run(
    chain: Chain,
    run: _BoundaryRun,
    vertices: dict[VertexId, Vertex],
) -> int:
    run_start = _run_start_vertex_id(run)
    run_end = _run_end_vertex_id(run)
    run_source_edge_ids = _run_source_edge_ids(run)
    if chain.start_vertex_id == chain.end_vertex_id and run_start == run_end:
        if _matches_cyclic_order(run_source_edge_ids, chain.source_edge_ids):
            return 1
        if _matches_cyclic_order(tuple(reversed(run_source_edge_ids)), chain.source_edge_ids):
            return -1

    if chain.start_vertex_id == run_start and chain.end_vertex_id == run_end:
        return 1
    if chain.start_vertex_id == run_end and chain.end_vertex_id == run_start:
        return -1
    chain_start_sources = set(vertices[chain.start_vertex_id].source_vertex_ids)
    chain_end_sources = set(vertices[chain.end_vertex_id].source_vertex_ids)
    run_start_sources = set(vertices[run_start].source_vertex_ids)
    run_end_sources = set(vertices[run_end].source_vertex_ids)
    if chain_start_sources & run_start_sources and chain_end_sources & run_end_sources:
        return 1
    if chain_start_sources & run_end_sources and chain_end_sources & run_start_sources:
        return -1
    return 1


def build_topology_snapshot(source: SourceMeshSnapshot) -> SurfaceModel:
    """Build a Layer 1 topology snapshot from a source mesh snapshot."""

    face_ids = selected_face_ids(source)
    edge_incidence = selected_edge_incidence(source, face_ids)
    boundary_mark_edge_ids = marked_patch_boundary_edge_ids(source)
    model_id = SurfaceModelId(f"surface:{source.id}")

    vertices = {
        VertexId(f"vertex:{source_vertex_id}"): Vertex(
            id=VertexId(f"vertex:{source_vertex_id}"),
            source_vertex_ids=(source_vertex_id,),
        )
        for source_vertex_id in source.vertices
    }

    chains: dict[ChainId, Chain] = {}
    chain_uses: dict[ChainUseId, ChainUse] = {}
    loops: dict[BoundaryLoopId, BoundaryLoop] = {}
    patches: dict[PatchId, Patch] = {}
    shells: dict[ShellId, Shell] = {}
    face_to_patch_id: dict[SourceFaceId, PatchId] = {}
    patch_face_ids: dict[PatchId, tuple[SourceFaceId, ...]] = {}
    patch_shell_ids: dict[PatchId, ShellId] = {}
    patch_loop_ids: dict[PatchId, list[BoundaryLoopId]] = defaultdict(list)
    chain_ids_by_key: dict[tuple[SourceEdgeId, ...], ChainId] = {}

    shell_components = _edge_connected_face_components(source, face_ids, edge_incidence)

    for shell_index, shell_face_ids in enumerate(shell_components):
        shell_id = ShellId(f"shell:{shell_index}")
        patch_components = _edge_connected_face_components(
            source,
            shell_face_ids,
            edge_incidence,
            boundary_mark_edge_ids,
        )
        shell_patch_ids: list[PatchId] = []

        for patch_face_ids_tuple in patch_components:
            patch_id = PatchId(f"patch:seed:{patch_face_ids_tuple[0]}")
            shell_patch_ids.append(patch_id)
            patch_face_ids[patch_id] = patch_face_ids_tuple
            patch_shell_ids[patch_id] = shell_id
            for face_id in patch_face_ids_tuple:
                face_to_patch_id[face_id] = patch_id

        shells[shell_id] = Shell(id=shell_id, patch_ids=tuple(shell_patch_ids))

    boundary_sides_by_patch: dict[PatchId, list[_BoundarySide]] = defaultdict(list)
    edge_patch_contexts = _edge_patch_contexts(edge_incidence, face_to_patch_id)
    materialized_vertex_ids = _materialized_vertex_ids_by_face(
        source,
        patch_face_ids,
        face_to_patch_id,
        edge_incidence,
        boundary_mark_edge_ids,
        vertices,
    )

    for face_id in face_ids:
        face = source.faces[face_id]
        patch_id = face_to_patch_id[face_id]
        for edge_index, source_edge_id in enumerate(face.edge_ids):
            selected_incident_face_ids = edge_incidence[source_edge_id]
            if not is_patch_boundary_edge(
                source_edge_id,
                selected_incident_face_ids,
                boundary_mark_edge_ids,
            ):
                continue

            source_edge = source.edges[source_edge_id]
            face_start = face.vertex_ids[edge_index]
            face_end = face.vertex_ids[(edge_index + 1) % len(face.vertex_ids)]
            orientation_sign = _source_edge_orientation_sign(source_edge.vertex_ids, face_start, face_end)
            if orientation_sign == 1:
                side_start_source_vertex_id = source_edge.vertex_ids[0]
                side_end_source_vertex_id = source_edge.vertex_ids[1]
            else:
                side_start_source_vertex_id = source_edge.vertex_ids[1]
                side_end_source_vertex_id = source_edge.vertex_ids[0]

            side_start_vertex_id = _boundary_endpoint_vertex_id(
                face_id,
                patch_id,
                side_start_source_vertex_id,
                materialized_vertex_ids,
            )
            side_end_vertex_id = _boundary_endpoint_vertex_id(
                face_id,
                patch_id,
                side_end_source_vertex_id,
                materialized_vertex_ids,
            )

            boundary_sides_by_patch[patch_id].append(
                _BoundarySide(
                    face_id=face_id,
                    edge_id=source_edge_id,
                    edge_index=edge_index,
                    start_vertex_id=side_start_vertex_id,
                    end_vertex_id=side_end_vertex_id,
                    run_kind=_boundary_run_kind(
                        source_edge_id,
                        selected_incident_face_ids,
                        edge_patch_contexts[source_edge_id],
                        boundary_mark_edge_ids,
                    ),
                )
            )

    for patch_id in patch_face_ids:
        ordered_cycles = _order_boundary_cycles(tuple(boundary_sides_by_patch.get(patch_id, ())))
        closed_cycles = [
            (cycle, closed)
            for cycle, closed in ordered_cycles
            if closed
        ]
        sorted_cycles = sorted(
            closed_cycles,
            key=lambda item: (-len(item[0]), str(item[0][0].edge_id) if item[0] else ""),
        )
        sorted_cycles.extend((cycle, closed) for cycle, closed in ordered_cycles if not closed)

        for loop_index, (cycle, closed) in enumerate(sorted_cycles):
            loop_id = BoundaryLoopId(f"loop:{patch_id}:{loop_index}")
            use_ids: list[ChainUseId] = []
            boundary_runs = _coalesce_boundary_runs(cycle, edge_patch_contexts)

            for position_in_loop, run in enumerate(boundary_runs):
                chain_key = _chain_lookup_key_for_run(run)
                if chain_key not in chain_ids_by_key:
                    source_edge_ids = _run_source_edge_ids(run)
                    chain_id = _chain_id_for_source_edge_ids(source_edge_ids)
                    chain_ids_by_key[chain_key] = chain_id
                    chains[chain_id] = Chain(
                        id=chain_id,
                        start_vertex_id=_run_start_vertex_id(run),
                        end_vertex_id=_run_end_vertex_id(run),
                        source_edge_ids=source_edge_ids,
                    )
                else:
                    chain_id = chain_ids_by_key[chain_key]

                use_id = ChainUseId(f"use:{patch_id}:{loop_index}:{position_in_loop}")
                chain_uses[use_id] = ChainUse(
                    id=use_id,
                    chain_id=chain_id,
                    patch_id=patch_id,
                    loop_id=loop_id,
                    orientation_sign=_orientation_sign_for_run(chains[chain_id], run, vertices),
                    position_in_loop=position_in_loop,
                    start_vertex_id=_run_start_vertex_id(run),
                    end_vertex_id=_run_end_vertex_id(run),
                )
                use_ids.append(use_id)

            if not closed:
                loop_kind = BoundaryLoopKind.DEGRADED
            elif loop_index == 0:
                loop_kind = BoundaryLoopKind.OUTER
            else:
                loop_kind = BoundaryLoopKind.INNER

            loops[loop_id] = BoundaryLoop(
                id=loop_id,
                patch_id=patch_id,
                kind=loop_kind,
                chain_use_ids=tuple(use_ids),
                loop_index=loop_index,
            )
            patch_loop_ids[patch_id].append(loop_id)

        patches[patch_id] = Patch(
            id=patch_id,
            shell_id=patch_shell_ids[patch_id],
            loop_ids=tuple(patch_loop_ids[patch_id]),
            source_face_ids=patch_face_ids[patch_id],
        )

    return SurfaceModel(
        id=model_id,
        shells=shells,
        patches=patches,
        loops=loops,
        chains=chains,
        chain_uses=chain_uses,
        vertices=vertices,
    )
