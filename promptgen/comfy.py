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
