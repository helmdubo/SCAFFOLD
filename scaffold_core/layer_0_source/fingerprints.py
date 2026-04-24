"""
Layer: 0 — Source

Rules:
- Structural fingerprint helpers only.
- No topology entities, geometry facts, relations, features, or runtime solve here.
- Fingerprints support override reassociation; they are not persistent CAD naming.
"""

from __future__ import annotations

from hashlib import sha1
from typing import Iterable


def make_structural_fingerprint(parts: Iterable[object]) -> str:
    """Return a deterministic lightweight fingerprint for source/provenance data."""

    payload = "|".join(str(part) for part in parts)
    return sha1(payload.encode("utf-8")).hexdigest()
