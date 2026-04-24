"""
Layer: pipeline

Rules:
- Cross-pass validation orchestration only.
- May inspect PipelineContext and diagnostics.
- Do not implement layer-specific invariant logic here.
"""

from __future__ import annotations

from scaffold_core.pipeline.context import PipelineContext


def assert_no_blocking_diagnostics(context: PipelineContext) -> None:
    """Raise if the current pipeline context contains blocking diagnostics."""

    if context.diagnostics.has_blocking:
        messages = "; ".join(d.message for d in context.diagnostics.diagnostics)
        raise ValueError(f"Blocking diagnostics present: {messages}")
