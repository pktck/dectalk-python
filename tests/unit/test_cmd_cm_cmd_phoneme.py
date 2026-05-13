"""Verify cm_cmd_phoneme matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_phoneme import cm_cmd_phoneme
from dectalk.cmd.cmd_states import (
    PHONEME_ASCKY,
    PHONEME_OFF,
    PHONEME_SPEAK,
    CMD_bad_string,
    CMD_success,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.kernel.ksd_t import KsdT


def _with_keywords(*keywords: str) -> CmdT:
    """Build a CmdT carrying ``param_index`` ASCII-encoded keywords."""
    state = CmdT()
    state.pString = [k.encode("latin-1") for k in keywords]
    state.param_index = len(keywords)
    return state


def test_ascky_sets_ascky_bit() -> None:
    """``[:phoneme ascky]`` ORs in PHONEME_ASCKY."""
    ksd = KsdT()
    cmd = _with_keywords("asky")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_success
    assert ksd.phoneme_mode & PHONEME_ASCKY


def test_arpabet_clears_ascky_bit() -> None:
    """``[:phoneme arpabet]`` clears PHONEME_ASCKY."""
    ksd = KsdT()
    ksd.phoneme_mode = PHONEME_ASCKY | PHONEME_SPEAK
    cmd = _with_keywords("arpabet")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_success
    assert not (ksd.phoneme_mode & PHONEME_ASCKY)
    assert ksd.phoneme_mode & PHONEME_SPEAK  # Other bits preserved.


def test_speak_sets_speak_bit() -> None:
    """``[:phoneme speak]`` ORs in PHONEME_SPEAK."""
    ksd = KsdT()
    cmd = _with_keywords("speak")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_success
    assert ksd.phoneme_mode & PHONEME_SPEAK


def test_silent_clears_speak_bit() -> None:
    """``[:phoneme silent]`` clears PHONEME_SPEAK."""
    ksd = KsdT()
    ksd.phoneme_mode = PHONEME_SPEAK
    cmd = _with_keywords("silent")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_success
    assert not (ksd.phoneme_mode & PHONEME_SPEAK)


def test_off_sets_off_bit() -> None:
    """``[:phoneme off]`` ORs in PHONEME_OFF."""
    ksd = KsdT()
    cmd = _with_keywords("off")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_success
    assert ksd.phoneme_mode & PHONEME_OFF


def test_on_clears_off_bit() -> None:
    """``[:phoneme on]`` clears PHONEME_OFF."""
    ksd = KsdT()
    ksd.phoneme_mode = PHONEME_OFF
    cmd = _with_keywords("on")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_success
    assert not (ksd.phoneme_mode & PHONEME_OFF)


def test_multiple_keywords_applied_in_order() -> None:
    """Successive keywords apply left-to-right."""
    ksd = KsdT()
    cmd = _with_keywords("asky", "speak", "on")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_success
    assert ksd.phoneme_mode & PHONEME_ASCKY
    assert ksd.phoneme_mode & PHONEME_SPEAK
    # "on" clears PHONEME_OFF, which was already 0.
    assert not (ksd.phoneme_mode & PHONEME_OFF)


def test_unknown_keyword_returns_bad_string() -> None:
    """Unknown keywords return CMD_bad_string."""
    ksd = KsdT()
    cmd = _with_keywords("bogus")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_bad_string


def test_unknown_keyword_in_middle_aborts_chain() -> None:
    """A bad keyword stops processing immediately."""
    ksd = KsdT()
    cmd = _with_keywords("speak", "bogus", "off")
    assert cm_cmd_phoneme(ksd, cmd) == CMD_bad_string
    assert ksd.phoneme_mode & PHONEME_SPEAK  # 'speak' was applied.
    assert not (ksd.phoneme_mode & PHONEME_OFF)  # 'off' was not reached.


def test_zero_params_returns_success_with_no_change() -> None:
    """No keywords → no-op success."""
    ksd = KsdT()
    ksd.phoneme_mode = 0x5
    cmd = _with_keywords()
    assert cm_cmd_phoneme(ksd, cmd) == CMD_success
    assert ksd.phoneme_mode == 0x5
