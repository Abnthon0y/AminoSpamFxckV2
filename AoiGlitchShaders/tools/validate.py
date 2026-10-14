#!/usr/bin/env python3
"""Compile every program of the pack with glslangValidator.

Mimics what Iris/OptiFine do before handing a program to the driver:
  * resolves  #include "/lib/..."  (paths relative to shaders/),
  * rewrites option #defines (value options and on/off toggles),
  * injects the loader macros right after #version (MC_VERSION, IS_IRIS,
    MC_RENDER_STAGE_*).
Each program is compiled for a set of option combinations, with and without
IS_IRIS (the OptiFine path binds the glyph atlas differently).

Usage:  python3 tools/validate.py            (needs glslangValidator in PATH)
"""
import itertools
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shaders")
INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"')
STAGES = ["NONE", "SKY", "SUNSET", "CUSTOM_SKY", "SUN", "MOON", "STARS", "VOID", "TERRAIN_SOLID",
          "TERRAIN_CUTOUT_MIPPED", "TERRAIN_CUTOUT", "ENTITIES", "BLOCK_ENTITIES", "DESTROY",
          "OUTLINE", "DEBUG", "HAND_SOLID", "TERRAIN_TRANSLUCENT", "TRIPWIRE", "PARTICLES",
          "CLOUDS", "RAIN_SNOW", "WORLD_BORDER", "HAND_TRANSLUCENT"]


def apply_options(line, options):
    for name, value in options.items():
        m = re.match(r'^(\s*)(//\s*)?#define\s+' + re.escape(name) + r'\b(.*)$', line)
        if not m:
            continue
        rest = m.group(3)
        if value is True:
            return f"#define {name}{rest}"
        if value is False:
            return f"//#define {name}{rest}"
        comment = rest[rest.index("//"):] if "//" in rest else ""
        return f"#define {name} {value} {comment}"
    return line


def preprocess(path, options, seen=None):
    seen = set() if seen is None else seen
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f.read().splitlines():
            m = INCLUDE_RE.match(line)
            if m:
                inc = os.path.join(ROOT, m.group(1).lstrip("/"))
                out.extend(preprocess(inc, options, seen))
                continue
            out.append(apply_options(line, options))
    return out


def build(program_path, options, iris):
    lines = preprocess(program_path, options)
    version_idx = next(i for i, l in enumerate(lines) if l.strip().startswith("#version"))
    macros = ["#define MC_VERSION 12004", "#define MC_GL_VERSION 460", "#define MC_GLSL_VERSION 460"]
    if iris:
        macros.append("#define IS_IRIS")
    macros += [f"#define MC_RENDER_STAGE_{s} {i}" for i, s in enumerate(STAGES)]
    return "\n".join(lines[:version_idx + 1] + macros + lines[version_idx + 1:]) + "\n"


VARIANTS = [
    {},
    {"SKY_STYLE": 0, "SKY_TEXT": 2, "WATER_STYLE": 1, "NOISE_STYLE": 0, "SKY_BURST_CENTER": 1},
    {"SKY_STYLE": 1, "SKY_TEXT": 0, "WATER_STYLE": 2, "NOISE_STYLE": 1, "SHADOWS": False, "BLOOM": False,
     "PIXELATION": True, "SKY_NIGHT_STYLE": 0},
    {"SKY_STYLE": 3, "WATER_STYLE": 3, "SKY_DROPS": False, "SKY_WINDOWS": False,
     "WAVING_PLANTS": False, "JELLY_LEAVES": False, "PLAYER_GLITCH": False, "GLITCH_ALL_ENTITIES": True,
     "GODRAYS": False, "LIGHT_PATCHES": False, "TORCH_FLICKER": False},
]


def main():
    programs = sorted(f for f in os.listdir(ROOT) if f.endswith((".vsh", ".fsh")))
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for prog, (vi, opts), iris in itertools.product(programs, enumerate(VARIANTS), (True, False)):
            src = build(os.path.join(ROOT, prog), opts, iris)
            stage = "vert" if prog.endswith(".vsh") else "frag"
            out = os.path.join(tmp, f"{prog}.{vi}.{int(iris)}.{stage}")
            with open(out, "w", encoding="utf-8") as f:
                f.write(src)
            res = subprocess.run(["glslangValidator", "-S", stage, out], capture_output=True, text=True)
            if res.returncode != 0:
                failures += 1
                print(f"FAIL {prog} variant={vi} iris={iris}\n{res.stdout}{res.stderr}")
    total = len(programs) * len(VARIANTS) * 2
    print(f"{total - failures}/{total} compilations OK ({len(programs)} programs x {len(VARIANTS)} option sets x 2 loaders)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
