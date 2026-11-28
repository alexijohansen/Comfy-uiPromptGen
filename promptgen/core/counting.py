"""Shared auto-increment logic for the Counter and the Batch Text Loader. In memory only."""

from __future__ import annotations

import random
from collections.abc import Hashable

_state: dict[Hashable, dict[str, int]] = {}


def take_number(key: Hashable, widget_value: int, auto_increment: bool) -> int:
    """Number to use for this run of the node identified by key.

    With auto_increment, every run moves on by one, even when a batch was queued with the same
    widget value. When the widget shows a different value than last time (typed by you, or moved
    on by the UI), counting continues from that value.
    """
    if not auto_increment:
        _state.pop(key, None)
        return widget_value
    last = _state.get(key)
    n = widget_value if last is None or last["widget"] != widget_value else last["next"]
    _state[key] = {"widget": widget_value, "next": n + 1}
    return n


def reset_all() -> None:
    """Forget all counters (used by tests)."""
    _state.clear()


def batch_position(index: int, total: int, when_done: str) -> tuple[int, int]:
    """For a batch loader: (position of the file to load, index to show next).

    when_done 'stop' raises once index passes the last file; 'start over' wraps around.
    """
    if total <= 0:
        raise ValueError("No files to load.")
    if index >= total and when_done != "start over":
        raise RuntimeError(f"All {total} files are done (index {index}). Set index back to 0 to start again.")
    position = index % total
    next_index = (position + 1) % total if when_done == "start over" else position + 1
    return position, next_index


def shuffled_order(total: int, seed: int, cycle: int = 0) -> list[int]:
    """A random but repeatable order of 0..total-1 for the given seed.

    Every position appears exactly once, so a full pass visits each file once. Each cycle
    (pass through the folder with 'start over') gets its own order.
    """
    order = list(range(total))
    random.Random(f"{seed}:{cycle}").shuffle(order)
    return order
