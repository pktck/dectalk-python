"""Verify par_print_rule_error matches par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_print_rule_error import par_print_rule_error


def test_emits_four_lines_in_c_order() -> None:
    """The function emits message, position, rule, and caret in that order."""
    output: list[str] = []
    par_print_rule_error(
        "bad token",
        b"abc:xyz",
        3,
        emit=output.append,
    )
    assert output == [
        "bad token",
        "error in rule at position 3",
        "rule, abc:xyz",
        "      " + " " * 3 + "^",
    ]


def test_caret_aligns_at_pos_zero() -> None:
    """At pos=0, the caret has no leading spaces beyond the 6-space prefix."""
    output: list[str] = []
    par_print_rule_error(
        "msg",
        b"x",
        0,
        emit=output.append,
    )
    assert output[3] == "      ^"  # 6 spaces then caret.


def test_caret_column_matches_c_layout() -> None:
    """The caret column equals ``6 + pos`` in characters."""
    output: list[str] = []
    par_print_rule_error(
        "x",
        b"hello world",
        5,
        emit=output.append,
    )
    caret_line = output[3]
    assert caret_line[-1] == "^"
    # 6 leading spaces + 5 spaces for pos = 11 chars before the caret.
    assert len(caret_line) - 1 == 6 + 5


def test_non_ascii_bytes_decoded_via_latin_1() -> None:
    """Non-ASCII bytes in the rule are rendered via latin-1."""
    output: list[str] = []
    par_print_rule_error(
        "x",
        b"\xc3\xa9",  # é in UTF-8 — but decoded as latin-1.
        0,
        emit=output.append,
    )
    # latin-1 decode: 0xc3 → 'Ã', 0xa9 → '©'.
    assert output[2] == "rule, Ã©"


def test_emit_callback_replaces_stdout() -> None:
    """A custom emit captures output instead of printing."""
    captured: list[str] = []
    par_print_rule_error("err", b"abc", 1, emit=captured.append)
    assert len(captured) == 4
