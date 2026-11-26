"""Finding and reading the files used by the batch loaders (text and images)."""

from __future__ import annotations

import os

TEXT_EXTENSIONS = (".txt",)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff")


def resolve_folder(folder: str, output_dir: str | None) -> str:
    """Absolute path of folder. A relative folder is taken inside output_dir."""
    folder = os.path.expanduser(str(folder).strip().strip('"'))
    if not os.path.isabs(folder) and output_dir is not None:
        folder = os.path.join(output_dir, folder)
    return os.path.abspath(folder)


def list_files(folder: str, extensions: tuple[str, ...]) -> list[str]:
    """Names of the files directly in folder with one of the extensions, sorted by name (case-insensitive)."""
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"Folder not found: {folder}")
    names = [f for f in os.listdir(folder)
             if f.lower().endswith(extensions) and os.path.isfile(os.path.join(folder, f))]
    return sorted(names, key=str.lower)


def list_text_files(folder: str) -> list[str]:
    return list_files(folder, TEXT_EXTENSIONS)


def list_image_files(folder: str) -> list[str]:
    return list_files(folder, IMAGE_EXTENSIONS)


def folder_fingerprint(folder: str, extensions: tuple[str, ...] = TEXT_EXTENSIONS) -> str:
    """Changes whenever a matching file in folder is added, removed or edited."""
    try:
        files = list_files(folder, extensions)
        return str([(f, os.path.getmtime(os.path.join(folder, f))) for f in files])
    except OSError as e:
        return str(e)


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read().strip()
