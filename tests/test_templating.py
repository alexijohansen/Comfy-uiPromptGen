from promptgen.core.templating import fill_template, split_lines, unfilled_tags


def test_split_lines_skips_empty_and_comments():
    assert split_lines("cat\n\n# note\n  dog  \ncow") == ["cat", "dog", "cow"]
    assert split_lines(None) == []


def test_fill_template_uses_lists_and_is_repeatable():
    lists = {"1": "cat\ndog\ncow", "2": "chair\ncouch"}
    a = fill_template("The {1} sat on the {2}", lists, seed=7)
    assert a == fill_template("The {1} sat on the {2}", lists, seed=7)
    animal, rest = a[len("The "):].split(" sat on the ")
    assert animal in {"cat", "dog", "cow"} and rest in {"chair", "couch"}


def test_same_tag_gets_same_pick_and_missing_tags_stay():
    out = fill_template("{1} and {1} and {3}", {"1": "a\nb\nc"}, seed=1)
    first, second, third = out.split(" and ")
    assert first == second
    assert third == "{3}"
    assert unfilled_tags(out) == ["3"]
