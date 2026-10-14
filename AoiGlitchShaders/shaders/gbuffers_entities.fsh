#version 120
/* AoiGlitch — gbuffers_entities (fragment): gray glitch + white noise on players. */

/* DRAWBUFFERS:0 */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/lighting.glsl"
#include "/lib/glitch.glsl"

uniform sampler2D texture;

varying vec2 texcoord;
varying vec2 lmcoord;
varying vec4 glcolor;
varying vec3 viewNormal;
varying vec3 playerPos;
varying float glitchOn;

void main() {
    vec4 base = texture2D(texture, texcoord) * glcolor;
    if (base.a < 0.1) discard;                       // silhouette = texture alpha
    vec3 albedo = mix(base.rgb, entityColor.rgb, entityColor.a);   // hurt flash

    vec3 col;
    if (glitchOn > 0.5) {
        float burst = min(glitchBurst(frameTimeCounter) * glitchIntensity, 1.0);
        // tearing: shift the texture lookup of some screen slices sideways
        float off = glitchSliceOffset(gl_FragCoord.xy, frameTimeCounter, burst);
        vec4 shifted = texture2D(texture, texcoord + vec2(off * 0.09 * glitchIntensity, 0.0)) * glcolor;
        vec3 src = shifted.a > 0.1 ? shifted.rgb : albedo;   // never punch holes
        col = glitchStyle(src, gl_FragCoord.xy, frameTimeCounter, burst, noiseAmount);
        // stays gray: lit by the luminance of the lightmap only
        col *= mix(1.0, luma(texture2D(lightmap, lmcoord).rgb), 0.6);
    } else {
        col = dreamLighting(albedo, lmcoord, 1.0, normalize(viewNormal), playerPos, 0.0, gl_FragCoord.xy, 1.0);
    }
    gl_FragData[0] = vec4(col, base.a);
}
