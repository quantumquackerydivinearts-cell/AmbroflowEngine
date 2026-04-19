#version 410 core

// Per-vertex attributes
layout(location = 0) in vec3 a_pos;
layout(location = 1) in vec2 a_uv;
layout(location = 2) in vec3 a_normal;

// Per-instance attributes (tile placement)
layout(location = 3) in vec3  i_offset;      // tile world position
layout(location = 4) in float i_tile_id;      // atlas tile index (float cast of uint)
layout(location = 5) in float i_height;       // Y displacement for elevation

uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec2 u_atlas_size;   // (cols, rows) in the tile atlas

out vec2  v_uv;
out vec3  v_world_pos;
out vec3  v_normal;
out float v_depth_linear;    // 0..1 linear depth for DoF

void main() {
    vec3 world = a_pos + i_offset + vec3(0.0, i_height, 0.0);
    vec4 clip  = u_proj * u_view * vec4(world, 1.0);
    gl_Position = clip;

    // Atlas UV: remap tile-local [0,1] to atlas cell
    float cols = u_atlas_size.x;
    float rows = u_atlas_size.y;
    float tile  = i_tile_id;
    float col   = mod(tile, cols);
    float row   = floor(tile / cols);
    v_uv = vec2(
        (col + a_uv.x) / cols,
        (row + a_uv.y) / rows
    );

    v_world_pos   = world;
    v_normal      = a_normal;
    // Linear 0..1 in camera space for DoF
    v_depth_linear = (-( u_view * vec4(world, 1.0)).z);
}