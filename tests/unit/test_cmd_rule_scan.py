"""Verify ``par_find_conditional_number`` / ``par_find_end_of_rule`` parity."""

from __future__ import annotations

import pytest

from dectalk.cmd import rule_scan as rs

# ---- par_find_end_of_rule ----


def test_end_of_rule_with_no_literals() -> None:
    """Stops at the first '/'."""
    rule = b"abc/def"
    assert rs.par_find_end_of_rule(rule, 0) == 3  # '/' at index 3


def test_end_of_rule_skips_exact_char_literal() -> None:
    """``'...'`` literals are skipped — interior '/' doesn't stop the scan."""
    # 'a' '/' 'b' is a literal; the outer '/' at index 5 is the end of rule.
    rule = b"'a/b'/x"  # rule_p=0: a/b is a literal, '/' at 5 ends rule
    assert rs.par_find_end_of_rule(rule, 0) == 5


def test_end_of_rule_skips_escape() -> None:
    """``\\X`` in a literal consumes one extra byte for the escape."""
    # Literal contains an escaped ']' (just for variety).
    rule = b"'a\\'b'/y"
    # Layout: ' a \ ' b ' / y
    # idx:    0 1 2 3 4 5 6 7
    # Walk: starting at 0 → exact_char_delim. rule_p++ → 1, skip literal:
    #   1: 'a' not ', 1 → 2: '\' → escape, +=1 (3), +=1 (4); 4: 'b' not ',
    #   +=1 → 5; 5: ' is terminator → stop. After loop, rule_p++ → 6.
    # 6 is '/' → outer while exits, return 6.
    assert rs.par_find_end_of_rule(rule, 0) == 6


def test_end_of_rule_none_rule() -> None:
    """NULL rule returns ``rule_p`` unchanged."""
    assert rs.par_find_end_of_rule(None, 42) == 42


def test_end_of_rule_immediate_slash() -> None:
    """Empty body — rule_p points at '/' from the start."""
    rule = b"/abc"
    assert rs.par_find_end_of_rule(rule, 0) == 0


# ---- par_find_conditional_number ----


def test_conditional_jump_one() -> None:
    """Skip past one ``|`` separator."""
    # rule: abc|def|ghi/
    rule = b"abc|def|ghi/"
    # rule_p=0, cond_num=1: walk → '|' at idx 3, cond_num→0, rule_p→4.
    assert rs.par_find_conditional_number(rule, 0, 1) == 4


def test_conditional_jump_two() -> None:
    """Skip past two ``|`` separators."""
    rule = b"abc|def|ghi/"
    # cond_num=2: → '|' at 3 (cond_num=1), → '|' at 7 (cond_num=0). rule_p=8.
    assert rs.par_find_conditional_number(rule, 0, 2) == 8


def test_conditional_skip_exact_literal() -> None:
    """``'|'`` inside a literal does not count as a separator."""
    rule = b"a'|b'|c|d/"
    # Literal 'a' at idx=1..5 (positions: a',|,b,', cumulative skip).
    # We need cond_num=1: encounter ' literal first, skip over the inner '|'.
    # Reaches '|' at outer level after skipping the literal.
    assert rs.par_find_conditional_number(rule, 0, 1) == 6


def test_conditional_state_part_terminator() -> None:
    """Encountering ``/`` early sets cond_num to -1 and decrements rule_p."""
    rule = b"abc/def"
    # cond_num=1, no '|' before '/'. The C source does cond_num=-1, rule_p--,
    # then rule_p++ at loop end. So rule_p stays at 3 (the '/' position).
    assert rs.par_find_conditional_number(rule, 0, 1) == 3


def test_conditional_none_rule() -> None:
    """NULL rule returns ``rule_p`` unchanged."""
    assert rs.par_find_conditional_number(None, 42, 5) == 42


def test_conditional_zero_cond_num() -> None:
    """cond_num=0 returns ``rule_p`` unchanged."""
    rule = b"abc|def|ghi/"
    assert rs.par_find_conditional_number(rule, 0, 0) == 0


@pytest.mark.parametrize(
    ("rule", "rule_p", "cond_num", "expected"),
    [
        (b"a|b|c|d/", 0, 1, 2),  # skip 1: '|' at 1, rule_p → 2
        (b"a|b|c|d/", 0, 2, 4),  # skip 2: '|' at 1, '|' at 3, rule_p → 4
        (b"a|b|c|d/", 0, 3, 6),  # skip 3: rule_p → 6
        (b"a|b/", 0, 5, 3),  # only 1 '|' present, then '/' — early stop
    ],
)
def test_conditional_parametric(rule: bytes, rule_p: int, cond_num: int, expected: int) -> None:
    """Several conditional-skip scenarios."""
    assert rs.par_find_conditional_number(rule, rule_p, cond_num) == expected
