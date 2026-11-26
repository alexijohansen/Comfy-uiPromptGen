"""Pieces shared by several nodes."""

from __future__ import annotations

from ..core.filenames import display_path, save_text
from ..comfy import log, output_dir

NOT_SAVED = "(not saved)"


def auto_increment_input() -> tuple:
    return ("BOOLEAN", {"default": True, "label_on": "on", "label_off": "off"})


class AutoIncrementNode:
    """Base for nodes with an auto_increment switch (Counter, Batch Text Loader).

    With auto_increment on the node is never cached, so every queued run executes and can take
    the next number from promptgen.core.counting. The UI is sent 'next_number' to show it.
    """

    HIDDEN = {"unique_id": "UNIQUE_ID"}

    @classmethod
    def IS_CHANGED(cls, auto_increment=True, **kwargs):
        if auto_increment:
            return float("nan")  # NaN never equals itself, so ComfyUI always re-runs the node
        return cls.fixed_fingerprint(**kwargs)

    @classmethod
    def fixed_fingerprint(cls, **kwargs) -> str:
        """Cache key when auto_increment is off. Override if outside data can change."""
        return ""


def save_and_describe(text: str, filename_prefix: str, filename: str | None, what: str, ext: str = ".txt") -> str:
    """Save text like the save nodes do and return the path to show on the node."""
    out = output_dir()
    path = save_text(text, filename_prefix, filename, out, ext)
    log.info("Saved %s to %s", what, path)
    return display_path(path, out)
