#version 120
#define VERTEX_SHADER
/* AoiGlitch — gbuffers_water (vertex): water + all translucent blocks. */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/block_ids.glsl"

attribute vec4 mc_Entity;

varying vec2 texcoord;
varying vec2 lmcoord;
varying vec4 glcolor;
varying vec3 viewPos;
varying vec3 viewNormal;
varying vec3 playerPos;
varying float isWater;

void main() {
    texcoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    lmcoord  = (gl_TextureMatrix[1] * gl_MultiTexCoord1).xy;
    glcolor  = gl_Color;
    isWater  = float(int(mc_Entity.x + 0.5) == ID_WATER);

    vec4 vp = gl_ModelViewMatrix * gl_Vertex;
    viewPos = vp.xyz;
    playerPos = mat3(gbufferModelViewInverse) * vp.xyz + gbufferModelViewInverse[3].xyz;
    viewNormal = normalize(gl_NormalMatrix * gl_Normal);
    gl_Position = ftransform();
}
