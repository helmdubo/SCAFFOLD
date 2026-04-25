"""
Layer: tests

Rules:
- Documentation-only pending tests.
- Skipped intentionally to mark deferred geometric disk-cycle ordering.
- No production logic here.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="G3b1 does deterministic incidence only; geometric disk-cycle ordering is deferred."
)
def test_junction_disk_cycle_ordering_is_unresolved() -> None:
    """G3b1 order is deterministic, not geometric.

    Disk-cycle ordering requires Layer 2 geometry policy and should be
    implemented later. Remove this skip when that policy and implementation
    exist.
    """
