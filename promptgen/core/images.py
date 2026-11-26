"""Reading an image file into arrays the way ComfyUI's Load Image node does (PIL + numpy only)."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageOps


def load_image_arrays(path: str) -> tuple[np.ndarray, np.ndarray]:
    """(rgb, mask) for the first frame of an image.

    rgb is float32 H x W x 3 in 0..1. mask is float32 H x W, 1 where the image is transparent
    (ComfyUI's convention), all zeros when it has no alpha channel.
    """
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode == "I":
            img = img.point(lambda v: v * (1 / 255))
        rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
        if "A" in img.getbands() or (img.mode == "P" and "transparency" in img.info):
            alpha = np.asarray(img.convert("RGBA").getchannel("A"), dtype=np.float32) / 255.0
            mask = 1.0 - alpha
        else:
            mask = np.zeros(rgb.shape[:2], dtype=np.float32)
    return rgb, mask
