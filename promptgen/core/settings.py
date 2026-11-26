"""Collecting the generation settings of a ComfyUI API prompt (samplers, model, resolution)."""

from __future__ import annotations

import json
from typing import Any

SAMPLER_KEYS = ["seed", "noise_seed", "steps", "cfg", "sampler_name", "scheduler", "denoise",
                "add_noise", "start_at_step", "end_at_step", "return_with_leftover_noise"]
MODEL_LOADERS = {"CheckpointLoaderSimple": "ckpt_name", "CheckpointLoader": "ckpt_name", "UNETLoader": "unet_name"}
VALUE_INPUTS = ("value", "seed", "noise_seed", "int", "float", "number")
MAX_LINK_DEPTH = 5


def _is_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)


def resolve_value(prompt: dict, value: Any, depth: int = 0) -> Any:
    """Follow a link [node_id, slot] back to a plain value. Best effort.

    Works for primitive/seed-style nodes (an input named value, seed, int, ... or a single input).
    Anything else is shown as '(from <type> node <id>)'.
    """
    if not _is_link(value):
        return value
    node = prompt.get(value[0], {})
    inputs = node.get("inputs", {})
    label = f"(from {node.get('class_type', '?')} node {value[0]})"
    if depth >= MAX_LINK_DEPTH:
        return label
    for key in VALUE_INPUTS:
        if key in inputs:
            return resolve_value(prompt, inputs[key], depth + 1)
    if len(inputs) == 1:
        return resolve_value(prompt, next(iter(inputs.values())), depth + 1)
    return label


def _is_sampler(class_type: str, inputs: dict) -> bool:
    return class_type.startswith("KSampler") or ("sampler_name" in inputs and "steps" in inputs)


def _sorted_nodes(prompt: dict):
    return sorted(prompt.items(), key=lambda kv: (len(kv[0]), kv[0]))


def collect_settings(prompt: dict | None, image_shape: tuple | None = None,
                     positive: str | None = None, negative: str | None = None) -> dict:
    """Settings of a run as a dict, ready to be written as JSON.

    image_shape is (batch, height, width, channels) of the decoded image, if available;
    otherwise the size is taken from the Empty Latent Image node.
    """
    prompt = prompt or {}
    samplers, models = [], []
    for nid, node in _sorted_nodes(prompt):
        ctype, inputs = node.get("class_type", ""), node.get("inputs", {})
        if _is_sampler(ctype, inputs):
            entry = {"node": nid, "type": ctype}
            entry.update({k: resolve_value(prompt, inputs[k]) for k in SAMPLER_KEYS if k in inputs})
            samplers.append(entry)
        elif ctype in MODEL_LOADERS and MODEL_LOADERS[ctype] in inputs:
            models.append(resolve_value(prompt, inputs[MODEL_LOADERS[ctype]]))

    resolution = None
    if image_shape is not None:
        resolution = {"width": image_shape[2], "height": image_shape[1], "batch_size": image_shape[0],
                      "source": "image"}
    else:
        for nid, node in _sorted_nodes(prompt):
            inputs = node.get("inputs", {})
            if "width" in inputs and "height" in inputs and "Latent" in node.get("class_type", ""):
                resolution = {
                    "width": resolve_value(prompt, inputs["width"]),
                    "height": resolve_value(prompt, inputs["height"]),
                    "batch_size": resolve_value(prompt, inputs.get("batch_size", 1)),
                    "source": f"{node['class_type']} node {nid}",
                }
                break

    return {
        "positive_prompt": positive,
        "negative_prompt": negative,
        "model": models[0] if len(models) == 1 else (models or None),
        "resolution": resolution,
        "samplers": samplers,
    }


def settings_json(settings: dict) -> str:
    return json.dumps(settings, indent=2, ensure_ascii=False)
