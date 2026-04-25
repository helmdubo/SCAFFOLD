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


@dataclass(frozen=True)
class _BoundarySide:
    face_id: SourceFaceId
    edge_id: SourceEdgeId
    edge_index: int
    start_vertex_id: VertexId
    end_vertex_id: VertexId


@dataclass(frozen=True)
class _BoundaryRun:
    sides: tuple[_BoundarySide, ...]
    patch_context: tuple[PatchId, ...]


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
) -> bool:
    return len(first) > 1 and first == second


def _atomic_boundary_runs(
    sides: tuple[_BoundarySide, ...],
    edge_patch_contexts: dict[SourceEdgeId, tuple[PatchId, ...]],
) -> tuple[_BoundaryRun, ...]:
    return tuple(
        _BoundaryRun(sides=(side,), patch_context=edge_patch_contexts[side.edge_id])
        for side in sides
    )


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

    for side in cycle[1:]:
        side_context = edge_patch_contexts[side.edge_id]
        if _can_merge_boundary_contexts(current_context, side_context):
            current_sides.append(side)
            continue
        runs.append(_BoundaryRun(sides=tuple(current_sides), patch_context=current_context))
        current_sides = [side]
        current_context = side_context

    runs.append(_BoundaryRun(sides=tuple(current_sides), patch_context=current_context))

    if len(runs) == 1:
        run = runs[0]
        if (
            len(run.sides) > 1
            and _can_merge_boundary_contexts(run.patch_context, run.patch_context)
            and _run_start_vertex_id(run) == _run_end_vertex_id(run)
        ):
            return _atomic_boundary_runs(cycle, edge_patch_contexts)
        return tuple(runs)

    if _can_merge_boundary_contexts(runs[-1].patch_context, runs[0].patch_context):
        runs[0] = _BoundaryRun(
            sides=runs[-1].sides + runs[0].sides,
            patch_context=runs[0].patch_context,
        )
        runs.pop()

    return tuple(runs)


def _run_source_edge_ids(run: _BoundaryRun) -> tuple[SourceEdgeId, ...]:
    return tuple(side.edge_id for side in run.sides)


def _chain_key_for_run(run: _BoundaryRun) -> tuple[SourceEdgeId, ...]:
    return tuple(sorted(_run_source_edge_ids(run), key=str))


def _chain_id_for_key(chain_key: tuple[SourceEdgeId, ...]) -> ChainId:
    return ChainId("chain:" + ":".join(str(edge_id) for edge_id in chain_key))


def _orientation_sign_for_run(chain: Chain, run: _BoundaryRun) -> int:
    run_start = _run_start_vertex_id(run)
    run_end = _run_end_vertex_id(run)
    if chain.start_vertex_id == run_start and chain.end_vertex_id == run_end:
        return 1
    if chain.start_vertex_id == run_end and chain.end_vertex_id == run_start:
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
            start_vertex_id = VertexId(f"vertex:{source_edge.vertex_ids[0]}")
            end_vertex_id = VertexId(f"vertex:{source_edge.vertex_ids[1]}")

            face_start = face.vertex_ids[edge_index]
            face_end = face.vertex_ids[(edge_index + 1) % len(face.vertex_ids)]
            orientation_sign = _source_edge_orientation_sign(source_edge.vertex_ids, face_start, face_end)
            if orientation_sign == 1:
                side_start_vertex_id = start_vertex_id
                side_end_vertex_id = end_vertex_id
            else:
                side_start_vertex_id = end_vertex_id
                side_end_vertex_id = start_vertex_id

            boundary_sides_by_patch[patch_id].append(
                _BoundarySide(
                    face_id=face_id,
                    edge_id=source_edge_id,
                    edge_index=edge_index,
                    start_vertex_id=side_start_vertex_id,
                    end_vertex_id=side_end_vertex_id,
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
                chain_key = _chain_key_for_run(run)
                if chain_key not in chain_ids_by_key:
                    chain_id = _chain_id_for_key(chain_key)
                    chain_ids_by_key[chain_key] = chain_id
                    chains[chain_id] = Chain(
                        id=chain_id,
                        start_vertex_id=_run_start_vertex_id(run),
                        end_vertex_id=_run_end_vertex_id(run),
                        source_edge_ids=_run_source_edge_ids(run),
                    )
                else:
                    chain_id = chain_ids_by_key[chain_key]

                use_id = ChainUseId(f"use:{patch_id}:{loop_index}:{position_in_loop}")
                chain_uses[use_id] = ChainUse(
                    id=use_id,
                    chain_id=chain_id,
                    patch_id=patch_id,
                    loop_id=loop_id,
                    orientation_sign=_orientation_sign_for_run(chains[chain_id], run),
                    position_in_loop=position_in_loop,
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
