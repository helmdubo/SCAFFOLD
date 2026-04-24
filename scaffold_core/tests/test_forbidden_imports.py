"""
Layer: tests

Rules:
- Architectural import boundary test only.
- No production logic here.
- Reads phase/layer routing from docs/context_map.yaml.
"""

from __future__ import annotations

import ast
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent
CONTEXT_MAP_PATH = REPO_ROOT / "docs" / "context_map.yaml"

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


def _read_context_map_lines() -> list[str]:
    return CONTEXT_MAP_PATH.read_text(encoding="utf-8").splitlines()


def _current_phase() -> str:
    for line in _read_context_map_lines():
        if line.startswith("current_phase:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("docs/context_map.yaml does not define current_phase")


def _list_items_under_section(section: str, subsection: str | None = None) -> tuple[str, ...]:
    """Read a simple list from docs/context_map.yaml without a YAML dependency.

    This parser intentionally supports only the small routing shape used by
    context_map.yaml. It is not a general YAML parser.
    """

    lines = _read_context_map_lines()
    in_section = False
    in_subsection = subsection is None
    items: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not line.startswith(" ") and stripped.endswith(":"):
            current_section = stripped[:-1]
            if current_section == section:
                in_section = True
                in_subsection = subsection is None
                continue
            if in_section:
                break
            continue

        if not in_section:
            continue

        if subsection is not None and line.startswith("  ") and not line.startswith("    "):
            current_subsection = stripped[:-1] if stripped.endswith(":") else stripped
            in_subsection = current_subsection == subsection
            continue

        if in_subsection and stripped.startswith("- "):
            items.append(stripped[2:])

    return tuple(items)


def _phase_forbidden_dirs() -> tuple[Path, ...]:
    phase = _current_phase()
    return tuple(REPO_ROOT / item for item in _list_items_under_section("phase_forbidden_dirs", phase))


def _layer_by_package() -> dict[str, int]:
    return {
        package_name: index
        for index, package_name in enumerate(_list_items_under_section("layer_order"))
    }


def _source_files() -> list[Path]:
    return [
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "tests" not in path.relative_to(PACKAGE_ROOT).parts
    ]


def _module_parts_from_file(path: Path) -> tuple[str, ...]:
    return path.relative_to(PACKAGE_ROOT).with_suffix("").parts


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
    layer_by_package = _layer_by_package()
    for part in parts:
        if part in layer_by_package:
            return layer_by_package[part]
    return None


def test_current_phase_forbidden_directories_do_not_exist() -> None:
    existing_forbidden_dirs = [path for path in _phase_forbidden_dirs() if path.exists()]
    assert not existing_forbidden_dirs


def test_forbidden_generic_module_names_do_not_exist() -> None:
    bad_files = [path for path in PACKAGE_ROOT.rglob("*.py") if path.stem in FORBIDDEN_MODULE_NAMES]
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
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} imports higher layer {imported}")
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
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} imports {imported}")
    assert not violations


def test_model_files_stay_pure() -> None:
    violations: list[str] = []
    forbidden_fragments = ("build", "pipeline", "bpy", "bmesh")
    for path in _source_files():
        if path.name != "model.py":
            continue
        for imported in _import_roots(path):
            if any(fragment in imported for fragment in forbidden_fragments):
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} imports {imported}")
    assert not violations
