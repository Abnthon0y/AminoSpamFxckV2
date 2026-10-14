#ifndef AOI_FOLIAGE
#define AOI_FOLIAGE
/* =========================================================================
   AoiGlitch — vertex animation of plants and leaves (vertex shaders only).
   Needs: common.glsl, settings.glsl
   All offsets are functions of CONTINUOUS world position, so a vertex shared
   by two neighbouring blocks moves identically in both -> no cracks.
   ========================================================================= */

/* ---- the global wind "canvas" --------------------------------------------
   One smooth vector field for the whole world:
     gust  = travelling wave along the wind direction (bands of stronger wind
             sweeping across the meadow at ~6 blocks/s),
     sway  = faster oscillation whose phase changes smoothly in space,
     flutter = small 3D variation so neighbouring plants are not in lockstep. */
vec3 windCanvas(vec3 wp, float t, vec2 dir) {
    vec2 perp = vec2(-dir.y, dir.x);
    float along = dot(wp.xz, dir);
    float across = dot(wp.xz, perp);
    float gust = 0.5 + 0.5 * sin(along * 0.21 - t * 1.25 + 0.6 * sin(across * 0.13));
    gust *= gust;
    float sway = sin(along * 0.85 - t * 2.6 + across * 0.35);
    float flutter = sin(dot(wp, vec3(1.7, 0.9, 1.3)) - t * 4.1);
    vec2 h = dir * ((0.25 + 0.75 * gust) * (0.7 + 0.3 * sway) + 0.08 * flutter)
           + perp * 0.18 * sway * gust;
    return vec3(h.x, 0.0, h.y);
}

/* ---- grass & flowers: bending ----------------------------------------------
   hw = height weight of the vertex: 0 at the root, 1 at the tip
        (single plants: 0/1 from the texture coordinate; double plants:
         lower half 0..0.5, upper half 0.5..1).
   Offset ~ wind * hw^2  (a cantilever bends quadratically: root fixed,
   tip moves the most), and the tip drops a little (|offset|^2 / 2H) so the
   stem keeps roughly its length instead of stretching.                    */
vec3 plantWave(vec3 wp, float t, float hw, float plantH, vec2 dir, float strength) {
    vec3 off = windCanvas(wp, t, dir) * strength * 0.17 * plantH * hw * hw;
    off.y -= dot(off.xz, off.xz) / (2.0 * max(plantH * hw, 0.1));
    return off;
}

/* ---- leaves: "jelly" -------------------------------------------------------
   d(P,t) = A * sum_i a_i * e_i * sin(k_i . P - w_i t)
     |k_i| ~ 8..10 rad/block -> wavelength < 1 block -> several wobble nodes
     inside every block (volume), yet continuous across blocks (no cracks).
     w_i = 2PI * freq * {1.00, 1.27, 0.83} -> fast, non-repeating jiggle.
     e_i partly along k_i -> compression waves = squash & stretch of jelly.
   Normal: for x' = x + d(x), the deformed normal to first order is
     n' = normalize(n - J^T n),  J = sum_i a_i A cos(phase_i) e_i k_i^T
   so J^T n = sum_i a_i A cos(phase_i) (e_i . n) k_i   (exact derivative). */
vec3 jellyOffset(vec3 wp, float t, float amp, float freq, vec3 n, out vec3 nOut) {
    const vec3 K1 = vec3( 6.1,  4.3,  5.2);
    const vec3 K2 = vec3(-4.7,  6.6,  3.9);
    const vec3 K3 = vec3( 5.5, -3.1, -7.0);
    const vec3 E1 = vec3( 0.28,  0.94,  0.19);
    const vec3 E2 = vec3( 0.91,  0.18, -0.37);
    const vec3 E3 = vec3(-0.27,  0.36,  0.89);
    float w = TAU * freq;
    float p1 = dot(K1, wp) - w * 1.00 * t;
    float p2 = dot(K2, wp) - w * 1.27 * t;
    float p3 = dot(K3, wp) - w * 0.83 * t;
    vec3 d = amp * (E1 * sin(p1) + E2 * (0.8 * sin(p2)) + E3 * (0.6 * sin(p3)));
    vec3 jtn = amp * (K1 * (dot(E1, n) * cos(p1))
                    + K2 * (0.8 * dot(E2, n) * cos(p2))
                    + K3 * (0.6 * dot(E3, n) * cos(p3)));
    nOut = normalize(n - jtn);
    return d;
}

// Leaves: the whole canopy drifts with the wind canvas like one sheet, and
// the jelly rides on top of it; gusts make the jelly wobble harder.
// tWind = time * windSpeed (canvas), tJelly = real seconds (freq is in Hz).
vec3 leavesWave(vec3 wp, float tWind, float tJelly, vec2 dir, float strength, float amp,
                float freq, vec3 n, out vec3 nOut) {
    vec3 sheet = windCanvas(wp, tWind, dir);
    float gust = length(sheet.xz);
    vec3 jelly = jellyOffset(wp, tJelly, amp * (0.6 + 0.6 * gust), freq, n, nOut);
    return sheet * 0.045 * strength + jelly;
}

#endif
