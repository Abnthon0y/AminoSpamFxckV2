#version 120
#define VERTEX_SHADER
/* AoiGlitch — gbuffers_skytextured: sun, moon, End sky, custom sky textures. */

varying vec2 texcoord;
varying vec4 glcolor;

void main() {
    gl_Position = ftransform();
    texcoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    glcolor = gl_Color;
}
