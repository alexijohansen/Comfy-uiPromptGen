from promptgen.core.counting import take_number


def test_batch_with_unchanged_widget_counts_up():
    assert [take_number("n", 1, True) for _ in range(5)] == [1, 2, 3, 4, 5]


def test_widget_change_restarts_from_widget_value():
    take_number("n", 1, True)
    assert take_number("n", 6, True) == 6   # UI moved the field on
    assert take_number("n", 1, True) == 1   # user typed 1 again


def test_ui_moving_each_queue_gives_same_numbers():
    assert [take_number("n", w, True) for w in (1, 2, 3)] == [1, 2, 3]


def test_fixed_and_separate_nodes():
    assert [take_number("a", 3, False) for _ in range(2)] == [3, 3]
    take_number("b", 1, True)
    assert take_number("c", 1, True) == 1
