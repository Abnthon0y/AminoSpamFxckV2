#ifndef AOI_COMMON
#define AOI_COMMON
/* =========================================================================
   AoiGlitch — common math: hashes, value/gradient noise, FBM, Voronoi, SDF.
   Written in the GLSL subset shared by desktop GLSL 1.20 and GLSL ES 3.00
   (no implicit int->float, no array constructors) so the very same file
   is used by the in-game programs AND by the WebGL preview harness.
   ========================================================================= */

#define PI  3.14159265
#define TAU 6.28318531

/* ---------- hashes ("hash without sine", Dave Hoskins) ---------------- */
// Stable on GPUs and on large world coordinates, unlike fract(sin(x)*43758).
float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float hash13(vec3 p3) {
    p3 = fract(p3 * 0.1031);
    p3 += dot(p3, p3.zyx + 31.32);
    return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xx + p3.yz) * p3.zy);
}

/* ---------- noise ------------------------------------------------------ */
// Value noise, quintic fade. Range [0, 1].
float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Gradient (Perlin-style) noise. Range roughly [-0.7, 0.7], zero mean.
float gnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    vec2 ga = hash22(i)                   * 2.0 - 1.0;
    vec2 gb = hash22(i + vec2(1.0, 0.0)) * 2.0 - 1.0;
    vec2 gc = hash22(i + vec2(0.0, 1.0)) * 2.0 - 1.0;
    vec2 gd = hash22(i + vec2(1.0, 1.0)) * 2.0 - 1.0;
    float va = dot(ga, f);
    float vb = dot(gb, f - vec2(1.0, 0.0));
    float vc = dot(gc, f - vec2(0.0, 1.0));
    float vd = dot(gd, f - vec2(1.0, 1.0));
    return mix(mix(va, vb, u.x), mix(vc, vd, u.x), u.y);
}

// Octave rotation removes the axis-aligned look of stacked noise.
const mat2 FBM_ROT = mat2(0.80, 0.60, -0.60, 0.80);

// Fractal Brownian Motion: sum of 5 octaves, gain 0.5, lacunarity ~2.
// Range roughly [-0.6, 0.6].
float fbm(vec2 p) {
    float sum = 0.0;
    float amp = 0.5;
    for (int i = 0; i < 5; i++) {
        sum += amp * gnoise(p);
        p = FBM_ROT * p * 2.03 + vec2(17.1, 3.7);
        amp *= 0.5;
    }
    return sum;
}

// Cheaper 3-octave version for inner loops / far LODs.
float fbm3(vec2 p) {
    float sum = 0.0;
    float amp = 0.5;
    for (int i = 0; i < 3; i++) {
        sum += amp * gnoise(p);
        p = FBM_ROT * p * 2.03 + vec2(17.1, 3.7);
        amp *= 0.5;
    }
    return sum;
}

// Vector FBM: two decorrelated FBMs -> a 2D displacement field.
vec2 fbm2(vec2 p) {
    return vec2(fbm(p), fbm(p + vec2(5.2, 1.3)));
}

/* ---------- Worley / Voronoi ------------------------------------------- */
// Returns vec3(F1, F2, hash of the nearest cell).
// Feature points orbit inside their cells -> the pattern "breathes" in time.
vec3 voronoi(vec2 p, float t) {
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    float f1 = 8.0;
    float f2 = 8.0;
    float id = 0.0;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 h = hash22(ip + g);
            vec2 o = 0.5 + 0.38 * sin(t + TAU * h);
            float d = length(g + o - fp);
            if (d < f1) {
                f2 = f1;
                f1 = d;
                id = hash12(ip + g + 19.7);
            } else if (d < f2) {
                f2 = d;
            }
        }
    }
    return vec3(f1, f2, id);
}

// Same as voronoi() but periodic along x with an integer period, for grids
// laid out in polar coordinates (angle wraps around without a seam).
vec3 voronoiPeriodic(vec2 p, float t, float periodX) {
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    float f1 = 8.0;
    float f2 = 8.0;
    float id = 0.0;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 cell = vec2(mod(ip.x + g.x, periodX), ip.y + g.y);
            vec2 h = hash22(cell);
            vec2 o = 0.5 + 0.38 * sin(t + TAU * h);
            float d = length(g + o - fp);
            if (d < f1) {
                f2 = f1;
                f1 = d;
                id = hash12(cell + 19.7);
            } else if (d < f2) {
                f2 = d;
            }
        }
    }
    return vec3(f1, f2, id);
}

/* ---------- small helpers ---------------------------------------------- */
float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

mat2 rot2(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat2(c, s, -s, c);
}

// Signed distance to a segment a-b (minus nothing: caller subtracts width).
float sdSegment(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a;
    vec2 ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h);
}

#ifndef VERTEX_SHADER   // derivatives exist only in fragment shaders
// Anti-aliased fill of a signed distance (negative = inside).
float aaFill(float d) {
    float w = fwidth(d) + 1e-5;
    return 1.0 - smoothstep(-w, w, d);
}

// Interleaved gradient noise (Jimenez 2014) — per-pixel dithering.
float ign(vec2 fragCoord) {
    return fract(52.9829189 * fract(dot(fragCoord, vec2(0.06711056, 0.00583715))));
}
#endif

#endif
