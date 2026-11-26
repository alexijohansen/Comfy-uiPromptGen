import json

from promptgen.core.settings import collect_settings, settings_json

PROMPT = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 123456, "steps": 30, "cfg": 6.5, "sampler_name": "euler",
                                               "scheduler": "normal", "denoise": 1.0, "model": ["4", 0]}},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 832, "height": ["12", 0], "batch_size": 1}},
    "12": {"class_type": "PrimitiveInt", "inputs": {"value": 1216}},
}


def test_collect_settings_follows_links():
    s = collect_settings(PROMPT, positive="a cat", negative="blurry")
    assert s["positive_prompt"] == "a cat" and s["negative_prompt"] == "blurry"
    assert s["model"] == "sdxl.safetensors"
    assert s["samplers"] == [{"node": "3", "type": "KSampler", "seed": 123456, "steps": 30, "cfg": 6.5,
                              "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}]
    assert s["resolution"] == {"width": 832, "height": 1216, "batch_size": 1, "source": "EmptyLatentImage node 5"}


def test_image_shape_wins_over_latent():
    assert collect_settings(PROMPT, (2, 768, 512, 3))["resolution"] == {
        "width": 512, "height": 768, "batch_size": 2, "source": "image"}


def test_empty_prompt_and_json_round_trip():
    s = collect_settings({})
    assert s == {"positive_prompt": None, "negative_prompt": None, "model": None, "resolution": None, "samplers": []}
    assert json.loads(settings_json(collect_settings(PROMPT, positive="ü"))) ["positive_prompt"] == "ü"
