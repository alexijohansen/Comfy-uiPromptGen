"""Counter and Batch Text Loader: nodes that move on by one every run."""

from __future__ import annotations

import os

from ..comfy import CATEGORY, output_dir
from ..core.counting import take_number
from ..core.filenames import clean_name
from ..core.textfiles import folder_fingerprint, list_text_files, read_text_file, resolve_folder
from .common import AutoIncrementNode, auto_increment_input

WHEN_DONE = ["stop", "start over"]


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


class PromptGenBatchText(AutoIncrementNode):
    DESCRIPTION = (
        "Loads one .txt file from a folder (sorted by name, index 0 is the first). With auto_increment on, "
        "each run loads the next file. 'folder' is a full path or a folder inside ComfyUI's output folder. "
        "Outputs the text and the file name without .txt."
    )
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("text", "name", "index", "total")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"default": "promptgen"}),
                "index": ("INT", {"default": 0, "min": 0, "max": 0x7FFFFFFF}),
                "auto_increment": auto_increment_input(),
                "when_done": (WHEN_DONE, {"default": "stop"}),
            },
            "hidden": cls.HIDDEN,
        }

    @classmethod
    def fixed_fingerprint(cls, folder="", index=0, **kwargs):
        # Same index, but the folder's files may have changed.
        return f"{index}|{folder_fingerprint(resolve_folder(folder, output_dir()))}"

    def run(self, folder, index, auto_increment, when_done, unique_id=None):
        path = resolve_folder(folder, output_dir())
        files = list_text_files(path)
        total = len(files)
        if total == 0:
            raise FileNotFoundError(f"No .txt files in {path}")

        index = take_number(("batch", unique_id), index, auto_increment)
        if index >= total and when_done == "stop":
            raise RuntimeError(f"All {total} files in {path} are done (index {index}). Set index back to 0 to start again.")
        i = index % total

        fname = files[i]
        text = read_text_file(os.path.join(path, fname))
        next_index = (i + 1) % total if when_done == "start over" else i + 1
        return {
            "ui": {"next_number": [next_index if auto_increment else index], "loaded": [f"{i + 1}/{total}: {fname}"]},
            "result": (text, os.path.splitext(fname)[0], i, total),
        }
