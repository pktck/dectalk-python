"""C-source parity test for ``cm_phon_check`` against cm_phon.c.

Re-parses the body of ``cm_phon_check`` (lines 535-677 in
``src/dapi/src/cmd/cm_phon.c``) using brace-depth tracking and
asserts the load-bearing structural invariants:

- The CR / LF / text_flush early-out is preserved.
- The ``international_phon_lang<0 && international_flag>=0`` arm is
  preserved (with the ``c == '_'`` capture case).
- The uncertain-phoneme replay guard ``hold_count > 1`` is preserved.
- The ``q_flag`` set / unset dispatch is preserved.

Plus behavioural tests of the Python architectural shim.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_phon_check import (
    PhonCheckInput,
    PhonCheckResult,
    cm_phon_check,
)
from dectalk.cmd.cmd_states import PHONEME_ASCKY

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_phon.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_cm_phon_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``cm_phon_check`` body via brace tracking."""
    text = _read_cm_phon_c()
    decl = re.search(r"\bint\s+cm_phon_check\s*\(", text)
    assert decl is not None, "cm_phon_check declaration not found in cm_phon.c"
    brace_start = text.index("{", decl.end())
    depth = 1
    i = brace_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, "Unbalanced braces extracting cm_phon_check body"
    return text[brace_start + 1 : i - 1]


# -- Structural assertions on the C body ----------------------------


def test_c_body_has_cr_lf_text_flush_early_out() -> None:
    """The body still short-circuits on CR / LF / text_flush."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*c\s*==\s*CR\s*\|\|\s*c\s*==\s*LF\s*\|\|"
        r"\s*pKsd_t\s*->\s*text_flush\s*\)",
        body,
    ), "expected CR/LF/text_flush short-circuit"


def test_c_body_has_international_underscore_capture() -> None:
    """The body still captures ``_`` into international_phon_lang."""
    body = _extract_body()
    # Two-step: the outer ``if (international_phon_lang<0 && ...)`` is present
    # AND the ``c=='_'`` body sets international_phon_lang from international_flag.
    assert re.search(
        r"international_phon_lang\s*<\s*0\s*&&\s*pCmd_t\s*->\s*international_flag\s*>=\s*0",
        body,
    )
    assert re.search(r"c\s*==\s*'_'", body), "expected ``c == '_'`` capture in cm_phon_check"


def test_c_body_has_hold_count_uncertain_guard() -> None:
    """``hold_count > 1 && check_uncertain_phones(q_flag, c)`` is preserved."""
    body = _extract_body()
    assert re.search(
        r"pCmd_t\s*->\s*hold_count\s*>\s*1\s*&&\s*\n*\s*check_uncertain_phones\s*\(",
        body,
    ), "expected ``hold_count > 1 && check_uncertain_phones(...)`` guard"


def test_c_body_dispatches_on_q_flag() -> None:
    """The body still branches on ``pCmd_t->q_flag``."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*pCmd_t\s*->\s*q_flag\s*\)", body), (
        "expected ``if (pCmd_t->q_flag)`` dispatch"
    )


def test_c_body_q_flag_has_close_bracket_arm() -> None:
    """The ``q_flag`` set branch handles ``]`` (calls cm_phon_lookup_arpa with space)."""
    body = _extract_body()
    # case ']': ... cm_phon_lookup_arpa(phTTS, pCmd_t->q_flag,' ')
    assert re.search(r"case\s+']'", body)
    assert re.search(
        r"cm_phon_lookup_arpa\s*\(\s*phTTS\s*,\s*pCmd_t\s*->\s*q_flag\s*,\s*' '\s*\)",
        body,
    ), "expected ``cm_phon_lookup_arpa(phTTS, q_flag, ' ')`` inside the ']' arm"


def test_c_body_handles_phoneme_ascky() -> None:
    """The no-q_flag default arm tests ``phoneme_mode & PHONEME_ASCKY``."""
    body = _extract_body()
    assert re.search(
        r"pKsd_t\s*->\s*phoneme_mode\s*&\s*PHONEME_ASCKY",
        body,
    ), "expected ``phoneme_mode & PHONEME_ASCKY`` test"


def test_c_body_returns_one_at_end() -> None:
    """The C body's final statement is ``return 1;``."""
    body = _extract_body()
    # Allow trailing whitespace / newlines before the close brace.
    assert re.search(r"return\s+1\s*;\s*$", body), "expected ``return 1;`` at end of body"


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


def test_python_cr_short_circuits() -> None:
    """CR returns rc=1 with state untouched."""
    inp = PhonCheckInput(c=ord("\r"), q_flag=42)
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert isinstance(res, PhonCheckResult)
    assert res.rc == 1
    assert res.q_flag == 42


def test_python_lf_short_circuits() -> None:
    """LF returns rc=1 with state untouched."""
    inp = PhonCheckInput(c=ord("\n"), q_flag=42)
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == 42


def test_python_text_flush_short_circuits() -> None:
    """A truthy text_flush returns rc=1 with state untouched."""
    inp = PhonCheckInput(c=ord("a"), text_flush=1, q_flag=42)
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == 42


def test_python_underscore_commits_intl_lang() -> None:
    """``_`` while a language is pending commits it as international_phon_lang."""
    inp = PhonCheckInput(
        c=ord("_"),
        q_flag=ord("u"),
        international_flag=3,
        international_temp=ord("s"),
    )
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == 0
    assert res.international_temp == 0
    assert res.international_flag == -1
    assert res.international_phon_lang == 3


def test_python_qflag_close_bracket_with_zero_arpa_returns_zero() -> None:
    """``]`` with q_flag pending and ARPA(q,' ')=0 returns rc=0."""
    inp = PhonCheckInput(c=ord("]"), q_flag=ord("r"))
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert res.rc == 0


def test_python_qflag_close_bracket_with_arpa_match_returns_one() -> None:
    """``]`` with q_flag pending and ARPA(q,' ')=2 returns rc=1, clears q_flag."""
    inp = PhonCheckInput(c=ord("]"), q_flag=ord("r"))
    res = cm_phon_check(inp, arpa_lookup=_arpa_two, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == 0


def test_python_qflag_close_bracket_with_space_skips_lookup() -> None:
    """``]`` with q_flag==' '`` does not consult the ARPA table."""
    calls: list[tuple[int, int]] = []

    def arpa(p1: int, p2: int) -> tuple[int, int]:
        calls.append((p1, p2))
        return 0, -1

    inp = PhonCheckInput(c=ord("]"), q_flag=ord(" "))
    res = cm_phon_check(inp, arpa_lookup=arpa, language_lookup=_lang_none)
    assert res.rc == 1
    assert calls == [], "expected no ARPA call when q_flag==' '"


def test_python_qflag_colon_requires_arpa_2() -> None:
    """``:`` with q_flag pending: ARPA(q,' ') != 2 returns rc=0."""
    inp = PhonCheckInput(c=ord(":"), q_flag=ord("r"))
    res = cm_phon_check(inp, arpa_lookup=_arpa_one, language_lookup=_lang_none)
    assert res.rc == 0


def test_python_qflag_default_no_qflag_sets_qflag() -> None:
    """ARPA-mode default arm (no q_flag) sets q_flag = c."""
    inp = PhonCheckInput(c=ord("r"), phoneme_mode=0, q_flag=0)
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == ord("r")


def test_python_qflag_default_ascky_mode_does_not_set_qflag() -> None:
    """ASCKY-mode default arm leaves q_flag at 0."""
    inp = PhonCheckInput(c=ord("r"), phoneme_mode=PHONEME_ASCKY, q_flag=0)
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == 0


def test_python_qflag_default_zero_arpa_match_returns_zero() -> None:
    """ARPA(q,c)=0 with no language match returns rc=0."""
    inp = PhonCheckInput(c=ord("b"), q_flag=ord("z"))
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert res.rc == 0


def test_python_qflag_default_arpa_match_one_sets_qflag() -> None:
    """ARPA(q,c)=1 sets q_flag = c."""
    inp = PhonCheckInput(c=ord("y"), q_flag=ord("r"))
    res = cm_phon_check(inp, arpa_lookup=_arpa_one, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == ord("y")


def test_python_qflag_default_arpa_match_two_clears_qflag() -> None:
    """ARPA(q,c)=2 clears q_flag."""
    inp = PhonCheckInput(c=ord("y"), q_flag=ord("r"))
    res = cm_phon_check(inp, arpa_lookup=_arpa_two, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == 0


def test_python_qflag_default_lang_match_captures() -> None:
    """A language-prefix match captures into international_flag/temp."""
    inp = PhonCheckInput(
        c=ord("s"),
        q_flag=ord("u"),
        international_flag=-1,
        international_phon_lang=-1,
    )
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_match_2)
    assert res.rc == 1
    assert res.international_flag == 2
    assert res.international_temp == ord("s")


def test_python_uncertain_phone_guard_returns_one() -> None:
    """hold_count>1 and uncertain phone returns rc=1 unchanged."""
    inp = PhonCheckInput(
        c=ord("x"),
        q_flag=ord("r"),  # (r,x) is in uncertain_phones
        hold_count=2,
    )
    res = cm_phon_check(inp, arpa_lookup=_arpa_zero, language_lookup=_lang_none)
    assert res.rc == 1
    assert res.q_flag == ord("r")
