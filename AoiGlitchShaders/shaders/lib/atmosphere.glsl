#ifndef AOI_ATMOSPHERE
#define AOI_ATMOSPHERE
/* =========================================================================
   AoiGlitch — haze / fog colour and density (no uniforms, pure functions).
   Needs: common.glsl, settings.glsl
   ========================================================================= */

// Pastel haze colour. Starts from the vanilla fog colour (so it follows the
// biome, the dimension, the weather and the time of day), pushes it towards
// pastel and adds a warm forward-scattering lobe around the sun (image 10).
vec3 getHazeColor(vec3 worldDir, vec3 sunDir, vec3 fogCol, float rain) {
    float bright = smoothstep(0.12, 0.55, luma(fogCol)); // 0 at night / Nether / End
    vec3 haze = mix(fogCol, vec3(luma(fogCol)), 0.15);
    haze += (vec3(1.0) - haze) * 0.12 * bright;          // lift towards white = pastel
    haze *= vec3(1.0, 0.975, 1.02);                      // hint of lavender

    float toSun = max(dot(worldDir, sunDir), 0.0);
    float lowSun = 1.0 - smoothstep(0.05, 0.45, sunDir.y);
    vec3 lobeCol = mix(vec3(1.0, 0.93, 0.80), vec3(1.0, 0.76, 0.66), lowSun);
    float lobe = pow(toSun, 6.0) * 0.30 + pow(toSun, 40.0) * 0.35;
    haze += lobeCol * lobe * bright * (1.0 - rain);

    haze = mix(haze, vec3(luma(haze)) * vec3(0.92, 0.95, 1.0), rain * 0.6);
    return haze;
}

// Fog amount for a terrain pixel.
//  * exponential haze with a height falloff (valleys hazier than peaks),
//  * plus a smoothstep "by depth" that dissolves everything before the
//    render-distance edge, so far chunks melt into the sky (image 11).
float getFogFactor(float dist, float worldY, float farPlane, float rain) {
    float density = 0.0032 * FOG_DENSITY * (1.0 + 2.5 * rain);
    float heightFalloff = exp(-max(worldY - 62.0, 0.0) * 0.012);
    float f = 1.0 - exp(-dist * density * mix(0.45, 1.0, heightFalloff));
    f = max(f, smoothstep(farPlane * 0.55, farPlane * 0.98, dist) * step(0.001, FOG_DENSITY));
    return clamp(f, 0.0, 1.0);
}

#endif
