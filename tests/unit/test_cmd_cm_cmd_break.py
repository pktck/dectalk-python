"""Verify cm_cmd_break matches cm_copt.c (incl. its C-source bug)."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_break import cm_cmd_break
from dectalk.cmd.cmd_states import CMD_bad_string, CMD_success
from dectalk.cmd.cmd_t import CmdT
from dectalk.kernel.ksd_t import KsdT


def _with_strings(*strings: str) -> CmdT:
    """Build a CmdT carrying ``param_index`` ASCII-encoded strings."""
    state = CmdT()
    state.pString = [s.encode("latin-1") for s in strings]
    state.param_index = len(strings)
    return state


def test_text_keyword_sets_wbreak_true_c_bug() -> None:
    """``[:break text]`` sets wbreak (C-source bug: case 0 is 'text')."""
    ksd = KsdT()
    cmd = _with_strings("text")
    result = cm_cmd_break(ksd, cmd)
    assert result == CMD_success
    assert ksd.wbreak == 1


def test_phonemes_keyword_clears_wbreak_c_bug() -> None:
    """``[:break phonemes]`` clears wbreak (case 1 is 'phonemes')."""
    ksd = KsdT()
    ksd.wbreak = 1
    cmd = _with_strings("phonemes")
    result = cm_cmd_break(ksd, cmd)
    assert result == CMD_success
    assert ksd.wbreak == 0


def test_on_keyword_is_noop_due_to_c_bug() -> None:
    """``[:break on]`` is a no-op (the C switch has no case for index 7)."""
    ksd = KsdT()
    cmd = _with_strings("on")
    result = cm_cmd_break(ksd, cmd)
    assert result == CMD_success
    assert ksd.wbreak == 0  # No change.


def test_off_keyword_is_noop_due_to_c_bug() -> None:
    """``[:break off]`` is a no-op too."""
    ksd = KsdT()
    ksd.wbreak = 1
    cmd = _with_strings("off")
    result = cm_cmd_break(ksd, cmd)
    assert result == CMD_success
    assert ksd.wbreak == 1  # No change.


def test_unknown_keyword_returns_bad_string() -> None:
    """Unknown keywords return CMD_bad_string."""
    ksd = KsdT()
    cmd = _with_strings("bogus")
    assert cm_cmd_break(ksd, cmd) == CMD_bad_string


def test_multiple_params_applied_in_order() -> None:
    """Successive params apply left-to-right; last write wins."""
    ksd = KsdT()
    cmd = _with_strings("text", "phonemes")
    result = cm_cmd_break(ksd, cmd)
    assert result == CMD_success
    assert ksd.wbreak == 0  # 'phonemes' was last → cleared.


def test_no_params_is_noop_success() -> None:
    """Zero-param invocation is a clean no-op."""
    ksd = KsdT()
    cmd = _with_strings()
    assert cm_cmd_break(ksd, cmd) == CMD_success
    assert ksd.wbreak == 0
