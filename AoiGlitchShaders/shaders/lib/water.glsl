#ifndef AOI_WATER
#define AOI_WATER
/* =========================================================================
   AoiGlitch — stylised water patterns (pure functions, world-anchored).
   Needs: common.glsl, settings.glsl
   Entry point: getStylizedWater(worldXZ, time, style, flowDir)
     style 0: ink marble     (image 3)  - nested domain warping + grain
     style 1: caustic net    (image 4)  - Worley F2-F1 lines
     style 2: ocean currents (image 5)  - anisotropic, advected warping
     style 3: marble with the caustic net drawn over it
   ========================================================================= */

const vec3 MARBLE_PAPER    = vec3(0.945, 0.940, 0.915);
const vec3 MARBLE_INK      = vec3(0.235, 0.475, 0.700);
const vec3 MARBLE_INK_DEEP = vec3(0.150, 0.350, 0.600);

const vec3 CAUSTIC_DEEP = vec3(0.125, 0.180, 0.640);
const vec3 CAUSTIC_LINE = vec3(0.930, 0.925, 0.800);

const vec3 CURRENT_FOAM = vec3(0.985, 0.945, 0.940);
const vec3 CURRENT_TEAL = vec3(0.200, 0.520, 0.600);
const vec3 CURRENT_DEEP = vec3(0.070, 0.300, 0.420);

// High-frequency "screen print" grain anchored to the water surface.
// It fades to 0.5 where one grain cell becomes smaller than a pixel,
// otherwise it would turn into sparkling aliasing in the distance.
float waterGrain(vec2 p, float freq) {
    vec2 gp = p * freq;
    float pixelsPerCell = 1.0 / max(length(fwidth(gp)), 1e-4);
    float g = vnoise(gp) * 0.6 + vnoise(gp * 2.7 + 3.1) * 0.4;
    return mix(0.5, g, smoothstep(0.8, 2.5, pixelsPerCell));
}

/* ---- image 3: ink marbling -------------------------------------------------
   f = fbm(p + k*r),  r = fbm2(p + k*q),  q = fbm2(p)   (Quilez domain warp)
   Stripes are iso-lines of f: sin(2PI * f * freq). The grain perturbs the
   threshold of the stripes, giving the grainy, printed edges of the reference. */
vec3 waterMarble(vec2 p, float t, float warpAmt, float grainAmt) {
    p *= 0.16;
    vec2 q = fbm2(p + vec2(0.0, t * 0.05));
    vec2 r = fbm2(p + 3.5 * warpAmt * q + vec2(1.7, 9.2) + vec2(0.13, 0.11) * t);
    float f = fbm(p + 3.5 * warpAmt * r);
    float stripes = 0.5 + 0.5 * sin(TAU * (f * 2.4 + 0.6 * r.x));
    float grain = waterGrain(p, 260.0) - 0.5;
    float ink = smoothstep(0.42, 0.58, stripes + grain * 0.45 * grainAmt);
    float deep = smoothstep(0.78, 0.96, stripes + grain * 0.2);
    vec3 col = mix(MARBLE_PAPER, MARBLE_INK, ink);
    col = mix(col, MARBLE_INK_DEEP, deep * 0.6);
    // ink spatter dots
    float dots = smoothstep(0.86, 0.90, vnoise(p * 90.0 + 7.0)) * (1.0 - ink);
    col = mix(col, MARBLE_INK, dots * 0.8 * grainAmt);
    col *= 1.0 - 0.10 * grainAmt * grain;
    return col;
}

/* ---- image 4: caustics -----------------------------------------------------
   Worley noise: F1 = distance to the nearest feature point, F2 = to the second.
   F2 - F1 == 0 exactly on the cell borders (Voronoi edges), so
   1 - smoothstep(0, w, F2 - F1) draws thin glowing lines; near the triple
   junctions F2-F1 stays small over a larger area -> bright "knots".
   Feature points orbit inside their cells -> the net moves like real light. */
float causticNet(vec2 p, float t, float warpAmt, out float halo) {
    p *= 0.42;
    p += warpAmt * 0.35 * fbm2(p * 0.6 + t * 0.07);         // organic, wobbly cells
    vec3 v1 = voronoi(p, t * 0.9);
    vec3 v2 = voronoi(p * 1.7 + vec2(3.1, 7.7), t * 1.2 + 2.0);
    float e1 = v1.y - v1.x;
    float e2 = v2.y - v2.x;
    float line1 = 1.0 - smoothstep(0.02, 0.09 + fwidth(e1), e1);
    float line2 = 1.0 - smoothstep(0.01, 0.05 + fwidth(e2), e2);
    halo = exp(-e1 * 6.0);
    return max(line1, line2 * 0.55);
}

vec3 waterCaustics(vec2 p, float t, float warpAmt, float grainAmt) {
    float halo;
    float net = causticNet(p, t, warpAmt, halo);
    // woven / cross-hatched texture of the lines (the reference looks printed on cloth)
    float weave = waterGrain(p, 40.0);
    net *= mix(1.0, 0.55 + 0.9 * weave, grainAmt);
    vec3 bg = CAUSTIC_DEEP * (0.88 + 0.30 * fbm3(p * 0.35 - t * 0.03));
    bg += vec3(0.05, 0.06, 0.12) * halo;
    return mix(bg, CAUSTIC_LINE, clamp(net + halo * halo * 0.15, 0.0, 1.0));
}

/* ---- image 5: directional currents ----------------------------------------
   Same warping idea, but in a frame aligned with the flow: the along-flow
   axis is stretched (x * 0.35) and advected (x - t * v), so the swirls become
   long parallel streaks drifting downstream. Three-tone ramp foam/teal/deep. */
vec3 waterCurrents(vec2 p, float t, vec2 flowDir, float warpAmt, float grainAmt) {
    p *= 0.12;
    vec2 fd = normalize(flowDir);
    vec2 fp = vec2(dot(p, fd), dot(p, vec2(-fd.y, fd.x)));
    fp.x = fp.x * 0.5 - t * 0.06;
    vec2 q = fbm2(fp * vec2(1.0, 1.6) + vec2(t * 0.02, 0.0));
    vec2 r = fbm2(fp + 2.0 * q + vec2(4.1, 1.7) - t * 0.015);   // second warp = curls
    float f = fbm(fp + 2.4 * warpAmt * r);
    float s = 0.5 + 0.5 * sin(TAU * (fp.y * 1.6 + f * 3.0 + q.x));
    s += (waterGrain(p, 300.0) - 0.5) * 0.35 * grainAmt;
    vec3 col = mix(CURRENT_FOAM, CURRENT_TEAL, smoothstep(0.38, 0.52, s));
    return mix(col, CURRENT_DEEP, smoothstep(0.70, 0.84, s));
}

vec3 getStylizedWater(vec2 worldXZ, float time, int style, vec2 flowDir) {
    vec2 p = worldXZ / WATER_SCALE;
    float t = time * WATER_SPEED;
    if (style == 1) return waterCaustics(p, t, WATER_WARP, WATER_GRAIN);
    if (style == 2) return waterCurrents(p, t, flowDir, WATER_WARP, WATER_GRAIN);
    vec3 col = waterMarble(p, t, WATER_WARP, WATER_GRAIN);
    if (style == 3) {
        float halo;
        float net = causticNet(p * 1.3, t, WATER_WARP, halo);
        col = mix(col * (1.0 - 0.15 * halo), vec3(1.0, 0.99, 0.94), net * 0.8);
    }
    return col;
}

#endif
