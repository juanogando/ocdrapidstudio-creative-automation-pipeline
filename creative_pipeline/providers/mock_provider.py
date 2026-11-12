"""Offline provider: draws a deterministic placeholder 'hero' with Pillow.

Why it exists: reviewers can clone the repo and run the full pipeline with no
API key, no network and no cost. Same prompt -> same image (seeded by a hash),
so test runs are reproducible.
"""
from __future__ import annotations

import hashlib
import random

from PIL import Image, ImageDraw, ImageFilter

from .base import ImageProvider


class MockProvider(ImageProvider):
    name = "mock"

    def generate(self, prompt: str, size: tuple[int, int]) -> Image.Image:
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        w, h = size

        # Two-colour vertical gradient background.
        top = tuple(rng.randint(40, 200) for _ in range(3))
        bottom = tuple(max(0, c - 70) for c in top)
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(1, h - 1)
            draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))

        # Soft "studio light" blob.
        glow = Image.new("L", (w, h), 0)
        ImageDraw.Draw(glow).ellipse([w * 0.15, h * 0.1, w * 0.85, h * 0.8], fill=110)
        img.paste(Image.new("RGB", (w, h), (255, 255, 255)), mask=glow.filter(ImageFilter.GaussianBlur(w // 8)))

        # A simple "product" bottle shape in the centre so crops have a subject.
        cx, cy = w // 2, int(h * 0.48)
        bw, bh = int(w * 0.18), int(h * 0.42)
        body = tuple(rng.randint(20, 235) for _ in range(3))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2], radius=bw // 4, fill=body)
        draw.rectangle([cx - bw // 6, cy - bh // 2 - bh // 7, cx + bw // 6, cy - bh // 2], fill=(30, 30, 30))
        draw.rectangle([cx - bw // 2 + 6, cy - bh // 8, cx + bw // 2 - 6, cy + bh // 8], fill=(245, 245, 240))
        return img
