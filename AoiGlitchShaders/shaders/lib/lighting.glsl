#ifndef AOI_LIGHTING
#define AOI_LIGHTING
/* =========================================================================
   AoiGlitch — soft, living "dreamy" lighting for gbuffers programs.
   Needs: common.glsl, settings.glsl, uniforms.glsl

   Base = vanilla lightmap (day/night, torches, night vision, gamma all keep
   working). On top of it, everything stays soft and close to white:
     * sun shadows only attenuate:  shade = 1 - DARKNESS * sky * (1 - sunVis)
     * the light changes colour over the day (golden hour, warm noon,
       blue moonlight) and the shade gets the complementary lavender,
     * drifting light patches (soft "cloud shadows") slide over the land,
     * backlit leaves and grass glow, torches breathe a warm pool of light.
   ========================================================================= */
#include "/lib/shadow_distort.glsl"
#include "/lib/params.glsl"
#include "/lib/atmosphere.glsl"

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

    // penumbra of ~0.35 block x SHADOW_SOFTNESS, in distorted shadow-map uv
    float radius = SHADOW_SOFTNESS * 0.35 / (2.0 * shadowDistance) / df;
    radius = clamp(radius, 0.5 / float(shadowMapResolution), 32.0 / float(shadowMapResolution));
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

// Drifting soft patches of light and shade, like the shadows of clouds under
// the patterned sky: a thin FBM layer at y = 220 is projected onto the ground
// along the light direction and scrolled by the wind (~2 blocks/s).
// Returns 1 in the bright patches, 0 in the shaded ones, very wide edges.
float lightPatches(vec3 worldPos, vec3 lightDirW, float t, vec2 wind) {
    vec2 p = worldPos.xz + lightDirW.xz * (220.0 - worldPos.y) / max(lightDirW.y, 0.15);
    p = p * 0.006 + wind * t * 0.012;
    float n = fbm3(p) + 0.5 * fbm3(p * 2.3 + 7.1);
    return smoothstep(-0.10, 0.35, n);
}

// albedo     : texture * vertex colour (no AO)
// lm         : lightmap coordinates (gl_TextureMatrix[1] * gl_MultiTexCoord1)
// ao         : vanilla ambient occlusion (vertex alpha with separateAo=true)
// foliage    : 1 for thin, translucent geometry (plants), 0.5 leaves, 0 solid
// worldLit   : 1 = world geometry (shadows + light patches), 0 = first-person hand
vec3 dreamLighting(vec3 albedo, vec2 lm, float ao, vec3 viewNormal, vec3 playerPos,
                   float foliage, vec2 fragCoord, float worldLit) {
    vec3 vanilla = texture2D(lightmap, lm).rgb;
    float sky = clamp((lm.y - 0.03125) * 1.0667, 0.0, 1.0);
    float block = clamp((lm.x - 0.03125) * 1.0667, 0.0, 1.0);
    vec3 worldNormal = mat3(gbufferModelViewInverse) * viewNormal;
    vec3 worldPos = playerPos + cameraPosition;
    vec3 lightDirV = normalize(shadowLightPosition);
    vec3 lightDirW = mat3(gbufferModelViewInverse) * lightDirV;
    float sunH = dot(normalize(sunPosition), normalize(upPosition));
    float day = smoothstep(-0.10, 0.15, sunH);

    // wrapped diffuse: the terminator is a wide soft gradient, never a hard cut
    float NdotL = dot(viewNormal, lightDirV);
    float diffuse = clamp((NdotL + 0.55) / 1.55, 0.0, 1.0);
    diffuse = mix(diffuse, 0.8, foliage);

    float shadow = 1.0;
#ifdef SHADOWS
    if (worldLit > 0.5) shadow = softShadow(playerPos, worldNormal, fragCoord);
#endif
#ifdef LIGHT_PATCHES
    if (worldLit > 0.5) {
        float patches = lightPatches(worldPos, lightDirW, frameTimeCounter, getWindDirection());
        shadow *= mix(1.0 - LIGHT_PATCHES_STRENGTH, 1.0, patches);
    }
#endif
    float sunVis = diffuse * shadow;

    float lightStrength = mix(0.35, 1.0, day) * (1.0 - 0.75 * rainStrength);
    float shade = 1.0 - SHADOW_DARKNESS * sky * lightStrength * (1.0 - sunVis);

    // colour temperature: the lit side takes the colour of the light (golden
    // hour, warm noon, blue moon), the shade the complementary lavender/violet
    vec3 sunCol = sunLightColor(sunH);
    float golden = (1.0 - smoothstep(0.05, 0.40, sunH)) * day;
    vec3 shadeCol = mix(vec3(0.88, 0.91, 1.08), vec3(0.94, 0.84, 1.10), golden);
    vec3 tint = mix(shadeCol, sunCol * 1.05, sunVis);
    tint = mix(vec3(1.0), tint, sky * mix(0.45, 1.0, day) * (1.0 - 0.8 * rainStrength));
    // sky from above, warm bounce from the ground below
    tint *= mix(vec3(1.04, 0.99, 0.95), vec3(0.98, 1.0, 1.03), worldNormal.y * 0.5 + 0.5);

    float softAo = mix(1.0, ao, AO_STRENGTH);
    vec3 light = vanilla * shade * softAo * tint * (1.0 + 0.14 * sunVis * day * sky);

#ifdef TORCH_FLICKER
    // warm pools around light sources that gently breathe; the flicker is a
    // smooth function of time AND position, so neighbouring torches differ
    float flick = 0.90 + 0.06 * sin(frameTimeCounter * 8.3 + worldPos.x * 0.7 + worldPos.z * 0.9)
                       + 0.04 * sin(frameTimeCounter * 13.1 + worldPos.y * 0.8);
    light += vec3(1.0, 0.68, 0.42) * pow(block, 3.0) * 0.22 * flick * (1.0 - 0.6 * sky * day);
#endif

    // translucency: leaves and grass seen against the light glow with its colour
    float back = pow(max(dot(normalize(playerPos), lightDirW), 0.0), 5.0);
    light += sunCol * back * foliage * shadow * sky * day * FOLIAGE_GLOW * 0.6;

    return albedo * light;
}

#endif
