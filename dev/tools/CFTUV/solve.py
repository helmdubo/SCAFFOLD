"""CFTUV Solve - public API facade.

All heavy logic lives in solve_* sibling modules.
This file re-exports the interface used by operators.py.
"""

from __future__ import annotations

try:
    from .solve_planning import (
        build_solver_graph,
        plan_solve_phase1,
    )
    from .solve_frontier import (
        build_root_scaffold_map,
    )
    from .solve_transfer import (
        execute_phase1_preview,
        execute_phase1_transfer_only,
        validate_scaffold_uv_transfer,
    )
    from .solve_skeleton import (
        apply_skeleton_solve,
        apply_skeleton_solve_to_scaffold_map,
    )
    from .solve_reporting import (
        format_root_scaffold_report,
        format_regression_snapshot_report,
        format_solve_plan_report,
    )
except ImportError:
    from solve_planning import (
        build_solver_graph,
        plan_solve_phase1,
    )
    from solve_frontier import (
        build_root_scaffold_map,
    )
    from solve_transfer import (
        execute_phase1_preview,
        execute_phase1_transfer_only,
        validate_scaffold_uv_transfer,
    )
    from solve_skeleton import (
        apply_skeleton_solve,
        apply_skeleton_solve_to_scaffold_map,
    )
    from solve_reporting import (
        format_root_scaffold_report,
        format_regression_snapshot_report,
        format_solve_plan_report,
    )


__all__ = [
    "build_solver_graph",
    "plan_solve_phase1",
    "build_root_scaffold_map",
    "execute_phase1_preview",
    "execute_phase1_transfer_only",
    "validate_scaffold_uv_transfer",
    "apply_skeleton_solve",
    "apply_skeleton_solve_to_scaffold_map",
    "format_root_scaffold_report",
    "format_regression_snapshot_report",
    "format_solve_plan_report",
]
