"""
Layer: user filters (the over filter stage, between Layer 4 and Layer 5)

Rules:
- Package marker only.
- The only place in scaffold_core where a world direction may appear.
- Reads Layers 0-4 read-only; never imports Layer 5.
- Layers 0-4 never import it; Layer 5 reads only its SeamDirectives.
"""
