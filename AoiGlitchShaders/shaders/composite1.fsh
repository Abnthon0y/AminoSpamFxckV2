#version 120
/* AoiGlitch — composite1: bloom bright pass.
   Only the part of the luminance ABOVE the threshold glows:
       bright = colour * max(L - T, 0) / L        (with a small soft knee)
   -> white blocks / pale sky add a faint halo, while the HDR sun (L ~ 4),
   lava and light sources (boosted in gbuffers_terrain) glow strongly.      */

/* DRAWBUFFERS:3 */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"

uniform sampler2D colortex0;

varying vec2 texcoord;

void main() {
#ifdef BLOOM
    vec3 c = texture2D(colortex0, texcoord).rgb;
    float l = max(luma(c), 1e-4);
    float knee = 0.1;
    float x = clamp(l - BLOOM_THRESHOLD + knee, 0.0, 2.0 * knee);
    float excess = max(x * x / (4.0 * knee), l - BLOOM_THRESHOLD);   // soft knee
    gl_FragData[0] = vec4(c * (excess / l), 1.0);
#else
    gl_FragData[0] = vec4(0.0);
#endif
}
