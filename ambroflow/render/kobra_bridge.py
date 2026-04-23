"""
ambroflow/render/kobra_bridge.py
================================
KobraBridge — Kobra/Shygazun scene data → Ambroflow renderer configuration.

Accepts plain dicts from the three Kobra pipeline outputs and produces a
KobraRenderConfig that can be applied to a live WorldRenderer + PostProcessor.

Inputs
------
  voxels           — output of entities_to_voxels(entities)
  chromatic_packet — output of build_renderer_chromatic_packet(profile)
  coherence        — output of WitnessTracker.get_coherence_summary()

Rose vector → light mapping
----------------------------
  Ru (red)    → sun warmth / heat radiance
  Ot (orange) → earthy mid warmth
  El (yellow) → bright ambient
  Ki (green)  → temperate fill
  Fu (blue)   → cool sky rim
  Ka (indigo) → cold depth shadow
  AE (violet) → ethereal edge

Coherence cuts
--------------
  resolved — full saturation, normal DoF, standard Lapidus grade
  frontier — reduced saturation, heavy vignette, wide blur, violet shadow shift

Primary register → render mode
-------------------------------
  light     — standard Lapidus (default)
  sound     — no visual change (pure audio territory)
  telepathy — cool sun shift, dreamlike
  haptics   — no visual change
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..world.map import Zone, Realm, WorldTileKind


# ── Kobra color → WorldTileKind ───────────────────────────────────────────────

_COLOR_TO_KIND: dict[str, WorldTileKind] = {
    "Ru": WorldTileKind.STONE,   # red → warm stone floor
    "Ot": WorldTileKind.ROAD,    # orange → worn road
    "El": WorldTileKind.DIRT,    # yellow → dirt path
    "Ki": WorldTileKind.GRASS,   # green → grass
    "Fu": WorldTileKind.WATER,   # blue → water
    "Ka": WorldTileKind.WALL,    # indigo → solid wall
    "AE": WorldTileKind.VOID,    # violet → void / out-of-zone
    "Ha": WorldTileKind.FLOOR,   # absolute positive → floor
    "Ga": WorldTileKind.VOID,    # subtractive → void
}


def _voxel_to_tile_kind(voxel: dict[str, Any]) -> WorldTileKind:
    z     = voxel.get("z", 0)
    layer = voxel.get("layer", "base")
    color = voxel.get("color", "Ki")
    meta  = voxel.get("meta", {})
    opacity = meta.get("opacity", "Na")

    if z > 0 or layer in ("ceiling", "side"):
        return WorldTileKind.WALL
    if opacity == "Ung":
        return WorldTileKind.WATER

    return _COLOR_TO_KIND.get(color, WorldTileKind.FLOOR)


# ── Voxels → Zone ─────────────────────────────────────────────────────────────

def voxels_to_zone(
    voxels:   list[dict[str, Any]],
    zone_id:  str   = "kobra_scene",
    realm:    Realm = Realm.LAPIDUS,
    name:     str   = "Kobra Scene",
) -> Zone:
    """
    Convert entities_to_voxels output to a Zone for WorldRenderer.load_zone().

    Kobra x → column, Kobra y → row, z > 0 or layer=ceiling/side → WALL.
    """
    if not voxels:
        return Zone(
            zone_id=zone_id, realm=realm, name=name,
            width=1, height=1,
            voxels={(0, 0): WorldTileKind.FLOOR},
            player_spawn=(0, 0),
        )

    xs = [v.get("x", 0) for v in voxels]
    ys = [v.get("y", 0) for v in voxels]
    width  = max(xs) + 1
    height = max(ys) + 1

    tile_map: dict[tuple[int, int], WorldTileKind] = {}
    player_spawn = (0, 0)

    for v in voxels:
        x, y = v.get("x", 0), v.get("y", 0)
        tile_map[(x, y)] = _voxel_to_tile_kind(v)
        if v.get("type") == "npc" and player_spawn == (0, 0):
            player_spawn = (x, y)

    return Zone(
        zone_id=zone_id, realm=realm, name=name,
        width=width, height=height,
        voxels=tile_map,
        player_spawn=player_spawn,
    )


# ── Chromatic packet → lighting ───────────────────────────────────────────────

_LAPIDUS_BASE_LIGHTING: dict[str, Any] = {
    "u_sun_dir":   (0.6,  1.0, -0.4),
    "u_sun_color": (1.00, 0.92, 0.70),
    "u_ambient":   (0.14, 0.12, 0.22),
    "u_rim_color": (0.55, 0.60, 0.75),
    "u_fog_near":  18.0,
    "u_fog_far":   60.0,
    "u_fog_color": (0.36, 0.33, 0.44),
}


def _chromatic_to_lighting(
    light_band:       dict[str, float],
    primary_register: Optional[str] = None,
) -> dict[str, Any]:
    """
    Map the chromatic packet's 'light' band to Lapidus lighting uniforms.

    Warm vectors (Ru/Ot/El) → sun warmth.
    Cool vectors (Fu/Ka/AE) → rim and shadow depth.
    Ki → ambient fill intensity.
    """
    ru = light_band.get("Ru", 0.0)
    ot = light_band.get("Ot", 0.0)
    el = light_band.get("El", 0.0)
    ki = light_band.get("Ki", 0.0)
    fu = light_band.get("Fu", 0.0)
    ka = light_band.get("Ka", 0.0)
    ae = light_band.get("AE", 0.0)

    warm = (ru + ot + el) / 3.0
    cool = (fu + ka + ae) / 3.0
    mid  = ki

    sun_color = (
        min(1.0, 0.85 + warm * 0.15),
        min(1.0, 0.80 + mid  * 0.12),
        min(1.0, 0.60 + cool * 0.35),
    )
    ambient = (
        min(1.0, 0.10 + warm * 0.04),
        min(1.0, 0.10 + mid  * 0.02),
        min(1.0, 0.18 + cool * 0.08),
    )
    rim_color = (
        min(1.0, 0.40 + cool * 0.15),
        min(1.0, 0.55 + mid  * 0.05),
        min(1.0, 0.65 + cool * 0.15),
    )

    lighting: dict[str, Any] = {
        "u_sun_color": sun_color,
        "u_ambient":   ambient,
        "u_rim_color": rim_color,
    }

    # Telepathy register → desaturate toward cool/violet
    if primary_register == "telepathy":
        lighting["u_sun_color"] = (
            max(0.0, sun_color[0] - 0.15),
            max(0.0, sun_color[1] - 0.10),
            min(1.0, sun_color[2] + 0.20),
        )
        lighting["u_ambient"] = (
            max(0.0, ambient[0] - 0.05),
            max(0.0, ambient[1] - 0.02),
            min(1.0, ambient[2] + 0.12),
        )

    return lighting


# ── Coherence → post config ───────────────────────────────────────────────────

@dataclass
class PostConfig:
    """Grade and DoF configuration derived from coherence state."""
    vignette_strength: float = 0.45
    saturation:        float = 0.88
    max_blur:          float = 14.0
    focus_dist:        float = 12.0
    focus_range:       float = 5.0


def _coherence_to_post_config(coherence: dict[str, Any]) -> PostConfig:
    """
    Map WitnessTracker coherence summary to PostProcessor settings.

    coherence_grade 0.0 = total frontier, 1.0 = fully attested.
    The frontier cut desaturates, vignettes, and widens DoF blur in proportion.
    """
    cut   = coherence.get("cut_character", "resolved")
    grade = float(coherence.get("coherence_grade", 1.0))

    if cut != "frontier":
        return PostConfig()

    return PostConfig(
        vignette_strength = min(0.90, 0.65 + (1.0 - grade) * 0.25),
        saturation        = max(0.25, 0.35 + grade * 0.53),
        max_blur          = min(28.0, 14.0 + (1.0 - grade) * 14.0),
        focus_dist        = 10.0 + (1.0 - grade) * 4.0,
        focus_range       = max(1.5, 5.0 - (1.0 - grade) * 3.5),
    )


# ── KobraRenderConfig ─────────────────────────────────────────────────────────

@dataclass
class KobraRenderConfig:
    """
    Complete render configuration assembled from a Kobra scene.
    Pass to apply_render_config() once before the render loop (static scenes)
    or each frame (dynamic coherence / live chromatic score).
    """
    zone:             Zone
    lighting:         dict[str, Any]
    post:             PostConfig
    primary_register: Optional[str] = None
    kael_active:      bool          = False
    cannabis_active:  bool          = False
    coherence_grade:  float         = 1.0


def build_render_config(
    voxels:           list[dict[str, Any]],
    chromatic_packet: dict[str, Any],
    coherence:        dict[str, Any],
    zone_id:          str   = "kobra_scene",
    realm:            Realm = Realm.LAPIDUS,
) -> KobraRenderConfig:
    """
    Assemble a KobraRenderConfig from the three Kobra data pipeline outputs.

    Parameters
    ----------
    voxels           : entities_to_voxels(entities)
    chromatic_packet : build_renderer_chromatic_packet(profile)
    coherence        : WitnessTracker.get_coherence_summary()
    """
    zone             = voxels_to_zone(voxels, zone_id=zone_id, realm=realm)
    primary_register = chromatic_packet.get("primary_register")
    light_band       = chromatic_packet.get("light", {})

    lighting = dict(_LAPIDUS_BASE_LIGHTING)
    lighting.update(_chromatic_to_lighting(light_band, primary_register))

    return KobraRenderConfig(
        zone             = zone,
        lighting         = lighting,
        post             = _coherence_to_post_config(coherence),
        primary_register = primary_register,
        kael_active      = chromatic_packet.get("kael_active",   False),
        cannabis_active  = chromatic_packet.get("is_ambiguous",  False),
        coherence_grade  = float(coherence.get("coherence_grade", 1.0)),
    )


# ── Renderer application ──────────────────────────────────────────────────────

def apply_render_config(
    config:         KobraRenderConfig,
    world_renderer,
    post_processor,
) -> None:
    """
    Apply a KobraRenderConfig to live WorldRenderer and PostProcessor instances.

    For static scenes, call once before the render loop.
    For dynamic coherence or live chromatic score, call each frame.
    load_zone() uploads GPU instance data — avoid inside the hot loop for
    large static scenes.
    """
    world_renderer.load_zone(config.zone)
    world_renderer.update_lighting(config.lighting)

    post_processor.set_grade_params(
        vignette_strength = config.post.vignette_strength,
        saturation        = config.post.saturation,
    )
    post_processor.set_dof_params(
        focus_dist  = config.post.focus_dist,
        focus_range = config.post.focus_range,
        max_blur    = config.post.max_blur,
    )