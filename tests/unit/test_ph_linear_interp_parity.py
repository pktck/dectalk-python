"""C-source parity test for ``linear_interp`` against ph_drwt02.c.

Re-parses the C body and asserts:

- The function signature matches ``static void linear_interp(PDPH_T)``.
- ``delcum`` accumulates ``delnote`` and ``f0 = f0start + (delcum >> 2)``.
- Positive ``delnote``: clamps ``f0`` not to overshoot ``newnote`` (above).
- Negative ``delnote``: clamps ``f0`` not to overshoot ``newnote`` (below).
- On clamp: writes ``newnote`` to ``f0start`` and zeros ``delcum`` / ``delnote``.
- ``f0prime = f0`` is written unconditionally.
- Singing branch: ``vibsw == 1`` adds 165 to ``timecosvib`` (wrap at TWOPI)
  and adds ``getcosine[timecosvib>>6] >> 3`` to ``f0prime``.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.cosine_tilt_tables import getcosine_tab
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import TWOPI
from dectalk.ph.linear_interp import linear_interp

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
        r"static\s+void\s+linear_interp\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "linear_interp() not found in ph_drwt02.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """Signature is ``static void linear_interp(PDPH_T)``."""
    text = _read_drwt02_c()
    sig = re.search(
        r"static\s+void\s+linear_interp\s*\(\s*PDPH_T\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_accumulator_and_f0_formula() -> None:
    """``delcum += delnote`` then ``f0 = f0start + (delcum >> 2)``."""
    body = _extract_body()
    assert re.search(r"pDphsettar->delcum\s*\+=\s*pDphsettar->delnote", body)
    assert re.search(
        r"pDph_t->f0\s*=\s*pDphsettar->f0start\s*\+\s*\(\s*pDphsettar->delcum\s*>>\s*2\s*\)",
        body,
    )


def test_positive_delnote_clamps_above() -> None:
    """If ``delnote >= 0`` and ``f0 > newnote``, clamp and reset accumulators."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*pDphsettar->delnote\s*>=\s*0\s*\)", body)
    assert re.search(r"if\s*\(\s*pDph_t->f0\s*>\s*pDphsettar->newnote\s*\)", body)


def test_negative_delnote_clamps_below() -> None:
    """If ``delnote < 0`` and ``f0 < newnote``, clamp and reset accumulators."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*pDph_t->f0\s*<\s*pDphsettar->newnote\s*\)", body)


def test_clamp_resets_state() -> None:
    """The clamp branches write newnote and zero ``delcum`` / ``delnote``."""
    body = _extract_body()
    # The pattern occurs twice (positive and negative branch); check both reset writes.
    assert len(re.findall(r"pDph_t->f0\s*=\s*pDphsettar->newnote\s*;", body)) >= 2
    assert len(re.findall(r"pDphsettar->f0start\s*=\s*pDphsettar->newnote\s*;", body)) >= 2
    assert len(re.findall(r"pDphsettar->delcum\s*=\s*0\s*;", body)) >= 2
    assert len(re.findall(r"pDphsettar->delnote\s*=\s*0\s*;", body)) >= 2


def test_f0prime_written_unconditionally() -> None:
    """``pDph_t->f0prime = pDph_t->f0;`` lives outside the clamp branches."""
    body = _extract_body()
    assert re.search(r"pDph_t->f0prime\s*=\s*pDph_t->f0\s*;", body)


def test_singing_branch_adds_vibrato() -> None:
    """``vibsw == 1`` increments ``timecosvib`` by 165 and adds vibrato."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*pDphsettar->vibsw\s*==\s*1\s*\)", body)
    assert re.search(r"pDphsettar->timecosvib\s*\+=\s*165", body)
    assert re.search(r"if\s*\(\s*pDphsettar->timecosvib\s*>\s*TWOPI\s*\)", body)
    assert re.search(r"pDphsettar->timecosvib\s*-=\s*TWOPI", body)
    assert re.search(
        r"pDph_t->f0prime\s*\+=\s*getcosine\s*\[\s*pDphsettar->timecosvib\s*>>\s*6\s*\]\s*>>\s*3",
        body,
    )


def test_python_no_op_when_pdphsettar_missing() -> None:
    """Missing target struct -> defensive early return."""
    state = DphT()
    state.pSTphsettar = None
    linear_interp(state)


def test_python_zero_state_stays_zero() -> None:
    """All-zero state: f0/f0prime stay 0, no vibrato applied."""
    state = DphT()
    settar = DphSettarSt()
    state.pSTphsettar = settar
    linear_interp(state)
    assert settar.delcum == 0
    assert state.f0 == 0
    assert state.f0prime == 0
    # vibsw is 0, so timecosvib must not advance.
    assert settar.timecosvib == 0


def test_python_positive_delnote_accumulates_toward_newnote() -> None:
    """Positive delnote: delcum grows by delnote each call until clamp."""
    state = DphT()
    settar = DphSettarSt(f0start=1000, newnote=1100, delnote=40, delcum=0)
    state.pSTphsettar = settar
    linear_interp(state)
    # First call: delcum = 40, f0 = 1000 + (40 >> 2) = 1000 + 10 = 1010.
    assert settar.delcum == 40
    assert state.f0 == 1010
    assert state.f0prime == 1010


def test_python_positive_delnote_clamps_at_newnote() -> None:
    """If f0 would overshoot newnote, clamp and zero accumulators."""
    state = DphT()
    # Choose delcum large enough that (delcum >> 2) pushes f0 past newnote.
    settar = DphSettarSt(f0start=1000, newnote=1050, delnote=400, delcum=200)
    state.pSTphsettar = settar
    linear_interp(state)
    # delcum becomes 600, f0 = 1000 + (600>>2) = 1000 + 150 = 1150 > newnote=1050.
    # Clamp resets all four fields.
    assert state.f0 == 1050
    assert settar.f0start == 1050
    assert settar.delcum == 0
    assert settar.delnote == 0
    assert state.f0prime == 1050


def test_python_negative_delnote_accumulates_toward_newnote() -> None:
    """Negative delnote: delcum decreases each call."""
    state = DphT()
    settar = DphSettarSt(f0start=1000, newnote=900, delnote=-40, delcum=0)
    state.pSTphsettar = settar
    linear_interp(state)
    # delcum = -40, f0 = 1000 + (-40 >> 2) = 1000 + (-10) = 990.
    assert settar.delcum == -40
    assert state.f0 == 990
    assert state.f0prime == 990


def test_python_negative_delnote_clamps_at_newnote() -> None:
    """If f0 would undershoot newnote, clamp and zero accumulators."""
    state = DphT()
    settar = DphSettarSt(f0start=1000, newnote=950, delnote=-400, delcum=-200)
    state.pSTphsettar = settar
    linear_interp(state)
    # delcum = -600, f0 = 1000 + (-600 >> 2) = 1000 - 150 = 850 < newnote=950.
    assert state.f0 == 950
    assert settar.f0start == 950
    assert settar.delcum == 0
    assert settar.delnote == 0
    assert state.f0prime == 950


def test_python_positive_delnote_no_clamp_when_below_newnote() -> None:
    """Positive delnote but f0 still below newnote: no clamp, no reset."""
    state = DphT()
    settar = DphSettarSt(f0start=1000, newnote=2000, delnote=40, delcum=0)
    state.pSTphsettar = settar
    linear_interp(state)
    # f0 = 1010, below newnote=2000, so no clamp.
    assert settar.delcum == 40  # not reset
    assert settar.delnote == 40  # not reset
    assert settar.f0start == 1000  # not overwritten
    assert state.f0 == 1010


def test_python_singing_advances_timecosvib_by_165() -> None:
    """vibsw=1 advances timecosvib by 165 per call."""
    state = DphT()
    settar = DphSettarSt(f0start=1000, newnote=2000, delnote=0, delcum=0, vibsw=1)
    state.pSTphsettar = settar
    linear_interp(state)
    assert settar.timecosvib == 165
    # f0prime gets vibrato added on top of f0=1000.
    # getcosine_tab[165>>6] = getcosine_tab[2] = 161; vibrato = 161 >> 3 = 20.
    expected_vibrato = getcosine_tab[165 >> 6] >> 3
    assert state.f0prime == 1000 + expected_vibrato


def test_python_singing_wraps_timecosvib_at_twopi() -> None:
    """timecosvib wraps when it would exceed TWOPI."""
    state = DphT()
    settar = DphSettarSt(
        f0start=1000, newnote=2000, delnote=0, delcum=0, vibsw=1, timecosvib=TWOPI - 100
    )
    state.pSTphsettar = settar
    linear_interp(state)
    # Before wrap: timecosvib = TWOPI - 100 + 165 = TWOPI + 65 > TWOPI -> wrap.
    # After wrap: timecosvib = 65.
    assert settar.timecosvib == 65


def test_python_singing_no_wrap_just_below_twopi() -> None:
    """timecosvib just below TWOPI: no wrap, LUT lookup at index 63 still valid."""
    state = DphT()
    # After += 165 we land at TWOPI - 1 = 4095. The C source uses '>' (strict),
    # so 4095 > TWOPI is false and no wrap occurs. Index = 4095 >> 6 = 63
    # (the last valid entry of the 64-entry LUT).
    settar = DphSettarSt(
        f0start=1000, newnote=2000, delnote=0, delcum=0, vibsw=1, timecosvib=TWOPI - 166
    )
    state.pSTphsettar = settar
    linear_interp(state)
    assert settar.timecosvib == TWOPI - 1


def test_python_no_vibrato_when_vibsw_zero() -> None:
    """vibsw=0: f0prime equals f0 exactly, no LUT lookup."""
    state = DphT()
    settar = DphSettarSt(f0start=1000, newnote=2000, delnote=40, delcum=0, vibsw=0, timecosvib=500)
    state.pSTphsettar = settar
    linear_interp(state)
    # No vibrato branch, so timecosvib must not advance.
    assert settar.timecosvib == 500
    assert state.f0prime == state.f0


def test_python_vibrato_uses_full_lut_range() -> None:
    """vibrato value = getcosine_tab[timecosvib >> 6] >> 3."""
    # Choose timecosvib so that (timecosvib + 165) >> 6 lands in the negative
    # portion of the LUT (index 32 is the minimum, -164).
    state = DphT()
    # We want timecosvib_after_increment >> 6 == 32.
    # So timecosvib_after_increment in [32*64, 33*64) = [2048, 2112).
    # Pick before-increment = 2048 - 165 = 1883.
    settar = DphSettarSt(f0start=0, newnote=10000, delnote=0, delcum=0, vibsw=1, timecosvib=1883)
    state.pSTphsettar = settar
    linear_interp(state)
    assert settar.timecosvib == 2048
    expected_vibrato = getcosine_tab[2048 >> 6] >> 3
    assert expected_vibrato == (-164 >> 3)
    assert state.f0prime == 0 + expected_vibrato
