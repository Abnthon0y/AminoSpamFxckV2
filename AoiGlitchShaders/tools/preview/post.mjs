// Runs the pack's real post-processing chain (composite1 -> composite2 ->
// composite3 -> final) on an ordinary screenshot with a synthetic depth map,
// using WebGL2 in headless Chromium. Lets you check bloom, the distance
// mosaic and the colour grading without launching Minecraft.
//
// Usage (from AoiGlitchShaders/):
//   NODE_PATH=$(npm root -g) node tools/preview/post.mjs <screenshot.png|jpg> <out.png> [horizon=0.45] [OPTION=value ...]
//   horizon: fraction of the image height (from the top) where the sky ends.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const here = path.dirname(new URL(import.meta.url).pathname);
const shaders = path.resolve(here, "../../shaders");

const [input, output, horizonArg, ...optArgs] = process.argv.slice(2);
if (!input || !output) {
  console.error("usage: post.mjs <screenshot> <out.png> [horizon] [OPTION=value ...]");
  process.exit(2);
}
const horizon = parseFloat(horizonArg ?? "0.45");
const options = Object.fromEntries(optArgs.map((a) => a.split("=")).map(([k, v]) => [k, v === "on" ? true : v === "off" ? false : v]));

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

const passes = ["composite1.fsh", "composite2.fsh", "composite3.fsh", "final.fsh"].map((f) => ({ name: f, src: toES(f) }));
const imgData = "data:image/" + (input.endsWith(".png") ? "png" : "jpeg") + ";base64," + fs.readFileSync(input).toString("base64");

const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const page = await browser.newPage();
await page.setContent(`<canvas id="c"></canvas>`);
const result = await page.evaluate(async ({ passes, imgData, horizon }) => {
  const img = new Image();
  img.src = imgData;
  await img.decode();
  const W = img.width, H = img.height;
  const canvas = document.getElementById("c");
  canvas.width = W; canvas.height = H;
  const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true });
  if (!gl.getExtension("EXT_color_buffer_float")) return { error: "no EXT_color_buffer_float" };

  const tex = (internal, format, type, data, mip) => {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    if (data instanceof HTMLImageElement) gl.texImage2D(gl.TEXTURE_2D, 0, internal, format, type, data);
    else gl.texImage2D(gl.TEXTURE_2D, 0, internal, W, H, 0, format, type, data);
    const nearest = internal === gl.R32F;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, nearest ? gl.NEAREST : mip ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, nearest ? gl.NEAREST : gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  };

  // camera: 70 deg vertical FOV, near 0.05, far 256 (16 chunks)
  const fov = 70 * Math.PI / 180, near = 0.05, far = 256, aspect = W / H;
  const f = 1 / Math.tan(fov / 2);
  // inverse of the GL perspective matrix (column-major)
  const projInv = new Float32Array([
    1 / (f / aspect), 0, 0, 0,
    0, 1 / f, 0, 0,
    0, 0, 0, (near - far) / (2 * far * near),
    0, 0, -1, (near + far) / (2 * far * near),
  ]);

  // synthetic depth: sky above the horizon line, a far tree line, then a
  // ground plane seen from 1.7 blocks high (distance = h / tan(angle down))
  const depth = new Float32Array(W * H);
  for (let y = 0; y < H; y++) {
    const v = 1 - (y + 0.5) / H;                     // 0 = top of the image
    const ang = (0.5 - v) * fov;                     // >0 above the view axis
    for (let x = 0; x < W; x++) {
      let d;
      if (v < horizon - 0.06) d = 1.0;
      else {
        let dist = v < horizon + 0.02 ? 180 + 40 * Math.sin(x * 0.05)
                 : Math.min(1.7 / Math.tan(Math.max(-(ang) + (0.5 - horizon) * fov, 0.004)), 200);
        const z = (far + near) / (far - near) - 2 * far * near / ((far - near) * dist);
        d = z * 0.5 + 0.5;
      }
      depth[y * W + x] = d;
    }
  }

  // a screenshot's top row must end up at the top of the GL framebuffer
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
  const colortex0 = tex(gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, img, false);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
  const depthtex0 = tex(gl.R32F, gl.RED, gl.FLOAT, depth, false);
  const colortex3 = tex(gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, null, true);
  const colortex4 = tex(gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, null, false);
  const colortex0b = tex(gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT, null, false);

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
    gl.uniform1f(gl.getUniformLocation(prog, "viewWidth"), W);
    gl.uniform1f(gl.getUniformLocation(prog, "viewHeight"), H);
    gl.uniform1f(gl.getUniformLocation(prog, "frameTimeCounter"), 12.0);
    gl.uniformMatrix4fv(gl.getUniformLocation(prog, "gbufferProjectionInverse"), false, projInv);
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
    run(passes[0], { colortex0 }, colortex3);                       // bright pass
    gl.bindTexture(gl.TEXTURE_2D, colortex3); gl.generateMipmap(gl.TEXTURE_2D);
    run(passes[1], { colortex3 }, colortex4);                       // bloom blur
    run(passes[2], { colortex0, colortex4, depthtex0 }, colortex0b); // bloom + mosaic
    run(passes[3], { colortex0: colortex0b }, null);                // grading
  } catch (e) {
    return { error: String(e) };
  }
  gl.finish();
  return { png: canvas.toDataURL("image/png") };
}, { passes, imgData, horizon });
await browser.close();
if (result.error) { console.error(result.error); process.exit(1); }
fs.writeFileSync(output, Buffer.from(result.png.split(",")[1], "base64"));
console.log("wrote", output);
