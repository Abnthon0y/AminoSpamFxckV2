/* =========================================================================
   AoiGlitch — shared code for the "simple" gbuffers programs.
   Without these programs a loader falls back along
       hand -> textured_lit -> textured -> basic -> (nothing)
   and with nothing at the end the first-person hand / held item, particles
   and outlines may not be drawn at all. Each wrapper picks a behaviour:
     GENERIC_TEXTURE   multiply by the bound texture
     GENERIC_LIGHTMAP  multiply by the vanilla lightmap (particles, rain)
     GENERIC_DREAM     full soft lighting, without shadows (the hand)
     (none of the two) fullbright: eyes, enchantment glint, beacon beam
   Needs: settings.glsl, common.glsl, uniforms.glsl
   ========================================================================= */

varying vec2 texcoord;
varying vec2 lmcoord;
varying vec4 glcolor;
varying vec3 viewNormal;
varying vec3 playerPos;

#ifdef VERTEX_SHADER

void main() {
    gl_Position = ftransform();
    texcoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    lmcoord  = (gl_TextureMatrix[1] * gl_MultiTexCoord1).xy;
    glcolor  = gl_Color;
    viewNormal = normalize(gl_NormalMatrix * gl_Normal);
    vec4 vp = gl_ModelViewMatrix * gl_Vertex;
    playerPos = mat3(gbufferModelViewInverse) * vp.xyz + gbufferModelViewInverse[3].xyz;
}

#else

#include "/lib/lighting.glsl"

uniform sampler2D texture;

void main() {
    vec4 col = glcolor;
#ifdef GENERIC_TEXTURE
    col *= texture2D(texture, texcoord);
#endif
    if (col.a < 0.01) discard;

#if defined GENERIC_DREAM
    col.rgb = dreamLighting(col.rgb, lmcoord, 1.0, normalize(viewNormal), playerPos,
                            0.0, gl_FragCoord.xy, 0.0);
#elif defined GENERIC_LIGHTMAP
    col.rgb *= texture2D(lightmap, lmcoord).rgb;
#endif
    gl_FragData[0] = col;
}

#endif
