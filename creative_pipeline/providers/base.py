"""Image-generation provider interface.

The pipeline only ever talks to this interface. Swapping OpenAI for Firefly,
Stability, or a local ComfyUI server means adding one class, not touching the
pipeline. That is the main architectural decision in the project.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image


class ImageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, size: tuple[int, int]) -> Image.Image:
        """Return a hero image for the prompt, roughly at `size` (w, h)."""
