#ifndef AOI_SHADOW_DISTORT
#define AOI_SHADOW_DISTORT
// Shadow-map distortion shared by shadow.vsh (writing) and lighting.glsl
// (reading): texels are concentrated near the player, z range is extended.
const float SHADOW_DISTORT = 0.85;

float shadowDistortFactor(vec2 p) {
    return length(p) * SHADOW_DISTORT + (1.0 - SHADOW_DISTORT);
}

vec3 distortShadow(vec3 p) {
    return vec3(p.xy / shadowDistortFactor(p.xy), p.z * 0.25);
}
#endif
