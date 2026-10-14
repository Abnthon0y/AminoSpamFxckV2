// Offline preview of the pack's procedural functions.
//
// The lib/*.glsl files are written in the GLSL subset shared by desktop
// GLSL 1.20 and GLSL ES 3.00, so the very same code is compiled here by
// WebGL2 (headless Chromium / SwiftShader) and rendered to PNG files.
//
// Usage (from AoiGlitchShaders/):
//   NODE_PATH=$(npm root -g) node tools/preview/preview.mjs [outDir]
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const here = path.dirname(new URL(import.meta.url).pathname);
const shaders = path.resolve(here, "../../shaders");
const outDir = path.resolve(process.argv[2] || path.join(here, "../../docs/previews"));
fs.mkdirSync(outDir, { recursive: true });

const lib = (name) => fs.readFileSync(path.join(shaders, "lib", name), "utf8");

function settings(overrides) {
  let src = lib("settings.glsl");
  for (const [name, value] of Object.entries(overrides)) {
    const re = new RegExp(`^(\\s*)(//\\s*)?#define\\s+${name}\\b.*$`, "m");
    const line = value === true ? `#define ${name}` : value === false ? `//#define ${name}` : `#define ${name} ${value}`;
    src = src.replace(re, line);
  }
  return src;
}

const PRELUDE = `#version 300 es
precision highp float;
precision highp int;
#define texture2D texture
out vec4 fragColor;
uniform vec2 uRes;
uniform float uTime;
uniform sampler2D uAtlas;
uniform vec3 uSunDir;
uniform vec3 uFog;
uniform float uRain;
uniform vec4 uCam;      // yaw, pitch, fov, camera height
uniform int uStyle;
uniform float uMix;

vec3 camDir(vec2 fc) {
    vec2 ndc = fc / uRes * 2.0 - 1.0;
    float t = tan(radians(uCam.z) * 0.5);
    float yaw = radians(uCam.x);
    float pitch = radians(uCam.y);
    vec3 fwd = vec3(cos(pitch) * cos(yaw), sin(pitch), cos(pitch) * sin(yaw));
    vec3 right = normalize(cross(fwd, vec3(0.0, 1.0, 0.0)));
    vec3 up = cross(right, fwd);
    return normalize(fwd + ndc.x * t * (uRes.x / uRes.y) * right + ndc.y * t * up);
}
`;

const LIBS = ["common.glsl", "atmosphere.glsl", "sky.glsl", "kanji.glsl", "water.glsl", "glitch.glsl", "grading.glsl"];

const SKY_MAIN = `
void main() {
    vec2 fc = gl_FragCoord.xy;
    vec3 dir = camDir(fc);
    float textMask;
    vec3 col = getCustomSky(dir, uSunDir, uTime, uStyle, uMix, SKY_WARP, SKY_SPEED, uFog, uRain, textMask);
#if SKY_TEXT > 0
    // identical to composite.fsh
    vec3 txt = skyTextLayer(dir, uTime, fc, uAtlas);
    float blueness = (col.b - max(col.r, col.g)) / max(col.b, 1e-3);
    float mask = textMask * smoothstep(0.10, 0.30, blueness);
    col = mix(col, vec3(1.0), txt.x * mask * SKY_TEXT_OPACITY);
    col = mix(col, mix(vec3(1.0), col, txt.z), txt.y * mask * SKY_TEXT_OPACITY);
#endif
    fragColor = vec4(dreamGrade(col), 1.0);
}`;

const WATER_MAIN = `
void main() {
    vec3 dir = camDir(gl_FragCoord.xy);
    vec3 haze = getHazeColor(dir, uSunDir, uFog, uRain);
    vec3 col = haze;
    if (dir.y < -0.001) {
        float dist = uCam.w / -dir.y;
        vec3 hit = vec3(0.0, uCam.w, 0.0) + dir * dist;
        vec3 w = getStylizedWater(hit.xz + vec2(100.0, 40.0), uTime, uStyle, vec2(0.8, 0.6));
        float fres = pow(1.0 - abs(dir.y), 3.0);
        w = mix(w, haze, fres * 0.35);
        col = mix(w, haze, getFogFactor(dist, 62.0, 192.0, uRain));
    }
    fragColor = vec4(dreamGrade(col), 1.0);
}`;

// 2D stand-in for a player skin: boxes with "skin", "shirt", "pants" colours.
const GLITCH_MAIN = `
float sdBox(vec2 p, vec2 b) { vec2 d = abs(p) - b; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0); }
vec4 figure(vec2 p) {
    vec4 c = vec4(0.0);
    if (sdBox(p - vec2(0.0, 0.40), vec2(0.13, 0.13)) < 0.0) c = vec4(mix(vec3(0.86, 0.66, 0.52), vec3(0.25, 0.15, 0.08), step(0.47, p.y)), 1.0);
    if (sdBox(p - vec2(0.0, 0.06), vec2(0.13, 0.21)) < 0.0) c = vec4(0.10, 0.62, 0.70, 1.0);
    if (sdBox(vec2(abs(p.x), p.y) - vec2(0.205, 0.06), vec2(0.065, 0.21)) < 0.0) c = vec4(mix(vec3(0.86, 0.66, 0.52), vec3(0.10, 0.62, 0.70), step(0.13, p.y)), 1.0);
    if (sdBox(vec2(abs(p.x), p.y) - vec2(0.066, -0.40), vec2(0.064, 0.25)) < 0.0) c = vec4(mix(vec3(0.22, 0.24, 0.62), vec3(0.35), step(p.y, -0.58)), 1.0);
    return c;
}
void main() {
    vec2 fc = gl_FragCoord.xy;
    vec2 p = (fc - 0.5 * uRes) / uRes.y * 1.25 + vec2(0.0, 0.05);
    vec3 bg = mix(vec3(0.42, 0.62, 0.30), vec3(0.78, 0.86, 0.97), smoothstep(-0.55, -0.45, p.y));
    vec4 base = figure(p);
    vec3 col = bg;
    if (base.a > 0.5) {
        float burst = min(glitchBurst(uTime) * GLITCH_INTENSITY, 1.0);
        float off = glitchSliceOffset(fc, uTime, burst);
        vec4 shifted = figure(p + vec2(off * 0.09 * GLITCH_INTENSITY, 0.0));
        vec3 src = shifted.a > 0.5 ? shifted.rgb : base.rgb;
        col = glitchStyle(src, fc, uTime, burst, NOISE_AMOUNT);
    }
    fragColor = vec4(dreamGrade(col), 1.0);
}`;

function source(main, overrides) {
  return PRELUDE + settings(overrides) + LIBS.map(lib).join("\n") + main;
}

const SUN_DAY = [0.62, 0.55, -0.56];
const SUN_SET = [0.97, 0.06, -0.22];
const SUN_NIGHT = [-0.6, -0.55, 0.58];
const FOG_DAY = [0.75, 0.85, 1.0];
const FOG_SET = [0.93, 0.70, 0.58];
const FOG_NIGHT = [0.03, 0.04, 0.09];

const scenes = [
  { name: "sky_burst_up",      main: SKY_MAIN, opts: { SKY_TEXT: 0 }, style: 0, cam: [0, 80, 110, 0], sun: SUN_DAY, fog: FOG_DAY },
  { name: "sky_ink_up",        main: SKY_MAIN, opts: { SKY_TEXT: 0 }, style: 1, cam: [0, 80, 110, 0], sun: SUN_DAY, fog: FOG_DAY },
  { name: "sky_mix_up",        main: SKY_MAIN, opts: { SKY_TEXT: 0 }, style: 2, mix: 0.45, cam: [0, 80, 110, 0], sun: SUN_DAY, fog: FOG_DAY },
  { name: "sky_burst_horizon", main: SKY_MAIN, opts: { SKY_TEXT: 0 }, style: 0, cam: [-40, 22, 80, 0], sun: SUN_DAY, fog: FOG_DAY },
  { name: "sky_text_atlas",    main: SKY_MAIN, opts: { SKY_TEXT: 1 }, style: 0, cam: [10, 55, 70, 0], sun: SUN_DAY, fog: FOG_DAY },
  { name: "sky_text_procedural", main: SKY_MAIN, opts: { SKY_TEXT: 2 }, style: 0, cam: [10, 55, 70, 0], sun: SUN_DAY, fog: FOG_DAY },
  { name: "sky_text_ink_windows", main: SKY_MAIN, opts: { SKY_TEXT: 1 }, style: 1, cam: [-75, 18, 70, 0], sun: SUN_DAY, fog: FOG_DAY },
  { name: "sky_sunset",        main: SKY_MAIN, opts: { SKY_TEXT: 1 }, style: 2, mix: 0.3, cam: [-5, 12, 85, 0], sun: SUN_SET, fog: FOG_SET },
  { name: "sky_night",         main: SKY_MAIN, opts: { SKY_TEXT: 1 }, style: 0, cam: [0, 60, 100, 0], sun: SUN_NIGHT, fog: FOG_NIGHT },
  { name: "water_marble",      main: WATER_MAIN, opts: {}, style: 0, cam: [30, -38, 75, 6], sun: SUN_DAY, fog: FOG_DAY },
  { name: "water_caustics",    main: WATER_MAIN, opts: {}, style: 1, cam: [30, -38, 75, 6], sun: SUN_DAY, fog: FOG_DAY },
  { name: "water_currents",    main: WATER_MAIN, opts: {}, style: 2, cam: [30, -38, 75, 6], sun: SUN_DAY, fog: FOG_DAY },
  { name: "water_marble_caustics", main: WATER_MAIN, opts: {}, style: 3, cam: [30, -38, 75, 6], sun: SUN_DAY, fog: FOG_DAY },
  { name: "player_glitch_idle",  main: GLITCH_MAIN, opts: {}, time: 0.2, cam: [0, 0, 60, 0], sun: SUN_DAY, fog: FOG_DAY },
  { name: "player_glitch_burst", main: GLITCH_MAIN, opts: {}, time: -1, cam: [0, 0, 60, 0], sun: SUN_DAY, fog: FOG_DAY },
];

const W = 540, H = 960;
const atlas = "data:image/png;base64," + fs.readFileSync(path.join(shaders, "textures/jp_atlas.png")).toString("base64");

const browser = await chromium.launch({
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage();
await page.setContent(`<canvas id="c" width="${W}" height="${H}"></canvas>`);
await page.evaluate(async (atlasUrl) => {
  const gl = document.getElementById("c").getContext("webgl2", { preserveDrawingBuffer: true });
  if (!gl) throw new Error("no webgl2");
  const img = new Image();
  img.src = atlasUrl;
  await img.decode();
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  window.__gl = gl;
}, atlas);

// a time at which glitchBurst() fires (same hash as lib/glitch.glsl)
function hash11(p) { p = (p * 0.1031) % 1; p *= p + 33.33; p *= p + p; return p - Math.floor(p); }
let burstTime = 0;
for (let slot = 0; slot < 400; slot++) {
  if (hash11(slot * 1.31 + 0.7) >= 0.82 && hash11(slot + 4.4) > 0.6) { burstTime = slot / 2 + 0.01; break; }
}

for (const s of scenes) {
  const src = source(s.main, s.opts);
  const t0 = Date.now();
  const png = await page.evaluate(({ src, s, W, H, burstTime }) => {
    const gl = window.__gl;
    const vs = gl.createShader(gl.VERTEX_SHADER);
    gl.shaderSource(vs, "#version 300 es\nin vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }");
    gl.compileShader(vs);
    const fs = gl.createShader(gl.FRAGMENT_SHADER);
    gl.shaderSource(fs, src);
    gl.compileShader(fs);
    if (!gl.getShaderParameter(fs, gl.COMPILE_STATUS)) return { error: gl.getShaderInfoLog(fs) };
    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return { error: gl.getProgramInfoLog(prog) };
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const u = (n) => gl.getUniformLocation(prog, n);
    const sun = s.sun; const l = Math.hypot(...sun);
    gl.uniform2f(u("uRes"), W, H);
    gl.uniform1f(u("uTime"), s.time === -1 ? burstTime : (s.time ?? 37.0));
    gl.uniform1i(u("uAtlas"), 0);
    gl.uniform3f(u("uSunDir"), sun[0] / l, sun[1] / l, sun[2] / l);
    gl.uniform3f(u("uFog"), ...s.fog);
    gl.uniform1f(u("uRain"), 0.0);
    gl.uniform4f(u("uCam"), ...s.cam);
    gl.uniform1i(u("uStyle"), s.style ?? 0);
    gl.uniform1f(u("uMix"), s.mix ?? 0.5);
    gl.viewport(0, 0, W, H);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.finish();
    return { png: gl.canvas.toDataURL("image/png") };
  }, { src, s, W, H, burstTime });
  if (png.error) {
    console.error(`${s.name}: ${png.error}`);
    process.exitCode = 1;
    continue;
  }
  fs.writeFileSync(path.join(outDir, `${s.name}.png`), Buffer.from(png.png.split(",")[1], "base64"));
  console.log(`${s.name}.png  (${Date.now() - t0} ms)`);
}
await browser.close();
