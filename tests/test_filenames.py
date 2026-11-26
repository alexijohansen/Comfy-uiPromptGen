import os

import pytest

from promptgen.core.filenames import clean_name, combine_name, display_path, save_text


@pytest.mark.parametrize("raw, expected", [
    ("promptgen/prompt__0001", "promptgen/prompt_0001"),
    ("a--b__c_-d", "a-b_c_d"),
    ("__x__/y--", "x/y"),
    ("promptgen\\p_0001.txt", "promptgen/p_0001.txt"),
    ("ok_name-1", "ok_name-1"),
])
def test_clean_name(raw, expected):
    assert clean_name(raw) == expected


@pytest.mark.parametrize("prefix, name, expected", [
    ("promptgen/before", "prompt_0001", "promptgen/before_prompt_0001"),
    ("promptgen/before", "promptgen/prompt_0001", "promptgen/before_prompt_0001"),
    ("promptgen/", "prompt_0002", "promptgen/prompt_0002"),
    ("", "prompt_0001", "prompt_0001"),
    ("before_", "_prompt__0003", "before_prompt_0003"),
    ("before/", "ArtemyFantasy/prompt_0001", "ArtemyFantasy/before/prompt_0001"),
    ("promptgen/before/", "ArtemyFantasy/0001", "ArtemyFantasy/promptgen/before/0001"),
    ("before/rewrite", "ArtemyFantasy/prompt_0001", "ArtemyFantasy/before/rewrite_prompt_0001"),
    ("ArtemyFantasy/", "ArtemyFantasy/prompt_0001", "ArtemyFantasy/prompt_0001"),
])
def test_combine_name(prefix, name, expected):
    assert combine_name(prefix, name) == expected


def test_numbered_names_count_up(tmp_path):
    first = save_text("a", "promptgen/text", None, str(tmp_path))
    second = save_text("b", "promptgen/text", None, str(tmp_path))
    assert first.endswith(os.path.join("promptgen", "text_00001.txt"))
    assert second.endswith(os.path.join("promptgen", "text_00002.txt"))


def test_named_never_overwrites(tmp_path):
    paths = [save_text(str(i), "promptgen/before", "prompt_0001", str(tmp_path)) for i in range(3)]
    names = [display_path(p, str(tmp_path)).replace("\\", "/") for p in paths]
    assert names == ["promptgen/before_prompt_0001.txt", "promptgen/before_prompt_0001_2.txt",
                     "promptgen/before_prompt_0001_3.txt"]
    assert open(paths[0], encoding="utf-8").read() == "0"


def test_txt_extension_not_doubled(tmp_path):
    path = save_text("x", "", "notes.txt", str(tmp_path))
    assert os.path.basename(path) == "notes.txt"


def test_paths_cannot_leave_output_folder(tmp_path):
    with pytest.raises(ValueError):
        save_text("x", "", "../evil", str(tmp_path / "out"))
