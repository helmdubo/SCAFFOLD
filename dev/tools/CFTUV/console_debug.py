from __future__ import annotations

from enum import Enum
from typing import Optional


class FrontierLiveTraceMode(str, Enum):
    """Режим live-trace для frontier telemetry."""

    OFF = "off"
    COMPACT = "compact"
    FULL = "full"


def _get_hotspotuv_settings():
    try:
        import bpy  # type: ignore
    except Exception:
        return None

    context = getattr(bpy, "context", None)
    if context is None:
        return None

    scene = getattr(context, "scene", None)
    if scene is None:
        return None

    return getattr(scene, "hotspotuv_settings", None)


def is_verbose_console_enabled() -> bool:
    settings = _get_hotspotuv_settings()
    return bool(getattr(settings, "dbg_verbose_console", False))


def normalize_frontier_live_trace_mode(
    mode: Optional[FrontierLiveTraceMode | str],
) -> FrontierLiveTraceMode:
    """Нормализует внешний mode в режим live-trace telemetry."""

    if mode is None:
        return FrontierLiveTraceMode.COMPACT
    if isinstance(mode, FrontierLiveTraceMode):
        return mode
    value = str(mode).strip().lower()
    for item in FrontierLiveTraceMode:
        if item.value == value:
            return item
    raise ValueError(f"Unsupported frontier live trace mode: {mode}")


def get_frontier_live_trace_mode() -> FrontierLiveTraceMode:
    """Определяет режим runtime live-trace для frontier telemetry.

    Совместимость:
    - `dbg_verbose_console = False` -> `off`
    - `dbg_verbose_console = True` и без явного mode -> `compact`
    - если позже появится строковый debug-параметр, принимаем
      `dbg_frontier_trace_mode`, `dbg_telemetry_trace_mode` или `dbg_trace_mode`
    """

    settings = _get_hotspotuv_settings()
    if not bool(getattr(settings, "dbg_verbose_console", False)):
        return FrontierLiveTraceMode.OFF

    for attr_name in (
        "dbg_frontier_trace_mode",
        "dbg_telemetry_trace_mode",
        "dbg_trace_mode",
    ):
        raw_mode = getattr(settings, attr_name, None)
        if raw_mode in (None, ""):
            continue
        try:
            return normalize_frontier_live_trace_mode(raw_mode)
        except ValueError:
            continue

    return FrontierLiveTraceMode.COMPACT


def trace_console(message: str) -> None:
    if is_verbose_console_enabled():
        print(message)
