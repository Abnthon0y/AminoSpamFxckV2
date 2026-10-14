// Runs the pack's real post-processing chain
//   composite (haze + light shafts) -> composite1 -> composite2 -> composite3 -> final
// on an ordinary screenshot with a synthetic depth map, using WebGL2 in
// headless Chromium. Lets you check the light shafts, bloom, the distance
// mosaic and the colour grading without launching Minecraft.
//
// Usage (from AoiGlitchShaders/):
//   NODE_PATH=$(npm root -g) node tools/preview/post.mjs <screenshot> <out.png> [key=value ...]
// keys:
//   horizon=0.45   fraction of the image height (from the top) where the ground starts
//   sun=0.5,0.2    position of the sun in the image (x, y from the top-left), for the shafts
//   skyLuma=0.55   above the horizon, pixels brighter than this count as open sky
//   fog=r,g,b      vanilla fog colour fed to the haze
//   any shader option, e.g. PIXELATION=on GODRAYS_STRENGTH=1.0
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const here = path.dirname(new URL(import.meta.url).pathname);
const shaders = path.resolve(here, "../../shaders");

const [input, output, ...kv] = process.argv.slice(2);
if (!input || !output) {
  console.error("usage: post.mjs <screenshot> <out.png> [key=value ...]");
  process.exit(2);
}
const args = Object.fromEntries(kv.map((a) => a.split("=")));
const scene = {
  horizon: parseFloat(args.horizon ?? "0.45"),
  sun: (args.sun ?? "0.5,0.2").split(",").map(Number),
  skyLuma: parseFloat(args.skyLuma ?? "0.55"),
  fog: (args.fog ?? "0.85,0.88,0.97").split(",").map(Number),
};
const options = Object.fromEntries(Object.entries(args)
  .filter(([k]) => /^[A-Z_]+$/.test(k))
  .map(([k, v]) => [k, v === "on" ? true : v === "off" ? false : v]));

function preprocess(file) {
  const src = fs.readFileSync(file, "utf8");
  return src.split("\n").map((line) => {
    const inc = line.match(/^\s*#include\s+"([^"]+)"/);
    if (inc) return preprocess(path.join(shaders, inc[1].replace(/^\//, "")));
    for (const [name, value] of Object.entries(options)) {
      if (new RegExp(`^\\s*(//\\s*)?#define\\s+${name}\\b`).test(line)) {
        return value === true ? `#define ${name}` : value === false ? `//#define ${name}` : `#define ${name} ${value}`;
      }
    }
    return line;
  }).join("\n");
}

// GLSL 1.20 program -> GLSL ES 3.00
function toES(file) {
  let src = preprocess(path.join(shaders, file));
  src = src.replace(/#version 120/, "#version 300 es\nprecision highp float;\nprecision highp int;\n#define texture2D texture\nout vec4 fragData0;");
  src = src.replace(/\bvarying\b/g, "in").replace(/gl_FragData\[0\]/g, "fragData0").replace(/gl_FragColor/g, "fragData0");
  return src;
}

const passes = ["composite.fsh", "composite1.fsh", "composite2.fsh", "composite3.fsh", "final.fsh"]
  .map((f) => ({ name: f, src: toES(f) }));
const imgData = "data:image/" + (input.endsWith(".png") ? "png" : "jpeg") + ";base64," + fs.readFileSync(input).toString("base64");
const atlas = "data:image/png;base64," + fs.readFileSync(path.join(shaders, "textures/jp_atlas.png")).toString("base64");

const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const page = await browser.newPage();
await page.setContent(`<canvas id="c"></canvas>`);
const result = await page.evaluate(async ({ passes, imgData, atlas, scene }) => {
  const load = async (src) => { const im = new Image(); im.src = src; await im.decode(); return im; };
  const img = await load(imgData);
  const atlasImg = await load(atlas);
  const W = img.width, H = img.height;
  const canvas = document.getElementById("c");
  canvas.width = W; canvas.height = H;
  const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true });
  if (!gl.getExtension("EXT_color_buffer_float")) return { error: "no EXT_color_buffer_float" };

  // read the screenshot's pixels (top row first) to find the open sky
  const c2 = document.createElement("canvas"); c2.width = W; c2.height = H;
  const ctx = c2.getContext("2d"); ctx.drawImage(img, 0, 0);
  const px = ctx.getImageData(0, 0, W, H).data;

  const tex = (internal, format, type, data, opts = {}) => {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    if (data instanceof HTMLImageElement) gl.texImage2D(gl.TEXTURE_2D, 0, internal, format, type, data);
    else gl.texImage2D(gl.TEXTURE_2D, 0, internal, W, H, 0, format, type, data);
    const filter = opts.nearest ? gl.NEAREST : gl.LINEAR;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, opts.mip ? gl.LINEAR_MIPMAP_LINEAR : filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  };

  // camera: 70 deg vertical FOV, near 0.05, far 256, looking along -z, up = +y
  const fov = 70 * Math.PI / 180, near = 0.05, far = 256, aspect = W / H;
  const f = 1 / Math.tan(fov / 2);
  const proj = new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) / (near - far), -1,
    0, 0, 2 * far * near / (near - far), 0,
  ]);
  const projInv = new Float32Array([
    aspect / f, 0, 0, 0,
    0, 1 / f, 0, 0,
    0, 0, 0, (near - far) / (2 * far * near),
    0, 0, -1, (near + far) / (2 * far * near),
  ]);
  const identity = new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
  // sun direction from its position in the image
  const sx = (scene.sun[0] * 2 - 1) * aspect / f, sy = (1 - scene.sun[1] * 2) / f;
  const sl = Math.hypot(sx, sy, 1);
  const sunPos = [sx / sl * 100, sy / sl * 100, -1 / sl * 100];

  // synthetic depth (GL row order: row 0 = bottom of the image)
  const depth = new Float32Array(W * H);
  const skyInfo = new Uint8Array(W * H * 4);
  for (let y = 0; y < H; y++) {
    const v = 1 - (y + 0.5) / H;                     // 0 = top of the image
    const ang = (0.5 - v) * fov;
    const srcRow = Math.floor(v * H);
    for (let x = 0; x < W; x++) {
      const i = (srcRow * W + x) * 4;
      const lum = (0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2]) / 255;
      let d;
      if (v < scene.horizon && lum > scene.skyLuma) d = 1.0;
      else {
        const dist = v < scene.horizon + 0.02 ? 150 + 30 * Math.sin(x * 0.05)
          : Math.min(1.7 / Math.tan(Math.max(-ang + (0.5 - scene.horizon) * fov, 0.004)), 200);
        d = ((far + near) / (far - near) - 2 * far * near / ((far - near) * dist)) * 0.5 + 0.5;
      }
      depth[y * W + x] = d;
      skyInfo[(y * W + x) * 4 + 1] = d >= 1.0 ? 255 : 0;    // g: "sky drawn here"
    }
  }

  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);              // screenshot top row -> top of the framebuffer
  const colortex0 = tex(gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, img);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
  const colortex12 = tex(gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, atlasImg);
  const depthtex0 = tex(gl.R32F, gl.RED, gl.FLOAT, depth, { nearest: true });
  const colortex2 = tex(gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, skyInfo, { nearest: true });
  const sceneA = tex(gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, null);
  const colortex3 = tex(gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, null, { mip: true });
  const colortex4 = tex(gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, null);
  const sceneB = tex(gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, null);

  const vsSrc = "#version 300 es\nin vec2 p; out vec2 texcoord; void main(){ texcoord = p * 0.5 + 0.5; gl_Position = vec4(p, 0.0, 1.0); }";
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);

  const run = (pass, inputs, target) => {
    const vs = gl.createShader(gl.VERTEX_SHADER); gl.shaderSource(vs, vsSrc); gl.compileShader(vs);
    const fs = gl.createShader(gl.FRAGMENT_SHADER); gl.shaderSource(fs, pass.src); gl.compileShader(fs);
    if (!gl.getShaderParameter(fs, gl.COMPILE_STATUS)) throw new Error(pass.name + ": " + gl.getShaderInfoLog(fs));
    const prog = gl.createProgram(); gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(pass.name + ": " + gl.getProgramInfoLog(prog));
    gl.useProgram(prog);
    const loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    let unit = 0;
    for (const [name, t] of Object.entries(inputs)) {
      gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.uniform1i(gl.getUniformLocation(prog, name), unit++);
    }
    const u = (n) => gl.getUniformLocation(prog, n);
    gl.uniform1f(u("viewWidth"), W);
    gl.uniform1f(u("viewHeight"), H);
    gl.uniform1f(u("frameTimeCounter"), 12.0);
    gl.uniform1f(u("far"), far);
    gl.uniform1f(u("near"), near);
    gl.uniform1f(u("rainStrength"), 0.0);
    gl.uniform1i(u("isEyeInWater"), 0);
    gl.uniform3f(u("cameraPosition"), 0, 70, 0);
    gl.uniform3f(u("sunPosition"), ...sunPos);
    gl.uniform3f(u("shadowLightPosition"), ...sunPos);
    gl.uniform3f(u("upPosition"), 0, 100, 0);
    gl.uniform3f(u("fogColor"), ...scene.fog);
    gl.uniformMatrix4fv(u("gbufferProjection"), false, proj);
    gl.uniformMatrix4fv(u("gbufferProjectionInverse"), false, projInv);
    gl.uniformMatrix4fv(u("gbufferModelViewInverse"), false, identity);
    gl.uniformMatrix4fv(u("gbufferModelView"), false, identity);
    let fb = null;
    if (target) {
      fb = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, target, 0);
    } else gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, W, H);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  };

  try {
    run(passes[0], { colortex0, colortex2, depthtex0, colortex12 }, sceneA);   // haze + shafts
    run(passes[1], { colortex0: sceneA }, colortex3);                           // bright pass
    gl.bindTexture(gl.TEXTURE_2D, colortex3); gl.generateMipmap(gl.TEXTURE_2D);
    run(passes[2], { colortex3 }, colortex4);                                   // bloom blur
    run(passes[3], { colortex0: sceneA, colortex4, depthtex0 }, sceneB);        // bloom (+ mosaic)
    run(passes[4], { colortex0: sceneB }, null);                                // grading
  } catch (e) {
    return { error: String(e) };
  }
  gl.finish();
  return { png: canvas.toDataURL("image/png") };
}, { passes, imgData, atlas, scene });
await browser.close();
if (result.error) { console.error(result.error); process.exit(1); }
fs.writeFileSync(output, Buffer.from(result.png.split(",")[1], "base64"));
console.log("wrote", output);
