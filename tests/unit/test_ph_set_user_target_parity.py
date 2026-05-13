"""C-source parity test for ``set_user_target`` against ph_drwt02.c.

Re-parses the C body and asserts:

- The function signature matches ``static void set_user_target(PDPH_T, short *)``.
- The pressure branch (``> 1500`` → ``(6 - tmp) * 100``) is intact.
- The unconditional ``%1000`` strip is intact.
- The sung-note branch indexes ``notetab[*-1]``, sets ``vibsw = 1``,
  and computes ``delnote = (newnote - f0) >> 2``.
- The linear-glide branch scales by 10, clamps to ``[LOWEST_F0,
  HIGHEST_F0]``, sets ``vibsw = 0``, branches on
  ``f0mode == TIME_VALUE_SPECIFIED``, and computes ``delnote =
  (newnote - f0) << 2`` plus the round-away-from-zero division.
- The trailing ``delcum = 0`` / ``f0start = pDph_t->f0`` writes
  are intact.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import HIGHEST_F0, LOWEST_F0
from dectalk.ph.inton_constants import NORMAL, TIME_VALUE_SPECIFIED
from dectalk.ph.notetab import notetab
from dectalk.ph.set_user_target import set_user_target

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_drwt02.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_drwt02_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_drwt02_c()
    match = re.search(
        r"static\s+void\s+set_user_target\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "set_user_target() not found in ph_drwt02.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """Signature is ``static void set_user_target(PDPH_T, short *)``."""
    text = _read_drwt02_c()
    sig = re.search(
        r"static\s+void\s+set_user_target\s*\(\s*PDPH_T\s+\w+\s*,"
        r"\s*short\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_pressure_branch_intact() -> None:
    """``> 1500`` → ``(6 - tmp) * 100`` pressure encoding."""
    body = _extract_body()
    assert re.search(r"\*psF0command\s*>\s*1500", body)
    assert re.search(r"tmp\s*=\s*\(\s*\*psF0command\s*/\s*1000\s*\)", body)
    assert re.search(r"tmp\s*=\s*\(\s*6\s*-\s*tmp\s*\)\s*\*\s*100", body)
    assert re.search(r"pDph_t->spressure\s*=\s*tmp\s*;", body)
    assert re.search(r"pDph_t->spressure\s*=\s*0\s*;", body)


def test_modulo_strip_intact() -> None:
    """Unconditional ``*psF0command %= 1000`` strips the pressure offset."""
    body = _extract_body()
    assert re.search(r"\*psF0command\s*=\s*\*psF0command\s*%\s*1000", body)


def test_sung_note_branch() -> None:
    """Sung-note branch: ``<= 37`` → notetab, vibsw=1, delnote>>=2."""
    body = _extract_body()
    assert re.search(r"\*psF0command\s*<=\s*37", body)
    assert re.search(
        r"pDphsettar->newnote\s*=\s*notetab\s*\[\s*\*psF0command\s*-\s*1\s*\]",
        body,
    )
    assert re.search(r"pDphsettar->vibsw\s*=\s*1\s*;", body)
    assert re.search(
        r"pDphsettar->delnote\s*=\s*\(\s*\(\s*pDphsettar->newnote\s*-\s*"
        r"pDph_t->f0\s*\)\s*>>\s*2\s*\)",
        body,
    )


def test_linear_branch_clamp() -> None:
    """Linear branch: ``*= 10``, clamp to ``[LOWEST_F0, HIGHEST_F0]``."""
    body = _extract_body()
    assert re.search(r"\*psF0command\s*\*=\s*10", body)
    assert re.search(
        r"if\s*\(\s*\*psF0command\s*<\s*LOWEST_F0\s*\)",
        body,
    )
    assert re.search(
        r"if\s*\(\s*\*psF0command\s*>\s*HIGHEST_F0\s*\)",
        body,
    )
    assert re.search(r"pDphsettar->newnote\s*=\s*\*psF0command", body)
    assert re.search(r"pDphsettar->vibsw\s*=\s*0\s*;", body)


def test_time_value_specified_branch() -> None:
    """``f0mode == TIME_VALUE_SPECIFIED`` uses ``dtimf0`` as duration."""
    body = _extract_body()
    assert re.search(
        r"pDph_t->f0mode\s*==\s*TIME_VALUE_SPECIFIED",
        body,
    )
    assert re.search(r"trandur\s*=\s*pDphsettar->dtimf0", body)
    assert re.search(
        r"trandur\s*==\s*0.*?pDph_t->f0\s*=\s*pDphsettar->newnote",
        body,
        re.DOTALL,
    )


def test_default_duration_from_allodurs() -> None:
    """Default branch uses ``allodurs[npg+1]`` as transition duration."""
    body = _extract_body()
    assert re.search(
        r"trandur\s*=\s*pDph_t->allodurs\s*\[\s*pDphsettar->npg\s*\+\s*1\s*\]",
        body,
    )


def test_delnote_round_and_divide() -> None:
    """delnote pre-division rounding and final divide-by-trandur."""
    body = _extract_body()
    assert re.search(
        r"pDphsettar->delnote\s*=\s*\(\s*pDphsettar->newnote\s*-\s*"
        r"pDph_t->f0\s*\)\s*<<\s*2",
        body,
    )
    assert re.search(
        r"pDphsettar->delnote\s*>\s*0.*?"
        r"pDphsettar->delnote\s*\+=\s*\(\s*trandur\s*-\s*1\s*\)",
        body,
        re.DOTALL,
    )
    assert re.search(
        r"pDphsettar->delnote\s*<\s*0.*?"
        r"pDphsettar->delnote\s*-=\s*\(\s*trandur\s*-\s*1\s*\)",
        body,
        re.DOTALL,
    )
    assert re.search(
        r"trandur\s*!=\s*0.*?pDphsettar->delnote\s*/=\s*trandur",
        body,
        re.DOTALL,
    )


def test_trailing_writes_intact() -> None:
    """``delcum = 0`` and ``f0start = pDph_t->f0`` close the function."""
    body = _extract_body()
    assert re.search(r"pDphsettar->delcum\s*=\s*0\s*;", body)
    assert re.search(r"pDphsettar->f0start\s*=\s*pDph_t->f0\s*;", body)


# -- Python-side behavioural tests -----------------------------------------


def _make_state(**dph_kwargs: object) -> tuple[DphT, DphSettarSt]:
    state = DphT(**dph_kwargs)  # type: ignore[arg-type]  # DphT has many field types
    settar = DphSettarSt()
    state.pSTphsettar = settar
    return state, settar


def test_python_sung_note_index_one_picks_c2() -> None:
    """``ps_f0command[0] == 1`` → notetab[0] = 640 Hzx10 (C2)."""
    state, settar = _make_state(f0=1000)
    cmd = [1]
    set_user_target(state, cmd)
    assert settar.newnote == notetab[0]  # 640
    assert settar.vibsw == 1
    # delnote = (640 - 1000) >> 2 = -360 >> 2 = -90 (Python arithmetic shift).
    assert settar.delnote == (640 - 1000) >> 2
    # delcum / f0start side-effects.
    assert settar.delcum == 0
    assert settar.f0start == 1000


def test_python_sung_note_index_37_picks_c5() -> None:
    """``ps_f0command[0] == 37`` → notetab[36] = 5120 Hzx10 (C5)."""
    state, settar = _make_state(f0=2560)
    cmd = [37]
    set_user_target(state, cmd)
    assert settar.newnote == notetab[36]
    assert settar.vibsw == 1


def test_python_linear_branch_clamps_low() -> None:
    """Value 38 → 38*10 = 380 → clamped up to LOWEST_F0 = 500."""
    state, settar = _make_state(f0=1000, f0mode=NORMAL, allodurs=[0, 0, 0])
    settar.npg = 0
    settar.dtimf0 = 0
    cmd = [38]
    set_user_target(state, cmd)
    assert cmd[0] == LOWEST_F0
    assert settar.newnote == LOWEST_F0
    assert settar.vibsw == 0


def test_python_linear_branch_clamps_high() -> None:
    """Value 700 → 7000 → clamped down to HIGHEST_F0 = 5121."""
    state, settar = _make_state(f0=1000, f0mode=NORMAL, allodurs=[0, 0, 0])
    settar.npg = 0
    cmd = [700]
    set_user_target(state, cmd)
    assert cmd[0] == HIGHEST_F0
    assert settar.newnote == HIGHEST_F0


def test_python_linear_branch_time_value_zero_trandur_snaps_f0() -> None:
    """TIME_VALUE_SPECIFIED with ``dtimf0 == 0`` snaps ``f0`` to newnote."""
    state, settar = _make_state(f0=1000, f0mode=TIME_VALUE_SPECIFIED)
    settar.dtimf0 = 0
    cmd = [200]  # 2000 Hzx10, in range
    set_user_target(state, cmd)
    assert settar.newnote == 2000
    assert state.f0 == 2000
    # f0start captures the *post-snap* f0.
    assert settar.f0start == 2000


def test_python_linear_branch_default_uses_allodurs() -> None:
    """Default branch reads ``allodurs[npg+1]`` for the transition dur."""
    state, settar = _make_state(f0=1000, f0mode=NORMAL, allodurs=[0, 0, 40, 0])
    settar.npg = 1
    cmd = [200]
    set_user_target(state, cmd)
    # newnote = 2000, delta = (2000 - 1000) << 2 = 4000, trandur = 40
    # delnote > 0 → add (40-1) = 4039, / 40 = 100 (C truncate-toward-zero).
    expected = ((2000 - 1000) << 2) + (40 - 1)
    assert settar.delnote == expected // 40


def test_python_pressure_branch_sets_spressure() -> None:
    """Command 2200 → pressure (6-2)*100 = 400; residual = 200."""
    state, settar = _make_state(f0=1000, f0mode=TIME_VALUE_SPECIFIED)
    settar.dtimf0 = 0
    cmd = [2200]
    set_user_target(state, cmd)
    assert state.spressure == 400
    # 2200 % 1000 = 200 → linear branch → 200*10 = 2000.
    assert settar.newnote == 2000


def test_python_pressure_branch_stops_at_1500() -> None:
    """Command 1500 is NOT > 1500, so no pressure write fires."""
    state, settar = _make_state(f0=1000, f0mode=TIME_VALUE_SPECIFIED, spressure=999)
    settar.dtimf0 = 0
    cmd = [1500]
    set_user_target(state, cmd)
    # spressure untouched.
    assert state.spressure == 999
    # 1500 % 1000 = 500 → linear branch → 5000 (in range).
    assert settar.newnote == 5000


def test_python_pressure_5000_drops_to_100() -> None:
    """Command 5300 → pressure (6-5)*100 = 100; residual = 300."""
    state, settar = _make_state(f0=1000, f0mode=TIME_VALUE_SPECIFIED)
    settar.dtimf0 = 0
    cmd = [5300]
    set_user_target(state, cmd)
    assert state.spressure == 100
    assert settar.newnote == 3000  # 300 * 10


def test_python_negative_delnote_rounds_away_from_zero() -> None:
    """Descending glide: ``(newnote - f0) << 2`` is negative, rounds down."""
    state, settar = _make_state(f0=2000, f0mode=NORMAL, allodurs=[0, 0, 30, 0])
    settar.npg = 1
    cmd = [100]  # newnote = 1000
    set_user_target(state, cmd)
    # delta = (1000 - 2000) << 2 = -4000, trandur = 30
    # delnote < 0 → -= (30 - 1) → -4029, / 30 = -134 (C trunc).
    raw = ((1000 - 2000) << 2) - (30 - 1)
    expected = -(abs(raw) // 30)  # C-style truncate toward zero
    assert settar.delnote == expected


def test_python_no_op_when_pdphsettar_missing() -> None:
    """Missing target struct → defensive early return."""
    state = DphT()
    state.pSTphsettar = None
    cmd = [200]
    set_user_target(state, cmd)
    # ps_f0command not stripped of pressure offset (early return).
    assert cmd == [200]


def test_python_zero_command_picks_index_minus_one() -> None:
    """``ps_f0command[0] == 0`` reads ``notetab[-1]`` (= last note in Python)."""
    state, settar = _make_state(f0=0)
    cmd = [0]
    set_user_target(state, cmd)
    # Python negative index wraps to last element.
    assert settar.newnote == notetab[-1]
    assert settar.vibsw == 1
