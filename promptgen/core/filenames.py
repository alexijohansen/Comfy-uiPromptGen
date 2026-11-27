"""Building safe file names (.txt by default) inside ComfyUI's output folder and writing the files.

Rules:
- repeated separators ('__', '--', '_-') become one, and are trimmed from both ends of each part;
- paths may never leave the output folder;
- existing files are never overwritten.
"""

from __future__ import annotations

import os
import re

SEPARATOR_RUN_RE = re.compile(r"[_-]{2,}")


def clean_name(name: str) -> str:
    """Normalise a relative name: '/' separators, no doubled or trailing '_'/'-'."""
    cleaned = []
    for part in re.split(r"[\\/]+", str(name).strip()):
        part = SEPARATOR_RUN_RE.sub(lambda m: m.group(0)[0], part).strip("_- ")
        if part:
            cleaned.append(part)
    return "/".join(cleaned)


def combine_name(prefix: str, name: str) -> str:
    """Combine a save node's prefix with an incoming file name.

    The folder of the incoming name comes first (outermost), then the prefix's folder,
    then '<prefix name>_<file name>':

    'before/'          + 'ArtemyFantasy/prompt_0001' -> 'ArtemyFantasy/before/prompt_0001'
    'promptgen/before' + 'prompt_0001'               -> 'promptgen/before_prompt_0001'
    'promptgen/'       + 'prompt_0001'               -> 'promptgen/prompt_0001'   (trailing '/': folder only)

    A folder that appears at the end of the name's folder and at the start of the prefix's
    folder is not doubled ('a/' + 'a/x' -> 'a/x').
    """
    is_folder = str(prefix).strip().endswith(("/", "\\"))
    prefix, name = clean_name(prefix), clean_name(name)
    if not prefix:
        return name
    p_dir, p_base = (prefix, "") if is_folder else os.path.split(prefix)
    n_dir, n_base = os.path.split(name)
    n_parts, p_parts = [x for x in n_dir.split("/") if x], [x for x in p_dir.split("/") if x]
    if n_parts and p_parts and n_parts[-1] == p_parts[0]:
        p_parts = p_parts[1:]
    folder = "/".join(n_parts + p_parts)
    base = f"{p_base}_{n_base}" if p_base else n_base
    return clean_name(f"{folder}/{base}" if folder else base)


def resolve_in_output(relative: str, output_dir: str) -> str:
    """Absolute path of relative inside output_dir. Raises ValueError if it would leave it."""
    out = os.path.abspath(output_dir)
    path = os.path.abspath(os.path.join(out, relative))
    if os.path.commonpath([out, path]) != out:
        raise ValueError(f"'{relative}' points outside the output folder.")
    return path


def _write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def save_numbered(text: str, filename_prefix: str, output_dir: str, ext: str = ".txt") -> str:
    """Save as <output>/<prefix>_00001<ext> using the next free number. Returns the path."""
    prefix = clean_name(filename_prefix) or "promptgen/text"
    n = 1
    while True:
        path = resolve_in_output(f"{prefix}_{n:05}{ext}", output_dir)
        if not os.path.exists(path):
            return _write(path, text)
        n += 1


def save_named(text: str, filename: str, output_dir: str, ext: str = ".txt") -> str:
    """Save as <output>/<filename><ext>. If it exists, add _2, _3, ... Returns the path."""
    name = str(filename).strip()
    if name.lower().endswith(ext.lower()):
        name = name[: -len(ext)]
    name = clean_name(name)
    if not name:
        raise ValueError(f"Filename '{filename}' is empty after cleaning.")
    path = resolve_in_output(name + ext, output_dir)
    n = 2
    while os.path.exists(path):
        path = resolve_in_output(f"{name}_{n}{ext}", output_dir)
        n += 1
    return _write(path, text)


def save_text(text: str, filename_prefix: str, filename: str | None, output_dir: str, ext: str = ".txt") -> str:
    """Save text the way the save nodes do: prefix + filename if a filename is given, else numbered."""
    if filename:
        return save_named(text, combine_name(filename_prefix, filename), output_dir, ext)
    return save_numbered(text, filename_prefix, output_dir, ext)


def display_path(path: str, output_dir: str) -> str:
    """Path shown on the node: relative to the output folder when possible."""
    try:
        return os.path.relpath(path, output_dir)
    except ValueError:  # e.g. different drive on Windows
        return path


def unique_file_path(filename_prefix: str, name: str | None, output_dir: str, ext: str, suffix: str = "",
                     default_prefix: str = "promptgen/video") -> str:
    """Path for a new (not yet written) file, built like the text save nodes do.

    With a name: <prefix + name><suffix><ext>, adding _2, _3, ... before the suffix if it exists.
    Without: <prefix>_00001<suffix><ext> with the next free number. Never overwrites.
    """
    if name:
        base = combine_name(filename_prefix, name)
        if not base:
            raise ValueError(f"File name '{name}' is empty after cleaning.")
        path, n = resolve_in_output(f"{base}{suffix}{ext}", output_dir), 2
        while os.path.exists(path):
            path, n = resolve_in_output(f"{base}_{n}{suffix}{ext}", output_dir), n + 1
    else:
        prefix = clean_name(filename_prefix) or default_prefix
        if str(filename_prefix).strip().endswith(("/", "\\")):
            prefix = f"{prefix}/{os.path.basename(default_prefix)}"
        n = 1
        while os.path.exists(path := resolve_in_output(f"{prefix}_{n:05}{suffix}{ext}", output_dir)):
            n += 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path
