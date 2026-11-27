"""The only place that touches ComfyUI internals (folder_paths). Everything else gets values passed in."""

from __future__ import annotations

import logging

try:
    import folder_paths
except ImportError:  # running outside ComfyUI, e.g. in tests
    folder_paths = None

log = logging.getLogger("promptgen")

CATEGORY = "PromptGen"


def output_dir() -> str | None:
    """ComfyUI's output folder, or None outside ComfyUI."""
    return folder_paths.get_output_directory() if folder_paths is not None else None


def torch_device():
    """The GPU ComfyUI uses (or the CPU outside ComfyUI / without a GPU)."""
    import torch

    try:
        import comfy.model_management as mm
        return mm.get_torch_device()
    except ImportError:
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def check_interrupted() -> None:
    """Raise if the user pressed Cancel in ComfyUI (no-op outside ComfyUI)."""
    try:
        import comfy.model_management as mm
    except ImportError:
        return
    mm.throw_exception_if_processing_interrupted()


class Progress:
    """ComfyUI's progress bar on the node (silent outside ComfyUI)."""

    def __init__(self, total: int):
        try:
            import comfy.utils
            self._bar = comfy.utils.ProgressBar(total)
        except ImportError:
            self._bar = None

    def update(self, n: int = 1) -> None:
        if self._bar is not None:
            self._bar.update(n)
