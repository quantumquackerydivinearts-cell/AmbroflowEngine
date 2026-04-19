#version 410 core

// ── Color Grade — Lapidus Overworld ──────────────────────────────────────────
//
// Applied after DoF.  Lapidus palette: warm amber highlights,
// deep violet-indigo shadows, desaturated midtones.
// Emulates the Octopath warm-cool split-toning look.

in vec2 v_uv;

uniform sampler2D u_color;
uniform float     u_time;
uniform float     u_vignette_strength;  // default 0.45
uniform float     u_saturation;         // default 0.88

layout(location = 0) out vec4 frag_color;

// Luminance (Rec.709)
float luma(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

// Lift-Gamma-Gain three-way color grade
vec3 lggg(vec3 c) {
    // Shadows: violet lift
    vec3 lift  = vec3(0.02,  0.01,  0.06);
    // Highlights: warm amber gain
    vec3 gain  = vec3(1.08,  1.03,  0.92);
    // Midtone gamma (slight desaturate toward stone)
    float gamma = 1.05;

    c = clamp(c, 0.0, 1.0);
    c = lift + c * (gain - lift);
    c = pow(c, vec3(1.0 / gamma));
    return c;
}

void main() {
    vec3 col = texture(u_color, v_uv).rgb;

    // Saturation
    float lum  = luma(col);
    col = mix(vec3(lum), col, u_saturation);

    // Three-way grade
    col = lggg(col);

    // Vignette — radial darkening, slightly offset toward bottom
    vec2 uv_c  = v_uv - vec2(0.5, 0.52);
    float vig  = 1.0 - dot(uv_c * vec2(1.2, 1.6), uv_c * vec2(1.2, 1.6));
    vig = clamp(vig, 0.0, 1.0);
    vig = pow(vig, u_vignette_strength);
    col *= vig;

    // Subtle film grain (dithering anti-banding, ~1/255 magnitude)
    float grain = fract(sin(dot(v_uv + u_time * 0.001, vec2(12.9898, 78.233))) * 43758.5453);
    col += (grain - 0.5) * (1.5 / 255.0);

    frag_color = vec4(clamp(col, 0.0, 1.0), 1.0);
}