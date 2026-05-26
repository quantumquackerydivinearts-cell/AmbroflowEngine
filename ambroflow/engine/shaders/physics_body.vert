#version 410 core

// Per-vertex (billboard quad corners)
layout(location = 0) in vec2  a_corner;  // [-0.5, 0.5] billboard-space
layout(location = 1) in vec2  a_uv;      // [0, 1] UV for glow

// Per-instance (one entry per physics body)
layout(location = 2) in vec3  i_world_pos;   // body centre in world space
layout(location = 3) in vec3  i_color;       // element / compound RGB
layout(location = 4) in float i_ke_norm;     // kinetic energy, normalised [0, 1]
layout(location = 5) in float i_radius;      // visual radius in world units

uniform mat4  u_view;
uniform mat4  u_proj;
uniform float u_time;

out vec2  v_uv;
out vec3  v_color;
out float v_ke_norm;
out float v_depth_linear;

void main() {
    // Place body centre in view space, then expand the quad in view XY.
    // This produces a billboard that always faces the camera.
    vec4 view_center = u_view * vec4(i_world_pos, 1.0);

    // Pulse radius gently: active bodies breathe, still bodies are fixed.
    float pulse_scale = 1.0 + i_ke_norm * 0.25 * sin(u_time * 6.28 + i_ke_norm * 4.0);
    view_center.xy += a_corner * i_radius * 2.0 * pulse_scale;

    gl_Position     = u_proj * view_center;
    v_uv            = a_uv;
    v_color         = i_color;
    v_ke_norm       = i_ke_norm;
    v_depth_linear  = -view_center.z;
}
