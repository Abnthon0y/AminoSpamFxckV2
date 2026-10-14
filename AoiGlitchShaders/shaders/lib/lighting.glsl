#ifndef AOI_LIGHTING
#define AOI_LIGHTING
/* =========================================================================
   AoiGlitch — soft "dreamy" lighting for gbuffers programs.
   Needs: common.glsl, settings.glsl, uniforms.glsl
   Idea: keep the vanilla lightmap (day/night, torches, night vision, gamma
   all keep working) and only let sun shadows *attenuate* it a little:
     shade = 1 - SHADOW_DARKNESS * skyLight * (1 - sunVisibility)
   so a full shadow never goes darker than ~60 %: soft, low-contrast (img 9).
   ========================================================================= */
#include "/lib/shadow_distort.glsl"

uniform sampler2D lightmap;
#ifdef SHADOWS
uniform sampler2D shadowtex1;
#endif

#ifdef SHADOWS
// 12-tap PCF on a Vogel (golden-angle) disk, rotated per pixel with
// interleaved gradient noise -> wide, grainy-soft penumbrae, no banding.
float softShadow(vec3 playerPos, vec3 worldNormal, vec2 fragCoord) {
    float dist = length(playerPos);
    float fade = smoothstep(shadowDistance * 0.75, shadowDistance * 0.95, dist);

    vec4 clip0 = shadowProjection * (shadowModelView * vec4(playerPos, 1.0));
    float df = shadowDistortFactor(clip0.xy);
    // normal offset proportional to the (distorted) shadow texel size -> no acne
    float texelWorld = 2.0 * shadowDistance / float(shadowMapResolution);
    vec3 offsetPos = playerPos + worldNormal * texelWorld * df * 1.6;
    vec4 clip = shadowProjection * (shadowModelView * vec4(offsetPos, 1.0));
    vec3 sc = distortShadow(clip.xyz) * 0.5 + 0.5;

    // penumbra of ~0.35 block, converted to distorted shadow-map uv
    float radius = SHADOW_SOFTNESS * 0.35 / (2.0 * shadowDistance) / df;
    radius = clamp(radius, 0.5 / float(shadowMapResolution), 24.0 / float(shadowMapResolution));
    float rot = ign(fragCoord) * TAU;

    float lit = 0.0;
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        float r = sqrt((fi + 0.5) / 12.0);
        float a = fi * 2.39996 + rot;
        vec2 o = vec2(cos(a), sin(a)) * r * radius;
        lit += step(sc.z - 0.00005, texture2D(shadowtex1, sc.xy + o).r);
    }
    lit /= 12.0;

    float outside = step(1.0, max(max(sc.x, sc.y), sc.z)) + step(min(min(sc.x, sc.y), sc.z), 0.0);
    return mix(lit, 1.0, max(fade, clamp(outside, 0.0, 1.0)));
}
#endif

// albedo     : texture * vertex colour (no AO)
// lm         : lightmap coordinates (gl_TextureMatrix[1] * gl_MultiTexCoord1)
// ao         : vanilla ambient occlusion (vertex alpha with separateAo=true)
// foliage    : 1 for thin, translucent geometry (plants, leaves)
vec3 dreamLighting(vec3 albedo, vec2 lm, float ao, vec3 viewNormal, vec3 playerPos,
                   float foliage, vec2 fragCoord) {
    vec3 vanilla = texture2D(lightmap, lm).rgb;
    float sky = clamp((lm.y - 0.03125) * 1.0667, 0.0, 1.0);
    vec3 worldNormal = mat3(gbufferModelViewInverse) * viewNormal;

    // wrapped diffuse: soft terminator instead of a hard cut at 90 degrees
    float NdotL = dot(viewNormal, normalize(shadowLightPosition));
    float diffuse = clamp((NdotL + 0.45) / 1.45, 0.0, 1.0);
    diffuse = mix(diffuse, 0.8, foliage);

    float shadow = 1.0;
#ifdef SHADOWS
    shadow = softShadow(playerPos, worldNormal, fragCoord);
#endif
    float sunVis = diffuse * shadow;

    float day = smoothstep(-0.10, 0.15, dot(normalize(sunPosition), normalize(upPosition)));
    float lightStrength = mix(0.35, 1.0, day) * (1.0 - 0.75 * rainStrength);
    float shade = 1.0 - SHADOW_DARKNESS * sky * lightStrength * (1.0 - sunVis);

    // colour temperature: warm sunlit side, cool lavender shade
    vec3 tint = mix(vec3(0.90, 0.92, 1.06), vec3(1.06, 1.00, 0.90), sunVis);
    tint = mix(vec3(1.0), tint, sky * day * (1.0 - rainStrength));

    float softAo = mix(1.0, ao, AO_STRENGTH);
    float hemi = 0.92 + 0.08 * worldNormal.y;
    float glow = 1.0 + 0.12 * sunVis * day * sky;
    return albedo * vanilla * (shade * softAo * hemi * glow) * tint;
}

#endif
