#version 410 core

// ── UI / Action Layer Vertex Shader ──────────────────────────────────────────
//
// Screen-space quads for PIL-rendered dialogue panels, portraits,
// dream sequence overlays.  Coordinates in normalised screen space [0,1].

layout(location = 0) in vec2 a_pos;   // quad corner in NDC [-1,1]
layout(location = 1) in vec2 a_uv;    // texture UV [0,1]

out vec2 v_uv;

void main() {
    v_uv        = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}