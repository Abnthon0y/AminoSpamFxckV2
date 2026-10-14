#version 120
/* AoiGlitch — gbuffers_water (fragment).
   Water ignores its vanilla texture and is painted with a world-anchored
   procedural pattern (lib/water.glsl); everything else that is translucent
   (stained glass, ice, slime, honey...) is lit normally.                    */

/* DRAWBUFFERS:0 */

#include "/lib/settings.glsl"
#include "/lib/common.glsl"
#include "/lib/uniforms.glsl"
#include "/lib/params.glsl"
#include "/lib/lighting.glsl"
#include "/lib/atmosphere.glsl"
#include "/lib/water.glsl"

uniform sampler2D texture;

varying vec2 texcoord;
varying vec2 lmcoord;
varying vec4 glcolor;
varying vec3 viewPos;
varying vec3 viewNormal;
varying vec3 playerPos;
varying float isWater;

void main() {
    vec3 n = normalize(viewNormal);

    if (isWater > 0.5) {
        vec3 wp = playerPos + cameraPosition;
        vec3 wn = mat3(gbufferModelViewInverse) * n;
        // top faces use XZ; the sides of falling water use (x+z, y) so the
        // pattern visibly runs down the waterfall
        vec2 coords = abs(wn.y) > 0.5 ? wp.xz : vec2(wp.x + wp.z, wp.y * 1.6);
        vec3 water = getStylizedWater(coords, frameTimeCounter, waterStyle, getWindDirection());

        // vanilla lightmap: dark at night and in caves, torches still light it
        vec3 light = texture2D(lightmap, lmcoord).rgb;
        water *= mix(vec3(1.0), light, 0.85);

        // Fresnel: grazing angles get more opaque and pick up the haze colour
        vec3 viewDir = normalize(viewPos);
        float fres = pow(1.0 - abs(dot(viewDir, n)), 3.0);
        vec3 worldDir = mat3(gbufferModelViewInverse) * viewDir;
        vec3 haze = getHazeColor(worldDir, getSunDirWorld(), fogColor, rainStrength);
        water = mix(water, haze * light, fres * 0.35);

        gl_FragData[0] = vec4(water, mix(WATER_ALPHA, 1.0, fres));
        return;
    }

    vec4 albedo = texture2D(texture, texcoord) * vec4(glcolor.rgb, 1.0);
    if (albedo.a < 0.01) discard;
    vec3 col = dreamLighting(albedo.rgb, lmcoord, 1.0, n, playerPos, 0.0, gl_FragCoord.xy);
    gl_FragData[0] = vec4(col, albedo.a);
}
