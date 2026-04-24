"""
Layer: tests

Rules:
- Architectural import boundary test only.
- No production logic here.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FUTURE_DIRS_G1 = {
    "layer_2_geometry",
    "layer_3_relations",
    "layer_4_features",
    "layer_5_runtime",
    "api",
    "ui",
}

FORBIDDEN_MODULE_NAMES = {
    "utils",
    "helpers",
    "common",
    "manager",
    "factory",
    "service",
    "base",
    "framework",
    "registry",
}

LAYER_BY_PACKAGE = {
    "layer_0_source": 0,
    "layer_1_topology": 1,
    "layer_2_geometry": 2,
    "layer_3_relations": 3,
    "layer_4_features": 4,
    "layer_5_runtime": 5,
}


def _source_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*.py")
        if "tests" not in path.relative_to(ROOT).parts
    ]


def _module_parts_from_file(path: Path) -> tuple[str, ...]:
    return path.relative_to(ROOT).with_suffix("").parts


def _import_roots(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _layer_index(parts: tuple[str, ...]) -> int | None:
    for part in parts:
        if part in LAYER_BY_PACKAGE:
            return LAYER_BY_PACKAGE[part]
    return None


def test_g1_future_phase_directories_do_not_exist() -> None:
    existing = {path.name for path in ROOT.iterdir() if path.is_dir()}
    assert not (existing & FUTURE_DIRS_G1)


def test_forbidden_generic_module_names_do_not_exist() -> None:
    bad_files = [path for path in ROOT.rglob("*.py") if path.stem in FORBIDDEN_MODULE_NAMES]
    assert not bad_files


def test_layers_do_not_import_higher_layers() -> None:
    violations: list[str] = []
    for path in _source_files():
        source_layer = _layer_index(_module_parts_from_file(path))
        if source_layer is None:
            continue
        for imported in _import_roots(path):
            parts = tuple(imported.split("."))
            if parts and parts[0] == "scaffold_core":
                parts = parts[1:]
            target_layer = _layer_index(parts)
            if target_layer is not None and target_layer > source_layer:
                violations.append(f"{path.relative_to(ROOT)} imports higher layer {imported}")
    assert not violations


def test_layers_do_not_import_pipeline_orchestration() -> None:
    violations: list[str] = []
    forbidden = {"scaffold_core.pipeline.passes", "scaffold_core.pipeline.validator"}
    for path in _source_files():
        parts = _module_parts_from_file(path)
        if "pipeline" in parts:
            continue
        if _layer_index(parts) is None:
            continue
        for imported in _import_roots(path):
            if imported in forbidden:
                violations.append(f"{path.relative_to(ROOT)} imports {imported}")
    assert not violations


def test_model_files_stay_pure() -> None:
    violations: list[str] = []
    forbidden_fragments = ("build", "pipeline", "bpy", "bmesh")
    for path in _source_files():
        if path.name != "model.py":
            continue
        for imported in _import_roots(path):
            if any(fragment in imported for fragment in forbidden_fragments):
                violations.append(f"{path.relative_to(ROOT)} imports {imported}")
    assert not violations
