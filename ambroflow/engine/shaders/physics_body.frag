#version 410 core

// Physics body — glowing soft-circle billboard.
//
// Stable bodies: steady, warm glow at their element colour.
// Active bodies: breathing pulse.
// Chaotic / explosive: bright flicker with hot-white core.
//
// The glow is a soft quadratic falloff from the centre so bodies
// blend into the Lapidus fog rather than stamping hard circles.

in vec2  v_uv;
in vec3  v_color;
in float v_ke_norm;
in float v_depth_linear;

uniform float u_time;
uniform float u_fog_near;   // match world renderer fog
uniform float u_fog_far;

layout(location = 0) out vec4 frag_color;

void main() {
    // Signed distance from disc centre: 0=centre, 1=edge
    float dist = length(v_uv - 0.5) * 2.0;
    if (dist > 1.0) discard;

    // Core glow: bright in centre, soft quadratic falloff
    float glow = 1.0 - dist * dist;

    // Hot-white core on high-energy bodies — energy bleaches toward white
    vec3 hot_white = vec3(1.0, 0.95, 0.85);
    vec3 core_color = mix(v_color, hot_white, v_ke_norm * (1.0 - dist * 0.8));

    // Additive rim: faint outer halo at element colour
    float rim = pow(1.0 - dist, 0.4) * 0.35;
    vec3 final_color = core_color * (glow * 1.6 + rim);

    // Fog fade — match world renderer so bodies dissolve at the horizon
    float fog_t = clamp((v_depth_linear - u_fog_near) / (u_fog_far - u_fog_near), 0.0, 1.0);
    fog_t = fog_t * fog_t;
    float fog_alpha = 1.0 - fog_t * 0.85;

    // Alpha: solid core, soft edge, fades with fog and settles at low KE
    float base_alpha = glow * 0.88 * fog_alpha;
    float energy_floor = 0.35 + v_ke_norm * 0.50;   // still bodies visible but dim
    float alpha = base_alpha * energy_floor;

    frag_color = vec4(final_color, alpha);
}
