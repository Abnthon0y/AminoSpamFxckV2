#version 120
/* AoiGlitch — composite3: add bloom, then the distance mosaic (image 8). */

/* DRAWBUFFERS:0 */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/pixelate.glsl"

uniform sampler2D colortex0;
uniform sampler2D colortex4;
uniform sampler2D depthtex0;

varying vec2 texcoord;

void main() {
    vec2 viewSize = vec2(viewWidth, viewHeight);
    vec2 fc = gl_FragCoord.xy;
    vec3 col = texture2D(colortex0, texcoord).rgb;
    vec2 bloomUv = texcoord;

#ifdef PIXELATION
    vec3 tile = chooseTile(depthtex0, fc, viewSize, gbufferProjectionInverse);
    float s = tile.x;
    float blend = tile.y;
    if (s > 1.5 || blend > 0.001) {
        vec3 own = s > 1.5 ? tileColor(colortex0, fc, s, viewSize) : col;
        vec3 parent = tileColor(colortex0, fc, s * 2.0, viewSize);
        col = mix(own, parent, blend);
        col = applyGrout(col, fc, s, 1.0 - blend);
        col = applyGrout(col, fc, s * 2.0, blend);
        float bs = blend > 0.5 ? s * 2.0 : s;
        bloomUv = (floor(fc / bs) + 0.5) * bs / viewSize;
    }
#endif

#ifdef BLOOM
    col += texture2D(colortex4, bloomUv).rgb * bloomIntensity;
#endif
    gl_FragData[0] = vec4(col, 1.0);
}
