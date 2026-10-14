#version 120
/* AoiGlitch — shadow pass (fragment): alpha-tested depth only. */

/* DRAWBUFFERS:0 */

#include "/lib/settings.glsl"

uniform sampler2D texture;

varying vec2 texcoord;
varying vec4 glcolor;

void main() {
    vec4 col = texture2D(texture, texcoord);
    if (col.a < 0.1) discard;            // texture alpha only: vertex alpha is AO
    gl_FragData[0] = vec4(col.rgb * glcolor.rgb, 1.0);
}
