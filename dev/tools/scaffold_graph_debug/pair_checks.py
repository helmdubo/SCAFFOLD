"""Compact continuity pair-check formatting for ScaffoldGraph debug overlays."""

from __future__ import annotations

import re
from typing import Any


_CUBE_OBJECT_KEY = "cube_1hole_2seams_tube"
_CYLINDER_OBJECT_KEY = "cylinder_1cap_all_seams"

_CUBE_FALSE_MERGE_PAIRS = (
    ("P0C1", "P1C1"),
    ("P0C0", "P2C0"),
    ("P1C1", "P1C2"),
    ("P1C2", "P1C3"),
    ("P2C3", "P2C0"),
    ("P2C2", "P2C3"),
)
_CUBE_EXPECTED_CONNECTED_PAIRS = (
    ("P1C1", "P2C0"),
    ("P1C3", "P2C2"),
    ("P1C2", "P2C3"),
)
_CUBE_STILL_UNRESOLVED_PAIRS = (("P1C0", "P2C1"),)


def format_continuity_pair_check(object_name: str, overlay: dict[str, Any]) -> str:
    """Format a compact pair-check report from serialized overlay data only."""

    label_to_component_id = _label_to_component_id(overlay)
    component_lines = _component_lines(overlay)
    lines = [
        "CONTINUITY PAIR CHECK",
        f"object: {object_name}",
        f"scaffold_edges: {_edge_count(overlay)}",
        f"continuity_components: {_component_count(overlay)}",
        "",
        "COMPONENTS",
        *component_lines,
    ]

    normalized_name = object_name.lower()
    if _CUBE_OBJECT_KEY in normalized_name:
        false_merge_passed = _append_pair_section(
            lines,
            "FALSE MERGE CHECKS (expected false)",
            _CUBE_FALSE_MERGE_PAIRS,
            False,
            label_to_component_id,
        )
        expected_connected_passed = _append_pair_section(
            lines,
            "EXPECTED CONNECTED (expected true)",
            _CUBE_EXPECTED_CONNECTED_PAIRS,
            True,
            label_to_component_id,
        )
        unresolved_check_passed = _append_pair_section(
            lines,
            "STILL UNRESOLVED (expected false)",
            _CUBE_STILL_UNRESOLVED_PAIRS,
            False,
            label_to_component_id,
        )
        lines.extend(
            [
                "",
                "RESULT",
                f"false_merge_checks_passed: {str(false_merge_passed).lower()}",
                f"expected_connected_passed: {str(expected_connected_passed).lower()}",
                f"unresolved_check_passed: {str(unresolved_check_passed).lower()}",
            ]
        )
    elif _CYLINDER_OBJECT_KEY in normalized_name:
        lines.append("")
        lines.append("pair expectations unavailable for this object; labels need mapping")
    else:
        lines.append("")
        lines.append("pair expectations unavailable for this object")

    return "\n".join(lines)


def _edge_count(overlay: dict[str, Any]) -> int:
    return int(overlay.get("scaffold_edge_count", len(overlay.get("edges", ()))))


def _component_count(overlay: dict[str, Any]) -> int:
    return int(
        overlay.get(
            "scaffold_continuity_component_count",
            len(overlay.get("continuity_components", ())),
        )
    )


def _label_to_component_id(overlay: dict[str, Any]) -> dict[str, str]:
    label_to_component: dict[str, str] = {}
    for edge in overlay.get("edges", ()):
        if not isinstance(edge, dict):
            continue
        label = _edge_label(edge)
        component_id = edge.get("continuity_component_id")
        if label != "MISSING_LABEL" and component_id is not None:
            label_to_component[label] = str(component_id)
    return label_to_component


def _component_lines(overlay: dict[str, Any]) -> list[str]:
    label_by_edge_id = {
        str(edge.get("id")): _edge_label(edge)
        for edge in overlay.get("edges", ())
        if isinstance(edge, dict) and edge.get("id") is not None
    }
    lines: list[str] = []
    for component in overlay.get("continuity_components", ()):
        if not isinstance(component, dict):
            continue
        edge_labels = [
            label_by_edge_id[edge_id]
            for edge_id in (str(item) for item in component.get("scaffold_edge_ids", ()))
            if edge_id in label_by_edge_id
        ]
        labels = ", ".join(sorted(edge_labels, key=_natural_key)) if edge_labels else "<no edges>"
        component_id = str(component.get("id", "MISSING_COMPONENT_ID"))
        lines.append(f"{component_id}: {labels}")
    if not lines:
        return ["<none>"]
    return lines


def _append_pair_section(
    lines: list[str],
    title: str,
    pairs: tuple[tuple[str, str], ...],
    expected: bool,
    label_to_component_id: dict[str, str],
) -> bool:
    lines.extend(("", title))
    section_results = []
    for first_label, second_label in pairs:
        line, passed = _pair_line(
            first_label,
            second_label,
            expected,
            label_to_component_id,
        )
        lines.append(line)
        section_results.append(passed)
    return all(section_results)


def _pair_line(
    first_label: str,
    second_label: str,
    expected: bool,
    label_to_component_id: dict[str, str],
) -> tuple[str, bool]:
    first_component = label_to_component_id.get(first_label)
    second_component = label_to_component_id.get(second_label)
    if first_component is None or second_component is None:
        first_value = first_component or "MISSING_LABEL"
        second_value = second_component or "MISSING_LABEL"
        return (
            f"{first_label} / {second_label}: MISSING_LABEL "
            f"component={first_value}/{second_value}",
            False,
        )
    connected = first_component == second_component
    return (
        f"{first_label} / {second_label}: {str(connected).lower()} "
        f"component={first_component}/{second_component}",
        connected is expected,
    )


def _natural_key(label: str) -> list[int | str]:
    return [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", label)
    ]


def _edge_label(edge: dict[str, Any]) -> str:
    label = edge.get("display_label")
    if label:
        return str(label)
    return "MISSING_LABEL"
