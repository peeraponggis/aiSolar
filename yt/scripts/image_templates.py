"""Static image template renderers (Pillow + HarfBuzz/FreeType for text).

Each `render_*` function takes plain, user-supplied fields -- no field here
is tied to a specific real person, brand, or organization. Any "social post"
look (name, badge, counts) is filled in by whoever uses the template, not
hardcoded, so the output is a generic post-style graphic rather than a
recreation of a particular app or account.

Text is drawn via scripts.thai_text (HarfBuzz shaping + FreeType rasterizing)
rather than Pillow's own ImageDraw.text: this Pillow build has no raqm
support, so combining Thai tone marks over certain vowels silently drop
(e.g. "ที่" renders as "ที") instead of positioning correctly -- a
correctness bug, not a cosmetic one, in a Thai-language tool.
"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

from scripts.thai_text import draw_text as _draw_text, measure_text as _measure_text

FONTS_DIR = os.getenv("FONTS_DIR", "F:/LocalAI/tools/fonts")
FONT_FILES = {
    "sarabun": "Sarabun-Regular.ttf",
    "kanit": "Kanit-Regular.ttf",
}
DEFAULT_W, DEFAULT_H = 1080, 1920

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "uploads" / "templates"


def _font_path(name: str) -> str:
    path = os.path.join(FONTS_DIR, FONT_FILES.get(name, FONT_FILES["sarabun"]))
    if not os.path.exists(path):
        path = os.path.join(FONTS_DIR, FONT_FILES["sarabun"])
    return path


def _wrap_text(text: str, font_path: str, size: int, max_width: int) -> list[str]:
    """Greedy word-wrap. Falls back to character wrapping for scripts/strings with no spaces."""
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if _measure_text(trial, font_path, size) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)

    if len(lines) == 1 and _measure_text(lines[0], font_path, size) > max_width:
        line = lines[0]
        out, buf = [], ""
        for ch in line:
            if _measure_text(buf + ch, font_path, size) <= max_width:
                buf += ch
            else:
                out.append(buf)
                buf = ch
        if buf:
            out.append(buf)
        return out
    return lines


def _cover_resize(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize+crop to fill a w x h box, like CSS object-fit: cover."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    src_ratio = img.width / img.height
    dst_ratio = w / h
    if src_ratio > dst_ratio:
        new_h = h
        new_w = int(h * src_ratio)
    else:
        new_w = w
        new_h = int(w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _rounded_mask(size: tuple[int, int], radius: int, supersample: int = 4) -> Image.Image:
    w, h = size
    big = (w * supersample, h * supersample)
    mask = Image.new("L", big, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, big[0] - 1, big[1] - 1], radius=radius * supersample, fill=255)
    return mask.resize(size, Image.LANCZOS)


def _oval_mask(size: tuple[int, int], supersample: int = 4) -> Image.Image:
    w, h = size
    big = (w * supersample, h * supersample)
    mask = Image.new("L", big, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, big[0] - 1, big[1] - 1], fill=255)
    return mask.resize(size, Image.LANCZOS)


def _save(img: Image.Image, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.convert("RGB").save(out_path, "PNG")


# ---------------------------------------------------------------------------
# Template 1: Quote Card -- photo background, quote text banner, credit badge
# ---------------------------------------------------------------------------
def render_quote_card(
    photo_path: str,
    out_path: str,
    quote_en: str = "",
    quote_th: str = "",
    credit: str = "",
    border_color: str = "#8b3a2f",
    font_name: str = "sarabun",
    w: int = DEFAULT_W, h: int = DEFAULT_H,
) -> str:
    fpath = _font_path(font_name)
    border = max(10, w // 60)
    canvas = Image.new("RGB", (w, h), border_color)
    inner = _cover_resize(Image.open(photo_path), w - border * 2, h - border * 2)
    canvas.paste(inner, (border, border))

    draw = ImageDraw.Draw(canvas, "RGBA")

    pad = int(w * 0.08)
    max_text_w = w - pad * 2
    en_size = int(w * 0.052)
    th_size = int(w * 0.040)

    en_lines = _wrap_text(quote_en, fpath, en_size, max_text_w) if quote_en.strip() else []
    th_lines = _wrap_text(quote_th, fpath, th_size, max_text_w) if quote_th.strip() else []

    line_gap = int(w * 0.015)
    en_lh = en_size + line_gap
    th_lh = th_size + line_gap
    banner_h = pad + len(en_lines) * en_lh + (int(w * 0.02) if th_lines else 0) + len(th_lines) * th_lh + pad
    banner_top = int(h * 0.12)

    draw.rectangle([0, banner_top, w, banner_top + banner_h], fill=(0, 0, 0, 150))

    y = banner_top + pad
    for line in en_lines:
        tw = _measure_text(line, fpath, en_size)
        _draw_text(canvas, ((w - tw) / 2, y), line, fpath, en_size, "white")
        y += en_lh
    if th_lines:
        y += int(w * 0.02)
        for line in th_lines:
            tw = _measure_text(line, fpath, th_size)
            _draw_text(canvas, ((w - tw) / 2, y), line, fpath, th_size, "#f0f0f0")
            y += th_lh

    if credit.strip():
        badge_size = int(w * 0.034)
        tw = _measure_text(credit.strip(), fpath, badge_size)
        bx0, by0 = border + int(w * 0.04), h - border - int(w * 0.09)
        bx1, by1 = bx0 + tw + int(w * 0.06), by0 + int(w * 0.07)
        draw.rectangle([bx0, by0, bx1, by1], fill="white")
        _draw_text(canvas, (bx0 + int(w * 0.03), by0 + int(w * 0.015)), credit.strip(), fpath, badge_size, "#222")

    _save(canvas, out_path)
    return out_path


# ---------------------------------------------------------------------------
# Template 2: Before / After -- two stacked polaroid-style photos
# ---------------------------------------------------------------------------
def render_before_after(
    photo_before: str,
    photo_after: str,
    out_path: str,
    label_before: str = "",
    label_after: str = "",
    bg_color: str = "#c9bfa5",
    font_name: str = "sarabun",
    w: int = DEFAULT_W, h: int = DEFAULT_H,
) -> str:
    fpath = _font_path(font_name)
    canvas = Image.new("RGB", (w, h), bg_color)
    draw = ImageDraw.Draw(canvas)
    label_size = int(w * 0.042)

    card_w = int(w * 0.72)
    photo_h = int(h * 0.30)
    card_pad = int(w * 0.025)
    label_h = int(h * 0.055)
    card_h = photo_h + card_pad * 2 + label_h
    gap = int(h * 0.025)

    total_h = card_h * 2 + gap
    top0 = (h - total_h) // 2
    x0 = (w - card_w) // 2

    for i, (photo, label) in enumerate([(photo_before, label_before), (photo_after, label_after)]):
        cy0 = top0 + i * (card_h + gap)
        draw.rectangle([x0, cy0, x0 + card_w, cy0 + card_h], fill="white")
        photo_img = _cover_resize(Image.open(photo), card_w - card_pad * 2, photo_h)
        canvas.paste(photo_img, (x0 + card_pad, cy0 + card_pad))
        if label.strip():
            tw = _measure_text(label.strip(), fpath, label_size)
            ly = cy0 + card_pad * 2 + photo_h + (label_h - label_size) // 2
            _draw_text(canvas, (x0 + (card_w - tw) / 2, ly), label.strip(), fpath, label_size, "#333")

    _save(canvas, out_path)
    return out_path


# ---------------------------------------------------------------------------
# Template 3: Framed Photo -- single photo in an oval/rounded frame
# ---------------------------------------------------------------------------
def render_framed_photo(
    photo_path: str,
    out_path: str,
    shape: str = "oval",  # "oval" | "rounded"
    frame_color1: str = "#a7c7e7",
    frame_color2: str = "#e7a7c9",
    bg_color: str = "#f3f1ec",
    w: int = DEFAULT_W, h: int = DEFAULT_H,
) -> str:
    canvas = Image.new("RGB", (w, h), bg_color)

    frame_w = int(w * 0.80)
    frame_h = int(h * 0.55)
    fx0 = (w - frame_w) // 2
    fy0 = (h - frame_h) // 2
    border = int(w * 0.018)

    # gradient ring behind the frame
    gradient = Image.new("RGB", (frame_w + border * 2, frame_h + border * 2))
    gdraw = ImageDraw.Draw(gradient)
    for yy in range(gradient.height):
        t = yy / max(1, gradient.height - 1)
        col = _lerp_color(frame_color1, frame_color2, t)
        gdraw.line([(0, yy), (gradient.width, yy)], fill=col)

    mask_fn = _oval_mask if shape == "oval" else (lambda size: _rounded_mask(size, radius=int(min(size) * 0.08)))
    ring_mask = mask_fn(gradient.size)
    canvas.paste(gradient, (fx0 - border, fy0 - border), ring_mask)

    photo_img = _cover_resize(Image.open(photo_path), frame_w, frame_h)
    photo_mask = mask_fn((frame_w, frame_h))
    canvas.paste(photo_img, (fx0, fy0), photo_mask)

    _save(canvas, out_path)
    return out_path


def _draw_checkmark(draw: ImageDraw.ImageDraw, x: float, y: float, d: float, color: str):
    """A simple check mark inside a d x d box starting at (x, y)."""
    p1 = (x + d * 0.22, y + d * 0.52)
    p2 = (x + d * 0.42, y + d * 0.72)
    p3 = (x + d * 0.80, y + d * 0.28)
    width = max(2, int(d * 0.12))
    draw.line([p1, p2, p3], fill=color, width=width, joint="curve")


def _draw_stat_icon(draw: ImageDraw.ImageDraw, kind: str, x: float, y: float, d: float):
    """Simple geometric placeholder icons (heart / speech bubble / arrow)."""
    if kind == "heart":
        r = d * 0.28
        draw.ellipse([x, y, x + r * 2, y + r * 2], fill="white")
        draw.ellipse([x + r * 1.2, y, x + r * 3.2, y + r * 2], fill="white")
        draw.polygon([
            (x, y + r * 1.1), (x + r * 2.2, y + d * 0.95), (x + r * 3.2, y + r * 1.1),
        ], fill="white")
    elif kind == "comment":
        draw.rounded_rectangle([x, y, x + d, y + d * 0.75], radius=d * 0.18, fill="white")
        draw.polygon([
            (x + d * 0.22, y + d * 0.70), (x + d * 0.40, y + d * 0.70), (x + d * 0.18, y + d * 0.95),
        ], fill="white")
    else:  # share / arrow
        draw.polygon([
            (x, y + d * 0.5), (x + d * 0.6, y), (x + d * 0.6, y + d * 0.25),
            (x + d, y + d * 0.25), (x + d, y + d * 0.75), (x + d * 0.6, y + d * 0.75),
            (x + d * 0.6, y + d),
        ], fill="white")


def _lerp_color(c1: str, c2: str, t: float) -> tuple[int, int, int]:
    def hex2rgb(c):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    a, b = hex2rgb(c1), hex2rgb(c2)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------------------
# Template 4: Social / News Repost -- generic configurable "post" look.
# Every label (channel name, counts, verified badge) is a plain parameter;
# nothing here is tied to a specific real account.
# ---------------------------------------------------------------------------
def _draw_social_repost_chrome(
    canvas: Image.Image,
    fpath: str,
    w: int, h: int,
    row_y: int,
    headline: str, channel_name: str, verified: bool,
    like_count: str, comment_count: str, share_count: str,
    caption: str,
    backing_panels: bool = False,
):
    """Draws the headline/channel-row/stats/caption chrome used by both the
    static image template and the transparent video-overlay variant. `row_y`
    is where the channel row + stats column start (just below wherever the
    caller's content -- a photo, or the live video showing through -- ends).

    `backing_panels` paints semi-opaque panels behind the headline and the
    bottom info area first. The static image template doesn't need this (its
    canvas already has a solid background); the video overlay is transparent
    everywhere, so without a panel the text would sit directly over whatever
    the video happens to show at that moment, including arbitrary bright
    footage -- unreadable.

    The layout was designed for 9:16. When w > h it switches to a landscape
    layout: sizes scale with the shorter side, and the channel row, caption
    and stats column are stacked up from the bottom edge (`row_y` is ignored)
    so nothing lands mid-frame or runs off the bottom.
    """
    draw = ImageDraw.Draw(canvas, "RGBA")
    landscape = w > h
    u = min(w, h)  # == w in portrait, so the 9:16 geometry is unchanged

    head_size = int(u * 0.06)
    head_lines = _wrap_text(headline.strip(), fpath, head_size, int(w * 0.85))[:3] if headline.strip() else []
    head_line_h = head_size + int(u * 0.015)
    head_y = int(u * 0.03) if landscape else int(h * 0.04)

    chan_size = int(u * 0.034)
    av_d = int(u * 0.09)
    av_x, av_y = int(u * 0.04), row_y

    cap_size = int(u * 0.036)
    cap_lines = (_wrap_text(caption.strip(), fpath, cap_size, int(w * (0.6 if landscape else 0.8)))[:3]
                 if caption.strip() else [])
    cap_y = h - int(h * 0.10) - len(cap_lines) * (cap_size + 6)

    stats = [(icon, count) for icon, count in
             [("heart", like_count), ("comment", comment_count), ("share", share_count)]
             if str(count).strip()]
    stat_size = int(u * 0.032)
    icon_d = int(u * 0.055)
    sx = w - int(u * 0.09)
    sy = row_y
    stat_pitch = int(h * 0.09)

    if landscape:
        # Bottom-up: caption sits on the bottom margin, the channel row above
        # it, and the stats column ends on the same margin at the right.
        margin = int(u * 0.04)
        box = lambda size: int(size * 1.32)  # Sarabun ascender+descender
        bottom = h - margin
        if cap_lines:
            cap_y = bottom - (len(cap_lines) - 1) * (cap_size + 6) - box(cap_size)
            bottom = cap_y - int(u * 0.02)
        av_y = bottom - av_d
        info_top = av_y if channel_name.strip() else (cap_y if cap_lines else h)

        stat_size = int(u * 0.03)
        icon_d = int(u * 0.05)
        stat_pitch = int(u * 0.115)
        sx = w - int(u * 0.075)
        col_h = (len(stats) - 1) * stat_pitch + icon_d + 4 + box(stat_size) if stats else 0
        sy = h - margin - col_h

    if backing_panels:
        if headline.strip():
            if landscape:
                head_bottom = head_y + (len(head_lines) - 1) * head_line_h + int(head_size * 1.32) + int(u * 0.02)
            else:
                head_bottom = int(h * 0.04) + int(w * 0.06) * 3
            draw.rectangle([0, 0, w, head_bottom], fill=(0, 0, 0, 160))
        if landscape:
            # One shape (bottom band + a tab rising behind the stats column)
            # so the overlap isn't darkened twice.
            pad = int(u * 0.025)
            shade = Image.new("L", (w, h), 0)
            if stats:
                half = int(u * 0.055)
                tab = (sx - half, sy - pad, sx + half, h + pad)  # bottom corners off-frame
                shade.paste(150, tab, _rounded_mask((tab[2] - tab[0], tab[3] - tab[1]), radius=pad))
            if info_top < h:
                ImageDraw.Draw(shade).rectangle([0, info_top - pad, w, h], fill=150)
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            layer.putalpha(shade)
            canvas.alpha_composite(layer)
        elif channel_name.strip() or caption.strip() or like_count or comment_count or share_count:
            draw.rectangle([0, row_y - int(h * 0.01), w, h], fill=(0, 0, 0, 150))

    y = head_y
    for line in head_lines:
        tw = _measure_text(line, fpath, head_size)
        _draw_text(canvas, ((w - tw) / 2, y), line, fpath, head_size, "#ffcc33")
        y += head_line_h

    if channel_name.strip():
        initial = channel_name.strip()[0].upper()
        draw.ellipse([av_x, av_y, av_x + av_d, av_y + av_d], fill="#555")
        init_size = int(av_d * 0.5)
        iw = _measure_text(initial, fpath, init_size)
        _draw_text(canvas, (av_x + (av_d - iw) / 2, av_y + av_d * 0.15), initial, fpath, init_size, "white")

        name_x = av_x + av_d + int(u * 0.025)
        _draw_text(canvas, (name_x, av_y + av_d * 0.15), channel_name.strip(), fpath, chan_size, "white")
        if verified:
            nw = _measure_text(channel_name.strip(), fpath, chan_size)
            bd = int(u * 0.03)
            badge_x = name_x + nw + int(u * 0.015)
            badge_y = av_y + av_d * 0.2
            draw.ellipse([badge_x, badge_y, badge_x + bd, badge_y + bd], fill="#3b9cff")
            _draw_checkmark(draw, badge_x, badge_y, bd, color="white")

    # Right-side engagement column: drawn icons (font glyph coverage for
    # heart/speech-bubble/arrow symbols is unreliable with Thai-only fonts)
    for icon, count in stats:
        _draw_stat_icon(draw, icon, sx - icon_d / 2, sy, icon_d)
        ctw = _measure_text(str(count), fpath, stat_size)
        _draw_text(canvas, (sx - ctw / 2, sy + icon_d + 4), str(count), fpath, stat_size, "white")
        sy += stat_pitch

    y = cap_y
    for line in cap_lines:
        _draw_text(canvas, (int(u * 0.04), y), line, fpath, cap_size, "white",
                   stroke_width=2, stroke_fill="black")
        y += cap_size + 6


def render_social_repost(
    photo_path: str,
    out_path: str,
    headline: str = "",
    channel_name: str = "",
    verified: bool = False,
    like_count: str = "",
    comment_count: str = "",
    share_count: str = "",
    caption: str = "",
    font_name: str = "sarabun",
    w: int = DEFAULT_W, h: int = DEFAULT_H,
) -> str:
    fpath = _font_path(font_name)
    canvas = Image.new("RGB", (w, h), "#111")
    content_h = int(h * 0.55)
    content = _cover_resize(Image.open(photo_path), w, content_h)
    content_top = int(h * 0.20)
    canvas.paste(content, (0, content_top))

    row_y = content_top + content_h + int(h * 0.015)
    _draw_social_repost_chrome(
        canvas, fpath, w, h, row_y,
        headline, channel_name, verified,
        like_count, comment_count, share_count, caption,
    )

    _save(canvas, out_path)
    return out_path


def render_social_repost_overlay(
    out_path: str,
    headline: str = "",
    channel_name: str = "",
    verified: bool = False,
    like_count: str = "",
    comment_count: str = "",
    share_count: str = "",
    caption: str = "",
    font_name: str = "sarabun",
    w: int = DEFAULT_W, h: int = DEFAULT_H,
    content_top_frac: float = 0.20,
    content_h_frac: float = 0.55,
) -> str:
    """Same chrome as render_social_repost, but on a transparent canvas with
    no baked-in photo -- meant to be composited over a real video via
    FFmpeg's overlay filter, with `content_top_frac`/`content_h_frac`
    marking the empty band where the live video shows through.
    """
    fpath = _font_path(font_name)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    row_y = int(h * content_top_frac) + int(h * content_h_frac) + int(h * 0.015)
    _draw_social_repost_chrome(
        canvas, fpath, w, h, row_y,
        headline, channel_name, verified,
        like_count, comment_count, share_count, caption,
        backing_panels=True,
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, "PNG")
    return out_path
