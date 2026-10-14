#ifndef AOI_SETTINGS
#define AOI_SETTINGS
/* =========================================================================
   AoiGlitch — user options.
   Every "#define NAME value // [list]" below is shown in-game in
   Video Settings -> Shader Packs -> Shader Options (Iris and OptiFine).
   Toggle options are "#define NAME" (on) / "//#define NAME" (off).
   ========================================================================= */

/* ------------------------------- Sky ------------------------------------ */
#define SKY_STYLE 2           // [0 1 2 3] 0 radial burst (img 1), 1 ink shards (img 2), 2 mix, 3 auto-morph
#define SKY_MIX 0.45          // [0.0 0.1 0.2 0.3 0.4 0.45 0.5 0.6 0.7 0.8 0.9 1.0]
#define SKY_WARP 1.0          // [0.0 0.25 0.5 0.75 1.0 1.25 1.5 2.0] domain-warp strength
#define SKY_SPEED 1.0         // [0.0 0.25 0.5 0.75 1.0 1.5 2.0 3.0]
#define SKY_RAYS 7            // [3 4 5 6 7 8 9 10 12]
#define SKY_TWIST 1.4         // [0.0 0.4 0.8 1.0 1.4 2.0 2.5 3.0]
#define SKY_BURST_CENTER 0    // [0 1] 0 zenith, 1 sun
#define SKY_DROPS             // teardrop comets of image 1
#define SKY_INK_DENSITY 1.0   // [0.25 0.5 0.75 1.0 1.25 1.5 2.0]
#define SKY_WINDOWS           // blue sky "windows" of image 2
#define SUN_SIZE 1.0          // [0.5 0.75 1.0 1.25 1.5 2.0]
#define SKY_STARS             // procedural stars at night
#define SKY_NIGHT_STYLE 1     // [0 1] 0 dimmed palette, 1 inverted: white turns black, blue darkens

/* ----------------------- Japanese glitch text --------------------------- */
#define SKY_TEXT 1            // [0 1 2] 0 off, 1 texture atlas, 2 procedural pseudo-kanji
#define SKY_TEXT_SIZE 1.0     // [0.6 0.8 1.0 1.25 1.5 2.0] glyph size in degrees
#define SKY_TEXT_DENSITY 0.8  // [0.4 0.5 0.6 0.7 0.8 0.9 1.0]
#define SKY_TEXT_OPACITY 0.85 // [0.25 0.5 0.7 0.85 1.0]
#define SKY_TEXT_FLICKER 1.0  // [0.0 0.5 1.0 1.5 2.0]
#define SKY_TEXT_GLITCH 1.0   // [0.0 0.5 1.0 1.5 2.0]
#define SKY_TEXT_GRAIN 0.4    // [0.0 0.2 0.4 0.6 0.8]

/* ------------------------------- Water ---------------------------------- */
#define WATER_STYLE 0         // [0 1 2 3] 0 ink marble (img 3), 1 caustics (img 4), 2 currents (img 5), 3 marble + caustics
#define WATER_SCALE 1.0       // [0.5 0.75 1.0 1.5 2.0]
#define WATER_SPEED 1.0       // [0.0 0.25 0.5 1.0 1.5 2.0]
#define WATER_WARP 1.0        // [0.0 0.5 1.0 1.5 2.0]
#define WATER_GRAIN 0.5       // [0.0 0.25 0.5 0.75 1.0]
#define WATER_ALPHA 0.82      // [0.5 0.6 0.7 0.82 0.9 1.0]

/* ------------------------- Players / entities --------------------------- */
#define PLAYER_GLITCH         // gray glitch + white noise on players
//#define GLITCH_ALL_ENTITIES // apply it to every entity, not only players
#define GLITCH_INTENSITY 1.0  // [0.0 0.25 0.5 0.75 1.0 1.5 2.0]
#define NOISE_AMOUNT 0.6      // [0.0 0.2 0.4 0.6 0.8 1.0]
#define NOISE_STYLE 2         // [0 1 2] 0 TV static, 1 halftone dots (img 7), 2 both
#define GLITCH_RATE 1.0       // [0.25 0.5 1.0 2.0 4.0] glitch bursts frequency

/* ------------------------------ Foliage --------------------------------- */
#define JELLY_LEAVES
#define JELLY_AMPLITUDE 0.03  // [0.01 0.02 0.03 0.04 0.05 0.07]
#define JELLY_FREQUENCY 5.0   // [2.0 3.0 4.0 5.0 7.0 9.0 12.0] wobbles per second
#define WAVING_PLANTS
#define WIND_STRENGTH 1.0     // [0.0 0.25 0.5 0.75 1.0 1.5 2.0]
#define WIND_SPEED 1.0        // [0.25 0.5 0.75 1.0 1.5 2.0]

/* ----------------------------- Pixelation ------------------------------- */
//#define PIXELATION        // off by default; turn on for the distance mosaic
#define PIXEL_START_DISTANCE 48.0  // [16.0 32.0 48.0 64.0 96.0 128.0]
#define PIXEL_END_DISTANCE 192.0   // [96.0 128.0 192.0 256.0 384.0 512.0]
#define PIXEL_MAX_SIZE 16.0        // [4.0 8.0 16.0 32.0]
#define PIXEL_SKY_SIZE 4.0         // [1.0 2.0 4.0 8.0 16.0 32.0] 1 = sky not pixelated
#define PIXEL_GROUT 0.35           // [0.0 0.15 0.35 0.5 0.75] light lines between tiles (img 8)

/* ------------------------- Light & atmosphere --------------------------- */
#define BLOOM
#define BLOOM_INTENSITY 0.6   // [0.0 0.25 0.4 0.6 0.8 1.0 1.5 2.0]
#define BLOOM_THRESHOLD 0.8   // [0.5 0.6 0.7 0.8 0.9 1.0] glow starts above this luminance
#define FOG_DENSITY 1.0       // [0.0 0.5 0.75 1.0 1.5 2.0 3.0]
#define COLOR_SATURATION 1.15 // [0.8 0.9 1.0 1.1 1.15 1.25 1.4]
#define PASTEL_AMOUNT 0.4     // [0.0 0.2 0.4 0.6 0.8]
#define SHADOW_LIFT 0.06      // [0.0 0.03 0.06 0.1 0.15]
#define VIGNETTE 0.22         // [0.0 0.1 0.22 0.35 0.5]
#define FILM_GRAIN 0.025      // [0.0 0.015 0.025 0.04 0.06]

/* ---------------------------- Living light ------------------------------ */
#define LIGHT_PATCHES               // soft patches of light/shade drifting with the wind
#define LIGHT_PATCHES_STRENGTH 0.35 // [0.15 0.25 0.35 0.5 0.65]
#define GODRAYS                     // soft light shafts from the sun / moon
#define GODRAYS_STRENGTH 0.5        // [0.2 0.35 0.5 0.75 1.0]
#define TORCH_FLICKER               // warm, gently breathing light around torches
#define FOLIAGE_GLOW 1.0            // [0.0 0.5 1.0 1.5 2.0] backlit leaves and grass

/* ------------------------------ Shadows --------------------------------- */
#define SHADOWS
#define SHADOW_DARKNESS 0.34  // [0.15 0.25 0.34 0.45 0.55 0.65] how dark a full shadow gets
#define SHADOW_SOFTNESS 1.6   // [0.5 1.0 1.6 2.0 2.5 3.0] penumbra width
#define AO_STRENGTH 0.5       // [0.0 0.25 0.5 0.75 1.0]

const int shadowMapResolution = 2048; // [1024 2048 3072 4096]
const float shadowDistance = 128.0;   // [64.0 96.0 128.0 160.0 192.0 256.0]
const float shadowDistanceRenderMul = 1.0;
const float sunPathRotation = -25.0;  // [-40.0 -30.0 -25.0 -15.0 0.0 15.0 25.0 30.0 40.0]

#endif
