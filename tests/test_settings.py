from promptgen.core.settings import describe_settings

PROMPT = {
    "3": {"class_type": "KSampler", "inputs": {"seed": 123456, "steps": 30, "cfg": 6.5, "sampler_name": "euler",
                                               "scheduler": "normal", "denoise": 1.0, "model": ["4", 0]}},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 832, "height": ["12", 0], "batch_size": 1}},
    "12": {"class_type": "PrimitiveInt", "inputs": {"value": 1216}},
}


def test_describe_settings_follows_links():
    text = describe_settings(PROMPT)
    assert "KSampler (node 3)" in text
    assert "  seed: 123456" in text and "  sampler_name: euler" in text
    assert "Model: sdxl.safetensors" in text
    assert "Resolution: 832 x 1216 (batch 1, from EmptyLatentImage node 5)" in text


def test_image_shape_wins_over_latent():
    assert "Resolution: 512 x 768 (batch 2)" in describe_settings(PROMPT, (2, 768, 512, 3))


def test_no_sampler():
    assert describe_settings({}) == "(no KSampler found in this workflow)"
