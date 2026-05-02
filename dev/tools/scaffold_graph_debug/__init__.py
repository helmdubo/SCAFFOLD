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
    from .operators import register as _register

    return _register()


def unregister():
    from .operators import unregister as _unregister

    return _unregister()


__all__ = ["bl_info", "register", "unregister"]
