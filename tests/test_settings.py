import json

from promptgen.core.settings import collect_settings, settings_json

PROMPT = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 123456, "steps": 30, "cfg": 6.5, "sampler_name": "euler",
                                               "scheduler": "normal", "denoise": 1.0, "model": ["4", 0]}},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 832, "height": ["12", 0], "batch_size": 1}},
    "12": {"class_type": "PrimitiveInt", "inputs": {"value": 1216}},
    "20": {"class_type": "LoraLoader", "inputs": {"lora_name": "style.safetensors", "strength_model": 0.8,
                                                  "strength_clip": 0.6, "model": ["4", 0], "clip": ["4", 1]}},
    "21": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "detail.safetensors", "strength_model": 1.0,
                                                           "model": ["20", 0]}},
    "22": {"class_type": "Power Lora Loader (rgthree)", "inputs": {
        "lora_1": {"on": True, "lora": "a.safetensors", "strength": 0.5},
        "lora_2": {"on": False, "lora": "off.safetensors", "strength": 1.0}}},
}


def test_collect_settings_follows_links():
    s = collect_settings(PROMPT, positive="a cat", negative="blurry")
    assert s["positive_prompt"] == "a cat" and s["negative_prompt"] == "blurry"
    assert s["model"] == "sdxl.safetensors"
    assert s["models"] == [{"node": "4", "type": "CheckpointLoaderSimple", "name": "sdxl.safetensors"}]
    assert s["loras"] == [
        {"node": "20", "type": "LoraLoader", "name": "style.safetensors", "strength_model": 0.8, "strength_clip": 0.6},
        {"node": "21", "type": "LoraLoaderModelOnly", "name": "detail.safetensors", "strength_model": 1.0},
        {"node": "22", "type": "Power Lora Loader (rgthree)", "name": "a.safetensors", "strength": 0.5},
    ]
    assert s["samplers"] == [{"node": "3", "type": "KSampler", "seed": 123456, "steps": 30, "cfg": 6.5,
                              "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}]
    assert s["resolution"] == {"width": 832, "height": 1216, "batch_size": 1, "source": "EmptyLatentImage node 5"}


def test_image_shape_wins_over_latent():
    assert collect_settings(PROMPT, (2, 768, 512, 3))["resolution"] == {
        "width": 512, "height": 768, "batch_size": 2, "source": "image"}


def test_empty_prompt_and_json_round_trip():
    s = collect_settings({})
    assert s == {"positive_prompt": None, "negative_prompt": None, "model": None, "models": [], "loras": [],
                 "resolution": None, "samplers": []}


def test_diffusion_model_loader():
    s = collect_settings({"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux.safetensors",
                                                                       "weight_dtype": "default"}}})
    assert s["model"] == "flux.safetensors" and s["models"][0]["type"] == "UNETLoader"
    assert json.loads(settings_json(collect_settings(PROMPT, positive="ü"))) ["positive_prompt"] == "ü"
