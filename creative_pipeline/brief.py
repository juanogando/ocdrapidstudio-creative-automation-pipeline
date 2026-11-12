"""Campaign brief: load a YAML/JSON file and validate it into typed objects.

Why dataclasses and not a dict: every later stage (assets, compose, checks)
reads the same fields, so we validate ONCE here and fail early with a clear
message instead of crashing halfway through a render.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class BriefError(ValueError):
    """Raised when the brief is missing something the pipeline needs."""


@dataclass
class Product:
    id: str                     # used for folder names and asset lookup
    name: str                   # shown to humans / in prompts
    description: str = ""       # feeds the image-generation prompt
    hero_asset: str | None = None  # optional explicit file in the assets folder


@dataclass
class Brand:
    name: str
    primary_color: str = "#111111"   # hex, used for the message band
    secondary_color: str = "#FFFFFF" # hex, used for message text
    logo: str | None = None          # file in the assets folder


@dataclass
class Brief:
    campaign_id: str
    products: list[Product]
    region: str
    audience: str
    message: str                               # base (English) message
    locales: list[str] = field(default_factory=lambda: ["en-US"])
    translations: dict[str, str] = field(default_factory=dict)  # locale -> message
    brand: Brand | None = None
    aspect_ratios: list[str] = field(default_factory=lambda: ["1:1", "9:16", "16:9"])
    prohibited_terms: list[str] = field(default_factory=list)  # extra legal words to flag

    def message_for(self, locale: str) -> str:
        """Localized message if the brief supplies one, otherwise the base message."""
        return self.translations.get(locale, self.message)


REQUIRED = ("campaign_id", "products", "region", "audience", "message")


def load_brief(path: str | Path) -> Brief:
    path = Path(path)
    if not path.exists():
        raise BriefError(f"Brief not found: {path}")
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    return parse_brief(data)


def parse_brief(data: dict) -> Brief:
    if not isinstance(data, dict):
        raise BriefError("Brief must be a mapping (YAML object / JSON object).")

    missing = [k for k in REQUIRED if not data.get(k)]
    if missing:
        raise BriefError(f"Brief is missing required field(s): {', '.join(missing)}")

    products = [Product(**p) for p in data["products"]]
    if len(products) < 2:
        raise BriefError("Brief must contain at least two products.")
    ids = [p.id for p in products]
    if len(set(ids)) != len(ids):
        raise BriefError(f"Product ids must be unique: {ids}")

    brand = Brand(**data["brand"]) if data.get("brand") else None

    ratios = data.get("aspect_ratios", ["1:1", "9:16", "16:9"])
    for r in ratios:
        parse_ratio(r)  # raises if malformed

    return Brief(
        campaign_id=data["campaign_id"],
        products=products,
        region=data["region"],
        audience=data["audience"],
        message=data["message"],
        locales=data.get("locales", ["en-US"]),
        translations=data.get("translations", {}),
        brand=brand,
        aspect_ratios=ratios,
        prohibited_terms=data.get("prohibited_terms", []),
    )


def parse_ratio(ratio: str) -> tuple[int, int]:
    """'9:16' -> (9, 16). Kept here so the brief is validated in one place."""
    try:
        w, h = (int(x) for x in ratio.split(":"))
        if w <= 0 or h <= 0:
            raise ValueError
        return w, h
    except ValueError as exc:
        raise BriefError(f"Bad aspect ratio '{ratio}', expected like '16:9'") from exc
