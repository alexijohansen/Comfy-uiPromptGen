"""Counter: a number that moves on by one every run."""

from __future__ import annotations

from ..comfy import CATEGORY
from ..core.counting import take_number
from ..core.filenames import clean_name
from .common import AutoIncrementNode, auto_increment_input


class PromptGenCounter(AutoIncrementNode):
    DESCRIPTION = (
        "Outputs current_number and 'prefix_0001'. With auto_increment on, the number goes up by 1 every run, "
        "also in a batch. Type a number to jump to it. Nothing is stored on disk."
    )
    CATEGORY = CATEGORY
    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("number", "name")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prefix": ("STRING", {"default": "prompt"}),
                "digits": ("INT", {"default": 4, "min": 1, "max": 12}),
                "current_number": ("INT", {"default": 1, "min": 0, "max": 0x7FFFFFFFFFFFFFFF}),
                "auto_increment": auto_increment_input(),
            },
            "hidden": cls.HIDDEN,
        }

    def run(self, prefix, digits, current_number, auto_increment, unique_id=None):
        n = take_number(("counter", unique_id), current_number, auto_increment)
        padded = str(n).zfill(digits)
        name = clean_name(f"{prefix}_{padded}" if prefix else padded)
        return {"ui": {"next_number": [n + 1 if auto_increment else n]}, "result": (n, name)}
