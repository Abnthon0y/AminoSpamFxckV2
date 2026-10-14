#version 120
/* AoiGlitch — composite: pastel fog/haze, Japanese text on the sky, light shafts.

   Buffer setup (parsed by Iris/OptiFine from this comment):
   const int colortex0Format = RGBA16F;
   const int colortex2Format = RGBA8;
   const int colortex3Format = RGBA16F;
   const int colortex4Format = RGBA16F;
*/
const bool colortex2Clear = true;
const vec4 colortex2ClearColor = vec4(0.0, 0.0, 0.0, 0.0);

/* DRAWBUFFERS:0 */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/atmosphere.glsl"
#include "/lib/kanji.glsl"

uniform sampler2D colortex0;
uniform sampler2D colortex2;
uniform sampler2D depthtex0;

// Glyph atlas. Iris binds it by name (customTexture.jpTextAtlas),
// OptiFine by the classic slot (texture.composite.colortex12).
#ifdef IS_IRIS
uniform sampler2D jpTextAtlas;
#else
uniform sampler2D colortex12;
#define jpTextAtlas colortex12
#endif

varying vec2 texcoord;

#ifdef GODRAYS
// Screen-space light shafts (an approximation of volumetric scattering):
// march from the pixel towards the sun (or moon) on screen and count how much
// open sky (depth == 1) lies on the way. Trees, terrain and the hand block
// it, so soft beams fall through every gap. Returns 0..1.
float lightShafts(vec2 uv, vec2 lightUv) {
    const int STEPS = 20;
    vec2 delta = (lightUv - uv) / float(STEPS);
    vec2 suv = uv + delta * ign(gl_FragCoord.xy);        // dithered start, no banding
    float acc = 0.0;
    float wsum = 0.0;
    float w = 1.0;
    for (int i = 0; i < STEPS; i++) {
        float inside = step(0.0, suv.x) * step(suv.x, 1.0) * step(0.0, suv.y) * step(suv.y, 1.0);
        acc += step(0.99999, texture2D(depthtex0, suv).r) * inside * w;
        wsum += w;
        w *= 0.94;                                        // nearer samples count more
        suv += delta;
    }
    return acc / wsum;
}
#endif

void main() {
    vec3 col = texture2D(colortex0, texcoord).rgb;
    float depth = texture2D(depthtex0, texcoord).r;

    vec4 vp = gbufferProjectionInverse * vec4(vec3(texcoord, depth) * 2.0 - 1.0, 1.0);
    vp.xyz /= vp.w;
    vec3 worldDir = normalize(mat3(gbufferModelViewInverse) * vp.xyz);
    vec3 haze = getHazeColor(worldDir, getSunDirWorld(), fogColor, rainStrength);

#if SKY_TEXT > 0
    // evaluated for every pixel (uniform control flow -> valid derivatives)
    vec3 txt = skyTextLayer(worldDir, frameTimeCounter, gl_FragCoord.xy, jpTextAtlas);
#endif

    if (depth < 1.0) {
        float dist = length(vp.xyz);
        if (isEyeInWater == 1) {
            col = mix(col, vec3(0.05, 0.12, 0.35) * (0.4 + 0.6 * luma(fogColor) * 2.0), 1.0 - exp(-dist / 22.0));
        } else if (isEyeInWater == 2) {
            col = mix(col, vec3(0.95, 0.38, 0.06), 1.0 - exp(-dist * 1.2));
        } else if (isEyeInWater == 3) {
            col = mix(col, vec3(0.85, 0.90, 0.97), 1.0 - exp(-dist * 0.8));
        } else {
            float worldY = (mat3(gbufferModelViewInverse) * vp.xyz).y
                         + gbufferModelViewInverse[3].y + cameraPosition.y;
            col = mix(col, haze, getFogFactor(dist, worldY, far, rainStrength));
        }
    } else {
        vec4 skyInfo = texture2D(colortex2, texcoord);   // r text mask, g sky drawn
        // pixels no sky geometry covered (vanilla leaves them in the clear
        // colour, e.g. just above / below the horizon): fill with haze
        col = mix(col, haze, 1.0 - skyInfo.g);
#if SKY_TEXT > 0
        // MASK = pattern mask from the sky shader (blue zones only)
        //      x colour mask: smoothstep on the "blueness" of the final colour,
        //        so white rays, clouds, haze, the sun and rainy skies stay clean
        float blueness = (col.b - max(col.r, col.g)) / max(col.b, 1e-3);
        float mask = skyInfo.r * smoothstep(0.10, 0.30, blueness) * float(isEyeInWater == 0);
        float a = txt.x * mask * SKY_TEXT_OPACITY;
        col = mix(col, vec3(1.0), a);
        // glitch: inverted cells = white block with the glyph cut out
        col = mix(col, mix(vec3(1.0), col, txt.z), txt.y * mask * SKY_TEXT_OPACITY);
#endif
    }

#ifdef GODRAYS
    vec3 lightV = normalize(shadowLightPosition);         // sun by day, moon by night
    vec4 lc = gbufferProjection * vec4(lightV * 100.0, 1.0);
    if (lc.w > 0.0 && isEyeInWater == 0) {
        float sunH = dot(normalize(sunPosition), normalize(upPosition));
        float day = smoothstep(-0.10, 0.15, sunH);
        float rays = lightShafts(texcoord, lc.xy / lc.w * 0.5 + 0.5);
        // strongest when looking towards the light, fades away from it
        float facing = pow(max(dot(normalize(vp.xyz), lightV), 0.0), 4.0);
        // over open sky the bloom already glows: keep only a faint veil there,
        // the beams are meant for the air in front of trees and terrain
        float onSky = step(1.0, depth);
        vec3 rayCol = sunLightColor(sunH) * mix(0.25, 1.0, day);
        col += rayCol * rays * facing * mix(1.0, 0.3, onSky)
             * GODRAYS_STRENGTH * 0.4 * (1.0 - rainStrength);
    }
#endif

    gl_FragData[0] = vec4(col, 1.0);
}
