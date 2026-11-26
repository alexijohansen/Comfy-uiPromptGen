"""Save Settings."""

from __future__ import annotations

from ..comfy import CATEGORY
from ..core.settings import describe_settings
from .common import save_and_describe


class PromptGenSaveSettings:
    DESCRIPTION = (
        "Saves the settings of every KSampler in this run (seed, steps, cfg, sampler, scheduler, denoise), "
        "the model and the image resolution to a .txt file. Connect the decoded image so it runs after the "
        "image is made and records the real size. filename / filename_prefix work like Show / Save Text."
    )
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("settings",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"filename_prefix": ("STRING", {"default": "promptgen/settings"})},
            "optional": {"image": ("IMAGE",), "filename": ("STRING", {"forceInput": True})},
            "hidden": {"prompt": "PROMPT"},
        }

    def run(self, filename_prefix, image=None, filename=None, prompt=None):
        text = describe_settings(prompt, tuple(image.shape) if image is not None else None)
        saved = save_and_describe(text, filename_prefix, filename, "settings")
        return {"ui": {"text": [text], "saved_file": [saved]}, "result": (text,)}
