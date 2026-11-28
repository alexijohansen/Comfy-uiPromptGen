"""Filling {1}, {2}, ... tags in a template with random lines from lists."""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Hashable, Mapping

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


Picker = Callable[[str, list[str], random.Random], str]


def random_pick(tag: str, entries: list[str], rng: random.Random) -> str:
    return rng.choice(entries)


# Shuffle bags: per (node, tag, list contents) the lines not used yet. In memory only.
_bags: dict[Hashable, list[str]] = {}


def bag_picker(node_key: Hashable) -> Picker:
    """Picker that uses every line once, in random order, before any line repeats.

    When all lines of a list have been used, the bag refills by itself. Changing the list
    (adding, removing or editing a line) starts a fresh bag.
    """
    def pick(tag: str, entries: list[str], rng: random.Random) -> str:
        key = (node_key, tag, tuple(entries))
        bag = _bags.get(key)
        if not bag:
            bag = entries[:]
            rng.shuffle(bag)
            _bags[key] = bag
        return bag.pop()
    return pick


def reset_bags() -> None:
    """Forget all shuffle bags (used by tests)."""
    _bags.clear()


def fill_template(template: str, lists: Mapping[str, str], seed: int, pick: Picker = random_pick) -> str:
    """Replace each {N} with an entry from lists["N"], chosen by pick (random by default).

    The same tag used twice gets the same pick. Tags without a (non-empty) list are left unchanged.
    """
    rng = random.Random(seed)
    picks = {}
    for num in sorted({int(n) for n in TAG_RE.findall(template)}):
        entries = split_lines(lists.get(str(num)))
        if entries:
            picks[str(num)] = pick(str(num), entries, rng)
    return TAG_RE.sub(lambda m: picks.get(m.group(1), m.group(0)), template)


def unfilled_tags(text: str) -> list[str]:
    """Tag numbers still present in text, e.g. ['3'] for 'a {3}'."""
    return sorted(set(TAG_RE.findall(text)), key=int)
