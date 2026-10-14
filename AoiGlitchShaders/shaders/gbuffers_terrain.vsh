#version 120
#define VERTEX_SHADER
/* AoiGlitch — gbuffers_terrain (vertex): waving plants + jelly leaves.
   Blocks are identified through mc_Entity.x, filled from block.properties. */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/block_ids.glsl"
#include "/lib/foliage.glsl"

attribute vec4 mc_Entity;
attribute vec4 mc_midTexCoord;

varying vec2 texcoord;
varying vec2 lmcoord;
varying vec4 glcolor;
varying vec3 viewNormal;
varying vec3 playerPos;
varying float foliage;
varying float emissive;

void main() {
    texcoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    lmcoord  = (gl_TextureMatrix[1] * gl_MultiTexCoord1).xy;
    glcolor  = gl_Color;                 // separateAo=true: rgb = tint, a = AO

    int id = int(mc_Entity.x + 0.5);
    vec3 normal = gl_Normal;             // terrain: model axes == world axes
    vec4 viewPos = gl_ModelViewMatrix * gl_Vertex;
    vec3 pPos = mat3(gbufferModelViewInverse) * viewPos.xyz + gbufferModelViewInverse[3].xyz;
    vec3 wPos = pPos + cameraPosition;   // continuous world position

    vec2 wDir = getWindDirection();
    float wStr = getWindStrength();
    float tWind = frameTimeCounter * windSpeed;
    bool animated = false;
    foliage = 0.0;
    emissive = float(id == ID_EMISSIVE);

#ifdef WAVING_PLANTS
    if (id == ID_PLANT || id == ID_PLANT_LOWER || id == ID_PLANT_UPPER) {
        // the top vertices of a cross-model plant use the upper half of its
        // texture: texcoord.y < mid texcoord.y  ->  0 at the root, 1 at the tip
        float isTop = gl_MultiTexCoord0.t < mc_midTexCoord.t ? 1.0 : 0.0;
        float hw = isTop;
        float plantH = 1.0;
        if (id == ID_PLANT_LOWER) { hw = 0.5 * isTop;       plantH = 2.0; }
        if (id == ID_PLANT_UPPER) { hw = 0.5 + 0.5 * isTop; plantH = 2.0; }
        pPos += plantWave(wPos, tWind, hw, plantH, wDir, wStr);
        normal = vec3(0.0, 1.0, 0.0);    // cross quads: light them like the ground
        foliage = 1.0;
        animated = true;
    }
#endif
#ifdef JELLY_LEAVES
    if (id == ID_LEAVES) {
        vec3 bentNormal;
        pPos += leavesWave(wPos, tWind, frameTimeCounter, wDir, wStr,
                           jellyAmplitude, jellyFrequency, normal, bentNormal);
        normal = bentNormal;             // analytic normal of the deformed surface
        foliage = 0.5;
        animated = true;
    }
#endif

    playerPos = pPos;
    viewNormal = normalize(gl_NormalMatrix * normal);
    gl_Position = animated ? gl_ProjectionMatrix * (gbufferModelView * vec4(pPos, 1.0))
                           : ftransform();
}
