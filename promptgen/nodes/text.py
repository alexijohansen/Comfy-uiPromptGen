"""Line List, Template and Show / Save Text."""

from __future__ import annotations

from ..comfy import CATEGORY, log
from ..core.templating import fill_template, unfilled_tags
from .common import NOT_SAVED, save_and_describe


class AnyNumberedInputs(dict):
    """Optional-inputs dict that accepts any input name.

    The Template node's inputs "1", "2", ... are added by the frontend (js/promptgen.js),
    so they can't be declared in advance. ComfyUI only asks 'is this input known?' and
    'what type is it?', and the answer is always: yes, a STRING.
    """

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        return ("STRING", {"forceInput": True})

    def get(self, key, default=None):
        return self[key]


class PromptGenLineList:
    DESCRIPTION = "A list of entries, one per line. Connect to a numbered input on PromptGen Template."
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("list",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": ("STRING", {"multiline": True, "default": "cat\ndog\ncow"})}}

    def run(self, text):
        return (text,)


class PromptGenTemplate:
    DESCRIPTION = (
        "Replaces {1}, {2}, ... with a random line from the list plugged into input 1, 2, ... "
        "A new input slot appears each time you connect one."
    )
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {"multiline": True, "default": "The {1} sat on the {2}"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "control_after_generate": True}),
            },
            "optional": AnyNumberedInputs(),
        }

    def run(self, template, seed, **lists):
        result = fill_template(template, {k: v for k, v in lists.items() if k.isdigit()}, seed)
        missing = unfilled_tags(result)
        if missing:
            log.warning("No list (or an empty list) for tag(s): %s", ", ".join("{" + m + "}" for m in missing))
        return (result,)


class PromptGenShowText:
    DESCRIPTION = (
        "Shows the text on the node and passes it through. Optionally saves it as a .txt file in "
        "ComfyUI's output folder. With 'filename' connected (e.g. from PromptGen Counter) the file is "
        "<filename_prefix>_<filename>.txt; otherwise <filename_prefix>_00001.txt. Never overwrites."
    )
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
                "save_to_file": ("BOOLEAN", {"default": False}),
                "filename_prefix": ("STRING", {"default": "promptgen/text"}),
            },
            "optional": {"filename": ("STRING", {"forceInput": True})},
        }

    def run(self, text, save_to_file, filename_prefix, filename=None):
        saved = save_and_describe(text, filename_prefix, filename, "text") if save_to_file else NOT_SAVED
        return {"ui": {"text": [text], "saved_file": [saved]}, "result": (text,)}
