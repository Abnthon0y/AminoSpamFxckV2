#version 120
/* AoiGlitch — gbuffers_terrain (fragment): soft dreamy lighting. */

/* DRAWBUFFERS:0 */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/lighting.glsl"

uniform sampler2D texture;

varying vec2 texcoord;
varying vec2 lmcoord;
varying vec4 glcolor;
varying vec3 viewNormal;
varying vec3 playerPos;
varying float foliage;
varying float emissive;

void main() {
    vec4 albedo = texture2D(texture, texcoord);
    if (albedo.a < 0.1) discard;
    albedo.rgb *= glcolor.rgb;

    vec3 col = dreamLighting(albedo.rgb, lmcoord, glcolor.a, normalize(viewNormal),
                             playerPos, foliage, gl_FragCoord.xy, 1.0);
    // light sources push their bright texels a bit higher -> they bloom
    col *= 1.0 + emissive * 0.6 * smoothstep(0.5, 0.9, luma(albedo.rgb));

    gl_FragData[0] = vec4(col, albedo.a);
}
