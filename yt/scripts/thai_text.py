"""Properly-shaped text rendering for Pillow.

Pillow's ImageDraw.text() has no complex-script shaping on this platform
(features.check("raqm") is False -- the Windows wheel doesn't bundle
libraqm), so combining Thai tone marks over certain vowels silently drop
(e.g. "ที่" -> "ที", "เชื่อ" -> "เชือ") instead of positioning correctly.
That changes word meaning, not just appearance, so it isn't cosmetic.

This renders through HarfBuzz (shaping: glyph selection + mark positioning)
and FreeType (rasterizing each shaped glyph), bypassing Pillow's unshaped
text path entirely. Both ship as self-contained pip wheels on Windows, so
no extra native DLLs need to be sourced or bundled.
"""
from functools import lru_cache

import freetype
import uharfbuzz as hb
from PIL import Image


@lru_cache(maxsize=16)
def _load(font_path: str, size: int):
    ft_face = freetype.Face(font_path)
    ft_face.set_pixel_sizes(0, size)

    with open(font_path, "rb") as f:
        font_bytes = f.read()
    hb_face = hb.Face(font_bytes)
    hb_font = hb.Font(hb_face)
    hb_font.scale = (size * 64, size * 64)

    return ft_face, hb_font


def _shape(text: str, font_path: str, size: int):
    ft_face, hb_font = _load(font_path, size)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf)
    return ft_face, buf.glyph_infos, buf.glyph_positions


def measure_text(text: str, font_path: str, size: int) -> float:
    if not text:
        return 0.0
    _, _, positions = _shape(text, font_path, size)
    return sum(p.x_advance for p in positions) / 64.0


def draw_text(
    img: Image.Image,
    xy: tuple[float, float],
    text: str,
    font_path: str,
    size: int,
    fill,
    stroke_width: int = 0,
    stroke_fill=None,
):
    """Draws `text` onto `img` (modified in place) at (x, y) = top-left of the line."""
    if not text:
        return
    ft_face, infos, positions = _shape(text, font_path, size)

    ascender = ft_face.size.ascender / 64.0
    pen_x, pen_y = xy[0], xy[1] + ascender

    for info, pos in zip(infos, positions):
        ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
        bitmap = ft_face.glyph.bitmap
        if bitmap.width and bitmap.rows:
            glyph_x = int(pen_x + pos.x_offset / 64.0 + ft_face.glyph.bitmap_left)
            glyph_y = int(pen_y - pos.y_offset / 64.0 - ft_face.glyph.bitmap_top)
            alpha = Image.frombytes("L", (bitmap.width, bitmap.rows), bytes(bitmap.buffer))

            if stroke_width > 0 and stroke_fill is not None:
                stroke_layer = Image.new("L", (bitmap.width + stroke_width * 2, bitmap.rows + stroke_width * 2), 0)
                for dx in range(-stroke_width, stroke_width + 1):
                    for dy in range(-stroke_width, stroke_width + 1):
                        if dx * dx + dy * dy <= stroke_width * stroke_width:
                            stroke_layer.paste(alpha, (stroke_width + dx, stroke_width + dy), alpha)
                solid = Image.new("RGB", stroke_layer.size, stroke_fill)
                img.paste(solid, (glyph_x - stroke_width, glyph_y - stroke_width), stroke_layer)

            solid = Image.new("RGB", alpha.size, fill)
            img.paste(solid, (glyph_x, glyph_y), alpha)

        pen_x += pos.x_advance / 64.0
        pen_y -= pos.y_advance / 64.0
