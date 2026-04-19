#version 410 core

// ── Depth of Field — Fragment Shader ─────────────────────────────────────────
//
// Octopath-style: sharp midground, soft foreground and far background.
// Reads hardware (non-linear) depth, linearises it, then blurs by CoC.
//
// Run twice as a separable 2-pass blur:
//   Pass 1: u_direction = (1,0)
//   Pass 2: u_direction = (0,1)

in vec2 v_uv;

uniform sampler2D u_color;        // scene color (RGBA16F)
uniform sampler2D u_depth;        // hardware depth buffer (bound as depth texture)
uniform vec2      u_resolution;   // viewport pixels
uniform vec2      u_direction;    // (1,0) or (0,1)

uniform float u_near;         // camera near plane, default 0.1
uniform float u_far;          // camera far plane,  default 500
uniform float u_focus_dist;   // world-space focus depth, default 14
uniform float u_focus_range;  // half-width of sharp band,  default 4
uniform float u_max_blur;     // max CoC pixel radius,       default 12

layout(location = 0) out vec4 frag_color;

// Linearise [0,1] hardware depth → view-space positive depth
float linearise(float d) {
    float z_ndc = d * 2.0 - 1.0;
    return 2.0 * u_near * u_far / (u_far + u_near - z_ndc * (u_far - u_near));
}

// CoC radius in pixels [0 .. u_max_blur]
float coc(float depth_lin) {
    float d = abs(depth_lin - u_focus_dist);
    float t = clamp((d - u_focus_range) / u_focus_range, 0.0, 1.0);
    return t * t * u_max_blur;
}

// 9-tap separable Gaussian
const float WEIGHTS[5] = float[](0.227027, 0.194595, 0.121622, 0.054054, 0.016216);

void main() {
    float hw_depth  = texture(u_depth, v_uv).r;
    float lin_depth = linearise(hw_depth);
    float radius    = coc(lin_depth);

    if (radius < 0.5) {
        frag_color = texture(u_color, v_uv);
        return;
    }

    vec2  texel  = 1.0 / u_resolution;
    float spread = radius / u_max_blur * 4.0;
    vec3  result = texture(u_color, v_uv).rgb * WEIGHTS[0];

    for (int i = 1; i < 5; ++i) {
        vec2 off = u_direction * texel * float(i) * spread;
        result  += texture(u_color, v_uv + off).rgb * WEIGHTS[i];
        result  += texture(u_color, v_uv - off).rgb * WEIGHTS[i];
    }

    frag_color = vec4(result, 1.0);
}