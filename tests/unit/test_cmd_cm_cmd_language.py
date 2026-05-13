"""Verify cm_cmd_language matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_language import cm_cmd_language
from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_bad_value,
    CMD_flushing,
    CMD_success,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.include.cmd_codes import LAST_VOICE
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import (
    LANG_both_ready,
    LANG_english,
    LANG_french,
    LANG_none,
)


def _with_keyword(keyword: str) -> CmdT:
    """Build a CmdT with the keyword in pString[0]."""
    state = CmdT()
    state.pString = [keyword.encode("latin-1")]
    return state


def _ready_state(lang: int) -> KsdT:
    """Build a KsdT with ``lang`` fully loaded."""
    state = KsdT()
    state.lang_ready[lang] = LANG_both_ready
    return state


def test_english_keyword_switches_to_english() -> None:
    """``[:lang english]`` switches to LANG_english if ready."""
    ksd = _ready_state(LANG_english)
    cmd = _with_keyword("english")
    assert cm_cmd_language(ksd, cmd) == CMD_success
    assert ksd.lang_curr == LANG_english


def test_us_alias_also_works() -> None:
    """``[:lang us]`` is an alias for ``english``."""
    ksd = _ready_state(LANG_english)
    cmd = _with_keyword("us")
    assert cm_cmd_language(ksd, cmd) == CMD_success
    assert ksd.lang_curr == LANG_english


def test_unloaded_language_returns_bad_value() -> None:
    """A language that isn't fully loaded returns CMD_bad_value."""
    ksd = KsdT()  # No languages ready.
    cmd = _with_keyword("english")
    assert cm_cmd_language(ksd, cmd) == CMD_bad_value
    assert ksd.lang_curr == LANG_none


def test_unknown_keyword_returns_bad_string() -> None:
    """Unknown keywords return CMD_bad_string."""
    ksd = _ready_state(LANG_english)
    cmd = _with_keyword("klingon")
    assert cm_cmd_language(ksd, cmd) == CMD_bad_string


def test_dispatches_last_voice_to_lts_pipe() -> None:
    """A LAST_VOICE signal is sent to the LTS pipe on success."""
    ksd = _ready_state(LANG_english)
    cmd = _with_keyword("us")
    fake_pipe = object()
    ksd.lts_pipe = fake_pipe
    writes: list[tuple[object, int]] = []
    cm_cmd_language(
        ksd,
        cmd,
        lts_pipe_write=lambda pipe, phone: writes.append((pipe, phone)),
    )
    # After default_lang runs, lts_pipe is reassigned from lang_lts[lang],
    # so the captured pipe handle may not be the original.
    assert len(writes) == 1
    assert writes[0][1] == LAST_VOICE


def test_sync_flushing_aborts_with_flushing() -> None:
    """A flushing sync returns CMD_flushing before the language switch."""
    ksd = _ready_state(LANG_english)
    cmd = _with_keyword("english")
    result = cm_cmd_language(ksd, cmd, sync_fn=lambda: CMD_flushing)
    assert result == CMD_flushing
    assert ksd.lang_curr == LANG_none  # Switch aborted.


def test_esc_command_takes_index_from_params() -> None:
    """When esc_command is TRUE, cmd_type comes from params[0]."""
    ksd = _ready_state(LANG_french)
    cmd = CmdT()
    cmd.esc_command = 1  # TRUE
    cmd.params = [2]  # Index for "french".
    assert cm_cmd_language(ksd, cmd) == CMD_success
    assert ksd.lang_curr == LANG_french


def test_empty_pstring_returns_bad_string() -> None:
    """An empty pString[] returns CMD_bad_string in keyword mode."""
    ksd = _ready_state(LANG_english)
    cmd = CmdT()
    cmd.esc_command = 0
    assert cm_cmd_language(ksd, cmd) == CMD_bad_string
