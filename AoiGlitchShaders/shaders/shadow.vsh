#version 120
#define VERTEX_SHADER
/* AoiGlitch — shadow pass (vertex). Plants and leaves get the very same
   displacement as in gbuffers_terrain, so their shadows move with them. */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/block_ids.glsl"
#include "/lib/foliage.glsl"
#include "/lib/shadow_distort.glsl"

attribute vec4 mc_Entity;
attribute vec4 mc_midTexCoord;

varying vec2 texcoord;
varying vec4 glcolor;

void main() {
    texcoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    glcolor = gl_Color;

    int id = int(mc_Entity.x + 0.5);
    // in the shadow pass gl_ModelViewMatrix = shadowModelView (+ chunk offset)
    vec3 pPos = (shadowModelViewInverse * (gl_ModelViewMatrix * gl_Vertex)).xyz;
    vec3 wPos = pPos + cameraPosition;
    vec2 wDir = getWindDirection();
    float wStr = getWindStrength();
    float tWind = frameTimeCounter * windSpeed;

#ifdef WAVING_PLANTS
    if (id == ID_PLANT || id == ID_PLANT_LOWER || id == ID_PLANT_UPPER) {
        float isTop = gl_MultiTexCoord0.t < mc_midTexCoord.t ? 1.0 : 0.0;
        float hw = isTop;
        float plantH = 1.0;
        if (id == ID_PLANT_LOWER) { hw = 0.5 * isTop;       plantH = 2.0; }
        if (id == ID_PLANT_UPPER) { hw = 0.5 + 0.5 * isTop; plantH = 2.0; }
        pPos += plantWave(wPos, tWind, hw, plantH, wDir, wStr);
    }
#endif
#ifdef JELLY_LEAVES
    if (id == ID_LEAVES) {
        vec3 unusedNormal;
        pPos += leavesWave(wPos, tWind, frameTimeCounter, wDir, wStr,
                           jellyAmplitude, jellyFrequency, gl_Normal, unusedNormal);
    }
#endif

    vec4 clip = gl_ProjectionMatrix * (shadowModelView * vec4(pPos, 1.0));
    clip.xyz = distortShadow(clip.xyz);
    gl_Position = clip;
}
