"""
Layer: 0 — Source

Rules:
- User override data models only.
- Overrides are inputs, not mutations.
- No topology entities, geometry facts, relations, features, or runtime solve here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class UserOverrideKind(str, Enum):
    """High-level user override categories."""

    SOURCE = "SOURCE"
    CLASSIFIER = "CLASSIFIER"
    FEATURE = "FEATURE"
    RUNTIME = "RUNTIME"


@dataclass(frozen=True)
class UserOverride:
    """A user-authored override addressed by structural fingerprint."""

    kind: UserOverrideKind
    target_fingerprint: str
    payload: Mapping[str, Any]
