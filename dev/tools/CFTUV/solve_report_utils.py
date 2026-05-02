from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ReportingMode(str, Enum):
    """Режим текстового рендера solve-отчётов."""

    SUMMARY = "summary"
    DIAGNOSTIC = "diagnostic"
    FORENSIC = "forensic"


@dataclass(frozen=True)
class ReportingOptions:
    """Лёгкая конфигурация текстового рендера без влияния на solve."""

    mode: ReportingMode = ReportingMode.DIAGNOSTIC


def normalize_reporting_mode(mode: Optional[ReportingMode | str]) -> ReportingMode:
    """Нормализует внешний mode-параметр к ReportingMode."""

    if mode is None:
        return ReportingMode.DIAGNOSTIC
    if isinstance(mode, ReportingMode):
        return mode
    value = str(mode).strip().lower()
    for item in ReportingMode:
        if item.value == value:
            return item
    raise ValueError(f"Unsupported reporting mode: {mode}")


def coerce_reporting_options(
    reporting: Optional[ReportingOptions] = None,
    *,
    mode: Optional[ReportingMode | str] = None,
) -> ReportingOptions:
    """Собирает итоговые reporting options из объекта и/или mode."""

    if reporting is None:
        return ReportingOptions(mode=normalize_reporting_mode(mode))
    if mode is None:
        return reporting
    return ReportingOptions(mode=normalize_reporting_mode(mode))


def _format_addr_body(body: str) -> str:
    return f"ADDR {body}"


def _format_quilt_prefix(quilt_index: Optional[int]) -> str:
    if quilt_index is None:
        return ""
    return f"Q{quilt_index}/"


def format_patch_address(patch_id: int, quilt_index: Optional[int] = None) -> str:
    """Стабильный адрес patch для отчётов и логов."""

    return _format_addr_body(f"{_format_quilt_prefix(quilt_index)}P{patch_id}")


def format_chain_address(
    chain_ref: tuple[int, int, int],
    quilt_index: Optional[int] = None,
) -> str:
    """Стабильный адрес boundary chain."""

    patch_id, loop_index, chain_index = chain_ref
    return _format_addr_body(
        f"{_format_quilt_prefix(quilt_index)}P{patch_id}/L{loop_index}/C{chain_index}"
    )


def format_corner_address(
    patch_id: int,
    loop_index: int,
    corner_index: int,
    quilt_index: Optional[int] = None,
) -> str:
    """Стабильный адрес boundary corner."""

    return _format_addr_body(
        f"{_format_quilt_prefix(quilt_index)}P{patch_id}/L{loop_index}/K{corner_index}"
    )


def format_patch_pair_address(
    owner_patch_id: int,
    target_patch_id: int,
    quilt_index: Optional[int] = None,
) -> str:
    """Стабильный адрес patch-pair / seam-пары."""

    return _format_addr_body(
        f"{_format_quilt_prefix(quilt_index)}P{owner_patch_id}<->P{target_patch_id}"
    )


def format_chain_pair_address(
    owner_ref: tuple[int, int, int],
    target_ref: tuple[int, int, int],
    quilt_index: Optional[int] = None,
) -> str:
    """Стабильный адрес пары цепочек на seam / attachment."""

    owner_patch_id, owner_loop_index, owner_chain_index = owner_ref
    target_patch_id, target_loop_index, target_chain_index = target_ref
    return _format_addr_body(
        f"{_format_quilt_prefix(quilt_index)}"
        f"P{owner_patch_id}/L{owner_loop_index}/C{owner_chain_index}"
        f"<->P{target_patch_id}/L{target_loop_index}/C{target_chain_index}"
    )


def format_stall_address(
    iteration: int,
    quilt_index: Optional[int] = None,
) -> str:
    """Стабильный адрес frontier stall-события."""

    return _format_addr_body(f"{_format_quilt_prefix(quilt_index)}S{iteration}")
