#version 120
/* AoiGlitch — composite2: bloom blur.
   colortex3 is mip-mapped (declared below -> Iris/OptiFine build the mip
   chain right before this pass). Mip level i is the bright pass averaged over
   2^i x 2^i pixels; a 3x3 tent filter on each of the levels 1..6 and a
   weighted sum gives a wide, smooth, Gaussian-like glow for 54 taps.        */

/* DRAWBUFFERS:4 */

const bool colortex3MipmapEnabled = true;

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"

uniform sampler2D colortex3;

varying vec2 texcoord;

void main() {
    vec3 bloom = vec3(0.0);
#ifdef BLOOM
    vec2 px = 1.0 / vec2(viewWidth, viewHeight);
    float total = 0.0;
    for (int i = 1; i <= 6; i++) {
        float lod = float(i);
        vec2 o = px * exp2(lod);
        vec3 s = texture2D(colortex3, texcoord, lod).rgb * 4.0;
        s += (texture2D(colortex3, texcoord + vec2( o.x, 0.0), lod).rgb
            + texture2D(colortex3, texcoord + vec2(-o.x, 0.0), lod).rgb
            + texture2D(colortex3, texcoord + vec2(0.0,  o.y), lod).rgb
            + texture2D(colortex3, texcoord + vec2(0.0, -o.y), lod).rgb) * 2.0;
        s += texture2D(colortex3, texcoord + o, lod).rgb
           + texture2D(colortex3, texcoord - o, lod).rgb
           + texture2D(colortex3, texcoord + vec2(o.x, -o.y), lod).rgb
           + texture2D(colortex3, texcoord + vec2(-o.x, o.y), lod).rgb;
        float w = 1.0 + 0.35 * lod;          // favour the wide, dreamy halos
        bloom += s / 16.0 * w;
        total += w;
    }
    bloom /= total;
#endif
    gl_FragData[0] = vec4(bloom, 1.0);
}
