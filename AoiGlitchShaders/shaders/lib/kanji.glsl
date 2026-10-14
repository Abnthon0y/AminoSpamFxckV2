#ifndef AOI_KANJI
#define AOI_KANJI
/* =========================================================================
   AoiGlitch — "BSOD terminal" Japanese text on the blue parts of the sky.
   Needs: common.glsl, settings.glsl
   Entry point: skyTextLayer(dir, time, fragCoord, atlas)
     returns vec3(textAlpha, invertedCell, rawGlyph)
   Variant 1 (SKY_TEXT == 1): glyphs sampled from a 16x16 atlas texture.
   Variant 2 (SKY_TEXT == 2): procedural pseudo-kanji built from SDF strokes.
   ========================================================================= */

/* ---- variant 2: procedural pseudo-kanji -----------------------------------
   A glyph is 3..7 strokes picked by hash bits from a kanji-like vocabulary:
   horizontal bars, vertical bars, a left radical, a box (口), sweeps (ノ, 乀)
   and a dot (丶). Strokes are segment SDFs, so they stay crisp at any size. */
float proceduralGlyph(vec2 uv, vec2 seed) {
    vec2 p = uv * 2.0 - 1.0;
    vec4 h  = vec4(hash12(seed), hash12(seed + 1.3), hash12(seed + 2.7), hash12(seed + 4.1));
    vec4 h2 = vec4(hash12(seed + 5.9), hash12(seed + 7.3), hash12(seed + 8.8), hash12(seed + 10.2));
    float d = 1e3;
    float split = step(0.55, h.x);                  // left radical + right body?
    float x0 = mix(-0.8, -0.15, split);             // body starts after the radical

    // left radical: tall stroke with a small tick (like 亻 / 氵)
    d = min(d, mix(1e3, sdSegment(p, vec2(-0.62, 0.85), vec2(-0.62, -0.85)), split));
    d = min(d, mix(1e3, sdSegment(p, vec2(-0.85, 0.35), vec2(-0.40, 0.55)), split * step(0.5, h2.w)));

    // horizontal bars
    d = min(d, mix(1e3, sdSegment(p, vec2(x0, 0.70), vec2(0.80, 0.70)), step(0.30, h.y)));
    d = min(d, mix(1e3, sdSegment(p, vec2(x0 + 0.25 * h.z, 0.05), vec2(0.75, 0.05)), step(0.40, h.z)));
    d = min(d, mix(1e3, sdSegment(p, vec2(x0, -0.72), vec2(0.85, -0.72)), step(0.45, h.w)));

    // vertical bar of the body
    float vx = mix(0.0, 0.35, split) + 0.25 * (h2.x - 0.5);
    d = min(d, mix(1e3, sdSegment(p, vec2(vx, 0.90), vec2(vx, -0.90)), step(0.35, h2.x)));

    // box 口
    vec2 bc = vec2(mix(0.0, 0.32, split), -0.15);
    vec2 bq = abs(p - bc) - vec2(0.38, 0.30);
    float box = abs(length(max(bq, 0.0)) + min(max(bq.x, bq.y), 0.0));
    d = min(d, mix(1e3, box, step(0.78, h2.y)));

    // sweeps: ノ (left-falling) and 乀 (right-falling)
    d = min(d, mix(1e3, sdSegment(p, vec2(0.10, 0.25), vec2(-0.70, -0.85)), step(0.62, h2.z)));
    d = min(d, mix(1e3, sdSegment(p, vec2(0.05, 0.10), vec2(0.85, -0.85)), step(h2.z, 0.22)));

    // dot 丶
    d = min(d, mix(1e3, sdSegment(p, vec2(-0.10, 0.98), vec2(0.06, 0.80)), step(h2.w, 0.30)));

    return aaFill(d - 0.10);
}

/* ---- variant 1: atlas tap -------------------------------------------------
   Atlas = 16x16 glyphs, white on black, texture v = 0 at the TOP row
   (Minecraft / Iris / OptiFine upload images top row first).               */
float glyphTap(sampler2D atlas, vec2 cellXY, vec2 uv) {
    uv = clamp(uv, 0.03, 0.97);                    // never bleed into neighbours
    return texture2D(atlas, (cellXY + vec2(uv.x, 1.0 - uv.y)) / 16.0).r;
}

vec3 skyTextLayer(vec3 dir, float t, vec2 fragCoord, sampler2D atlas) {
    /* -- 1. text grid on the sphere --------------------------------------
       Rows = bands of constant elevation. Each row gets its own INTEGER
       number of columns ~ 2*PI*cos(elevation) / glyphWidth, so glyphs keep
       their aspect ratio up to the zenith and the azimuth wraps seamlessly. */
    float g = radians(SKY_TEXT_SIZE);
    float rowH = g * 1.3;
    float el = asin(clamp(dir.y, -1.0, 1.0));
    float az = atan(dir.z, dir.x);
    float rowF = el / rowH;
    float row = floor(rowF);
    float cols = max(8.0, floor(TAU * cos((row + 0.5) * rowH) / (g * 0.9)));
    float colF = (az / TAU + 0.5) * cols;

    // derivatives first, before anything that depends on per-cell hashes
    vec2 ddx = dFdx(vec2(colF, rowF));
    vec2 ddy = dFdy(vec2(colF, rowF));
    ddx.x = abs(ddx.x) > 0.5 * cols ? 0.0 : ddx.x;   // azimuth seam
    ddy.x = abs(ddy.x) > 0.5 * cols ? 0.0 : ddy.x;

    /* -- 2. glitch ------------------------------------------------------
       Time is cut into 0.25 s slots; a slot "fires" with a small probability.
       While it fires, a random band of rows slides sideways and some cells
       are drawn inverted (white block, glyph cut out).                     */
    float gslot = floor(t * 4.0);
    float ev = step(1.0 - 0.09 * SKY_TEXT_GLITCH, hash11(gslot * 1.37 + 0.5));
    float bandC = floor((hash11(gslot + 7.7) - 0.5) * 140.0);
    float bandW = 1.0 + floor(hash11(gslot + 3.1) * 7.0);
    float inBand = ev * step(abs(row - bandC), bandW);
    colF += inBand * (hash11(row * 0.71 + gslot) - 0.5) * 30.0;
    // constant low-level line jitter, like a bad video signal
    float jslot = floor(t * 15.0);
    colF += step(0.985, hash12(vec2(row, jslot))) * (hash12(vec2(jslot, row)) - 0.5) * 3.0 * SKY_TEXT_GLITCH;

    float col = floor(colF);
    vec2 cell = vec2(mod(col, cols), row);
    vec2 local = vec2(fract(colF), fract(rowF));

    /* -- 3. page layout: terminal blocks with ragged lines, empty lines,
       gaps between "words" ------------------------------------------------ */
    const float BLOCK = 30.0;
    float blk = floor(cell.x / BLOCK);
    float inBlk = cell.x - blk * BLOCK;
    float lineLen = BLOCK * mix(0.3, 1.0, hash12(vec2(blk, row) + 0.37));
    float present = step(inBlk + 0.5, lineLen) * step(1.0, inBlk);
    present *= step(0.14, hash12(vec2(row, 91.7)));
    present *= step(hash12(cell + 1.9), SKY_TEXT_DENSITY + 0.12);

    /* -- 4. which glyph: hash(cell, epoch); every cell re-rolls its glyph
       at its own random rate -> the dump is constantly being rewritten.    */
    float rate = mix(0.08, 1.2, hash12(cell + 4.2)) * SKY_TEXT_FLICKER;
    float epoch = floor(t * rate + hash12(cell) * 10.0);
    vec2 seed = cell + epoch * vec2(1.73, 3.19);

    vec2 guv = vec2(local.x, (local.y - 0.115) / 0.77);      // glyph box in the cell
    float inBox = step(0.0, guv.y) * step(guv.y, 1.0);

    float cov;
#if SKY_TEXT == 2
    cov = proceduralGlyph(clamp(guv, 0.0, 1.0), seed);
#else
    float idx = floor(hash12(seed) * 256.0);
    vec2 cellXY = vec2(mod(idx, 16.0), floor(idx / 16.0));
    vec2 ax = vec2(ddx.x, ddx.y / 0.77) * 0.25;
    vec2 ay = vec2(ddy.x, ddy.y / 0.77) * 0.25;
    cov = 0.25 * (glyphTap(atlas, cellXY, guv + ax + ay) + glyphTap(atlas, cellXY, guv + ax - ay)
                + glyphTap(atlas, cellXY, guv - ax + ay) + glyphTap(atlas, cellXY, guv - ax - ay));
#endif
    cov *= inBox;

    /* -- 5. flicker + grain ---------------------------------------------- */
    float flick = 1.0 - SKY_TEXT_FLICKER * 0.4 * step(0.88, hash12(cell + floor(t * 10.0) * 0.731));
    float frame = mod(floor(t * 30.0), 97.0);
    float grainN = hash12(fragCoord + frame * 13.0);
    float grain = mix(1.0, smoothstep(0.12, 0.55, grainN), SKY_TEXT_GRAIN);

    float alpha = cov * present * flick * grain;
    float inv = inBand * step(0.78, hash12(cell + gslot)) * present;
    return vec3(alpha, inv, cov * grain);
}

#endif
