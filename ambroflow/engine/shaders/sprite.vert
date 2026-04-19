#version 410 core

// ── Sprite Billboard Vertex Shader ───────────────────────────────────────────
//
// Each sprite is a camera-facing quad anchored at world_pos.
// The quad is expanded in view space so it always faces the camera.
//
// Per-vertex (unit quad in [-0.5,0.5]×[0,1]):
layout(location = 0) in vec2 a_quad;   // (x, y) quad corner
layout(location = 1) in vec2 a_uv;     // texture coords

// Per-instance:
layout(location = 2) in vec3  i_world_pos;  // anchor (feet of sprite)
layout(location = 3) in vec2  i_size;       // (width, height) in world units
layout(location = 4) in float i_frame_u;    // atlas U offset (normalised)
layout(location = 5) in float i_frame_v;    // atlas V offset (normalised)
layout(location = 6) in float i_frame_w;    // atlas frame width (normalised)
layout(location = 7) in float i_frame_h;    // atlas frame height (normalised)

uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec3 u_cam_right;  // view matrix row 0 (right vector)
uniform vec3 u_cam_up;     // world Y-axis locked up (no tilt on up axis)

out vec2  v_uv;
out float v_depth_linear;

void main() {
    // Billboard: expand quad in camera-right and world-up (Y-locked)
    // anchor is at the feet → offset by i_size.y upward
    vec3 right = normalize(u_cam_right);
    vec3 up    = vec3(0.0, 1.0, 0.0);   // Y-locked — no camera tilt leak

    vec3 world = i_world_pos
               + right * (a_quad.x * i_size.x)
               + up    * (a_quad.y * i_size.y);

    vec4 clip  = u_proj * u_view * vec4(world, 1.0);
    gl_Position = clip;

    v_uv = vec2(
        i_frame_u + a_uv.x * i_frame_w,
        i_frame_v + a_uv.y * i_frame_h
    );
    v_depth_linear = -(u_view * vec4(world, 1.0)).z;
}