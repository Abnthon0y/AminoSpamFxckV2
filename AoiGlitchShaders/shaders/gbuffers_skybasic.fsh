#version 120
/* AoiGlitch — gbuffers_skybasic: fully procedural sky.
   The vanilla sky colour is ignored; every pixel computes its world-space view
   direction and evaluates getCustomSky() (lib/sky.glsl).
   colortex0 = sky colour (HDR sun for bloom)
   colortex2 = r: where Japanese text may appear, g: "sky was drawn here"     */

/* DRAWBUFFERS:02 */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/atmosphere.glsl"
#include "/lib/sky.glsl"

varying vec4 glcolor;

void main() {
#ifdef MC_RENDER_STAGE_STARS
    if (renderStage == MC_RENDER_STAGE_STARS) discard;      // we draw our own stars
#endif
#ifdef MC_RENDER_STAGE_SUNSET
    if (renderStage == MC_RENDER_STAGE_SUNSET) discard;     // and our own sunset
#endif
    // fallback for loaders without render stages: vanilla stars are grey + translucent
    if (glcolor.a < 0.99 && abs(glcolor.r - glcolor.g) < 0.002 && abs(glcolor.g - glcolor.b) < 0.002) discard;

    vec2 uv = gl_FragCoord.xy / vec2(viewWidth, viewHeight);
    vec4 vp = gbufferProjectionInverse * vec4(uv * 2.0 - 1.0, 1.0, 1.0);
    vec3 worldDir = normalize(mat3(gbufferModelViewInverse) * (vp.xyz / vp.w));

    float textMask;
    vec3 sky = getCustomSky(worldDir, getSunDirWorld(), frameTimeCounter, skyStyle, getSkyMix(),
                            skyWarpStrength, skySpeed, fogColor, rainStrength, textMask);

    gl_FragData[0] = vec4(sky, 1.0);
    gl_FragData[1] = vec4(textMask, 1.0, 0.0, 1.0);
}
