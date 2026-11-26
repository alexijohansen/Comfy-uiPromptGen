"""Shared auto-increment logic for the Counter and the Batch Text Loader. In memory only."""

from __future__ import annotations

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
