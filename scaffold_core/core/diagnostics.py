"""
Layer: core diagnostics

Rules:
- Cross-cutting diagnostic data models only.
- No layer-specific validation logic here.
- No imports from layer packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class DiagnosticSeverity(str, Enum):
    """Pipeline diagnostic severity."""

    BLOCKING = "BLOCKING"
    DEGRADED = "DEGRADED"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class Diagnostic:
    """Structured diagnostic emitted by builders, validators and pipeline passes."""

    code: str
    severity: DiagnosticSeverity
    message: str
    source: str
    entity_ids: Sequence[str] = field(default_factory=tuple)
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiagnosticReport:
    """Immutable collection of diagnostics."""

    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def has_blocking(self) -> bool:
        return any(d.severity is DiagnosticSeverity.BLOCKING for d in self.diagnostics)

    def extend(self, diagnostics: Sequence[Diagnostic]) -> "DiagnosticReport":
        return DiagnosticReport(self.diagnostics + tuple(diagnostics))
