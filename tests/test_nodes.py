"""Node-level tests with ComfyUI's output folder pointed at a temp dir."""

import pytest

from promptgen import NODE_CLASS_MAPPINGS, comfy
from promptgen.nodes.batch import PromptGenBatchImage, PromptGenBatchText
from promptgen.nodes.counter import PromptGenCounter
from promptgen.nodes.text import PromptGenShowText, PromptGenTemplate


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(comfy, "output_dir", lambda: str(tmp_path))
    for module in ("promptgen.nodes.common", "promptgen.nodes.batch"):
        monkeypatch.setattr(f"{module}.output_dir", lambda: str(tmp_path))
    return tmp_path


def test_all_nodes_registered_with_stable_ids():
    assert set(NODE_CLASS_MAPPINGS) == {
        "PromptGenLineList", "PromptGenTemplate", "PromptGenOllamaRewrite", "PromptGenShowText",
        "PromptGenCounter", "PromptGenBatchText", "PromptGenBatchImage", "PromptGenSaveSettings",
        "PromptGenBatchVideo", "PromptGenVR180Stereo", "PromptGenVR180", "PromptGenVR180Settings", "PromptGenSaveVR180", "PromptGenSaveVideoHQ",
    }


def test_template_node_accepts_any_numbered_input():
    optional = PromptGenTemplate.INPUT_TYPES()["optional"]
    assert "7" in optional and optional["7"][0] == "STRING"
    (prompt,) = PromptGenTemplate().run("a {1}", 0, **{"1": "cat"})
    assert prompt == "a cat"


def test_counter_and_save_node_together(out):
    counter, save = PromptGenCounter(), PromptGenShowText()
    saved = []
    for _ in range(3):
        name = counter.run("prompt", 4, 1, True, unique_id="9")["result"][1]
        saved.append(save.run("x", True, "promptgen/after/", name)["ui"]["saved_file"][0].replace("\\", "/"))
    assert saved == ["promptgen/after/prompt_0001.txt", "promptgen/after/prompt_0002.txt",
                     "promptgen/after/prompt_0003.txt"]


def test_counter_cache_key():
    assert PromptGenCounter.IS_CHANGED(auto_increment=True) != PromptGenCounter.IS_CHANGED(auto_increment=True)
    assert PromptGenCounter.IS_CHANGED(auto_increment=False) == ""


def test_save_off_reports_not_saved(out):
    assert PromptGenShowText().run("x", False, "p")["ui"]["saved_file"] == ["(not saved)"]


def test_batch_loader_walks_folder(out):
    folder = out / "prompts"
    folder.mkdir()
    for name, text in [("b.txt", "second"), ("a.txt", "first"), ("skip.png", "")]:
        (folder / name).write_text(text, encoding="utf-8")
    node = PromptGenBatchText()
    runs = [node.run("prompts", 0, True, "start over", unique_id="3")["result"] for _ in range(3)]
    assert runs == [("first", "a", 0, 2), ("second", "b", 1, 2), ("first", "a", 0, 2)]

    node2 = PromptGenBatchText()
    node2.run("prompts", 0, True, "stop", unique_id="4")
    node2.run("prompts", 0, True, "stop", unique_id="4")
    with pytest.raises(RuntimeError, match="are done"):
        node2.run("prompts", 0, True, "stop", unique_id="4")


def test_save_settings_writes_json(out):
    import json

    from promptgen.nodes.settings import PromptGenSaveSettings

    ui = PromptGenSaveSettings().run("before/", None, "ArtemyFantasy/prompt_0001", "a cat", "blurry",
                                     prompt={})["ui"]
    assert ui["saved_file"][0].replace("\\", "/") == "ArtemyFantasy/before/prompt_0001.json"
    data = json.loads((out / "ArtemyFantasy" / "before" / "prompt_0001.json").read_text(encoding="utf-8"))
    assert data["positive_prompt"] == "a cat" and data["negative_prompt"] == "blurry"


def test_save_settings_prompts_are_text_boxes_and_empty_is_null(out):
    import json

    from promptgen.nodes.settings import PromptGenSaveSettings

    spec = PromptGenSaveSettings.INPUT_TYPES()["optional"]["negative_prompt"]
    assert spec[0] == "STRING" and spec[1].get("multiline") and not spec[1].get("forceInput")
    PromptGenSaveSettings().run("", None, "s", "a cat", "", prompt={})
    data = json.loads((out / "s.json").read_text(encoding="utf-8"))
    assert data["positive_prompt"] == "a cat" and data["negative_prompt"] is None


def test_batch_image_loader_walks_folder(out, monkeypatch):
    from PIL import Image

    folder = out / "imgs"
    folder.mkdir()
    Image.new("RGB", (4, 2), (255, 0, 0)).save(folder / "a.png")
    Image.new("RGBA", (3, 3), (0, 0, 0, 0)).save(folder / "b.png")
    (folder / "notes.txt").write_text("not an image", encoding="utf-8")
    # torch is not needed to test the stepping: return the numpy arrays instead
    from promptgen.core.images import load_image_arrays
    monkeypatch.setattr(PromptGenBatchImage, "load", lambda self, path: load_image_arrays(path))

    node = PromptGenBatchImage()
    first = node.run("imgs", 0, True, "stop", unique_id="5")
    second = node.run("imgs", 0, True, "stop", unique_id="5")
    (rgb, mask, name, index, total) = first["result"]
    assert (name, index, total, rgb.shape, mask.max()) == ("a", 0, 2, (2, 4, 3), 0.0)
    assert second["result"][2:] == ("b", 1, 2) and second["result"][1].min() == 1.0  # fully transparent
    assert second["ui"]["next_number"] == [2]
    with pytest.raises(RuntimeError, match="are done"):
        node.run("imgs", 0, True, "stop", unique_id="5")


def test_batch_image_random_order_visits_each_once(out, monkeypatch):
    folder = out / "rand"
    folder.mkdir()
    names = [f"img_{i:02}" for i in range(8)]
    for n in names:
        (folder / f"{n}.png").write_bytes(b"")
    monkeypatch.setattr(PromptGenBatchImage, "load", lambda self, path: (None, None))
    assert "random_order" in PromptGenBatchImage.INPUT_TYPES()["required"]
    assert "random_order" not in PromptGenBatchText.INPUT_TYPES()["required"]

    node = PromptGenBatchImage()
    runs = [node.run("rand", 0, True, "stop", unique_id="r", random_order=True, random_seed=42)["result"]
            for _ in range(8)]
    seen = [r[2] for r in runs]
    assert sorted(seen) == names and seen != names       # every image once, not in name order
    assert [r[3] for r in runs] == list(range(8))        # index still counts up
    again = PromptGenBatchImage()
    assert [again.run("rand", i, False, "stop", random_order=True, random_seed=42)["result"][2]
            for i in range(8)] == seen                   # same seed, same order
