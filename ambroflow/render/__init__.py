"""
ambroflow.render
================
GL rendering layer: world geometry, sprites, post-processing, UI overlay.
"""

from .world        import WorldRenderer, LAPIDUS_LIGHTING
from .sprite       import SpriteRenderer
from .post         import PostProcessor
from .ui           import UIRenderer, UIPanel
from .kobra_bridge import (
    KobraRenderConfig,
    PostConfig,
    build_render_config,
    apply_render_config,
    voxels_to_zone,
)

__all__ = [
    "WorldRenderer",
    "LAPIDUS_LIGHTING",
    "SpriteRenderer",
    "PostProcessor",
    "UIRenderer",
    "UIPanel",
    "KobraRenderConfig",
    "PostConfig",
    "build_render_config",
    "apply_render_config",
    "voxels_to_zone",
]