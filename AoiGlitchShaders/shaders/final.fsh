#version 120
/* AoiGlitch — final: dreamy colour grading, vignette, film grain. */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/grading.glsl"

uniform sampler2D colortex0;

varying vec2 texcoord;

void main() {
    vec3 col = dreamGrade(texture2D(colortex0, texcoord).rgb);

    vec2 d = texcoord - 0.5;
    col *= 1.0 - VIGNETTE * smoothstep(0.15, 0.55, dot(d, d));

    float frame = mod(floor(frameTimeCounter * 24.0), 97.0);
    col += (hash12(gl_FragCoord.xy + frame * 13.0) - 0.5) * FILM_GRAIN;   // also de-bands

    gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
