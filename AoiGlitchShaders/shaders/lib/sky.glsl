#ifndef AOI_SKY
#define AOI_SKY
/* =========================================================================
   AoiGlitch — procedural sky.
   Needs: common.glsl, settings.glsl, atmosphere.glsl
   Entry point: getCustomSky(...)   (pure function, no uniforms)

   Style A "burst"  (image 1): polar coordinates + domain-warped FBM rays,
                               misregistered orange/yellow rims, teardrops.
   Style B "ink"    (image 2): SDF crescents/arcs, thresholded noise,
                               log-polar Voronoi splinters, sky "windows".
   ========================================================================= */

// ---- palette (sRGB) ------------------------------------------------------
const vec3 SKY_BLUE       = vec3(0.150, 0.290, 0.780);  // ultramarine
const vec3 SKY_PERIWINKLE = vec3(0.415, 0.440, 0.900);
const vec3 SKY_WHITE      = vec3(0.945, 0.950, 0.955);
const vec3 SKY_LEMON      = vec3(0.900, 0.965, 0.560);  // soft yellow-green glow
const vec3 SKY_YELLOW     = vec3(1.000, 0.890, 0.150);
const vec3 SKY_ORANGE     = vec3(0.950, 0.380, 0.100);
const vec3 SKY_PEACH      = vec3(0.950, 0.850, 0.780);
const vec3 SKY_SILVER     = vec3(0.770, 0.790, 0.810);

const vec3 INK_PAPER   = vec3(0.955, 0.955, 0.948);
const vec3 INK_SMUDGE  = vec3(0.780, 0.790, 0.800);
const vec3 INK_BLACK   = vec3(0.010, 0.010, 0.012);
const vec3 INK_SKY_TOP = vec3(0.230, 0.510, 0.860);
const vec3 INK_SKY_LOW = vec3(0.560, 0.760, 0.950);
const vec3 INK_HALO    = vec3(0.700, 0.820, 0.990);

/* ---- sky sphere -> 2D -----------------------------------------------------
   Azimuthal-equidistant ("fisheye") projection around `axis`:
   |p| = angle(dir, axis) / 90deg  ->  with axis = up the horizon is |p| = 1.
   atan() is only used later on the *warped* p, so the warp itself is seamless. */
vec2 skyDomeCoords(vec3 dir, vec3 axis) {
    vec3 ref = abs(axis.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.0, 1.0);
    vec3 tx = normalize(cross(ref, axis));
    vec3 ty = cross(axis, tx);
    float ang = acos(clamp(dot(dir, axis), -1.0, 1.0));
    vec2 a = vec2(dot(dir, tx), dot(dir, ty));            // |a| = sin(ang)
    return a * (ang / max(sin(ang), 1e-4)) / (0.5 * PI);
}

/* =============================== STYLE A ================================= */

// Signed ray field: > 0 inside a white ray, < 0 in the blue gaps.
//   rays  = cos(N * (angle + twist * sqrt(r)) + warp * fbm)   -> N spiral arms
//   th(r) decreases outwards so rays get wider towards the horizon.
//   The FBM is sampled on (cos a, sin a), so angle -PI and PI agree (no seam).
float burstField(vec2 q, float t, float warpAmt) {
    float r = length(q);
    float a = atan(q.y, q.x);
    vec2 circ = vec2(cos(a), sin(a));
    float n = fbm3(circ * 1.6 + vec2(r * 2.3 - t * 0.05, t * 0.031));
    float spiral = a + SKY_TWIST * sqrt(r) + t * 0.035;
    float rays = cos(float(SKY_RAYS) * spiral + 3.0 * warpAmt * n);
    float th = 0.28 - 0.55 * smoothstep(0.05, 1.10, r) + 0.30 * n;
    float core = (0.19 - r) * 6.0;                       // white explosion core
    return max(rays - th, core);
}

// Teardrop: circular head of radius `rad` at the origin, tail tapering to -y.
float sdTeardrop(vec2 p, float rad, float len) {
    if (p.y >= 0.0) return length(p) - rad;
    if (-p.y > len) return length(p + vec2(0.0, len));
    float k = -p.y / len;
    return abs(p.x) - rad * pow(1.0 - k, 0.75);
}

// Comets flying outwards along the rays. Cells live in (angle, log r) space,
// so drops grow towards the horizon like in a worm's-eye perspective.
float skyDrops(vec2 q, float t, out float streak) {
    const float K = 40.0;                                    // angular lanes
    float r = length(q);
    float a = atan(q.y, q.x);
    vec2 g = vec2((a / TAU + 0.5) * K, log(max(r, 1e-3)) * 7.0 - t * 0.9);
    vec2 id = floor(g);
    vec2 hid = vec2(mod(id.x, K), id.y);                     // seam-safe id
    vec2 f = fract(g) - 0.5;
    float exists = step(hash12(hid), 0.26);
    // head near the outer edge of the cell, tail fits inside the cell
    vec2 d = f - vec2((hash12(hid + 3.1) - 0.5) * 0.45, 0.16);
    d.x *= 7.0 * TAU / K;                                    // isotropic cell metric
    float size = 0.10 + 0.07 * hash12(hid + 7.7);
    float m = aaFill(sdTeardrop(d, size, 0.58));
    float zone = smoothstep(0.28, 0.45, r) * (1.0 - smoothstep(1.05, 1.25, r));
    // yellow streak inside the tail
    float wobble = 0.25 * size * sin(d.y * 40.0);
    streak = (1.0 - smoothstep(0.0, size * 0.33, abs(d.x + wobble)))
           * smoothstep(-0.56, -size * 0.6, d.y) * step(d.y, size * 0.3);
    return m * exists * zone;
}

vec3 skyBurst(vec2 p, float t, float warpAmt, out float blueMask) {
    // 1) two-level domain warping (q = p + w * fbm(p + fbm(p))):
    //    turns the geometric spiral into liquid, organic petals.
    vec2 w1 = vec2(fbm3(p * 1.20 + vec2(0.0, t * 0.020)), fbm3(p * 1.20 + vec2(5.2, 1.3 - t * 0.017)));
    vec2 w2 = vec2(fbm3(p * 1.90 + 2.6 * w1 + vec2(1.7, 9.2) + t * 0.012),
                   fbm3(p * 1.90 + 2.6 * w1 + vec2(8.3, 2.8) - t * 0.010));
    vec2 q = p + warpAmt * 0.24 * w2 + vec2(1e-5, 0.0);

    float f = burstField(q, t, warpAmt);
    float white = aaFill(-f);

    // 2) misregistered screen print: the blue shape shifted twice gives a thin
    //    red-orange rim and a wider yellow rim on one side of every edge.
    vec2 off = vec2(0.0055, -0.0060);
    float b1 = aaFill(burstField(q - off, t, warpAmt));
    float b2 = aaFill(burstField(q - off * 2.4, t, warpAmt));
    float rimOrange = white * b1;
    float rimYellow = white * (1.0 - b1) * b2;

    float r = length(q);
    float a = atan(q.y, q.x);
    float spiral = a + SKY_TWIST * sqrt(r) + t * 0.035;

    // 3) blue zones: airbrushed periwinkle clouds
    float peri = smoothstep(-0.05, 0.30, fbm(q * 1.3 + vec2(t * 0.015, 3.0)));
    vec3 blueCol = mix(SKY_BLUE, SKY_PERIWINKLE, 0.85 * peri);

    // 4) white zones: lemon glow hugging the blue edges + peach/silver wisps
    float glowZone = smoothstep(-0.15, 0.25, fbm3(q * 1.7 + 7.0));
    float glow = exp(-max(f, 0.0) * 5.0) * glowZone;
    float bleed = exp(-max(-f, 0.0) * 14.0) * glowZone * 0.30;
    float wispField = cos(float(SKY_RAYS) * 3.0 * spiral + 7.0 * fbm3(q * 2.2 + 1.0));
    float wisp = smoothstep(0.80, 0.97, wispField) * smoothstep(0.45, 0.85, r)
               * smoothstep(-0.10, 0.20, fbm3(q * 0.9 - 4.0));
    vec3 wispCol = mix(SKY_PEACH, SKY_SILVER, step(0.0, fbm3(q * 0.7 + 9.0)));
    vec3 whiteCol = mix(SKY_WHITE, wispCol, wisp * 0.85);
    whiteCol = mix(whiteCol, SKY_LEMON, glow * 0.85);
    blueCol = mix(blueCol, SKY_LEMON, bleed);

    vec3 col = mix(blueCol, whiteCol, white);
    // only some edges carry the rim (like the central silhouette of image 1)
    float rimZone = (1.0 - smoothstep(0.45, 0.95, r)) * smoothstep(-0.02, 0.12, fbm3(q * 1.3 + 21.0));
    col = mix(col, SKY_ORANGE, rimOrange * rimZone);
    col = mix(col, SKY_YELLOW, rimYellow * rimZone);
    blueMask = (1.0 - white) * (1.0 - bleed);

#ifdef SKY_DROPS
    // white drops on blue, blue drops on white, both with a yellow streak
    float streak;
    float drop = skyDrops(q, t, streak);
    col = mix(col, mix(SKY_WHITE, SKY_BLUE, white), drop);
    col = mix(col, SKY_YELLOW, streak * drop * 0.9);
    blueMask = mix(blueMask, white, drop);
#endif
    return col;
}

/* =============================== STYLE B ================================= */

vec3 skyInk(vec2 p, vec3 dir, float t, float warpAmt, float density,
            out float inkMask, out float blueMask) {
    // jerky time: every ~2 s there is a chance the whole drawing "snaps"
    float snap = floor(t * 0.45);
    float jerk = step(0.72, hash11(snap * 2.17)) * (hash11(snap + 0.37) - 0.5);
    vec2 w = fbm2(p * 1.5 + vec2(t * 0.020, -t * 0.015));
    vec2 q = rot2(jerk * 0.25) * (p + warpAmt * 0.07 * w) + vec2(1e-5, 0.0);
    float r = length(q);
    float a = atan(q.y, q.x);
    float knot = exp(-r * 1.6);                    // ink concentrates at the centre

    // --- photocopied paper: off-white + grey grungy smudges + grain ---
    float smudge = fbm(q * 2.6 + 11.0);
    float grain = vnoise(q * 230.0);
    vec3 col = INK_PAPER;
    col = mix(col, INK_SMUDGE, smoothstep(0.05, 0.30, smudge) * 0.5);
    col = mix(col, vec3(0.55), smoothstep(0.26, 0.42, smudge + 0.3 * (grain - 0.5)) * 0.3);

    float az = atan(dir.z, dir.x);
    float el = asin(clamp(dir.y, -1.0, 1.0));
    blueMask = 0.0;

#ifdef SKY_WINDOWS
    // --- rectangular "windows" cut through the paper, showing a cloudy sky.
    // Grid in (azimuth, elevation) so the windows stay upright on the horizon.
    const float WCOLS = 14.0;
    vec2 wg = vec2((az / TAU + 0.5) * WCOLS, el / (0.5 * PI) * 3.5);
    vec2 wid = vec2(mod(floor(wg.x), WCOLS), floor(wg.y));
    vec2 wf = fract(wg);
    float epoch = floor(t * 0.05 + hash12(wid) * 3.0);      // windows reshuffle
    float isWin = step(hash12(wid + epoch * 7.3), 0.22);
    vec4 m = 0.07 + 0.30 * vec4(hash22(wid + epoch + 1.3), hash22(wid + epoch + 8.9));
    vec2 lo = m.xy;
    vec2 hi = 1.0 - m.zw;
    vec2 dd = abs(wf - 0.5 * (lo + hi)) - 0.5 * (hi - lo);
    float sdw = length(max(dd, 0.0)) + min(max(dd.x, dd.y), 0.0);
    vec2 notchC = mix(lo, hi, step(0.5, hash22(wid + epoch + 4.4)));
    vec2 nd = abs(wf - notchC) - 0.32 * (hi - lo);
    sdw = max(sdw, -(length(max(nd, 0.0)) + min(max(nd.x, nd.y), 0.0)));   // stepped corner
    float inside = aaFill(sdw) * isWin;
    float halo = exp(-max(sdw, 0.0) * 22.0) * isWin * (1.0 - inside);
    vec3 skyCol = mix(INK_SKY_LOW, INK_SKY_TOP, clamp(dir.y * 1.3 + 0.25, 0.0, 1.0));
    float clouds = smoothstep(0.02, 0.38, fbm(vec2(wg.x * 2.3, wg.y * 4.0) + vec2(t * 0.02, 0.0)));
    skyCol = mix(skyCol, vec3(0.975), clouds * 0.9);
    col = mix(col, INK_HALO, halo * 0.75);
    col = mix(col, skyCol, inside);
    blueMask = inside * (1.0 - clouds * 0.8);
#endif

    float ink = 0.0;

    // --- 1. blades: crescent = disc minus offset disc -> razor-sharp horns
    for (int i = 0; i < 14; i++) {
        float fi = float(i);
        vec2 h = hash22(vec2(fi * 7.31, 1.7));
        float ang = fi * 2.39996 + 0.06 * t * (h.x - 0.5) + 0.2 * sin(t * 0.17 + fi * 1.3);
        float R = mix(0.10, 0.80, h.y * h.y);
        vec2 c = vec2(cos(ang), sin(ang)) * 0.30 * h.x;
        float dirA = ang + 1.3 + 2.0 * hash11(fi + 3.3);
        float thick = mix(0.025, 0.11, hash11(fi + 5.1) * hash11(fi + 6.6));
        vec2 c2 = c + vec2(cos(dirA), sin(dirA)) * R * thick;
        float d = max(length(q - c) - R, -(length(q - c2) - R * (1.0 - 0.15 * thick)));
        float on = step(hash11(fi + 0.5), 0.45 + 0.4 * density);
        ink = max(ink, aaFill(d) * on);
    }

    // --- 2. calligraphic arcs: blunt start, hairline tail
    for (int i = 0; i < 6; i++) {
        float fi = float(i) + 20.0;
        vec2 h = hash22(vec2(fi, 4.2));
        float ang = fi * 2.39996 - 0.05 * t;
        vec2 c = vec2(cos(ang), sin(ang)) * mix(0.1, 0.6, h.x);
        float R = mix(0.15, 0.70, h.y);
        vec2 rel = q - c;
        float u = fract((atan(rel.y, rel.x) - ang) / TAU);
        float span = mix(0.15, 0.40, hash11(fi));
        float taper = clamp(1.0 - u / span, 0.0, 1.0);
        float d = abs(length(rel) - R) - 0.014 * taper * (0.5 + h.x);
        ink = max(ink, aaFill(d) * step(u, span));
    }

    // --- 3. scribbles: zero-crossings of gradient noise thresholded very thin
    float sc = gnoise(q * 5.5 + w * 2.0 + vec2(0.0, t * 0.05));
    float scrib = 1.0 - smoothstep(0.0, 0.006 + fwidth(sc), abs(sc));
    scrib *= smoothstep(0.10, 0.35, fbm3(q * 1.8 - 3.0) + knot * 0.4) * density;
    ink = max(ink, scrib * 0.9);

    // --- 4. splinters: Voronoi in (angle, log r) -> radial glass shards
    vec2 sp = vec2((a / TAU + 0.5) * 30.0, log(max(r, 1e-3)) * 1.5 - t * 0.03);
    vec3 v = voronoiPeriodic(sp, 0.3 * t, 30.0);
    float edgeD = v.y - v.x;
    float shardSel = step(1.0 - 0.16 * density * (0.4 + knot), v.z);
    float shardFill = shardSel * smoothstep(0.0, 0.05, edgeD);
    float shardShade = mix(0.0, 0.45, smoothstep(0.0, 0.6, v.x));
    float edge = (1.0 - smoothstep(0.0, 0.03 + fwidth(edgeD), edgeD))
               * step(0.75, hash11(v.z * 91.0)) * knot;

    // --- 5. glitch bars: tiny black rectangles blinking in a fine grid
    vec2 bg = vec2((az / TAU + 0.5) * 160.0, el * 60.0);
    vec2 bid = vec2(mod(floor(bg.x), 160.0), floor(bg.y));
    vec2 bf = fract(bg);
    float bar = step(0.996, hash12(bid + floor(t * 2.0))) * step(0.2, bf.y) * step(bf.y, 0.6);

    col = mix(col, vec3(shardShade), shardFill * 0.95);
    float black = max(max(ink, edge), bar);
    col = mix(col, INK_BLACK, black);
    inkMask = max(black, shardFill);
    blueMask *= 1.0 - inkMask;
    return col;
}

/* ======================= sun, moon, stars, time ========================== */

vec3 skySunMoon(vec3 dir, vec3 sunDir, float rain, out float cover) {
    // sun: a glowing diamond (L1 norm in the sun's tangent plane, image 10)
    vec3 tx = normalize(vec3(sunDir.y, -sunDir.x, 0.0));
    vec3 ty = cross(tx, sunDir);
    float cs = dot(dir, sunDir);
    vec2 sp = vec2(dot(dir, tx), dot(dir, ty)) / max(cs, 0.05);   // gnomonic
    float size = 0.042 * SUN_SIZE;
    float core = (1.0 - smoothstep(size * 0.86, size, abs(sp.x) + abs(sp.y))) * step(0.0, cs);
    float ang = acos(clamp(cs, -1.0, 1.0));
    float glow = exp(-ang / (size * 0.9)) * 0.9 + exp(-ang * 4.0) * 0.18;
    // moon: soft pale disc
    float angM = acos(clamp(-cs, -1.0, 1.0));
    float moonCore = 1.0 - smoothstep(size * 0.55, size * 0.62, angM);
    float moonGlow = exp(-angM / (size * 1.2)) * 0.25;

    float vis = (1.0 - 0.85 * rain) * smoothstep(-0.05, 0.02, dir.y);
    cover = clamp(core + glow * 0.6 + moonCore, 0.0, 1.0);
    return (vec3(1.0, 0.95, 0.86) * (core * 4.0 + glow)
          + vec3(0.80, 0.86, 1.00) * (moonCore * 1.4 + moonGlow)) * vis;
}

float skyStars(vec3 dir, float t) {
    vec3 p = dir * 220.0;
    vec3 ip = floor(p);
    float h = hash13(ip);
    float s = step(0.992, h) * (1.0 - smoothstep(0.05, 0.22, length(fract(p) - 0.5)));
    return s * (0.55 + 0.45 * sin(t * 3.0 + h * 500.0));
}

// Day / sunset / night / rain grading of the flat pattern colours.
vec3 skyTimeOfDay(vec3 col, vec3 dir, vec3 sunDir, float rain) {
    float day = smoothstep(-0.12, 0.18, sunDir.y);
    float sunset = 1.0 - smoothstep(0.0, 0.35, abs(sunDir.y + 0.02));
    float toSun = max(dot(dir, sunDir), 0.0);
    float warmZone = sunset * (0.35 + 0.65 * pow(toSun, 3.0)) * (1.0 - smoothstep(0.0, 0.7, dir.y));
    col = mix(col, col * vec3(1.06, 0.86, 0.80) + vec3(0.06, 0.02, 0.03), warmZone);
    // night: remap 0..1 into a navy range, keeps the pattern readable
    vec3 night = mix(vec3(0.010, 0.014, 0.055), vec3(0.25, 0.27, 0.40), col);
    col = mix(night, col, day);
    col = mix(col, vec3(luma(col)) * vec3(0.92, 0.95, 1.0) * 0.85, rain * 0.75);
    return col;
}

/* ============================= entry point ================================
   dir      world-space view direction (normalized)
   sunDir   world-space sun direction (normalized)
   style    0 burst, 1 ink, 2 mix (mixAmt), 3 morph (mixAmt = animated uniform)
   textMask (out) where the Japanese text layer is allowed (blue zones)       */
vec3 getCustomSky(vec3 dir, vec3 sunDir, float time, int style, float mixAmt,
                  float warpAmt, float speed, vec3 fogCol, float rain, out float textMask) {
    float t = time * speed;
#if SKY_BURST_CENTER == 1
    vec3 axis = normalize(sunDir + vec3(0.0, 1.2, 0.0));   // follows the sun, never degenerate
#else
    vec3 axis = vec3(0.0, 1.0, 0.0);
#endif
    vec2 p = rot2(t * 0.01) * skyDomeCoords(dir, axis);

    vec3 colA = vec3(0.0);
    vec3 colB = vec3(0.0);
    float blueA = 0.0;
    float blueB = 0.0;
    float inkMask = 0.0;
    if (style != 1) colA = skyBurst(p, t, warpAmt, blueA);
    if (style != 0) colB = skyInk(p, dir, t, warpAmt, SKY_INK_DENSITY, inkMask, blueB);

    vec3 col;
    float blue;
    if (style == 0) {
        col = colA;
        blue = blueA;
    } else if (style == 1) {
        col = colB;
        blue = blueB;
    } else {
        // Dissolve: an FBM threshold sweeps through the sky (organic morph),
        // and the black strokes of style B are overlaid on style A as m grows.
        float m = clamp(mixAmt, 0.0, 1.0);
        float n = clamp(0.5 + 0.9 * fbm3(p * 1.3 + vec2(5.0, t * 0.01)), 0.0, 1.0);
        float bRegion = 1.0 - smoothstep(m - 0.06, m + 0.06, n);
        col = mix(colA, colB, bRegion);
        float overlay = inkMask * (1.0 - bRegion) * smoothstep(0.05, 0.30, m);
        col = mix(col, INK_BLACK, overlay);
        float seam = 1.0 - abs(bRegion * 2.0 - 1.0);
        col = mix(col, SKY_LEMON, seam * seam * 0.6);                    // glowing seam
        blue = mix(blueA, blueB, bRegion) * (1.0 - overlay);
    }

    col = skyTimeOfDay(col, dir, sunDir, rain);

    // horizon haze (same colour as the terrain fog -> seamless horizon)
    float horizon = pow(1.0 - smoothstep(-0.03, 0.25, dir.y), 1.5);
    col = mix(col, getHazeColor(dir, sunDir, fogCol, rain), horizon);

#ifdef SKY_STARS
    float night = 1.0 - smoothstep(-0.20, 0.05, sunDir.y);
    col += vec3(0.9, 0.93, 1.0) * skyStars(dir, time) * night * blue * (1.0 - rain) * (1.0 - horizon);
#endif

    float cover;
    col += skySunMoon(dir, sunDir, rain, cover);   // HDR, feeds the bloom
    textMask = blue * (1.0 - horizon) * (1.0 - cover);
    return col;
}

#endif
