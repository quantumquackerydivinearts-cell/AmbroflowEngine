#version 410 core

// ── UI / Action Layer Fragment Shader ────────────────────────────────────────
//
// Renders a PIL-sourced RGBA texture onto a screen-space quad.
// Premultiplied alpha expected from PIL (RGBA mode).

in vec2 v_uv;

uniform sampler2D u_ui_tex;
uniform float     u_opacity;   // master fade (0=invisible, 1=full)

layout(location = 0) out vec4 frag_color;

void main() {
    vec4 col = texture(u_ui_tex, v_uv);
    frag_color = vec4(col.rgb, col.a * u_opacity);
}