#ifndef AOI_PIXELATE
#define AOI_PIXELATE
/* =========================================================================
   AoiGlitch — distance-driven mosaic (image 8). Post-process only.
   Needs: common.glsl, settings.glsl

   Problem: if every pixel picked its own tile size from its own depth, tiles
   of different sizes would overlap and tear. Solution = quadtree:
   tile sizes are powers of two (32,16,8,4,2) aligned to the screen, and a
   tile of size s is used when the desired size *at its centre* is >= s.
   All pixels inside a tile see the same centre -> they agree -> clean tiling.
   Smoothness: we blend from tile s towards its parent 2s by
   log2(desired) - log2(s), so the size grows continuously with distance.
   ========================================================================= */

// Linear (eye-space) depth from a [0,1] depth-buffer value.
float linearizeDepth(float depth, float n, float f) {
    float z = depth * 2.0 - 1.0;
    return 2.0 * n * f / (f + n - z * (f - n));
}

// True distance camera->pixel (better than linear depth at screen edges).
float viewDistance(vec2 uv, float depth, mat4 projInv) {
    vec4 v = projInv * vec4(vec3(uv, depth) * 2.0 - 1.0, 1.0);
    return length(v.xyz / v.w);
}

// pixelSize = mix(1, max, smoothstep(start, end, distance))
float desiredPixelSize(float dist, float depth) {
    if (depth >= 1.0) return PIXEL_SKY_SIZE;
    return mix(1.0, PIXEL_MAX_SIZE, smoothstep(PIXEL_START_DISTANCE, PIXEL_END_DISTANCE, dist));
}

// Average colour of the size-s tile containing fragCoord: a 4x4 grid of
// bilinear taps (each tap already averages 2x2 pixels). Exact box filter up
// to 8 px tiles, evenly spread sampling above -> tiles don't shimmer.
// (No mip-mapping on purpose: tile-quantised uvs have zero/huge derivatives,
// which would make implicit-LOD sampling pick wrong mip levels.)
vec3 tileColor(sampler2D tex, vec2 fragCoord, float s, vec2 viewSize) {
    vec2 c = (floor(fragCoord / s) + 0.5) * s;
    vec3 sum = vec3(0.0);
    for (int j = 0; j < 4; j++) {
        for (int i = 0; i < 4; i++) {
            vec2 o = (vec2(float(i), float(j)) + 0.5) * 0.25 - 0.5;
            sum += texture2D(tex, (c + o * s) / viewSize).rgb;
        }
    }
    return sum / 16.0;
}

// Returns vec3(tileSize, blendToParent, unused).
vec3 chooseTile(sampler2D depthTex, vec2 fragCoord, vec2 viewSize, mat4 projInv) {
    float chosen = 1.0;
    float want = 1.0;
    for (int i = 5; i >= 1; i--) {
        float s = exp2(float(i));
        vec2 cuv = (floor(fragCoord / s) + 0.5) * s / viewSize;
        float d = texture2D(depthTex, cuv).r;
        float w = desiredPixelSize(viewDistance(cuv, d, projInv), d);
        if (w >= s) {
            chosen = s;
            want = w;
            break;
        }
    }
    if (chosen < 1.5) {
        float d = texture2D(depthTex, fragCoord / viewSize).r;
        want = desiredPixelSize(viewDistance(fragCoord / viewSize, d, projInv), d);
    }
    float blend = smoothstep(0.0, 1.0, clamp(log2(want) - log2(chosen), 0.0, 1.0));
    return vec3(chosen, blend, 0.0);
}

// Light grout lines between tiles, like the tiled mosaic of image 8.
vec3 applyGrout(vec3 col, vec2 fragCoord, float s, float strength) {
    vec2 f = fragCoord - floor(fragCoord / s) * s;
    float line = (1.0 - step(1.0, min(f.x, f.y))) * step(3.5, s);
    return mix(col, mix(col, vec3(0.94, 0.96, 1.0), 0.65), line * strength * PIXEL_GROUT);
}

#endif
