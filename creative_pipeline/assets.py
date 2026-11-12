"""Asset resolution: reuse an existing hero image, or generate one.

Lookup order for each product:
  1. the file named in the brief (`hero_asset`)
  2. any image in the assets folder whose name starts with the product id
  3. generate with the provider, then SAVE it back to the assets folder

Step 3 saving back is deliberate: the next run (or the next market) reuses it
instead of paying to generate again. That is the "reuse when available" rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .brief import Brief, Product
from .providers import ImageProvider

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
HERO_SIZE = (1536, 1536)  # large square master; every ratio is cropped from it


@dataclass
class ResolvedAsset:
    product_id: str
    image: Image.Image
    source: str        # "reused" or "generated"
    path: Path


def build_prompt(brief: Brief, product: Product) -> str:
    """Prompt is built from brief fields so creative stays on-brief and on-market."""
    brand = brief.brand.name if brief.brand else "the brand"
    return (
        f"Studio product photograph of {product.name} by {brand}. {product.description} "
        f"Styled for {brief.audience} in {brief.region}. Clean background, soft key light, "
        f"product centred with empty space at the bottom for a headline. No text, no logos."
    )


def find_existing(product: Product, assets_dir: Path) -> Path | None:
    if product.hero_asset:
        p = assets_dir / product.hero_asset
        return p if p.exists() else None
    for p in sorted(assets_dir.glob(f"{product.id}*")):
        if p.suffix.lower() in IMAGE_EXTS:
            return p
    return None


def resolve_hero(brief: Brief, product: Product, assets_dir: Path, provider: ImageProvider) -> ResolvedAsset:
    assets_dir.mkdir(parents=True, exist_ok=True)
    existing = find_existing(product, assets_dir)
    if existing:
        return ResolvedAsset(product.id, Image.open(existing).convert("RGB"), "reused", existing)

    image = provider.generate(build_prompt(brief, product), HERO_SIZE)
    out = assets_dir / f"{product.id}_hero_generated.png"
    image.save(out)
    return ResolvedAsset(product.id, image, "generated", out)


def load_logo(brief: Brief, assets_dir: Path) -> Image.Image | None:
    if not (brief.brand and brief.brand.logo):
        return None
    p = assets_dir / brief.brand.logo
    return Image.open(p).convert("RGBA") if p.exists() else None
