#version 120
/* AoiGlitch — gbuffers_skytextured.
   The vanilla sun/moon squares are dropped (sun=false / moon=false in
   shaders.properties, and again here by render stage): lib/sky.glsl draws a
   glowing diamond sun and a soft moon instead. Everything else (End sky,
   resource-pack skies) passes through and is flagged as "sky drawn".        */

/* DRAWBUFFERS:02 */

uniform sampler2D texture;
uniform int renderStage;

varying vec2 texcoord;
varying vec4 glcolor;

void main() {
#if defined MC_RENDER_STAGE_SUN && defined MC_RENDER_STAGE_MOON
    if (renderStage == MC_RENDER_STAGE_SUN || renderStage == MC_RENDER_STAGE_MOON) discard;
#endif
    vec4 col = texture2D(texture, texcoord) * glcolor;
    gl_FragData[0] = col;
    gl_FragData[1] = vec4(0.0, 1.0, 0.0, col.a);
}
