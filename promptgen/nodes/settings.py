"""Save Settings."""

from __future__ import annotations

from ..comfy import CATEGORY
from ..core.settings import collect_settings, settings_json
from .common import save_and_describe


class PromptGenSaveSettings:
    DESCRIPTION = (
        "Saves the positive and negative prompt, the settings of every KSampler in this run (seed, steps, cfg, "
        "sampler, scheduler, denoise), the models, the LoRAs and the image resolution to a .json file. Connect the decoded "
        "image so it runs after the image is made and records the real size. filename / filename_prefix work "
        "like Show / Save Text."
    )
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("json",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"filename_prefix": ("STRING", {"default": "promptgen/settings"})},
            "optional": {
                "image": ("IMAGE",),
                "filename": ("STRING", {"forceInput": True}),
                "positive_prompt": ("STRING", {"forceInput": True}),
                "negative_prompt": ("STRING", {"forceInput": True}),
            },
            "hidden": {"prompt": "PROMPT"},
        }

    def run(self, filename_prefix, image=None, filename=None, positive_prompt=None, negative_prompt=None,
            prompt=None):
        settings = collect_settings(
            prompt, tuple(image.shape) if image is not None else None, positive_prompt, negative_prompt
        )
        text = settings_json(settings)
        saved = save_and_describe(text, filename_prefix, filename, "settings", ext=".json")
        return {"ui": {"text": [text], "saved_file": [saved]}, "result": (text,)}
