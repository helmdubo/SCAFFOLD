"""
Layer: tests

Rules:
- Layer 3 semantic leakage guard only.
- Tests may inspect source files but must not define production logic.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYER_3_ROOT = ROOT / "layer_3_relations"
FORBIDDEN_TOKENS = frozenset({
    "H_FRAME",
    "V_FRAME",
    "WALL",
    "FLOOR",
    "SLOPE",
    "AlignmentClass",
    "PatchAxes",
    "WorldOrientation",
    "WORLD_UP",
    "ChainContinuationRelation",
    "Junction",
    "Feature",
    "Pin",
    "UV",
})


def _identifiers(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[-1])
            if node.asname:
                names.add(node.asname)
    return names


def test_layer_3_relations_does_not_contain_semantic_role_tokens() -> None:
    violations: list[str] = []
    for path in LAYER_3_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        leaked = _identifiers(tree) & FORBIDDEN_TOKENS
        for token in sorted(leaked):
            violations.append(f"{path.relative_to(ROOT)} uses {token}")

    assert not violations
