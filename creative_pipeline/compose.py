"""Composition: fit the hero into each aspect ratio and lay out message + logo.

Layout rules (kept simple and explicit so they are easy to defend):
  * output sizes are the social-platform standards for each ratio
  * the product is never cropped by default: the hero is fit whole ("contain") into
    the space above the message band, on a background matched to the photo's edges.
    "cover" (fill the frame, trim the overflow) is used only when the brief asks for it
  * the message sits in a brand-colour band inside a safe zone, so platform UI
    (Stories bars, captions) does not cover it
  * text auto-shrinks and wraps until it fits the band

PROPRIETARY BOUNDARY: geometric crops and fixed layout rules are a public POC
method. OCD RAPID STUDIO uses proprietary layout and production tools that
are not included in, or described by, this repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
    font: object = None                   # font used for the message (checked for missing glyphs)
    hero_box: tuple[int, int, int, int] | None = None  # where the whole product image was placed


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


def contain_fit(canvas: Image.Image, img: Image.Image, area: tuple[int, int, int, int],
                box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Scale the WHOLE image to fit inside `box` (no cropping) and paste it centred, untouched.

    The rest of `area` is filled by extending the photo's own outer edge (its studio backdrop)
    outwards and softening it, so the backdrop continues seamlessly. The product pixels are never
    blended, faded or cut. Returns the box the image actually occupies.
    """
    x0, y0, x1, y1 = box
    ax0, ay0, ax1, ay1 = area
    scale = min((x1 - x0) / img.width, (y1 - y0) / img.height)
    w, h = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    left, top = x0 + ((x1 - x0) - w) // 2, y0 + ((y1 - y0) - h) // 2
    fitted = img.convert("RGB").resize((w, h), Image.LANCZOS)

    # Backdrop: stretch the photo's 1-pixel outer rows/columns out to the edges of the area.
    aw, ah = ax1 - ax0, ay1 - ay0
    back = Image.new("RGB", (aw, ah))
    px, py = left - ax0, top - ay0                      # photo position inside the area
    edge = max(2, min(w, h) // 200)                     # average a few pixels to avoid streaks
    top_row = fitted.crop((0, 0, w, edge)).resize((w, 1), Image.BOX)
    bot_row = fitted.crop((0, h - edge, w, h)).resize((w, 1), Image.BOX)
    l_col = fitted.crop((0, 0, edge, h)).resize((1, h), Image.BOX)
    r_col = fitted.crop((w - edge, 0, w, h)).resize((1, h), Image.BOX)
    back.paste(fitted, (px, py))
    if py > 0:
        back.paste(top_row.resize((w, py)), (px, 0))
    if ah - (py + h) > 0:
        back.paste(bot_row.resize((w, ah - py - h)), (px, py + h))
    full_col_l = Image.new("RGB", (1, ah))
    full_col_l.paste(top_row.crop((0, 0, 1, 1)).resize((1, max(1, py))), (0, 0))
    full_col_l.paste(l_col, (0, py))
    full_col_l.paste(bot_row.crop((0, 0, 1, 1)).resize((1, max(1, ah - py - h))), (0, py + h))
    full_col_r = Image.new("RGB", (1, ah))
    full_col_r.paste(top_row.crop((w - 1, 0, w, 1)).resize((1, max(1, py))), (0, 0))
    full_col_r.paste(r_col, (0, py))
    full_col_r.paste(bot_row.crop((w - 1, 0, w, 1)).resize((1, max(1, ah - py - h))), (0, py + h))
    if px > 0:
        back.paste(full_col_l.resize((px, ah)), (0, 0))
    if aw - (px + w) > 0:
        back.paste(full_col_r.resize((aw - px - w, ah)), (px + w, 0))
    back = back.filter(ImageFilter.GaussianBlur(max(4, min(w, h) // 40)))   # soften the stretch

    canvas.paste(back, (ax0, ay0))
    canvas.paste(fitted, (left, top))                    # the product image itself, unaltered
    return (left, top, left + w, top + h)


def _font(size: int, script: str, fonts: dict | None = None) -> ImageFont.FreeTypeFont:
    """Brand fonts from the brief win; then system fallbacks for the script."""
    preferred = [f for f in ((fonts or {}).get(script), (fonts or {}).get("latin")) if f]
    for cand in preferred + FONT_CANDIDATES[script] + FONT_CANDIDATES["latin"]:
        try:
            font = ImageFont.truetype(cand, size)
        except OSError:
            continue
        try:  # variable fonts default to their lightest weight; headlines want Bold
            font.set_variation_by_name("Bold")
        except Exception:
            pass
        return font
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


def fit_text(draw, text: str, box_w: int, box_h: int, script: str,
             fonts: dict | None = None, max_size: int = 110):
    """Largest font size (down to a floor) whose wrapped text fits the box."""
    for size in range(min(int(box_h * 0.45), max_size), 18, -2):
        font = _font(size, script, fonts)
        lines = _wrap(draw, text, font, box_w, script == "cjk")
        line_h = int(size * 1.2)
        if len(lines) * line_h <= box_h and all(draw.textlength(l, font=font) <= box_w for l in lines):
            return font, lines, line_h
    font = _font(18, script, fonts)
    return font, _wrap(draw, text, font, box_w, script == "cjk"), 22


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def compose(hero: Image.Image, ratio: str, message: str, locale: str,
            band_color: str, text_color: str, logo: Image.Image | None,
            fonts: dict | None = None, fit: str = "contain") -> tuple[Image.Image, Layout]:
    w, h = output_size(ratio)
    margin = int(min(w, h) * 0.05)
    landscape = w > h

    # Logo size and position are known up front so the product can be placed clear of it.
    logo_w = logo_h = 0
    logo_top = int(h * 0.14) if ratio == "9:16" else margin
    if logo is not None:
        logo_w = int(w * (0.26 if ratio == "9:16" else 0.18))
        logo_h = round(logo.height * logo_w / logo.width)

    hero_box = None
    if landscape:
        # Wide formats: the product goes on the left, the message in a side panel on the right.
        hero_w = int(w * 0.58)
        canvas = Image.new("RGBA", (w, h), hex_to_rgb(band_color) + (255,))
        if fit == "cover":
            canvas.paste(cover_crop(hero, (hero_w, h)), (0, 0))
            hero_box = (0, 0, hero_w, h)
        else:
            top = logo_top + logo_h + margin // 2 if logo is not None else margin
            hero_box = contain_fit(canvas, hero, (0, 0, hero_w, h), (margin, top, hero_w - margin, h - margin))
        band = (hero_w + margin, margin * 3, w - margin, h - margin * 3)
    else:
        # Safe zone: Stories (9:16) keep ~14% clear top and bottom for platform UI.
        bottom_safe = int(h * 0.14) if ratio == "9:16" else margin
        band_h = int(h * (0.18 if ratio == "9:16" else 0.22))
        band = (margin, h - bottom_safe - band_h, w - margin, h - bottom_safe)
        if fit == "cover":
            canvas = cover_crop(hero, (w, h)).convert("RGBA")
            hero_box = (0, 0, w, h)
        else:
            # The whole product sits between the logo and the message band: nothing covers it.
            canvas = Image.new("RGBA", (w, h))
            top = logo_top + logo_h + margin // 2 if logo is not None else margin
            hero_box = contain_fit(canvas, hero, (0, 0, w, h), (margin, top, w - margin, band[1] - margin // 2))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(band, radius=margin // 2, fill=hex_to_rgb(band_color) + (235,))
    canvas = Image.alpha_composite(canvas, overlay)

    draw = ImageDraw.Draw(canvas)
    pad = margin // 2
    script = _script_for(locale)
    # Landscape side panel is tall and narrow: cap the size so headlines don't shout.
    font, lines, line_h = fit_text(draw, message, band[2] - band[0] - 2 * pad, band[3] - band[1] - 2 * pad,
                                   script, fonts, max_size=84 if landscape else 110)
    y = band[1] + ((band[3] - band[1]) - len(lines) * line_h) // 2
    for line in lines:
        x = band[0] + ((band[2] - band[0]) - draw.textlength(line, font=font)) // 2
        draw.text((x, y), line, font=font, fill=hex_to_rgb(text_color))
        y += line_h

    logo_box = None
    if logo is not None:
        logo_box = (margin, logo_top, margin + logo_w, logo_top + logo_h)
        canvas.alpha_composite(logo.resize((logo_w, logo_h), Image.LANCZOS), (margin, logo_top))

    return canvas.convert("RGB"), Layout(band, logo_box, font, hero_box)


def save(img: Image.Image, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / name
    img.save(p, quality=92)
    return p
