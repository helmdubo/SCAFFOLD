"""
Layer: 1 — Topology

Rules:
- Validate Layer 1 topology invariants only.
- Do not fix invalid topology here.
- Do not compute geometry facts, relations, features, or runtime solve.
"""

from __future__ import annotations

from collections import defaultdict

from scaffold_core.core.diagnostics import Diagnostic, DiagnosticSeverity
from scaffold_core.ids import ChainId
from scaffold_core.layer_1_topology.model import BoundaryLoopKind, SurfaceModel
from scaffold_core.layer_1_topology.queries import chain_use_vertices


def validate_topology(model: SurfaceModel) -> tuple[Diagnostic, ...]:
    """Validate core Layer 1 invariants."""

    diagnostics: list[Diagnostic] = []
    diagnostics.extend(validate_loop_closure(model))
    diagnostics.extend(validate_chain_cardinality(model))
    diagnostics.extend(validate_patch_outer_loops(model))
    return tuple(diagnostics)


def validate_loop_closure(model: SurfaceModel) -> tuple[Diagnostic, ...]:
    """Validate that ChainUses in every loop form a closed oriented cycle."""

    diagnostics: list[Diagnostic] = []
    for loop in model.loops.values():
        if not loop.chain_use_ids:
            diagnostics.append(
                Diagnostic(
                    code="TOPOLOGY_LOOP_EMPTY",
                    severity=DiagnosticSeverity.BLOCKING,
                    message="BoundaryLoop has no ChainUses.",
                    source="layer_1_topology.invariants.validate_loop_closure",
                    entity_ids=(str(loop.id),),
                )
            )
            continue

        for index, use_id in enumerate(loop.chain_use_ids):
            next_use_id = loop.chain_use_ids[(index + 1) % len(loop.chain_use_ids)]
            _start, end = chain_use_vertices(model, use_id)
            next_start, _next_end = chain_use_vertices(model, next_use_id)
            if end != next_start:
                diagnostics.append(
                    Diagnostic(
                        code="TOPOLOGY_LOOP_NOT_CLOSED",
                        severity=DiagnosticSeverity.BLOCKING,
                        message="BoundaryLoop ChainUses do not form a closed oriented cycle.",
                        source="layer_1_topology.invariants.validate_loop_closure",
                        entity_ids=(str(loop.id), str(use_id), str(next_use_id)),
                        evidence={"end_vertex": str(end), "next_start_vertex": str(next_start)},
                    )
                )
    return tuple(diagnostics)


def validate_chain_cardinality(model: SurfaceModel) -> tuple[Diagnostic, ...]:
    """Validate and classify ChainUse cardinality cases."""

    diagnostics: list[Diagnostic] = []
    uses_by_chain: dict[ChainId, list[str]] = defaultdict(list)
    patches_by_chain: dict[ChainId, list[str]] = defaultdict(list)

    for use in model.chain_uses.values():
        uses_by_chain[use.chain_id].append(str(use.id))
        patches_by_chain[use.chain_id].append(str(use.patch_id))

    for chain_id in model.chains:
        use_ids = uses_by_chain.get(chain_id, [])
        patch_ids = patches_by_chain.get(chain_id, [])
        use_count = len(use_ids)
        unique_patch_count = len(set(patch_ids))

        if use_count == 0:
            diagnostics.append(
                Diagnostic(
                    code="TOPOLOGY_CHAIN_UNUSED",
                    severity=DiagnosticSeverity.DEGRADED,
                    message="Chain has no ChainUses.",
                    source="layer_1_topology.invariants.validate_chain_cardinality",
                    entity_ids=(str(chain_id),),
                )
            )
        elif use_count == 1:
            diagnostics.append(
                Diagnostic(
                    code="TOPOLOGY_CHAIN_BORDER",
                    severity=DiagnosticSeverity.INFO,
                    message="Chain is a mesh/selection border.",
                    source="layer_1_topology.invariants.validate_chain_cardinality",
                    entity_ids=(str(chain_id), *use_ids),
                )
            )
        elif use_count == 2 and unique_patch_count == 1:
            diagnostics.append(
                Diagnostic(
                    code="TOPOLOGY_CHAIN_SEAM_SELF",
                    severity=DiagnosticSeverity.INFO,
                    message="Chain has two uses in the same Patch: SEAM_SELF.",
                    source="layer_1_topology.invariants.validate_chain_cardinality",
                    entity_ids=(str(chain_id), *use_ids),
                )
            )
        elif use_count == 2 and unique_patch_count == 2:
            diagnostics.append(
                Diagnostic(
                    code="TOPOLOGY_CHAIN_SHARED",
                    severity=DiagnosticSeverity.INFO,
                    message="Chain is shared by two different Patches.",
                    source="layer_1_topology.invariants.validate_chain_cardinality",
                    entity_ids=(str(chain_id), *use_ids),
                )
            )
        elif use_count > 2:
            diagnostics.append(
                Diagnostic(
                    code="TOPOLOGY_CHAIN_NON_MANIFOLD",
                    severity=DiagnosticSeverity.DEGRADED,
                    message="Chain has more than two ChainUses.",
                    source="layer_1_topology.invariants.validate_chain_cardinality",
                    entity_ids=(str(chain_id), *use_ids),
                    evidence={"use_count": use_count},
                )
            )
    return tuple(diagnostics)


def validate_patch_outer_loops(model: SurfaceModel) -> tuple[Diagnostic, ...]:
    """Validate that every Patch has exactly one outer loop where possible."""

    diagnostics: list[Diagnostic] = []
    for patch in model.patches.values():
        outer_loops = [
            model.loops[loop_id]
            for loop_id in patch.loop_ids
            if model.loops[loop_id].kind is BoundaryLoopKind.OUTER
        ]
        if len(outer_loops) != 1:
            diagnostics.append(
                Diagnostic(
                    code="TOPOLOGY_PATCH_OUTER_LOOP_COUNT",
                    severity=DiagnosticSeverity.BLOCKING,
                    message="Patch should have exactly one outer loop.",
                    source="layer_1_topology.invariants.validate_patch_outer_loops",
                    entity_ids=(str(patch.id),),
                    evidence={"outer_loop_count": len(outer_loops)},
                )
            )
    return tuple(diagnostics)
