"""OpenAI Images API provider (gpt-image-1).

Plain HTTP via `requests` instead of the SDK: one less dependency, and the
request/response is easy to read in an interview.
"""
from __future__ import annotations

import base64
import io
import os

import requests
from PIL import Image

from .base import ImageProvider

API_URL = "https://api.openai.com/v1/images/generations"


class OpenAIProvider(ImageProvider):
    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 120):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.model = model or os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
        self.timeout = timeout

    @staticmethod
    def _closest_size(size: tuple[int, int]) -> str:
        # gpt-image-1 accepts three sizes; pick the one nearest the target shape.
        w, h = size
        if abs(w - h) / max(w, h) < 0.15:
            return "1024x1024"
        return "1536x1024" if w > h else "1024x1536"

    def generate(self, prompt: str, size: tuple[int, int]) -> Image.Image:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "prompt": prompt, "size": self._closest_size(size), "n": 1},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI image error {resp.status_code}: {resp.text[:300]}")
        b64 = resp.json()["data"][0]["b64_json"]
        return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
