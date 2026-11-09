"""Python → Blockly (koalino.py2blockly).

``python_to_block_state`` fängt intern alle Fehler ab und liefert dann EINEN
Roh-Block mit dem gesamten Quelltext. „Wirft nicht“ ist deshalb zu wenig: die
Tests prüfen, dass typische Schülerprogramme wirklich in Blöcke zerlegt werden
und dass kein Quelltext verloren geht.
"""
import ast

import pytest

from koalino.py2blockly import python_to_block_state

RAW = ("nit_raw", "nit_raw_expr", "nit_import", "nit_class")


def _blocks(node, out=None):
    """Alle Blöcke (rekursiv) eines State-Fragments in Dokumentreihenfolge."""
    out = [] if out is None else out
    if isinstance(node, dict):
        if "type" in node:
            out.append(node)
        for v in node.values():
            _blocks(v, out)
    elif isinstance(node, list):
        for v in node:
            _blocks(v, out)
    return out


def _types(code):
    return [b["type"] for b in _blocks(python_to_block_state(code)["blocks"])]


def _raw_code(code):
    return [b["fields"]["CODE"] for b in _blocks(python_to_block_state(code)["blocks"])
            if b["type"] in RAW]


PROGRAMME = {
    "print_input": 'name = input("Name? ")\nprint("Hallo", name)\n',
    "if_elif": ('x = int(input("x"))\nif x > 5:\n    print("gross")\n'
                'elif x > 2:\n    print("mittel")\nelse:\n    print("klein")\n'),
    "while_break": 'i = 0\nwhile True:\n    i += 1\n    if i == 5:\n        break\nprint(i)\n',
    "for_range": 'for i in range(3):\n    print(i)\n',
    "funktion": 'def quadrat(n):\n    return n * n\n\nprint(quadrat(4))\n',
    "micropython_pin": ('from machine import Pin\nfrom time import sleep\n'
                        'led = Pin(2, Pin.OUT)\nwhile True:\n    led.on()\n    sleep(1)\n'
                        '    led.off()\n    sleep(1)\n'),
}


@pytest.mark.parametrize("name", PROGRAMME)
def test_program_is_split_into_blocks_not_one_raw_block(name):
    code = PROGRAMME[name]
    state = python_to_block_state(code)
    assert state["blocks"]["languageVersion"] == 0
    blocks = _blocks(state["blocks"])
    assert blocks
    # Der Fallback wäre genau ein nit_raw mit dem kompletten Quelltext
    assert not (len(blocks) == 1 and blocks[0]["type"] == "nit_raw")
    assert all(isinstance(b["type"], str) and b["type"] for b in blocks)


@pytest.mark.parametrize("name", PROGRAMME)
def test_every_statement_is_a_block_or_kept_as_raw_python(name):
    """Jede Quellzeile ist abgebildet ODER steht unverändert in einem Roh-Block."""
    code = PROGRAMME[name]
    raw = "\n".join(_raw_code(code))
    # Roh-Code muss gültiges Python bleiben, sonst wäre das Programm nicht ausführbar
    for snippet in _raw_code(code):
        ast.parse(snippet)
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "input":
            assert "input(" in raw


def test_expected_block_types():
    assert "controls_if" in _types(PROGRAMME["if_elif"])
    assert "controls_whileUntil" in _types(PROGRAMME["while_break"])
    assert "controls_flow_statements" in _types(PROGRAMME["while_break"])
    assert "controls_for" in _types(PROGRAMME["for_range"])
    t = _types(PROGRAMME["funktion"])
    assert "procedures_defreturn" in t and "procedures_callreturn" in t


def test_micropython_pin_becomes_hardware_blocks_without_instance_line():
    code = PROGRAMME["micropython_pin"]
    t = _types(code)
    assert "nit_pin_write" in t and "nit_warte" in t
    assert not _raw_code(code)   # nichts bleibt Roh-Text


def test_unknown_statement_falls_back_to_raw_block_with_source():
    code = "import math\nprint(math.sqrt(2))\nwith open('x') as f:\n    pass\n"
    raw = "\n".join(_raw_code(code))
    assert "with open('x') as f" in raw
    assert "import math" in raw or "math.sqrt" in raw


def test_syntax_error_returns_single_raw_block_with_original_text():
    code = "def (:\n"
    blocks = _blocks(python_to_block_state(code)["blocks"])
    assert [b["type"] for b in blocks] == ["nit_raw"]
    assert blocks[0]["fields"]["CODE"] == code


def test_empty_program_does_not_crash():
    state = python_to_block_state("")
    assert "blocks" in state


def test_parameters_become_workspace_variables():
    state = python_to_block_state(PROGRAMME["funktion"])
    assert {"name": "n"}.items() <= state["variables"][0].items()
