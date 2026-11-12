"""Composition: crop the hero to each aspect ratio and lay out message + logo.

Layout rules (kept simple and explicit so they are easy to defend):
  * output sizes are the social-platform standards for each ratio
  * crop = "cover" (fill the frame, trim the overflow), centred on the subject
  * the message sits in a brand-colour band inside a safe zone, so platform UI
    (Stories bars, captions) does not cover it
  * text auto-shrinks and wraps until it fits the band
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .brief import parse_ratio

OUTPUT_SIZES = {"1:1": (1080, 1080), "9:16": (1080, 1920), "16:9": (1920, 1080)}

FONT_CANDIDATES = {
    "latin": ["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "cjk": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "C:/Windows/Fonts/msyhbd.ttc",
            "/System/Library/Fonts/PingFang.ttc"],
}


@dataclass
class Layout:
    band_box: tuple[int, int, int, int]   # x0, y0, x1, y1 of the message band
    logo_box: tuple[int, int, int, int] | None


def output_size(ratio: str) -> tuple[int, int]:
    if ratio in OUTPUT_SIZES:
        return OUTPUT_SIZES[ratio]
    w, h = parse_ratio(ratio)          # any other ratio: 1080 on the short side
    return (1080, round(1080 * h / w)) if w <= h else (round(1080 * w / h), 1080)


def cover_crop(img: Image.Image, size: tuple[int, int], focus_x: float = 0.5, focus_y: float = 0.45) -> Image.Image:
    """Scale to fill `size`, then crop. focus_x/y (0-1) pick which part of the overflow survives."""
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = int((resized.width - tw) * focus_x)
    top = int((resized.height - th) * focus_y)
    return resized.crop((left, top, left + tw, top + th))


def _font(size: int, script: str) -> ImageFont.FreeTypeFont:
    for cand in FONT_CANDIDATES[script] + FONT_CANDIDATES["latin"]:
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _script_for(locale: str) -> str:
    return "cjk" if locale.split("-")[0] in {"ja", "zh", "ko"} else "latin"


# Japanese/Chinese punctuation that must not begin a line (simple kinsoku rule).
NO_LINE_START = set("。、，．・：；？！ー）」』】ぁぃぅぇぉっゃゅょァィゥェォッャュョ")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, cjk: bool) -> list[str]:
    units = list(text) if cjk else text.split()
    joiner = "" if cjk else " "
    lines, cur = [], ""
    for u in units:
        trial = f"{cur}{joiner}{u}" if cur else u
        # In CJK, let closing punctuation hang on the current line instead of starting a new one.
        if draw.textlength(trial, font=font) <= max_w or (cjk and u in NO_LINE_START):
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = u
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text: str, box_w: int, box_h: int, script: str):
    """Largest font size (down to a floor) whose wrapped text fits the box."""
    for size in range(min(int(box_h * 0.45), 120), 18, -2):
        font = _font(size, script)
        lines = _wrap(draw, text, font, box_w, script == "cjk")
        line_h = int(size * 1.2)
        if len(lines) * line_h <= box_h and all(draw.textlength(l, font=font) <= box_w for l in lines):
            return font, lines, line_h
    font = _font(18, script)
    return font, _wrap(draw, text, font, box_w, script == "cjk"), 22


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def compose(hero: Image.Image, ratio: str, message: str, locale: str,
            band_color: str, text_color: str, logo: Image.Image | None) -> tuple[Image.Image, Layout]:
    w, h = output_size(ratio)
    margin = int(min(w, h) * 0.05)
    landscape = w > h

    if landscape:
        # Wide formats: a square-ish hero cannot fill the width without losing the
        # product, so place the product on the left and the message in a side panel.
        hero_w = int(w * 0.58)
        canvas = Image.new("RGBA", (w, h), hex_to_rgb(band_color) + (255,))
        canvas.paste(cover_crop(hero, (hero_w, h)), (0, 0))
        band = (hero_w + margin, margin * 3, w - margin, h - margin * 3)
    else:
        canvas = cover_crop(hero, (w, h)).convert("RGBA")
        # Safe zone: Stories (9:16) keep ~14% clear top and bottom for platform UI.
        bottom_safe = int(h * 0.14) if ratio == "9:16" else margin
        band_h = int(h * (0.18 if ratio == "9:16" else 0.22))
        band = (margin, h - bottom_safe - band_h, w - margin, h - bottom_safe)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(band, radius=margin // 2, fill=hex_to_rgb(band_color) + (235,))
    canvas = Image.alpha_composite(canvas, overlay)

    draw = ImageDraw.Draw(canvas)
    pad = margin // 2
    script = _script_for(locale)
    font, lines, line_h = fit_text(draw, message, band[2] - band[0] - 2 * pad, band[3] - band[1] - 2 * pad, script)
    y = band[1] + ((band[3] - band[1]) - len(lines) * line_h) // 2
    for line in lines:
        x = band[0] + ((band[2] - band[0]) - draw.textlength(line, font=font)) // 2
        draw.text((x, y), line, font=font, fill=hex_to_rgb(text_color))
        y += line_h

    logo_box = None
    if logo is not None:
        lw = int(w * (0.26 if ratio == "9:16" else 0.18))
        lh = round(logo.height * lw / logo.width)
        top = int(h * 0.14) if ratio == "9:16" else margin
        logo_box = (margin, top, margin + lw, top + lh)
        canvas.alpha_composite(logo.resize((lw, lh), Image.LANCZOS), (margin, top))

    return canvas.convert("RGB"), Layout(band, logo_box)


def save(img: Image.Image, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    img.save(p, quality=92)
    return p
