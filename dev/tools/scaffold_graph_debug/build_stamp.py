"""Build stamp helpers for the ScaffoldGraph debug add-on."""

from __future__ import annotations

from pathlib import Path
import subprocess


OVERLAY_VERSION = "overlay-v3"
_BUILD_STAMP = OVERLAY_VERSION


def resolve_build_stamp() -> str:
    """Return short git hash plus dirty flag, with version fallback."""

    repo_root = Path(__file__).resolve().parents[3]
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return OVERLAY_VERSION
    return f"{commit}{'-dirty' if dirty else ''}"


def set_build_stamp(value: str) -> None:
    global _BUILD_STAMP
    _BUILD_STAMP = value


def get_build_stamp() -> str:
    return _BUILD_STAMP
