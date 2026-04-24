"""
Layer: core evidence

Rules:
- Cross-cutting evidence data models only.
- No layer-specific scoring or validation logic here.
- No imports from layer packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Evidence:
    """Structured evidence for derived facts, diagnostics and later rules."""

    source: str
    summary: str
    data: Mapping[str, Any] = field(default_factory=dict)
