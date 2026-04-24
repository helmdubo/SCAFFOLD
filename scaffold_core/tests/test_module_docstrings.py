"""
Layer: tests

Rules:
- Architectural module docstring test only.
- No production logic here.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*.py")
        if path.name != "__init__.py" and "tests" not in path.relative_to(ROOT).parts
    ]


def test_modules_declare_layer_and_rules() -> None:
    missing: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstring = ast.get_docstring(tree) or ""
        if "Layer:" not in docstring or "Rules:" not in docstring:
            missing.append(str(path.relative_to(ROOT)))
    assert not missing
