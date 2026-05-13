"""Verify par_skip_standard matches par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_skip_standard import par_skip_standard
from dectalk.cmd.par_structs import ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL


def _silent_emit(_text: str) -> None:
    """Discard diagnostics so test output stays clean."""


def test_skips_simple_count_block() -> None:
    """``a<3>`` advances rule offset past the ``>``."""
    rule = b"a<3>rest"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == 0
    assert rv.rule == 4


def test_skips_star_block() -> None:
    """``a<*>`` is valid; star marks zero-or-more."""
    rule = b"a<*>"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == 0
    assert rv.rule == 4


def test_skips_plus_block() -> None:
    """``a<+>`` is valid; plus marks one-or-more."""
    rule = b"a<+>"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == 0
    assert rv.rule == 4


def test_skips_negation_marker() -> None:
    """``a~<3>`` advances past the ``~`` then the block."""
    rule = b"a~<3>rest"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == 0
    assert rv.rule == 5


def test_skips_count_range() -> None:
    """``a<1-5>`` (inclusive range)."""
    rule = b"a<1-5>tail"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == 0
    assert rv.rule == 6


def test_skips_open_ended_range() -> None:
    """``a<2-*>`` (two-or-more)."""
    rule = b"a<2-*>tail"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == 0
    assert rv.rule == 6


def test_skips_csv_enumeration() -> None:
    """``a<1,2,3>`` (allowed counts)."""
    rule = b"a<1,2,3>tail"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == 0
    assert rv.rule == 8


def test_missing_open_angle_fails() -> None:
    """A type with no ``<`` triggers FATAL_FAIL."""
    rule = b"a3>rest"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == FATAL_FAIL


def test_missing_close_after_star_fails() -> None:
    """``a<*x>`` — '*' must be immediately followed by '>'."""
    rule = b"a<*x>"
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=_silent_emit)
    assert rv.value == FATAL_FAIL


def test_emits_diagnostic_on_error() -> None:
    """The diagnostic sink receives par_print_rule_error output."""
    captured: list[str] = []
    rule = b"abc"  # No '<' at all → triggers error.
    rv = ReturnValue(rule=0)
    par_skip_standard(rule, rv, emit=captured.append)
    assert any("no < found" in line for line in captured)
