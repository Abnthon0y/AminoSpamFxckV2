#ifndef AOI_UNIFORMS
#define AOI_UNIFORMS
/* =========================================================================
   AoiGlitch — standard Iris / OptiFine uniforms, declared once.
   (Samplers are declared in the programs that actually read them.)
   ========================================================================= */

uniform float frameTimeCounter;     // seconds, wraps every hour
uniform float rainStrength;
uniform float viewWidth;
uniform float viewHeight;
uniform float near;
uniform float far;
uniform int   isEyeInWater;         // 0 air, 1 water, 2 lava, 3 powder snow

uniform vec3 cameraPosition;
uniform vec3 sunPosition;           // view space, length 100
uniform vec3 upPosition;            // view space, length 100
uniform vec3 shadowLightPosition;   // sun by day, moon by night (view space)
uniform vec3 fogColor;
uniform vec3 skyColor;

uniform mat4 gbufferModelView;
uniform mat4 gbufferModelViewInverse;
uniform mat4 gbufferProjection;
uniform mat4 gbufferProjectionInverse;
uniform mat4 shadowModelView;
uniform mat4 shadowModelViewInverse;
uniform mat4 shadowProjection;

uniform int  renderStage;           // MC_RENDER_STAGE_* (Iris & OptiFine 1.17+)
uniform int  entityId;              // from entity.properties
uniform vec4 entityColor;           // red hurt flash / creeper white

// world-space sun direction (works in every program)
vec3 getSunDirWorld() {
    return normalize(mat3(gbufferModelViewInverse) * sunPosition);
}

#endif
