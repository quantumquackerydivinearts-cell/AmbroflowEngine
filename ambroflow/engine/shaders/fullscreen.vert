#version 410 core

// ── Fullscreen Triangle ───────────────────────────────────────────────────────
//
// Single triangle that covers the screen — no VBO needed.
// Draw with: glDrawArrays(GL_TRIANGLES, 0, 3)  (empty VAO bound)

out vec2 v_uv;

void main() {
    // Vertices at NDC corners via gl_VertexID trick
    vec2 pos;
    pos.x = float((gl_VertexID & 1) << 2) - 1.0;
    pos.y = float((gl_VertexID & 2) << 1) - 1.0;
    v_uv  = pos * 0.5 + 0.5;
    gl_Position = vec4(pos, 0.0, 1.0);
}