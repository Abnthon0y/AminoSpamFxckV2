#!/usr/bin/env python3
"""Build shaders/textures/jp_atlas.png: 16x16 Japanese glyphs, white on black.

Usage:  python3 tools/make_atlas.py [path/to/font.ttf]
Any font with Japanese coverage works (IPAGothic, Noto Sans JP, ...).
Cell = 32 px, glyph ~24 px, centred -> 512 x 512 grayscale PNG. The shader
reads the red channel as coverage (lib/kanji.glsl, glyphTap()).
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HIRAGANA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
KATAKANA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンー"
# Kanji: a "system error / dream / sky" vocabulary + very common characters.
KANJI = (
    "致命的停止警告異常記憶破損電源接続再起動終了開始読込書込失敗成功"
    "夢空青花光水雲星月日風雨雪海川山森桜影闇静夜朝昼夕虹霧氷炎音声"
    "心魂目手口人生死時間世界中上下左右前後内外大小高低長短新古明暗"
    "白黒赤緑金銀紫黄灰色形線点面体文字言語書画像映写真実幻想現在過"
    "未来始終回転送受信号符化解析計算機械情報処理装置管制御入出力"
)
CHARS = (HIRAGANA + KATAKANA + KANJI)
CELL = 32
GRID = 16


def main():
    font_path = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
    chars = []
    for c in CHARS:
        if c not in chars:
            chars.append(c)
    chars = (chars * 2)[:GRID * GRID]          # exactly 256 glyphs
    font = ImageFont.truetype(font_path, 25)
    img = Image.new("L", (CELL * GRID, CELL * GRID), 0)
    draw = ImageDraw.Draw(img)
    for i, ch in enumerate(chars):
        cx = (i % GRID) * CELL + CELL / 2
        cy = (i // GRID) * CELL + CELL / 2
        draw.text((cx, cy), ch, fill=255, font=font, anchor="mm")
    out = os.path.join(os.path.dirname(__file__), "..", "shaders", "textures", "jp_atlas.png")
    img.save(os.path.normpath(out), optimize=True)
    print(f"{len(set(chars))} unique glyphs -> {os.path.normpath(out)}")


if __name__ == "__main__":
    main()
