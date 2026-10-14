#ifndef AOI_PARAMS
#define AOI_PARAMS
/* =========================================================================
   AoiGlitch — the "control panel".
   These are the parameter names from the spec. Two kinds:

   1) STATIC parameters, set by the player in the Shader Options GUI.
      Iris/OptiFine cannot push arbitrary values into a uniform from the
      menu, so they are #define options (settings.glsl) aliased here as
      constants. To turn any of them into a real uniform: replace
          const float jellyAmplitude = JELLY_AMPLITUDE;
      by
          uniform float jellyAmplitude;
      and give it an expression in shaders.properties:
          uniform.float.jellyAmplitude = 0.03 + 0.02*rainStrength

   2) DYNAMIC parameters: real custom uniforms computed every frame by the
      loader from the expressions in shaders.properties (see there).
   ========================================================================= */

// ---- static (GUI) ---------------------------------------------------------
const int   skyStyle           = SKY_STYLE;
const float skyMix             = SKY_MIX;
const float skyWarpStrength    = SKY_WARP;
const float skySpeed           = SKY_SPEED;

const int   waterStyle         = WATER_STYLE;

const float glitchIntensity    = GLITCH_INTENSITY;
const float noiseAmount        = NOISE_AMOUNT;

const float jellyAmplitude     = JELLY_AMPLITUDE;
const float jellyFrequency     = JELLY_FREQUENCY;
const float windSpeed          = WIND_SPEED;

const float pixelStartDistance = PIXEL_START_DISTANCE;
const float pixelEndDistance   = PIXEL_END_DISTANCE;
const float pixelMaxSize       = PIXEL_MAX_SIZE;

const float bloomIntensity     = BLOOM_INTENSITY;
const float fogDensity         = FOG_DENSITY;
const float colorSaturation    = COLOR_SATURATION;

// ---- dynamic (shaders.properties custom uniforms) -------------------------
uniform float windStrength;    // 1 + 0.9*rainStrength  -> stronger wind in storms
uniform vec2  windDirection;   // slowly veering unit vector
uniform float skyMorph;        // 0..1, used by SKY_STYLE 3

// Fallbacks keep the pack working on a loader without custom uniforms
// (an unset uniform reads as 0).
vec2 getWindDirection() {
    return dot(windDirection, windDirection) > 0.25 ? normalize(windDirection) : vec2(0.8, 0.6);
}
float getWindStrength() {
    return WIND_STRENGTH * (windStrength > 0.001 ? windStrength : 1.0);
}
float getSkyMix() {
    return skyStyle == 3 ? skyMorph : skyMix;
}

#endif
