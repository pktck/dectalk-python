"""C-source parity test for ``cm_phon_match`` against cm_phon.c.

Re-parses the body of ``cm_phon_match`` (lines 765-999 in
``src/dapi/src/cmd/cm_phon.c``) using brace-depth tracking and asserts
the load-bearing structural invariants:

- The CR / LF / text_flush early-out is preserved.
- The ``param_index && cm_phon_param_check(c)`` arm is preserved.
- The ``international_phon_lang<0 && international_flag>=0`` arm is
  preserved and the failing-ARPA path emits ``CMD_bad_phoneme`` /
  ``cm_pars_new_state(STATE_TOSS)`` / ``cm_phon_flush``.
- The ``q_flag`` set branch's ``]`` / ``:`` / default arms are
  preserved, including the language lookup detour.
- The no-q_flag default arm dispatches on ``phoneme_mode & PHONEME_ASCKY``.

Plus behavioural tests of the Python architectural shim's deterministic
pieces.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_phon_match import (
    PhonMatchInput,
    PhonMatchResult,
    cm_phon_match,
)
from dectalk.cmd.cmd_states import (
    PHONEME_ASCKY,
    STATE_COMMAND,
    STATE_NORMAL,
    STATE_TOSS,
    CMD_bad_phoneme,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_phon.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_cm_phon_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``cm_phon_match`` body via brace tracking."""
    text = _read_cm_phon_c()
    decl = re.search(r"\bvoid\s+cm_phon_match\s*\(", text)
    assert decl is not None, "cm_phon_match declaration not found in cm_phon.c"
    brace_start = text.index("{", decl.end())
    depth = 1
    i = brace_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, "Unbalanced braces extracting cm_phon_match body"
    return text[brace_start + 1 : i - 1]


# -- Structural assertions on the C body ----------------------------


def test_c_body_has_cr_lf_text_flush_early_out() -> None:
    """The body still short-circuits on CR / LF / text_flush."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*c\s*==\s*CR\s*\|\|\s*c\s*==\s*LF\s*\|\|"
        r"\s*pKsd_t\s*->\s*text_flush\s*\)",
        body,
    )


def test_c_body_param_index_phon_param_check_arm() -> None:
    """The body still has the ``param_index && cm_phon_param_check(c)`` arm."""
    body = _extract_body()
    assert re.search(
        r"pCmd_t\s*->\s*param_index\s*&&\s*cm_phon_param_check\s*\(\s*phTTS\s*,\s*c\s*\)",
        body,
    )


def test_c_body_international_arm_calls_cm_phon_flush_on_match() -> None:
    """The intl arm's match=1 path calls cm_phon_flush."""
    body = _extract_body()
    # Inside the int'l arm there is a switch on cm_phon_lookup_arpa(...).
    # case 1 sets q_flag = international_temp then calls cm_phon_flush.
    assert re.search(r"cm_phon_flush\s*\(\s*phTTS\s*\)", body)


def test_c_body_international_arm_emits_cmd_bad_phoneme() -> None:
    """The intl arm's match=0 path emits CMD_bad_phoneme and STATE_TOSS."""
    body = _extract_body()
    assert re.search(r"cm_cmd_error_comm\s*\(\s*phTTS\s*,\s*CMD_bad_phoneme\s*\)", body)
    assert re.search(r"cm_pars_new_state\s*\(\s*pCmd_t\s*,\s*STATE_TOSS\s*\)", body)


def test_c_body_qflag_close_bracket_resets_to_normal() -> None:
    """``]`` while q_flag pending eventually calls cm_cmd_reset_comm(STATE_NORMAL)."""
    body = _extract_body()
    assert re.search(
        r"cm_cmd_reset_comm\s*\(\s*pCmd_t\s*,\s*STATE_NORMAL\s*\)",
        body,
    )


def test_c_body_qflag_colon_resets_to_command_when_arpa_two() -> None:
    """``:`` arm dispatches STATE_COMMAND when ARPA == 2."""
    body = _extract_body()
    assert re.search(
        r"cm_cmd_reset_comm\s*\(\s*pCmd_t\s*,\s*STATE_COMMAND\s*\)",
        body,
    )


def test_c_body_default_arm_consults_language_lookup() -> None:
    """The q_flag default arm consults ``cm_phon_lookup_language``."""
    body = _extract_body()
    assert re.search(
        r"cm_phon_lookup_language\s*\(\s*phTTS\s*,\s*\(unsigned\s+char\)\s*pCmd_t\s*->\s*q_flag",
        body,
    )


def test_c_body_default_arm_calls_cm_phon_param_check_on_match_one() -> None:
    """The q_flag default's case-1 path consults ``cm_phon_param_check(c)``."""
    body = _extract_body()
    # case 1: if (cm_phon_param_check(phTTS, c) == FALSE) q_flag = c; else q_flag = 0;
    assert re.search(
        r"cm_phon_param_check\s*\(\s*phTTS\s*,\s*c\s*\)\s*==\s*FALSE",
        body,
    )


def test_c_body_no_qflag_dispatches_on_phoneme_ascky() -> None:
    """The no-q_flag default arm tests ``phoneme_mode & PHONEME_ASCKY``."""
    body = _extract_body()
    assert re.search(
        r"pKsd_t\s*->\s*phoneme_mode\s*&\s*PHONEME_ASCKY",
        body,
    )


def test_c_body_no_qflag_ascky_calls_cm_phon_lookup_asc() -> None:
    """ASCKY mode calls ``cm_phon_lookup_asc`` and falls into the error path on FALSE."""
    body = _extract_body()
    assert re.search(
        r"cm_phon_lookup_asc\s*\(\s*phTTS\s*,\s*c\s*\)\s*==\s*FALSE",
        body,
    )


# -- Behavioural tests of the Python shim ---------------------------


def _arpa_zero(_p1: int, _p2: int) -> tuple[int, int]:
    return 0, -1


def _arpa_one(_p1: int, _p2: int) -> tuple[int, int]:
    return 1, 0


def _arpa_two(_p1: int, _p2: int) -> tuple[int, int]:
    return 2, 0


def _lang_none(_p1: int, _p2: int) -> int:
    return -1


def _lang_match_2(_p1: int, _p2: int) -> int:
    return 2


def _asc_hit(_c: int) -> int:
    return 0


def _asc_miss(_c: int) -> int:
    return -1


def _no_param_check(_c: int) -> bool:
    return False


def _param_check_hit(_c: int) -> bool:
    return True


def test_python_returns_dataclass_result() -> None:
    """The shim returns a :class:`PhonMatchResult`."""
    inp = PhonMatchInput(c=ord("a"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert isinstance(res, PhonMatchResult)


def test_python_cr_short_circuits() -> None:
    """CR returns without touching state."""
    inp = PhonMatchInput(c=ord("\r"), q_flag=42)
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.q_flag == 42
    assert res.error_code == 0


def test_python_lf_short_circuits() -> None:
    """LF returns without touching state."""
    inp = PhonMatchInput(c=ord("\n"), q_flag=42)
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.q_flag == 42


def test_python_text_flush_short_circuits() -> None:
    """A truthy text_flush returns without touching state."""
    inp = PhonMatchInput(c=ord("a"), text_flush=1, q_flag=42)
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.q_flag == 42


def test_python_param_check_arm_short_circuits() -> None:
    """``param_index>0 && param_check(c)`` returns immediately."""
    inp = PhonMatchInput(c=ord("0"), param_index=1, q_flag=42)
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_param_check_hit,
    )
    assert res.q_flag == 42
    assert res.error_code == 0
    assert res.flushed is False


def test_python_qflag_close_bracket_resets_to_normal() -> None:
    """``]`` with q_flag and ARPA(q,' ')=2 sets reset_state=STATE_NORMAL."""
    inp = PhonMatchInput(c=ord("]"), q_flag=ord("r"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_two,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.reset_state == STATE_NORMAL


def test_python_qflag_close_bracket_bad_phoneme_when_arpa_zero() -> None:
    """``]`` with q_flag and ARPA(q,' ')=0 emits CMD_bad_phoneme."""
    inp = PhonMatchInput(c=ord("]"), q_flag=ord("r"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.error_code == CMD_bad_phoneme
    assert res.new_state == STATE_NORMAL


def test_python_qflag_colon_resets_to_command_when_arpa_two() -> None:
    """``:`` with q_flag and ARPA(q,' ')=2 sets reset_state=STATE_COMMAND."""
    inp = PhonMatchInput(c=ord(":"), q_flag=ord("r"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_two,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.reset_state == STATE_COMMAND
    assert res.flushed is True


def test_python_qflag_colon_bad_phoneme_when_arpa_one() -> None:
    """``:`` with q_flag and ARPA(q,' ')=1 emits CMD_bad_phoneme."""
    inp = PhonMatchInput(c=ord(":"), q_flag=ord("r"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_one,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.error_code == CMD_bad_phoneme
    assert res.new_state == STATE_TOSS


def test_python_qflag_default_arpa_zero_emits_error() -> None:
    """q_flag set, ARPA(q,c)=0 emits CMD_bad_phoneme and STATE_TOSS."""
    inp = PhonMatchInput(c=ord("z"), q_flag=ord("r"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.error_code == CMD_bad_phoneme
    assert res.new_state == STATE_TOSS


def test_python_qflag_default_arpa_one_sets_qflag_to_c() -> None:
    """q_flag set, ARPA(q,c)=1, param_check=False sets q_flag = c."""
    inp = PhonMatchInput(c=ord("y"), q_flag=ord("r"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_one,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.q_flag == ord("y")
    assert res.flushed is True


def test_python_qflag_default_arpa_one_clears_qflag_if_param_check() -> None:
    """q_flag set, ARPA(q,c)=1, param_check=True clears q_flag."""
    inp = PhonMatchInput(c=ord("y"), q_flag=ord("r"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_one,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_param_check_hit,
    )
    assert res.q_flag == 0


def test_python_qflag_default_arpa_two_clears_qflag() -> None:
    """q_flag set, ARPA(q,c)=2 clears q_flag."""
    inp = PhonMatchInput(c=ord("y"), q_flag=ord("r"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_two,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.q_flag == 0


def test_python_qflag_default_language_match_captures() -> None:
    """A language-prefix match captures, doesn't ARPA-lookup."""
    inp = PhonMatchInput(c=ord("s"), q_flag=ord("u"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_match_2,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.international_flag == 2
    assert res.international_temp == ord("s")


def test_python_no_qflag_close_bracket_resets_to_normal() -> None:
    """``]`` without q_flag sets reset_state=STATE_NORMAL."""
    inp = PhonMatchInput(c=ord("]"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.reset_state == STATE_NORMAL


def test_python_no_qflag_colon_resets_to_command() -> None:
    """``:`` without q_flag sets reset_state=STATE_COMMAND."""
    inp = PhonMatchInput(c=ord(":"))
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.reset_state == STATE_COMMAND


def test_python_no_qflag_arpa_default_sets_qflag() -> None:
    """ARPA-mode no-q_flag default sets q_flag = c."""
    inp = PhonMatchInput(c=ord("r"), phoneme_mode=0)
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.q_flag == ord("r")


def test_python_no_qflag_ascky_miss_emits_error() -> None:
    """ASCKY-mode no-q_flag with miss emits CMD_bad_phoneme."""
    inp = PhonMatchInput(c=ord("r"), phoneme_mode=PHONEME_ASCKY)
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_miss,
        param_check=_no_param_check,
    )
    assert res.error_code == CMD_bad_phoneme
    assert res.new_state == STATE_TOSS


def test_python_no_qflag_ascky_hit_no_error() -> None:
    """ASCKY-mode no-q_flag with hit leaves no error."""
    inp = PhonMatchInput(c=ord("r"), phoneme_mode=PHONEME_ASCKY)
    res = cm_phon_match(
        inp,
        arpa_lookup=_arpa_zero,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
    )
    assert res.error_code == 0


def test_python_callbacks_are_invoked() -> None:
    """Optional callbacks fire when their side-effect arms are taken."""
    flush_calls: list[int] = []
    err_calls: list[int] = []
    state_calls: list[int] = []
    reset_calls: list[int] = []

    inp = PhonMatchInput(c=ord("]"), q_flag=ord("r"))
    cm_phon_match(
        inp,
        arpa_lookup=_arpa_two,
        language_lookup=_lang_none,
        asc_lookup=_asc_hit,
        param_check=_no_param_check,
        phon_flush=lambda: flush_calls.append(1),
        error_comm=err_calls.append,
        new_state=state_calls.append,
        reset_comm=reset_calls.append,
    )
    # ``]`` with q_flag set & ARPA(q,' ')=2: cm_phon_flush, then
    # cm_cmd_reset_comm(STATE_NORMAL).
    assert flush_calls == [1]
    assert reset_calls == [STATE_NORMAL]
    assert err_calls == []
