"""Filling {1}, {2}, ... tags in a template with random lines from lists."""

from __future__ import annotations

import random
import re
from collections.abc import Mapping

TAG_RE = re.compile(r"\{(\d+)\}")


def split_lines(text: str | None) -> list[str]:
    """Return the entries of a multiline list: one per line, skipping empty lines and '#' comments."""
    if not text:
        return []
    entries = []
    for line in str(text).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            entries.append(line)
    return entries


def fill_template(template: str, lists: Mapping[str, str], seed: int) -> str:
    """Replace each {N} with a random entry from lists["N"].

    The same tag used twice gets the same pick. Tags without a (non-empty) list are left unchanged.
    """
    rng = random.Random(seed)
    picks = {}
    for num in sorted({int(n) for n in TAG_RE.findall(template)}):
        entries = split_lines(lists.get(str(num)))
        if entries:
            picks[str(num)] = rng.choice(entries)
    return TAG_RE.sub(lambda m: picks.get(m.group(1), m.group(0)), template)


def unfilled_tags(text: str) -> list[str]:
    """Tag numbers still present in text, e.g. ['3'] for 'a {3}'."""
    return sorted(set(TAG_RE.findall(text)), key=int)
