"""Verify par_set_return_level / par_get_return_level match par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_limits import PAR_MAX_RETURN_LEVEL
from dectalk.cmd.par_return_stack import par_get_return_level, par_set_return_level


def test_set_pushes_onto_stack() -> None:
    """A single push advances the cursor and stores the rule."""
    stack = [0] * PAR_MAX_RETURN_LEVEL
    level = [0]
    par_set_return_level(stack, level, 7)
    assert stack[0] == 7
    assert level[0] == 1


def test_pop_returns_top_then_decrements() -> None:
    """A pop returns the top rule and decrements the cursor."""
    stack = [0] * PAR_MAX_RETURN_LEVEL
    level = [0]
    par_set_return_level(stack, level, 7)
    par_set_return_level(stack, level, 8)
    assert level[0] == 2
    assert par_get_return_level(stack, level, 99) == 8
    assert level[0] == 1
    assert par_get_return_level(stack, level, 99) == 7
    assert level[0] == 0


def test_pop_empty_falls_through_to_next() -> None:
    """Popping an empty stack returns ``current_rule_number + 1``."""
    stack = [0] * PAR_MAX_RETURN_LEVEL
    level = [0]
    assert par_get_return_level(stack, level, 42) == 43
    assert level[0] == 0  # cursor unchanged


def test_set_at_capacity_drops_silently() -> None:
    """Pushing at full capacity is silently dropped (matches C source)."""
    stack = [0] * PAR_MAX_RETURN_LEVEL
    level = [PAR_MAX_RETURN_LEVEL]
    par_set_return_level(stack, level, 99)
    assert level[0] == PAR_MAX_RETURN_LEVEL  # cursor unchanged
    # Last stack slot is unchanged.
    assert stack[-1] == 0


def test_push_to_capacity_then_pop_returns_lifo() -> None:
    """Filling to capacity then popping all returns in LIFO order."""
    stack = [0] * PAR_MAX_RETURN_LEVEL
    level = [0]
    for i in range(PAR_MAX_RETURN_LEVEL):
        par_set_return_level(stack, level, 100 + i)
    assert level[0] == PAR_MAX_RETURN_LEVEL
    for i in reversed(range(PAR_MAX_RETURN_LEVEL)):
        assert par_get_return_level(stack, level, -1) == 100 + i
    assert level[0] == 0
