"""Batch Text Loader and Batch Image Loader: load the next file from a folder on every run."""

from __future__ import annotations

import os

from ..comfy import CATEGORY, output_dir
from ..core.counting import batch_position, take_number
from ..core.textfiles import (IMAGE_EXTENSIONS, TEXT_EXTENSIONS, folder_fingerprint, list_files,
                              read_text_file, resolve_folder)
from .common import AutoIncrementNode, auto_increment_input

WHEN_DONE = ["stop", "start over"]


class BatchFolderNode(AutoIncrementNode):
    """Shared inputs and stepping logic. Subclasses set EXTENSIONS, KIND and implement load()."""

    EXTENSIONS: tuple[str, ...] = ()
    KIND = ""            # "text" or "images": also used by the "Queue all" button
    DEFAULT_FOLDER = ""
    CATEGORY = CATEGORY
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"default": cls.DEFAULT_FOLDER,
                                      "tooltip": "A full path like D:\\videos, or a folder inside ComfyUI's output "
                                                 "folder. Empty = the output folder itself."}),
                "index": ("INT", {"default": 0, "min": 0, "max": 0x7FFFFFFF,
                                  "tooltip": "Which file to load: 0 is the first (sorted by name)."}),
                "auto_increment": (auto_increment_input()[0],
                                   {**auto_increment_input()[1],
                                    "tooltip": "On: every run loads the next file. Off: the same file every run."}),
                "when_done": (WHEN_DONE, {"default": "stop",
                                          "tooltip": "After the last file: stop with a message, or start over at "
                                                     "the first file."}),
            },
            "hidden": cls.HIDDEN,
        }

    @classmethod
    def fixed_fingerprint(cls, folder="", index=0, **kwargs):
        # Same index, but the folder's files may have changed.
        return f"{index}|{folder_fingerprint(resolve_folder(folder, output_dir()), cls.EXTENSIONS)}"

    def load(self, path: str, **options) -> tuple:
        """Outputs for one file (before name, index and total). options: a subclass's extra inputs."""
        raise NotImplementedError

    def run(self, folder, index, auto_increment, when_done, unique_id=None, **options):
        path = resolve_folder(folder, output_dir())
        files = list_files(path, self.EXTENSIONS)
        total = len(files)
        if total == 0:
            raise FileNotFoundError(f"No {'/'.join(self.EXTENSIONS)} files in {path}")

        index = take_number((self.KIND, unique_id), index, auto_increment)
        try:
            position, next_index = batch_position(index, total, when_done)
        except RuntimeError as e:
            raise RuntimeError(f"{e} Folder: {path}") from e

        fname = files[position]
        outputs = self.load(os.path.join(path, fname), **options)
        return {
            "ui": {"next_number": [next_index if auto_increment else index],
                   "loaded": [f"{position + 1}/{total}: {fname}"]},
            "result": (*outputs, os.path.splitext(fname)[0], position, total),
        }


class PromptGenBatchText(BatchFolderNode):
    DESCRIPTION = (
        "Loads one .txt file from a folder (sorted by name, index 0 is the first). With auto_increment on, "
        "each run loads the next file. 'folder' is a full path or a folder inside ComfyUI's output folder. "
        "Outputs the text and the file name without .txt."
    )
    EXTENSIONS = TEXT_EXTENSIONS
    KIND = "text"
    DEFAULT_FOLDER = "promptgen"
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("text", "name", "index", "total")

    def load(self, path):
        return (read_text_file(path),)


class PromptGenBatchImage(BatchFolderNode):
    DESCRIPTION = (
        "Loads one image (png, jpg, webp, ...) from a folder (sorted by name, index 0 is the first). With "
        "auto_increment on, each run loads the next image. 'folder' is a full path or a folder inside ComfyUI's "
        "output folder. Outputs the image, its mask (from transparency) and the file name without extension."
    )
    EXTENSIONS = IMAGE_EXTENSIONS
    KIND = "images"
    DEFAULT_FOLDER = ""
    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "INT", "INT")
    RETURN_NAMES = ("image", "mask", "name", "index", "total")

    def load(self, path):
        import torch  # ComfyUI always has torch; imported here so the rest can be tested without it

        from ..core.images import load_image_arrays

        rgb, mask = load_image_arrays(path)
        return torch.from_numpy(rgb)[None, ...], torch.from_numpy(mask)[None, ...]
