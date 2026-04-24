#version 410 core

// ── Lapidus Overworld — Fragment Shader ──────────────────────────────────────
//
// Visual identity: warm stone, deep forest green, amber torchlight.
// Palette pulled from Ko's Labyrinth / Octopath Overworld analogue:
//   - Base:     dusty sandstone / slate
//   - Accent:   amber + copper for warm light sources
//   - Shadow:   deep violet-blue (not pure black)
//   - Rim:      cool silver-white from sky
//
// Lighting model: 1 directional sun + 1 ambient fill + 1 rim from above-behind.
//
// Interseam shading: darkens pixels near tile-boundary seams.
//   All tiles are XZ unit quads centred on integer offsets, so seams fall at
//   half-integer world coordinates.  u_seam_width controls the shadow band
//   (in tile-space, 0→0.5) and u_seam_strength controls its peak opacity.

in vec2  v_uv;
in vec3  v_world_pos;
in vec3  v_normal;
in float v_depth_linear;

uniform sampler2D u_atlas;
uniform float     u_time;           // seconds, for subtle shimmer/wind

// Light direction (normalised, in world space)
uniform vec3 u_sun_dir;       // default: normalize(vec3(0.6, 1.0, -0.4))
uniform vec3 u_sun_color;     // (1.00, 0.92, 0.70)  warm amber sun
uniform vec3 u_ambient;       // (0.14, 0.12, 0.22)  violet-blue fill
uniform vec3 u_rim_color;     // (0.55, 0.60, 0.75)  cool sky rim

// Fog
uniform float u_fog_near;     // default 18
uniform float u_fog_far;      // default 60
uniform vec3  u_fog_color;    // (0.36, 0.33, 0.44)  dusty lilac horizon

// Interseam shading
uniform float u_seam_width;    // default 0.06  — shadow band width in tile-space (0..0.5)
uniform float u_seam_strength; // default 0.45  — peak shadow opacity at seam edge

layout(location = 0) out vec4 frag_color;

void main() {
    vec4 albedo = texture(u_atlas, v_uv);
    if (albedo.a < 0.01) discard;

    vec3 N = normalize(v_normal);
    vec3 L = normalize(u_sun_dir);

    // Diffuse wrap — soften terminator (wrap = 0.3)
    float diff = max(dot(N, L) * 0.7 + 0.3, 0.0);

    // Rim from directly above-behind (simulates sky dome bounce)
    vec3 rim_dir = normalize(vec3(-0.1, 1.0, 0.5));
    float rim = pow(1.0 - max(dot(N, rim_dir), 0.0), 3.0) * 0.4;

    vec3 lit = albedo.rgb * (u_ambient + u_sun_color * diff + u_rim_color * rim);

    // ── Interseam contact shadow ──────────────────────────────────────────────
    // Tiles are unit XZ quads centred at integer offsets, so the shared edge
    // between adjacent tiles sits at half-integer world positions.
    // fract(pos + 0.5) maps seam → 0, tile-centre → 0.5.
    vec2  seam    = fract(v_world_pos.xz + 0.5);
    vec2  sd2     = min(seam, 1.0 - seam);   // 0 at seam, 0.5 at centre
    float sd      = min(sd2.x, sd2.y);       // nearest seam in X or Z

    // Shadow darkens the lit colour, then fades out with fog
    float seam_shadow = (1.0 - smoothstep(0.0, u_seam_width, sd)) * u_seam_strength;

    // Depth fog
    float fog_t = clamp((v_depth_linear - u_fog_near) / (u_fog_far - u_fog_near), 0.0, 1.0);
    fog_t = fog_t * fog_t;   // quadratic curve — dense near horizon

    // Apply seam shadow before fog (seam detail dissolves into fog naturally)
    lit = lit * (1.0 - seam_shadow * (1.0 - fog_t));

    vec3 final = mix(lit, u_fog_color, fog_t);

    frag_color = vec4(final, albedo.a);
}