"""
Layer: cross-cutting constants

Rules:
- Contains global project-level defaults only.
- Algorithm-specific constants belong near the algorithm.
- Does not import layer packages.
"""

WORLD_UP = (0.0, 0.0, 1.0)
DEFAULT_FLOAT_EPSILON = 1.0e-6
