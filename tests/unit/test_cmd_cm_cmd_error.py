"""Verify cm_cmd_error matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_error import cm_cmd_error
from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_success,
    ERROR_escape,
    ERROR_ignore,
    ERROR_speak,
    ERROR_text,
    ERROR_tone,
)
from dectalk.cmd.cmd_t import CmdT


def _with_keyword(keyword: str) -> CmdT:
    """Build a CmdT carrying a single ASCII-encoded keyword."""
    state = CmdT()
    state.pString = [keyword.encode("latin-1")]
    return state


def test_ignore_keyword() -> None:
    """``[:error ignore]`` sets error_mode to ERROR_ignore."""
    cmd = _with_keyword("ignore")
    result = cm_cmd_error(cmd)
    assert result == CMD_success
    assert cmd.error_mode == ERROR_ignore


def test_text_keyword() -> None:
    """``[:error text]`` sets error_mode to ERROR_text."""
    cmd = _with_keyword("text")
    result = cm_cmd_error(cmd)
    assert result == CMD_success
    assert cmd.error_mode == ERROR_text


def test_escape_keyword() -> None:
    """``[:error escape]`` sets error_mode to ERROR_escape."""
    cmd = _with_keyword("escape")
    result = cm_cmd_error(cmd)
    assert result == CMD_success
    assert cmd.error_mode == ERROR_escape


def test_speak_keyword() -> None:
    """``[:error speak]`` sets error_mode to ERROR_speak."""
    cmd = _with_keyword("speak")
    result = cm_cmd_error(cmd)
    assert result == CMD_success
    assert cmd.error_mode == ERROR_speak


def test_tone_keyword() -> None:
    """``[:error tone]`` sets error_mode to ERROR_tone."""
    cmd = _with_keyword("tone")
    result = cm_cmd_error(cmd)
    assert result == CMD_success
    assert cmd.error_mode == ERROR_tone


def test_unknown_keyword_returns_bad_string() -> None:
    """Unknown keywords return CMD_bad_string and don't change error_mode."""
    cmd = _with_keyword("bogus")
    cmd.error_mode = ERROR_speak
    assert cm_cmd_error(cmd) == CMD_bad_string
    assert cmd.error_mode == ERROR_speak  # Unchanged.


def test_empty_pstring_returns_bad_string() -> None:
    """An empty pString[] return slot returns CMD_bad_string."""
    cmd = CmdT()
    assert cm_cmd_error(cmd) == CMD_bad_string
