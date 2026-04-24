"""
Layer: tests

Rules:
- Layer 2 semantic leakage guard only.
- Tests may inspect source files but must not define production logic.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYER_2_ROOT = ROOT / "layer_2_geometry"
FORBIDDEN_TOKENS = (
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "AlignmentClass",
    "PatchAxes",
    "WorldOrientation",
    "DihedralKind",
    "Feature",
    "Pin",
    "UV",
)


def test_layer_2_geometry_does_not_contain_semantic_role_tokens() -> None:
    violations: list[str] = []
    for path in LAYER_2_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                violations.append(f"{path.relative_to(ROOT)} contains {token}")

    assert not violations
