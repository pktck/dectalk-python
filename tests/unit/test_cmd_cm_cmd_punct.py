"""Verify cm_cmd_punct matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_punct import cm_cmd_punct
from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_success,
    PUNCT_all,
    PUNCT_none,
    PUNCT_pass,
    PUNCT_some,
)
from dectalk.cmd.cmd_t import CmdT


def _with_keyword(keyword: str) -> CmdT:
    """Build a CmdT carrying a single ASCII-encoded keyword."""
    state = CmdT()
    state.pString = [keyword.encode("latin-1")]
    return state


def test_none_keyword() -> None:
    """``[:punct none]`` sets punct_mode to PUNCT_none."""
    cmd = _with_keyword("none")
    assert cm_cmd_punct(cmd) == CMD_success
    assert cmd.punct_mode == PUNCT_none


def test_some_keyword() -> None:
    """``[:punct some]`` sets punct_mode to PUNCT_some."""
    cmd = _with_keyword("some")
    assert cm_cmd_punct(cmd) == CMD_success
    assert cmd.punct_mode == PUNCT_some


def test_all_keyword() -> None:
    """``[:punct all]`` sets punct_mode to PUNCT_all."""
    cmd = _with_keyword("all")
    assert cm_cmd_punct(cmd) == CMD_success
    assert cmd.punct_mode == PUNCT_all


def test_pass_keyword() -> None:
    """``[:punct pass]`` sets punct_mode to PUNCT_pass."""
    cmd = _with_keyword("pass")
    assert cm_cmd_punct(cmd) == CMD_success
    assert cmd.punct_mode == PUNCT_pass


def test_unknown_keyword_returns_bad_string() -> None:
    """Unknown keywords return CMD_bad_string."""
    cmd = _with_keyword("bogus")
    assert cm_cmd_punct(cmd) == CMD_bad_string


def test_empty_pstring_returns_bad_string() -> None:
    """An empty pString[] returns CMD_bad_string."""
    cmd = CmdT()
    assert cm_cmd_punct(cmd) == CMD_bad_string
