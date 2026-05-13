"""Verify cm_cmd_say matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_say import cm_cmd_say
from dectalk.cmd.cmd_states import CMD_bad_string, CMD_flushing, CMD_success
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.say_flags import (
    SAY_CLAUSE,
    SAY_FLETTER,
    SAY_LETTER,
    SAY_LINE,
    SAY_SYLLABLE,
    SAY_WORD,
)
from dectalk.kernel.ksd_t import KsdT


def _with_keyword(keyword: str) -> CmdT:
    """Build a CmdT carrying a single ASCII-encoded keyword."""
    state = CmdT()
    state.pString = [keyword.encode("latin-1")]
    return state


def test_clause_keyword() -> None:
    """``[:say clause]`` sets sayflag to SAY_CLAUSE."""
    ksd = KsdT()
    cmd = _with_keyword("clause")
    assert cm_cmd_say(ksd, cmd) == CMD_success
    assert ksd.sayflag == SAY_CLAUSE


def test_word_keyword() -> None:
    """``[:say word]`` sets sayflag to SAY_WORD."""
    ksd = KsdT()
    cmd = _with_keyword("word")
    assert cm_cmd_say(ksd, cmd) == CMD_success
    assert ksd.sayflag == SAY_WORD


def test_letter_keyword_with_clean_sync() -> None:
    """``[:say letter]`` sets sayflag to SAY_LETTER when sync succeeds."""
    ksd = KsdT()
    cmd = _with_keyword("letter")
    assert cm_cmd_say(ksd, cmd) == CMD_success
    assert ksd.sayflag == SAY_LETTER


def test_letter_keyword_with_flushing_sync_aborts() -> None:
    """``[:say letter]`` returns CMD_flushing when sync says so."""
    ksd = KsdT()
    cmd = _with_keyword("letter")
    result = cm_cmd_say(ksd, cmd, sync_fn=lambda: CMD_flushing)
    assert result == CMD_flushing
    assert ksd.sayflag == 0  # Unchanged.


def test_filtered_letter_keyword() -> None:
    """``[:say filtered_letter]`` sets sayflag to SAY_FLETTER."""
    ksd = KsdT()
    cmd = _with_keyword("filtered_letter")
    assert cm_cmd_say(ksd, cmd) == CMD_success
    assert ksd.sayflag == SAY_FLETTER


def test_filtered_letter_with_flushing_sync_aborts() -> None:
    """``[:say filtered_letter]`` honours sync flush."""
    ksd = KsdT()
    cmd = _with_keyword("filtered_letter")
    result = cm_cmd_say(ksd, cmd, sync_fn=lambda: CMD_flushing)
    assert result == CMD_flushing
    assert ksd.sayflag == 0


def test_line_keyword() -> None:
    """``[:say line]`` sets sayflag to SAY_LINE."""
    ksd = KsdT()
    cmd = _with_keyword("line")
    assert cm_cmd_say(ksd, cmd) == CMD_success
    assert ksd.sayflag == SAY_LINE


def test_syllable_keyword() -> None:
    """``[:say syllable]`` sets sayflag to SAY_SYLLABLE.

    The C source's comment says "syllables" but the actual option
    table entry is "syllable" (singular). Passing "syllables" with
    a trailing 's' fails the prefix match.
    """
    ksd = KsdT()
    cmd = _with_keyword("syllable")
    assert cm_cmd_say(ksd, cmd) == CMD_success
    assert ksd.sayflag == SAY_SYLLABLE


def test_unknown_keyword_returns_bad_string() -> None:
    """Unknown keywords return CMD_bad_string."""
    ksd = KsdT()
    cmd = _with_keyword("bogus")
    assert cm_cmd_say(ksd, cmd) == CMD_bad_string


def test_empty_pstring_returns_bad_string() -> None:
    """An empty pString[] return slot returns CMD_bad_string."""
    ksd = KsdT()
    cmd = CmdT()
    assert cm_cmd_say(ksd, cmd) == CMD_bad_string
