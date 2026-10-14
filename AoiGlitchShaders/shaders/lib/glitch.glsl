#ifndef AOI_GLITCH
#define AOI_GLITCH
/* =========================================================================
   AoiGlitch — gray glitch + white noise for players (pure functions).
   Needs: common.glsl, settings.glsl
   ========================================================================= */

// TV static: one independent random value per pixel per "video frame".
// 24 frames/s, cycled through 97 seeds so hash inputs stay small (precision).
float whiteNoise(vec2 fragCoord, float t) {
    float frame = mod(floor(t * 24.0), 97.0);
    return hash12(fragCoord + vec2(frame * 37.0, frame * 17.0));
}

// Halftone dots like image 7: a 45-degree dot screen whose dot radius follows
// a slowly drifting cloudy FBM -> patches of denser / sparser dots.
float halftoneDots(vec2 fragCoord, float t, float cellPx) {
    vec2 p = rot2(0.785398) * fragCoord / cellPx;
    vec2 cell = floor(p);
    vec2 f = fract(p) - 0.5;
    float cloud = clamp(0.5 + 1.1 * fbm3(cell * 0.07 + vec2(t * 0.35, -t * 0.22)), 0.0, 1.0);
    float radius = cloud * 0.46;
    return 1.0 - smoothstep(radius - 0.07, radius + 0.07, length(f));   // 1 = black dot
}

// Rare, abrupt "signal drop". Time is cut in slots of 0.5 s / GLITCH_RATE;
// ~18 % of the slots contain a burst lasting 4..17 % of the slot.
// Returns the burst strength (0 almost all the time).
float glitchBurst(float t) {
    float rate = 2.0 * GLITCH_RATE;
    float slot = floor(t * rate);
    float on = step(0.82, hash11(slot * 1.31 + 0.7));
    float dur = mix(0.08, 0.35, hash11(slot + 9.1));
    return on * step(fract(t * rate), dur) * mix(0.4, 1.0, hash11(slot + 4.4));
}

// Horizontal tearing: the screen is cut into slices of random height; during
// a burst some slices are shifted sideways. Returns an offset in [-0.5, 0.5].
float glitchSliceOffset(vec2 fragCoord, float t, float burst) {
    float vframe = mod(floor(t * 30.0), 97.0);
    float sliceH = mix(3.0, 22.0, hash11(vframe + 0.3));
    float slice = floor(fragCoord.y / sliceH);
    float h = hash12(vec2(slice, vframe));
    float moved = step(0.55, hash12(vec2(slice * 1.7, vframe + 3.0)));
    return (h - 0.5) * moved * burst;
}

// Final look: gray body + black halftone dots + white static flecks + scanlines.
vec3 glitchStyle(vec3 albedo, vec2 fragCoord, float t, float burst, float noiseAmt) {
    float gray = dot(albedo, vec3(0.299, 0.587, 0.114));
    gray = mix(gray, 0.55, 0.25);                          // flatten towards mid gray
    vec3 col = vec3(gray);

    float n = whiteNoise(fragCoord, t);
    float dots = halftoneDots(fragCoord, t, 6.0);
#if NOISE_STYLE == 0
    dots = 0.0;
#endif
#if NOISE_STYLE == 1
    n = 0.0;
#endif
    col = mix(col, vec3(0.04), dots * noiseAmt * 0.85);
    // threshold the static: step() turns smooth noise into hard white specks
    float specks = step(1.0 - 0.28 * noiseAmt - 0.5 * burst, n);
    col = mix(col, vec3(1.0), specks);
    // during a burst the body briefly drowns in full-strength static
    col = mix(col, vec3(n), burst * 0.6);
    col *= 0.90 + 0.10 * sin(fragCoord.y * PI * 0.5);     // scanlines
    return col;
}

#endif
