"""Brand-compliance and legal checks, run on every finished creative.

These are guardrails, not a replacement for human review: they catch the
cheap, common mistakes before a regional approver ever sees the file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from PIL import Image

from .compose import Layout, hex_to_rgb

# Claims that typically need legal sign-off in ad copy. Extendable per brief.
DEFAULT_PROHIBITED = ["guaranteed", "cure", "cures", "risk-free", "miracle", "#1", "best ever", "100% safe"]


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _luminance(rgb) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a, b) -> float:
    """WCAG 2.x contrast ratio between two RGB colours (1.0 to 21.0)."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check_logo(layout: Layout, logo_expected: bool) -> CheckResult:
    if not logo_expected:
        return CheckResult("logo_present", True, "no logo in brief (skipped)")
    ok = layout.logo_box is not None
    return CheckResult("logo_present", ok, "logo placed" if ok else "logo missing from assets folder")


def check_brand_color(img: Image.Image, layout: Layout, brand_hex: str, tol: int = 40) -> CheckResult:
    """Sample the band's corner region (no text there) and compare to the brand colour."""
    x0, y0, x1, y1 = layout.band_box
    sample = img.crop((x0 + 12, y0 + 6, x0 + 40, y0 + 20)).resize((1, 1)).getpixel((0, 0))
    target = hex_to_rgb(brand_hex)
    dist = max(abs(s - t) for s, t in zip(sample, target))
    return CheckResult("brand_color", dist <= tol, f"band {sample} vs brand {target} (max diff {dist})")


def check_contrast(band_hex: str, text_hex: str, minimum: float = 4.5) -> CheckResult:
    ratio = contrast_ratio(hex_to_rgb(band_hex), hex_to_rgb(text_hex))
    return CheckResult("text_contrast", ratio >= minimum, f"{ratio:.1f}:1 (WCAG AA needs {minimum}:1)")


def check_legal(message: str, prohibited: list[str] | None = None) -> CheckResult:
    words = prohibited or DEFAULT_PROHIBITED
    hits = [w for w in words if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", message, re.IGNORECASE)]
    return CheckResult("legal_terms", not hits, f"flagged: {hits}" if hits else "no prohibited terms")
