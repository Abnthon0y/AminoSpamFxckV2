#ifndef AOI_GRADING
#define AOI_GRADING
/* =========================================================================
   AoiGlitch — "dreamy" colour grading (final pass).
   Needs: common.glsl, settings.glsl
   ========================================================================= */

// Soft shoulder: identity below 0.75, highlights (HDR sun, bloom) roll off
// exponentially towards 1 instead of clipping -> nothing burns out.
vec3 softClip(vec3 c) {
    const float k = 0.75;
    vec3 over = max(c - k, 0.0);
    return min(c, vec3(k)) + (1.0 - k) * (1.0 - exp(-over / (1.0 - k)));
}

vec3 dreamGrade(vec3 c) {
    c = softClip(c);
    float l = luma(c);

    // vibrance: boost saturation more for bright and for still-muted colours,
    // less for colours that are already saturated -> no burnt-out primaries
    float mx = max(c.r, max(c.g, c.b));
    float mn = min(c.r, min(c.g, c.b));
    float sat = (mx - mn) / max(mx, 1e-4);
    float boost = (COLOR_SATURATION - 1.0) * mix(0.5, 1.0, smoothstep(0.2, 0.75, l)) * (1.0 - sat);
    c = max(mix(vec3(l), c, 1.0 + boost), 0.0);

    // pastel: wash the highlights towards white, soften the contrast
    c = mix(c, vec3(1.0), PASTEL_AMOUNT * 0.30 * smoothstep(0.45, 1.0, l));
    c = mix(vec3(0.5), c, 1.0 - 0.10 * PASTEL_AMOUNT);

    // split toning: violet-blue shadows, peach highlights
    vec3 shadowTint = vec3(0.92, 0.94, 1.08);
    vec3 lightTint  = vec3(1.04, 1.00, 0.95);
    c *= mix(shadowTint, lightTint, smoothstep(0.1, 0.8, l));

    // lift: blacks become a soft lavender instead of pure black
    vec3 liftTint = vec3(0.62, 0.55, 1.0);
    c = c * (1.0 - SHADOW_LIFT) + SHADOW_LIFT * liftTint;

    return clamp(c, 0.0, 1.0);
}

#endif
