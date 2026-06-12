"""
Transport-consistent unfolded frame view for tracer spike v3.

This module is disposable consumer tooling outside scaffold_core. It computes
island-local axis roles from Pass 1 evidence without storing roles in core.
"""

from __future__ import annotations

from collections import defaultdict, deque
from math import cos, sin, sqrt
from typing import Any

from scaffold_core.layer_2_geometry.measures import cross, dot, length, normalize


AXIS_CLASS_MIN_COS = 0.92
AXIS_ROLE_TIE_EPSILON = 1.0e-6


def build_unfolded_frame_view(context: Any, islands: list[dict[str, Any]], stitch_decisions):
    relations = context.relation_snapshot
    topology = context.topology_snapshot
    geometry = context.geometry_facts
    evidence_by_id = {item.id: item for item in relations.patch_chain_directional_evidence}
    island_by_patch_id = {
        patch_id: island["id"]
        for island in islands
        for patch_id in island["patch_ids"]
    }
    frame_state = _patch_frame_state(islands, stitch_decisions, relations, geometry, evidence_by_id)
    ambiguities: list[str] = []
    axis_roles_by_island = {}
    family_axis_roles = {}
    evidence_axes = {}

    for island in islands:
        island_id = island["id"]
        patch_ids = set(island["patch_ids"])
        family_rows = _family_rows(topology, geometry, relations, evidence_by_id, frame_state, island_id, patch_ids)
        axis_a = _select_axis_a(island_id, family_rows, ambiguities)
        axis_b = _select_axis_b(island_id, family_rows, axis_a, ambiguities)
        axis_context = {"axis_a": axis_a, "axis_b": axis_b}
        classified_rows = []
        for row in family_rows:
            role = _axis_role_for_direction(row["direction_2d"], axis_context)
            family_axis_roles[(island_id, row["family_id"])] = role
            dot_a = _axis_dot(row["direction_2d"], axis_a)
            dot_b = _axis_dot(row["direction_2d"], axis_b)
            if (
                axis_a is not None
                and axis_b is not None
                and max(dot_a, dot_b) >= AXIS_CLASS_MIN_COS
                and abs(dot_a - dot_b) <= AXIS_ROLE_TIE_EPSILON
            ):
                ambiguities.append(
                    f"{island_id} {row['family_id']}: tied AXIS_A/AXIS_B projection; picked {role}"
                )
            classified_rows.append({
                "family_id": row["family_id"],
                "role": role,
                "length": round(row["length"], 6),
                "direction_2d": _round2(row["direction_2d"]),
                "dot_axis_a": round(dot_a, 6) if axis_a is not None else None,
                "dot_axis_b": round(dot_b, 6) if axis_b is not None else None,
                "member_count": row["member_count"],
                "patch_ids": row["patch_ids"],
            })

        axis_roles_by_island[island_id] = {
            "axis_a": _axis_record(axis_a),
            "axis_b": _axis_record(axis_b),
            "families": classified_rows,
            "ambiguities": [
                ambiguity
                for ambiguity in ambiguities
                if ambiguity.startswith(f"{island_id} ")
            ],
            "patch_frames": frame_state["report"]["islands"].get(island_id, {}),
        }

    for evidence in sorted(evidence_by_id.values(), key=lambda item: item.id):
        island_id = island_by_patch_id.get(str(evidence.patch_id))
        if island_id is None:
            continue
        direction_2d = _classification_direction_2d(evidence, frame_state, island_id)
        sign_direction_2d = _endpoint_direction_2d(evidence, topology, geometry, frame_state, island_id)
        if _length2(sign_direction_2d) == 0.0:
            sign_direction_2d = direction_2d
        role = _axis_role_for_direction(direction_2d, axis_roles_by_island.get(island_id, {}))
        axis = _axis_direction(axis_roles_by_island.get(island_id, {}), role)
        evidence_axes[evidence.id] = {
            "axis_role": role,
            "direction_2d": _round2(direction_2d),
            "sign_direction_2d": _round2(sign_direction_2d),
            "orientation_sign": _orientation_sign(sign_direction_2d, axis, evidence.orientation_sign),
            "patch_chain_id": str(evidence.patch_chain_id),
            "chain_id": str(evidence.parent_chain_id),
            "patch_id": str(evidence.patch_id),
        }

    return {
        "axis_roles_by_island": axis_roles_by_island,
        "family_axis_roles": family_axis_roles,
        "evidence_axes": evidence_axes,
        "ambiguities": ambiguities,
        "report": {
            **frame_state["report"],
            "axis_class_min_cos": AXIS_CLASS_MIN_COS,
            "oblique_evidence_count": sum(
                1 for row in evidence_axes.values() if row["axis_role"] == "OBLIQUE"
            ),
            "l5_contract_input_count": len(frame_state["report"]["l5_contract_inputs"]),
        },
    }


def role_for_member_ids(member_ids, evidence_by_id, frame_view, island_id):
    directions = []
    for member_id in member_ids:
        row = frame_view["evidence_axes"].get(member_id)
        evidence = evidence_by_id.get(member_id)
        if row is None or evidence is None:
            continue
        directions.append((tuple(row["direction_2d"]), evidence.length))
    direction = _weighted_direction_2d(directions)
    return _axis_role_for_direction(
        direction,
        frame_view["axis_roles_by_island"].get(island_id, {}),
    )


def _patch_frame_state(islands, stitch_decisions, relations, geometry, evidence_by_id):
    accepted_by_patch = defaultdict(list)
    for decision in stitch_decisions:
        if not decision.get("accepted"):
            continue
        accepted_by_patch[decision["from_patch_id"]].append(decision)
        accepted_by_patch[decision["to_patch_id"]].append(decision)

    crossing_records = _crossing_records(relations)
    report = {"islands": {}, "l5_contract_inputs": []}
    state = {"frames": {}, "root_axes": {}, "report": report}
    for island in islands:
        island_id = island["id"]
        seed_patch_id = island["seed_patch_id"]
        root_u = _seed_axis(seed_patch_id, evidence_by_id)
        normal = _patch_normal(seed_patch_id, geometry)
        root_v = normalize(cross(normal, root_u))
        if length(root_v) == 0.0:
            root_v = _fallback_perpendicular(root_u)
        state["root_axes"][island_id] = {"u": root_u, "v": root_v}
        state["frames"][(island_id, seed_patch_id)] = _identity_matrix()
        patch_report = {
            seed_patch_id: {"parent_patch_id": None, "signed_dihedral_radians": 0.0}
        }
        queue = deque([seed_patch_id])
        island_patch_ids = set(island["patch_ids"])
        while queue:
            parent = queue.popleft()
            for decision in sorted(accepted_by_patch[parent], key=lambda item: item["patch_adjacency_id"]):
                child = decision["to_patch_id"] if decision["from_patch_id"] == parent else decision["from_patch_id"]
                if child not in island_patch_ids or (island_id, child) in state["frames"]:
                    continue
                angle, source = _transport_angle_to_parent(
                    parent,
                    child,
                    decision,
                    crossing_records,
                    report["l5_contract_inputs"],
                )
                axis = _chain_axis(decision["chain_id"], geometry)
                local_rotation = _rotation_matrix(axis, angle)
                state["frames"][(island_id, child)] = _matmul(
                    state["frames"][(island_id, parent)],
                    local_rotation,
                )
                patch_report[child] = {
                    "parent_patch_id": parent,
                    "patch_adjacency_id": decision["patch_adjacency_id"],
                    "chain_id": decision["chain_id"],
                    "signed_dihedral_radians": round(angle, 12),
                    "signed_dihedral_source": source,
                }
                queue.append(child)
        for patch_id in sorted(island_patch_ids):
            if (island_id, patch_id) in state["frames"]:
                continue
            state["frames"][(island_id, patch_id)] = _identity_matrix()
            patch_report[patch_id] = {
                "parent_patch_id": None,
                "signed_dihedral_radians": 0.0,
                "signed_dihedral_source": "L5_CONTRACT_INPUTS: missing accepted stitch tree parent",
            }
            report["l5_contract_inputs"].append(
                f"{island_id} {patch_id}: no accepted stitch-tree parent; identity frame fallback"
            )
        report["islands"][island_id] = patch_report
    return state


def _crossing_records(relations):
    rows = defaultdict(list)
    for family in relations.connected_direction_families:
        for record in family.crossing_records:
            if record.patch_adjacency_id is None:
                continue
            rows[str(record.patch_adjacency_id)].append(record)
    for key in rows:
        rows[key].sort(key=lambda item: (-item.confidence, item.kind, item.first_directional_evidence_id))
    return rows


def _transport_angle_to_parent(parent, child, decision, crossing_records, l5_inputs):
    for record in crossing_records.get(decision["patch_adjacency_id"], ()):
        first = str(record.first_patch_id)
        second = str(record.second_patch_id)
        if first == child and second == parent:
            return float(record.signed_dihedral_radians), record.kind
        if first == parent and second == child:
            return -float(record.signed_dihedral_radians), record.kind
    l5_inputs.append(
        f"{decision['patch_adjacency_id']}: no crossing-record dihedral for {parent}->{child}; used 0"
    )
    return 0.0, "L5_CONTRACT_INPUTS: missing crossing-record dihedral"


def _family_rows(topology, geometry, relations, evidence_by_id, frame_state, island_id, patch_ids):
    rows = []
    for family in sorted(relations.connected_direction_families, key=lambda item: item.id):
        directions = []
        patch_id_rows = set()
        for member_id in family.member_directional_evidence_ids:
            evidence = evidence_by_id[member_id]
            if str(evidence.patch_id) not in patch_ids:
                continue
            directions.append((
                _classification_direction_2d(evidence, frame_state, island_id),
                evidence.length,
            ))
            patch_id_rows.add(str(evidence.patch_id))
        if not directions:
            continue
        rows.append({
            "family_id": family.id,
            "length": sum(weight for _direction, weight in directions),
            "direction_2d": _weighted_direction_2d(directions),
            "member_count": len(directions),
            "patch_ids": sorted(patch_id_rows),
        })
    return rows


def _classification_direction_2d(evidence, frame_state, island_id):
    return _direction_2d(evidence.direction, evidence.patch_id, frame_state, island_id)


def _endpoint_direction_2d(evidence, topology, geometry, frame_state, island_id):
    endpoint_delta = _patch_chain_endpoint_delta(evidence, topology, geometry)
    return _direction_2d(endpoint_delta, evidence.patch_id, frame_state, island_id)


def _direction_2d(direction, patch_id, frame_state, island_id):
    frame = frame_state["frames"][(island_id, str(patch_id))]
    transformed = _matvec(frame, direction)
    axes = frame_state["root_axes"][island_id]
    return _normalize2((dot(transformed, axes["u"]), dot(transformed, axes["v"])))


def _patch_chain_endpoint_delta(evidence, topology, geometry):
    patch_chain = topology.patch_chains.get(evidence.patch_chain_id)
    if patch_chain is None or patch_chain.start_vertex_id is None or patch_chain.end_vertex_id is None:
        return (0.0, 0.0, 0.0)
    start = geometry.vertex_facts.get(patch_chain.start_vertex_id)
    end = geometry.vertex_facts.get(patch_chain.end_vertex_id)
    if start is None or end is None:
        return (0.0, 0.0, 0.0)
    return (
        end.position[0] - start.position[0],
        end.position[1] - start.position[1],
        end.position[2] - start.position[2],
    )


def _select_axis_a(island_id, family_rows, ambiguities):
    if not family_rows:
        return None
    rows = sorted(family_rows, key=lambda row: (-row["length"], row["family_id"]))
    top = rows[0]
    tied = [row["family_id"] for row in rows if abs(row["length"] - top["length"]) <= AXIS_ROLE_TIE_EPSILON]
    if len(tied) > 1:
        ambiguities.append(f"{island_id}: AXIS_A family length tie {tied}; picked {top['family_id']}")
    return {"family_id": top["family_id"], "direction": top["direction_2d"], "length": top["length"]}


def _select_axis_b(island_id, family_rows, axis_a, ambiguities):
    if axis_a is None:
        return None
    candidates = [row for row in family_rows if row["family_id"] != axis_a["family_id"]]
    if not candidates:
        return None
    scored = []
    for row in candidates:
        orthogonality = 1.0 - abs(_dot2(row["direction_2d"], axis_a["direction"]))
        scored.append((orthogonality, row["length"], row))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]["family_id"]))
    top_orthogonality, top_length, top = scored[0]
    tied = [
        row["family_id"]
        for orthogonality, row_length, row in scored
        if abs(orthogonality - top_orthogonality) <= AXIS_ROLE_TIE_EPSILON
        and abs(row_length - top_length) <= AXIS_ROLE_TIE_EPSILON
    ]
    if len(tied) > 1:
        ambiguities.append(
            f"{island_id}: AXIS_B orthogonality/length tie {tied}; picked {top['family_id']}"
        )
    return {
        "family_id": top["family_id"],
        "direction": top["direction_2d"],
        "length": top["length"],
        "orthogonality_score": top_orthogonality,
    }


def _axis_role_for_direction(direction, axis_context):
    axis_a = axis_context.get("axis_a")
    axis_b = axis_context.get("axis_b")
    dot_a = _axis_dot(direction, axis_a)
    dot_b = _axis_dot(direction, axis_b)
    if dot_a < AXIS_CLASS_MIN_COS and dot_b < AXIS_CLASS_MIN_COS:
        return "OBLIQUE"
    if dot_a >= dot_b:
        return "AXIS_A"
    return "AXIS_B"


def _axis_dot(direction, axis):
    if axis is None:
        return 0.0
    return abs(_dot2(_normalize2(direction), _normalize2(axis["direction"])))


def _axis_direction(axis_context, role):
    if role == "AXIS_A" and axis_context.get("axis_a") is not None:
        return tuple(axis_context["axis_a"]["direction"])
    if role == "AXIS_B" and axis_context.get("axis_b") is not None:
        return tuple(axis_context["axis_b"]["direction"])
    return None


def _axis_record(axis):
    if axis is None:
        return None
    record = {
        "seed_family_id": axis["family_id"],
        "direction": _round2(axis["direction"]),
        "length": round(axis["length"], 6),
    }
    if "orthogonality_score" in axis:
        record["orthogonality_score"] = round(axis["orthogonality_score"], 6)
    return record


def _orientation_sign(direction_2d, axis, fallback):
    if axis is None:
        return int(fallback)
    return 1 if _dot2(_normalize2(direction_2d), _normalize2(axis)) >= 0.0 else -1


def _weighted_direction_2d(weighted_directions):
    rows = [(direction, weight) for direction, weight in weighted_directions if _length2(direction) > 0.0]
    if not rows:
        return (0.0, 0.0)
    seed = max(rows, key=lambda item: (item[1], item[0]))[0]
    total = [0.0, 0.0]
    for direction, weight in rows:
        direction = _normalize2(direction)
        if _dot2(direction, seed) < 0.0:
            direction = (-direction[0], -direction[1])
        total[0] += direction[0] * weight
        total[1] += direction[1] * weight
    return _normalize2(tuple(total))


def _seed_axis(seed_patch_id, evidence_by_id):
    candidates = [
        evidence for evidence in evidence_by_id.values()
        if str(evidence.patch_id) == seed_patch_id and length(evidence.direction) > 0.0
    ]
    if not candidates:
        return (1.0, 0.0, 0.0)
    return normalize(max(candidates, key=lambda item: (item.length, item.id)).direction)


def _patch_normal(patch_id, geometry):
    for key, facts in geometry.patch_facts.items():
        if str(key) == patch_id and length(facts.normal) > 0.0:
            return normalize(facts.normal)
    return (0.0, 0.0, 1.0)


def _chain_axis(chain_id, geometry):
    for key, facts in geometry.chain_facts.items():
        if str(key) == chain_id and length(facts.chord_direction) > 0.0:
            return normalize(facts.chord_direction)
    return (1.0, 0.0, 0.0)


def _fallback_perpendicular(axis):
    candidate = cross(axis, (0.0, 0.0, 1.0))
    if length(candidate) == 0.0:
        candidate = cross(axis, (0.0, 1.0, 0.0))
    return normalize(candidate) if length(candidate) > 0.0 else (0.0, 1.0, 0.0)


def _rotation_matrix(axis, angle):
    axis = normalize(axis)
    if length(axis) == 0.0:
        return _identity_matrix()
    x, y, z = axis
    c = cos(angle)
    s = sin(angle)
    t = 1.0 - c
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )


def _identity_matrix():
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _matmul(left, right):
    return tuple(
        tuple(sum(left[row][k] * right[k][col] for k in range(3)) for col in range(3))
        for row in range(3)
    )


def _matvec(matrix, vector):
    return tuple(sum(matrix[row][col] * vector[col] for col in range(3)) for row in range(3))


def _dot2(first, second):
    return first[0] * second[0] + first[1] * second[1]


def _length2(vector):
    return sqrt(vector[0] * vector[0] + vector[1] * vector[1])


def _normalize2(vector):
    size = _length2(vector)
    if size == 0.0:
        return (0.0, 0.0)
    return (vector[0] / size, vector[1] / size)


def _round2(vector):
    return [round(float(vector[0]), 6), round(float(vector[1]), 6)]
