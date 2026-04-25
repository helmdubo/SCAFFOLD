"""
Layer: tests

Rules:
- Documentation-only pending tests.
- Skipped intentionally to mark unresolved OQ-11 cases for the future
  AlignmentClass agent.
- These tests do not assert a specific resolution of OQ-11.
- No production logic here.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="DD-29 / DD-30 / OQ-11: closed-Chain handling for AlignmentClass is unresolved."
)
def test_closed_seam_loop_chain_handling_is_unresolved() -> None:
    """G3a coalesces a closed shared seam loop into one Chain with
    start_vertex_id == end_vertex_id and no stable chord direction.

    See `test_chain_coalescing.test_closed_seam_loop_coalesces_to_one_shared_chain`
    for the current G3a behavior. That behavior is correct for PatchAdjacency.

    OQ-11 must decide how AlignmentClass treats such Chains. Possible
    resolutions include geometry-based refinement, exclusion from direction
    clustering, marking as direction-unstable, or another mechanism.

    Remove this skip when OQ-11 is resolved and the chosen handling is
    implemented and tested in G3c.
    """


@pytest.mark.skip(
    reason="DD-29 / DD-30 / OQ-11: turning-Chain handling for AlignmentClass is unresolved."
)
def test_turning_chain_handling_is_unresolved() -> None:
    """G3a may coalesce a multi-corner shared boundary into one Chain that
    crosses significant direction changes.

    That behavior is correct for PatchAdjacency. It is not yet decided how
    AlignmentClass should treat such Chains.

    OQ-11 must specify the policy. Remove this skip when the resolution is
    implemented and tested in G3c.
    """


@pytest.mark.skip(
    reason="DD-29 / DD-30 / OQ-11: direction-ambiguous Chain handling for AlignmentClass is unresolved."
)
def test_direction_ambiguous_chain_handling_is_unresolved() -> None:
    """G3a Chains can have shape_hint = UNKNOWN in Layer 2 because they have
    no stable chord direction.

    Layer 2 may expose that signal. It is not yet decided how
    AlignmentClass consumes it: skip the Chain, refine it into stable
    sub-segments, defer to user override, or another approach.

    OQ-11 must specify the policy. Remove this skip when the resolution is
    implemented and tested in G3c.
    """
