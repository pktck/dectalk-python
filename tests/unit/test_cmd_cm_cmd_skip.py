"""Verify cm_cmd_skip matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_skip import cm_cmd_skip
from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_success,
    SKIP_all,
    SKIP_cpg,
    SKIP_email,
    SKIP_none,
    SKIP_punct,
    SKIP_rule,
)
from dectalk.cmd.cmd_t import CmdT


def _with_keyword(keyword: str) -> CmdT:
    """Build a CmdT carrying a single ASCII-encoded keyword."""
    state = CmdT()
    state.pString = [keyword.encode("latin-1")]
    return state


def test_none_keyword() -> None:
    """``[:skip none]`` sets skip_mode to SKIP_none."""
    cmd = _with_keyword("none")
    assert cm_cmd_skip(cmd) == CMD_success
    assert cmd.skip_mode == SKIP_none


def test_email_keyword() -> None:
    """``[:skip email]`` sets skip_mode to SKIP_email."""
    cmd = _with_keyword("email")
    assert cm_cmd_skip(cmd) == CMD_success
    assert cmd.skip_mode == SKIP_email


def test_punct_keyword() -> None:
    """``[:skip punct]`` sets skip_mode to SKIP_punct."""
    cmd = _with_keyword("punct")
    assert cm_cmd_skip(cmd) == CMD_success
    assert cmd.skip_mode == SKIP_punct


def test_rule_keyword() -> None:
    """``[:skip rule]`` sets skip_mode to SKIP_rule."""
    cmd = _with_keyword("rule")
    assert cm_cmd_skip(cmd) == CMD_success
    assert cmd.skip_mode == SKIP_rule


def test_all_keyword() -> None:
    """``[:skip all]`` sets skip_mode to SKIP_all."""
    cmd = _with_keyword("all")
    assert cm_cmd_skip(cmd) == CMD_success
    assert cmd.skip_mode == SKIP_all


def test_cpg_keyword() -> None:
    """``[:skip cpg]`` sets skip_mode to SKIP_cpg."""
    cmd = _with_keyword("cpg")
    assert cm_cmd_skip(cmd) == CMD_success
    assert cmd.skip_mode == SKIP_cpg


def test_unknown_keyword_returns_bad_string() -> None:
    """Unknown keywords return CMD_bad_string."""
    cmd = _with_keyword("bogus")
    assert cm_cmd_skip(cmd) == CMD_bad_string


def test_empty_pstring_returns_bad_string() -> None:
    """An empty pString[] returns CMD_bad_string."""
    cmd = CmdT()
    assert cm_cmd_skip(cmd) == CMD_bad_string
