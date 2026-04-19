#version 410 core

// ── Sprite Billboard Fragment Shader ─────────────────────────────────────────
//
// Alpha-tested sprites in world space.  Hard alpha cutoff for pixel-art
// sprites; no premultiplied alpha assumed.

in vec2  v_uv;
in float v_depth_linear;

uniform sampler2D u_sprite_atlas;
uniform vec3      u_ambient;        // match world ambient so sprites integrate
uniform vec3      u_sun_color;      // rim tint from world sun
uniform float     u_alpha_cutoff;   // default 0.5 — pixel-art hard edge

layout(location = 0) out vec4 frag_color;

void main() {
    vec4 col = texture(u_sprite_atlas, v_uv);
    if (col.a < u_alpha_cutoff) discard;

    // Minimal flat lighting integration — sprites are pre-lit by artist
    // but we mix ambient to avoid them looking pasted-on in dark areas
    vec3 final = col.rgb * (u_ambient * 2.0 + u_sun_color * 0.4);
    final = min(final, col.rgb * 1.15);   // don't over-brighten

    frag_color = vec4(final, col.a);
}