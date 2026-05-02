from __future__ import annotations

from mathutils import Vector

try:
    from .console_debug import trace_console
    from .model import (
        ChainNeighborKind,
        PatchGraph,
        PatchNode,
        SeamEdge,
        MeshPreflightIssue,
        MeshPreflightReport,
        FormattedReport,
    )
    from .analysis_records import (
        _RawPatchBoundaryData,
        _PatchTopologyAssemblyState,
        _PatchNeighborChainRef,
    )
    from .analysis_boundary import (
        _trace_boundary_loops,
        _validate_raw_patch_boundary_data,
        _build_boundary_loops,
        _validate_patch_loop_classification,
    )
    from .analysis_classification import (
        _classify_patch,
        _build_patch_basis,
        _classify_loops_outer_hole,
    )
except ImportError:
    from console_debug import trace_console
    from model import (
        ChainNeighborKind,
        PatchGraph,
        PatchNode,
        SeamEdge,
        MeshPreflightIssue,
        MeshPreflightReport,
        FormattedReport,
    )
    from analysis_records import (
        _RawPatchBoundaryData,
        _PatchTopologyAssemblyState,
        _PatchNeighborChainRef,
    )
    from analysis_boundary import (
        _trace_boundary_loops,
        _validate_raw_patch_boundary_data,
        _build_boundary_loops,
        _validate_patch_loop_classification,
    )
    from analysis_classification import (
        _classify_patch,
        _build_patch_basis,
        _classify_loops_outer_hole,
    )


def _coerce_face_indices(bm, faces_or_indices):
    bm.faces.ensure_lookup_table()

    ordered = []
    seen = set()
    for item in faces_or_indices or []:
        face_index = item.index if hasattr(item, "index") else int(item)
        if face_index in seen:
            continue
        if face_index < 0 or face_index >= len(bm.faces):
            continue
        seen.add(face_index)
        ordered.append(face_index)
    return ordered


def validate_solver_input_mesh(bm, face_indices, area_epsilon=1e-10):
    """Validate mesh topology before entering the solve pipeline."""

    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    checked_face_indices = tuple(_coerce_face_indices(bm, face_indices))
    report = MeshPreflightReport(checked_face_indices=checked_face_indices)
    if not checked_face_indices:
        return report

    relevant_face_set = set(checked_face_indices)
    face_signatures = {}
    for face in bm.faces:
        signature = tuple(sorted(vert.index for vert in face.verts))
        face_signatures.setdefault(signature, []).append(face.index)

    seen_duplicate_groups = set()
    for face_index in checked_face_indices:
        face = bm.faces[face_index]
        unique_vert_indices = tuple(sorted({vert.index for vert in face.verts}))
        if len(unique_vert_indices) < len(face.verts) or len(unique_vert_indices) < 3 or face.calc_area() <= area_epsilon:
            report.issues.append(
                MeshPreflightIssue(
                    code='DEGENERATE_FACE',
                    message=f'Face {face_index} is degenerate or repeats vertices',
                    face_indices=(face_index,),
                    vert_indices=unique_vert_indices,
                )
            )

        signature = tuple(sorted(vert.index for vert in face.verts))
        duplicate_faces = tuple(sorted(face_signatures.get(signature, [])))
        if len(duplicate_faces) > 1 and duplicate_faces not in seen_duplicate_groups:
            seen_duplicate_groups.add(duplicate_faces)
            report.issues.append(
                MeshPreflightIssue(
                    code='DUPLICATE_FACE',
                    message=f'Faces share identical vertex set: {list(duplicate_faces)}',
                    face_indices=duplicate_faces,
                    vert_indices=signature,
                )
            )

    visited_edges = set()
    for face_index in checked_face_indices:
        face = bm.faces[face_index]
        for edge in face.edges:
            if edge.index in visited_edges:
                continue
            visited_edges.add(edge.index)
            linked_faces = tuple(sorted(linked_face.index for linked_face in edge.link_faces))
            if len(linked_faces) <= 2:
                continue
            if not relevant_face_set.intersection(linked_faces):
                continue
            report.issues.append(
                MeshPreflightIssue(
                    code='NON_MANIFOLD_EDGE',
                    message=f'Edge {edge.index} has {len(linked_faces)} linked faces',
                    face_indices=linked_faces,
                    edge_indices=(edge.index,),
                    vert_indices=tuple(vert.index for vert in edge.verts),
                )
            )

    return report


def format_solver_input_preflight_report(report, mesh_name=None) -> FormattedReport:
    """Build text lines for blocking solve preflight issues."""

    lines = []
    if mesh_name:
        lines.append(f'Mesh: {mesh_name}')
    lines.append(f'Checked faces: {len(report.checked_face_indices)}')

    if report.is_valid:
        summary = f'Solver preflight: OK | faces:{len(report.checked_face_indices)}'
        return FormattedReport(lines=lines, summary=summary)

    issue_counts = {}
    for issue in report.issues:
        issue_counts[issue.code] = issue_counts.get(issue.code, 0) + 1

    lines.append('Blocking issues:')
    for issue in report.issues[:16]:
        refs = []
        if issue.face_indices:
            refs.append(f'faces:{list(issue.face_indices)}')
        if issue.edge_indices:
            refs.append(f'edges:{list(issue.edge_indices)}')
        if issue.vert_indices:
            refs.append(f'verts:{list(issue.vert_indices)}')
        suffix = f" | {' '.join(refs)}" if refs else ''
        lines.append(f'  - {issue.code}: {issue.message}{suffix}')

    remaining = len(report.issues) - 16
    if remaining > 0:
        lines.append(f'  - ... {remaining} more issues')

    parts = [f'{code}:{issue_counts[code]}' for code in sorted(issue_counts.keys())]
    summary = 'Solver preflight failed: ' + ', '.join(parts)
    return FormattedReport(lines=lines, summary=summary)

def get_expanded_islands(bm, initial_faces):
    """Build full/core islands for the two-pass unwrap pipeline."""

    initial_indices = _coerce_face_indices(bm, initial_faces)
    initial_set = set(initial_indices)
    visited = set()
    islands = []

    for start_idx in initial_indices:
        if start_idx in visited:
            continue

        full_faces = []
        core_faces = []
        stack = [start_idx]
        visited.add(start_idx)

        while stack:
            face_idx = stack.pop()
            face = bm.faces[face_idx]
            full_faces.append(face)
            if face_idx in initial_set:
                core_faces.append(face)

            for edge in face.edges:
                if edge.seam:
                    continue
                for neighbor in edge.link_faces:
                    neighbor_idx = neighbor.index
                    if neighbor_idx in visited:
                        continue
                    visited.add(neighbor_idx)
                    stack.append(neighbor_idx)

        islands.append({"full": full_faces, "core": core_faces})

    return islands


def _flood_fill_patches(bm, face_indices):
    """Flood-fill face groups split by seam and mesh borders."""

    face_indices = _coerce_face_indices(bm, face_indices)
    face_set = set(face_indices)
    visited = set()
    patches = []

    for start_idx in face_indices:
        if start_idx in visited:
            continue

        stack = [start_idx]
        visited.add(start_idx)
        patch = []

        while stack:
            face_idx = stack.pop()
            face = bm.faces[face_idx]
            patch.append(face_idx)

            for edge in face.edges:
                if edge.seam:
                    continue
                for neighbor in edge.link_faces:
                    neighbor_idx = neighbor.index
                    if neighbor_idx not in face_set or neighbor_idx in visited:
                        continue
                    visited.add(neighbor_idx)
                    stack.append(neighbor_idx)

        patches.append(patch)

    return patches



def _report_graph_topology_invariant_violation(rule_code, detail):
    """Emit a deterministic graph-level topology invariant violation."""

    trace_console(f"[CFTUV][TopologyInvariant] Graph {rule_code} {detail}")



def _report_junction_invariant_violation(vert_index, rule_code, detail):
    """Emit a deterministic junction-level topology invariant violation."""

    trace_console(f"[CFTUV][TopologyInvariant] Junction V{vert_index} {rule_code} {detail}")


def _iter_patch_neighbor_chain_refs(graph):
    """Yield all final chains that claim an opposite patch as neighbor."""

    for patch_id, node in graph.nodes.items():
        for loop_index, boundary_loop in enumerate(node.boundary_loops):
            for chain_index, chain in enumerate(boundary_loop.chains):
                if not chain.has_patch_neighbor:
                    continue
                yield _PatchNeighborChainRef(
                    patch_id=patch_id,
                    loop_index=loop_index,
                    chain_index=chain_index,
                    neighbor_patch_id=chain.neighbor_patch_id,
                    start_vert_index=chain.start_vert_index,
                    end_vert_index=chain.end_vert_index,
                )


def _validate_patch_graph_seam_consistency(graph):
    """Validate that patch-neighbor chains agree with the final seam graph."""

    refs_by_pair: dict[tuple[int, int], list[_PatchNeighborChainRef]] = {}
    for chain_ref in _iter_patch_neighbor_chain_refs(graph):
        pair_key = (
            min(chain_ref.patch_id, chain_ref.neighbor_patch_id),
            max(chain_ref.patch_id, chain_ref.neighbor_patch_id),
        )
        refs_by_pair.setdefault(pair_key, []).append(chain_ref)

    for pair_key, chain_refs in refs_by_pair.items():
        patch_a_id, patch_b_id = pair_key
        seam = graph.get_seam(patch_a_id, patch_b_id)
        if seam is None:
            _report_graph_topology_invariant_violation(
                "X5",
                f"missing_seam pair={pair_key} chain_refs="
                f"{[(ref.patch_id, ref.loop_index, ref.chain_index) for ref in chain_refs]}",
            )
            continue

        shared_vert_indices = set(seam.shared_vert_indices)
        endpoint_pairs_by_patch: dict[int, set[tuple[int, int]]] = {
            patch_a_id: set(),
            patch_b_id: set(),
        }

        for chain_ref in chain_refs:
            if (
                chain_ref.start_vert_index not in shared_vert_indices
                or chain_ref.end_vert_index not in shared_vert_indices
            ):
                _report_graph_topology_invariant_violation(
                    "X6",
                    f"chain_endpoint_outside_seam pair={pair_key} "
                    f"ref=P{chain_ref.patch_id}L{chain_ref.loop_index}C{chain_ref.chain_index} "
                    f"endpoints=({chain_ref.start_vert_index},{chain_ref.end_vert_index}) "
                    f"shared={sorted(shared_vert_indices)}",
                )

            endpoint_pairs_by_patch.setdefault(chain_ref.patch_id, set()).add(chain_ref.endpoint_pair)

        if not endpoint_pairs_by_patch.get(patch_a_id) or not endpoint_pairs_by_patch.get(patch_b_id):
            _report_graph_topology_invariant_violation(
                "X5",
                f"one_sided_patch_neighbor pair={pair_key} "
                f"counts=({len(endpoint_pairs_by_patch.get(patch_a_id, set()))},"
                f"{len(endpoint_pairs_by_patch.get(patch_b_id, set()))})",
            )
            continue

        if endpoint_pairs_by_patch[patch_a_id] != endpoint_pairs_by_patch[patch_b_id]:
            _report_graph_topology_invariant_violation(
                "X6",
                f"endpoint_pair_mismatch pair={pair_key} "
                f"a={sorted(endpoint_pairs_by_patch[patch_a_id])} "
                f"b={sorted(endpoint_pairs_by_patch[patch_b_id])}",
            )


def _begin_patch_topology_assembly(patch_id, patch_face_indices, bm):
    """Create one explicit patch assembly state before graph integration."""

    patch_type, world_facing, normal, area, perimeter = _classify_patch(bm, patch_face_indices)
    basis_u, basis_v = _build_patch_basis(bm, patch_face_indices, patch_type, normal)
    patch_faces = [bm.faces[idx] for idx in patch_face_indices]
    raw_loops = _trace_boundary_loops(patch_faces)
    centroid = _compute_centroid(bm, patch_face_indices)
    mesh_verts, mesh_vert_indices, mesh_edges, mesh_tris = _serialize_patch_geometry(bm, patch_face_indices)

    node = PatchNode(
        patch_id=patch_id,
        face_indices=list(patch_face_indices),
        centroid=centroid,
        normal=normal,
        area=area,
        perimeter=perimeter,
        patch_type=patch_type,
        world_facing=world_facing,
        basis_u=basis_u,
        basis_v=basis_v,
        boundary_loops=[],
        mesh_verts=mesh_verts,
        mesh_vert_indices=mesh_vert_indices,
        mesh_edges=mesh_edges,
        mesh_tris=mesh_tris,
    )
    return _PatchTopologyAssemblyState(
        patch_id=patch_id,
        node=node,
        raw_boundary_data=_RawPatchBoundaryData(
            face_indices=list(patch_face_indices),
            raw_loops=raw_loops,
            basis_u=basis_u.copy(),
            basis_v=basis_v.copy(),
        ),
    )


def _build_patch_topology_assembly_states(bm, patches_raw):
    """Build raw patch assembly states before classification / final serialization."""

    return [
        _begin_patch_topology_assembly(patch_id, patch_face_indices, bm)
        for patch_id, patch_face_indices in enumerate(patches_raw)
    ]


def _register_patch_topology_assembly_states(patch_graph, patch_states):
    """Register patch nodes early so face_to_patch exists before boundary serialization."""

    for patch_state in patch_states:
        patch_graph.add_node(patch_state.node)


def _classify_patch_topology_assembly_states(bm, patch_states, obj=None):
    """Run loop-kind classification and raw-boundary validation over assembly states."""

    raw_patch_data = {
        patch_state.patch_id: patch_state.raw_boundary_data
        for patch_state in patch_states
    }
    _classify_loops_outer_hole(bm, raw_patch_data, obj)

    for patch_state in patch_states:
        _validate_raw_patch_boundary_data(
            patch_state.patch_id,
            patch_state.raw_boundary_data,
            bm,
        )


def _finalize_patch_topology_assembly_states(patch_graph, patch_states, bm):
    """Finalize BoundaryLoop serialization for all already-registered patches."""

    for patch_state in patch_states:
        node = patch_state.node
        patch_data = patch_state.raw_boundary_data
        node.boundary_loops = _build_boundary_loops(
            patch_data.raw_loops,
            patch_data.face_indices,
            patch_graph.face_to_patch,
            patch_state.patch_id,
            node.basis_u,
            node.basis_v,
            bm,
        )
        _validate_patch_loop_classification(node)


def _compute_centroid(bm, face_indices):
    """Compute the patch centroid as an average over face vertices."""

    center = Vector((0.0, 0.0, 0.0))
    count = 0
    for face_idx in face_indices:
        face = bm.faces[face_idx]
        for vert in face.verts:
            center += vert.co
            count += 1
    return center / max(count, 1)


def _serialize_patch_geometry(bm, face_indices):
    """Serialize patch geometry into verts/tris for debug and reports."""

    vert_map = {}
    mesh_verts = []
    mesh_vert_indices = []
    mesh_edges = set()
    mesh_tris = []

    for face_idx in face_indices:
        face = bm.faces[face_idx]
        for edge in face.edges:
            a = int(edge.verts[0].index)
            b = int(edge.verts[1].index)
            if a != b:
                mesh_edges.add((min(a, b), max(a, b)))

        tri = []
        for vert in face.verts:
            if vert.index not in vert_map:
                vert_map[vert.index] = len(mesh_verts)
                mesh_verts.append(vert.co.copy())
                mesh_vert_indices.append(int(vert.index))
            tri.append(vert_map[vert.index])

        if len(tri) == 3:
            mesh_tris.append(tuple(tri))
            continue

        for tri_index in range(1, len(tri) - 1):
            mesh_tris.append((tri[0], tri[tri_index], tri[tri_index + 1]))

    return mesh_verts, mesh_vert_indices, sorted(mesh_edges), mesh_tris



def _build_seam_edges(face_to_patch, bm):
    """Build SeamEdge relations between neighboring patches."""

    seam_links = {}

    for edge in bm.edges:
        if not edge.seam:
            continue

        patch_ids = sorted({
            face_to_patch[face.index]
            for face in edge.link_faces
            if face.index in face_to_patch
        })
        if len(patch_ids) != 2:
            continue

        key = (patch_ids[0], patch_ids[1])
        edge_len = edge.calc_length()
        info = seam_links.setdefault(
            key,
            {
                "shared_length": 0.0,
                "shared_vert_indices": set(),
                "longest_edge_length": -1.0,
                "longest_edge_verts": (0, 0),
            },
        )
        info["shared_length"] += edge_len
        info["shared_vert_indices"].update(vert.index for vert in edge.verts)
        if edge_len > info["longest_edge_length"]:
            info["longest_edge_length"] = edge_len
            info["longest_edge_verts"] = (edge.verts[0].index, edge.verts[1].index)

    return [
        SeamEdge(
            patch_a_id=patch_a_id,
            patch_b_id=patch_b_id,
            shared_length=info["shared_length"],
            shared_vert_indices=sorted(info["shared_vert_indices"]),
            longest_edge_verts=info["longest_edge_verts"],
            longest_edge_length=info["longest_edge_length"],
        )
        for (patch_a_id, patch_b_id), info in seam_links.items()
    ]

def _compute_chain_dihedral_convexity(chain, owner_normal, neighbor_normal):
    """Вычисляет dihedral convexity для PATCH-neighbor chain.

    Использует chord chain как proxy направления seam edge.
    Возвращает: -1..+1 (negative=concave/inner, positive=convex/outer).
    """
    if len(chain.vert_cos) < 2:
        return 0.0

    edge_dir = chain.vert_cos[-1] - chain.vert_cos[0]
    if edge_dir.length_squared < 1e-12:
        return 0.0
    edge_dir = edge_dir.normalized()

    # cross(edge, owner_normal) даёт вектор "от поверхности owner patch"
    cross = edge_dir.cross(owner_normal)
    if cross.length_squared < 1e-12:
        return 0.0
    cross = cross.normalized()

    # dot с нормалью соседа:
    # positive → нормали расходятся → convex (внешний угол)
    # negative → нормали сходятся → concave (внутренний угол)
    dot = cross.dot(neighbor_normal)

    # Guard: слишком маленький сигнал → neutral
    if abs(dot) < 0.01:
        return 0.0
    return max(-1.0, min(1.0, dot))


def _assign_chain_dihedral_convexity(patch_graph):
    """Post-pass: вычисляет dihedral_convexity для всех PATCH-neighbor chains.

    Вызывается после полной сборки PatchGraph (nodes, loops, chains, seams).
    Не изменяет topology — только заполняет derived contextual field.
    """
    for patch_id, node in patch_graph.nodes.items():
        for boundary_loop in node.boundary_loops:
            for chain in boundary_loop.chains:
                if chain.neighbor_kind != ChainNeighborKind.PATCH:
                    continue
                neighbor_node = patch_graph.nodes.get(chain.neighbor_patch_id)
                if neighbor_node is None:
                    continue
                chain.dihedral_convexity = _compute_chain_dihedral_convexity(
                    chain, node.normal, neighbor_node.normal,
                )

def build_patch_graph(bm, face_indices, obj=None):
    """Build a PatchGraph from BMesh patch analysis."""

    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    patch_graph = PatchGraph()
    face_indices = _coerce_face_indices(bm, face_indices)
    if not face_indices:
        return patch_graph

    patches_raw = _flood_fill_patches(bm, face_indices)
    patch_states = _build_patch_topology_assembly_states(bm, patches_raw)
    _register_patch_topology_assembly_states(patch_graph, patch_states)

    # Ð•Ð´Ð¸Ð½ÑÑ‚Ð²ÐµÐ½Ð½Ñ‹Ð¹ Ð´Ð¾Ð¿ÑƒÑÑ‚Ð¸Ð¼Ñ‹Ð¹ side effect Ð²Ð½ÑƒÑ‚Ñ€Ð¸ analysis: Ð²Ñ€ÐµÐ¼ÐµÐ½Ð½Ñ‹Ð¹ UV unwrap
    # Ð´Ð»Ñ Ð¾Ð¿Ñ€ÐµÐ´ÐµÐ»ÐµÐ½Ð¸Ñ OUTER/HOLE Ñƒ multi-loop boundary.
    _classify_patch_topology_assembly_states(bm, patch_states, obj)
    _finalize_patch_topology_assembly_states(patch_graph, patch_states, bm)
    patch_graph.rebuild_chain_use_index()

    for seam_edge in _build_seam_edges(patch_graph.face_to_patch, bm):
        patch_graph.add_edge(seam_edge)
    _validate_patch_graph_seam_consistency(patch_graph)
    _assign_chain_dihedral_convexity(patch_graph)

    return patch_graph


