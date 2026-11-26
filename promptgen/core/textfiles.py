"""Finding and reading the .txt files used by the Batch Text Loader."""

from __future__ import annotations

import os


def resolve_folder(folder: str, output_dir: str | None) -> str:
    """Absolute path of folder. A relative folder is taken inside output_dir."""
    folder = os.path.expanduser(str(folder).strip().strip('"'))
    if not os.path.isabs(folder) and output_dir is not None:
        folder = os.path.join(output_dir, folder)
    return os.path.abspath(folder)


def list_text_files(folder: str) -> list[str]:
    """Names of the .txt files directly in folder, sorted by name (case-insensitive)."""
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"Folder not found: {folder}")
    names = [f for f in os.listdir(folder) if f.lower().endswith(".txt") and os.path.isfile(os.path.join(folder, f))]
    return sorted(names, key=str.lower)


def folder_fingerprint(folder: str) -> str:
    """Changes whenever a .txt file in folder is added, removed or edited."""
    try:
        files = list_text_files(folder)
        return str([(f, os.path.getmtime(os.path.join(folder, f))) for f in files])
    except OSError as e:
        return str(e)


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read().strip()
