"""Blender dev add-on for ScaffoldGraph visual debugging."""

bl_info = {
    "name": "Scaffold Graph Debug",
    "author": "Scaffold",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "category": "UV",
    "description": "Dev ScaffoldGraph Grease Pencil overlay",
    "location": "View3D > Sidebar > Scaffold",
}


def register():
    import sys
    from pathlib import Path

    repo_root = str(Path(__file__).resolve().parents[3])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)  # scaffold_core, read by the payload builder
    from .operators import register as _register

    return _register()


def unregister():
    from .operators import unregister as _unregister

    return _unregister()


__all__ = ["bl_info", "register", "unregister"]
