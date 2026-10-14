#version 120
#define VERTEX_SHADER
/* AoiGlitch — gbuffers_skybasic: the sky dome geometry (overworld only). */

varying vec4 glcolor;

void main() {
    gl_Position = ftransform();
    glcolor = gl_Color;
}
