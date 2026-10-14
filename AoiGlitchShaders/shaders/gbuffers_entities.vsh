#version 120
#define VERTEX_SHADER
/* AoiGlitch — gbuffers_entities (vertex).
   Isolation: Iris/OptiFine set the uniform entityId to the number mapped to
   the entity being drawn in entity.properties (entity.10000 = player). Only
   those draws get the glitch; blocks, sky and water never run this program. */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/block_ids.glsl"
#include "/lib/glitch.glsl"

varying vec2 texcoord;
varying vec2 lmcoord;
varying vec4 glcolor;
varying vec3 viewNormal;
varying vec3 playerPos;
varying float glitchOn;

void main() {
    texcoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    lmcoord  = (gl_TextureMatrix[1] * gl_MultiTexCoord1).xy;
    glcolor  = gl_Color;

    vec4 viewPos = gl_ModelViewMatrix * gl_Vertex;
    playerPos = mat3(gbufferModelViewInverse) * viewPos.xyz + gbufferModelViewInverse[3].xyz;
    viewNormal = normalize(gl_NormalMatrix * gl_Normal);
    gl_Position = gl_ProjectionMatrix * viewPos;

    glitchOn = 0.0;
#ifdef PLAYER_GLITCH
  #ifdef GLITCH_ALL_ENTITIES
    glitchOn = 1.0;
  #else
    glitchOn = float(entityId == ID_PLAYER);
  #endif
    // lost sync: during a burst the whole figure jumps sideways / vertically
    float burst = glitchBurst(frameTimeCounter) * glitchOn * glitchIntensity;
    float vframe = mod(floor(frameTimeCounter * 30.0), 97.0);
    gl_Position.x += burst * (hash11(vframe) - 0.5) * 0.06 * gl_Position.w;
    gl_Position.y += burst * step(0.6, hash11(vframe + 5.0)) * 0.02 * gl_Position.w;
#endif
}
