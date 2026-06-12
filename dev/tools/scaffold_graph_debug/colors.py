"""Stable color helpers for ScaffoldGraph debug overlays."""

from __future__ import annotations

import colorsys
import hashlib


NEUTRAL_GRAY = (0.58, 0.58, 0.58, 1.0)
SPINE_COLOR = (0.05, 0.78, 1.0, 1.0)
PARALLEL_RAIL_COLOR = (0.2, 0.9, 1.0, 1.0)
RIB_COLOR = (1.0, 0.62, 0.08, 1.0)
BRANCH_COLOR = (1.0, 0.9, 0.05, 1.0)
SEWABLE_SEAM_COLOR = (0.15, 0.9, 0.28, 1.0)
CUT_SEAM_COLOR = (1.0, 0.08, 0.08, 1.0)
SCAFFOLD_NODE_COLOR = (1.0, 0.95, 0.22, 1.0)
RUN_ENDPOINT_JUNCTION_COLOR = (0.95, 0.35, 1.0, 1.0)


def stable_color(identifier: str, *, saturation: float = 0.7, value: float = 0.95) -> tuple[float, float, float, float]:
    """Return a deterministic pseudo-random color for an id."""

    digest = hashlib.sha256(identifier.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return (red, green, blue, 1.0)


def material_key(identifier: str) -> str:
    """Return a Blender-safe material suffix."""

    return "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in identifier) or "unnamed"
