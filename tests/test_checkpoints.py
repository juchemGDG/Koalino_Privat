"""Kontrollpunkte der Debugging-Landkarte (koalino.checkpoints)."""
from koalino import checkpoints as cp

MARK = cp.MARK


def test_is_checkpoint():
    assert cp.is_checkpoint(f'print("K1")  {MARK}')
    assert cp.is_checkpoint(f'    print("K12: x =", x)  {MARK}')
    assert not cp.is_checkpoint('print("K1")')
    assert not cp.is_checkpoint('print("Hallo")  # Kontrollpunkt')


def test_insert_numbers_in_file_order():
    text = "a = 1\nb = 2\nc = 3"
    text, _ = cp.insert(text, 3)
    text, line = cp.insert(text, 1)
    assert line == 1
    lines = text.split("\n")
    assert lines[0] == f'print("K1")  {MARK}'
    assert lines[3] == f'print("K2")  {MARK}'


def test_insert_with_variable_name_prints_value():
    text, line = cp.insert("x = 5\nprint(x)", 2, name="x")
    assert line == 2
    assert text.split("\n")[1] == f'print("K1: x =", x)  {MARK}'


def test_insert_ignores_invalid_variable_name():
    text, line = cp.insert("x = 5", 1, name="x); import os")
    assert text.split("\n")[0] == f'print("K1")  {MARK}'
    assert "import" not in text


def test_insert_keeps_indentation_of_block():
    text = "for i in range(3):\n    print(i)"
    new, line = cp.insert(text, 2)
    assert new.split("\n")[line - 1].startswith('    print("K1")')


def test_insert_into_empty_line_after_colon_indents():
    text = "if True:\n"
    new, line = cp.insert(text, 2)
    assert new.split("\n")[line - 1].startswith('    print("K1")')


def test_insert_into_empty_line_before_code_uses_following_indent():
    text = "if True:\n\n    pass"
    new, line = cp.insert(text, 2)
    assert new.split("\n")[line - 1].startswith('    print("K1")')


def test_insert_beyond_end_appends():
    new, line = cp.insert("a = 1", 99)
    assert line == 2
    assert new.split("\n")[-1] == f'print("K1")  {MARK}'


def test_renumber_closes_gaps():
    text = f'print("K5")  {MARK}\nx = 1\nprint("K9")  {MARK}'
    out = cp.renumber(text)
    assert out.split("\n")[0].startswith('print("K1")')
    assert out.split("\n")[2].startswith('print("K2")')


def test_remove_all_returns_count_and_leaves_code():
    text = f'a = 1\nprint("K1")  {MARK}\nb = 2\n    print("K2")  {MARK}'
    out, n = cp.remove_all(text)
    assert n == 2
    assert out == "a = 1\nb = 2"


def test_reached_in_output():
    out = "K1\nHallo\nK2: x = 5\nK10\nnicht K3"
    assert cp.reached_in_output(out) == [1, 2, 10]
    assert cp.reached_in_output("") == []
    assert cp.reached_in_output(None) == []


def test_line_of():
    text = f'a = 1\nprint("K1")  {MARK}\nb = 2\nprint("K2")  {MARK}'
    assert cp.line_of(text, 1) == 2
    assert cp.line_of(text, 2) == 4
    assert cp.line_of(text, 3) is None
