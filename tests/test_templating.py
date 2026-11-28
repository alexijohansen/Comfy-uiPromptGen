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


def test_no_repeats_uses_every_line_once_per_round():
    from collections import Counter

    from promptgen.nodes.text import PromptGenTemplate

    assert "pick_mode" in PromptGenTemplate.INPUT_TYPES()["required"]
    node = PromptGenTemplate()
    lines = "a\nb\nc\nd"
    picks = [node.run("{1}", seed, "no repeats", unique_id="7", **{"1": lines})[0] for seed in range(12)]
    for start in (0, 4, 8):                      # each round of 4 uses every line exactly once
        assert sorted(picks[start:start + 4]) == ["a", "b", "c", "d"]
    assert Counter(picks) == {"a": 3, "b": 3, "c": 3, "d": 3}


def test_no_repeats_bags_are_per_tag_and_reset_when_list_changes():
    from promptgen.nodes.text import PromptGenTemplate

    node = PromptGenTemplate()
    run = lambda lists, seed: node.run("{1}|{2}", seed, "no repeats", unique_id="8", **lists)[0].split("|")
    first = [run({"1": "x\ny", "2": "p\nq\nr"}, s) for s in range(6)]
    assert sorted(f[0] for f in first[:2]) == ["x", "y"]
    assert sorted(f[1] for f in first[:3]) == ["p", "q", "r"]
    changed = [run({"1": "x\ny\nz", "2": "p\nq\nr"}, s)[0] for s in range(3)]
    assert sorted(changed) == ["x", "y", "z"]    # edited list: fresh bag with the new line


def test_no_repeats_is_never_cached_but_random_is():
    from promptgen.nodes.text import PromptGenTemplate

    nan = PromptGenTemplate.IS_CHANGED(pick_mode="no repeats")
    assert nan != nan
    assert PromptGenTemplate.IS_CHANGED(pick_mode="random") == ""


def test_no_repeats_never_repeats_across_a_refill():
    import random

    from promptgen.core import templating

    for seed in range(200):
        templating.reset_bags()
        pick = templating.bag_picker("n")
        picks = [pick("1", ["a", "b", "c"], random.Random(seed * 100 + s)) for s in range(30)]
        assert all(x != y for x, y in zip(picks, picks[1:]))
        assert all(sorted(picks[i:i + 3]) == ["a", "b", "c"] for i in range(0, 30, 3))


def test_no_repeats_edge_cases():
    import random

    from promptgen.core import templating

    pick = templating.bag_picker("e")
    rng = random.Random(0)
    assert [pick("1", ["only"], rng) for _ in range(3)] == ["only"] * 3       # single line
    assert {pick("2", ["a", "a", "b"], rng) for _ in range(6)} == {"a", "b"}  # duplicate lines are fine
    for i in range(50):                                                       # editing the list ...
        pick("3", [str(i), "x"], rng)
    assert len(templating._bags) == 3                                         # ... keeps one bag per input
    assert templating.fill_template("{1} {2}", {"1": "", "2": "\n# only a comment\n"}, 0,
                                    templating.bag_picker("z")) == "{1} {2}"  # empty lists: no pick, no error
