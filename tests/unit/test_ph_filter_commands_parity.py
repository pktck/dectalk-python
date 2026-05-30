"""C-source parity test for ``filter_commands`` against ph_drwt01.c.

The pure-Python build targets the production ``libtts_us.so`` config
(``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING``, ``HLSYN`` undefined),
whose F0 contour generator is ``ph_drwt01.c`` — *not* the HLSYN
``ph_drwt02.c`` the port originally followed. ``ph_drwt01.c`` defines
``filter_commands`` twice: the first (line ~2102) is the
``NWSNOAA`` / ``ENGLISH_UK`` variant, the second (line ~3221) is the
active one. We extract the **second** definition.

The active filter is a cascaded **two-pole** critically-damped IIR — the
dominant F0 dynamic-range driver — not the single-pole
``f0 += (f0in - f0) >> 2`` smoother of the HLSYN build. This test pins
that structure and the Python port's recurrence.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.filter_commands import filter_commands
from dectalk.ph.getcosine import F0SHFT
from dectalk.ph.math_helpers import mlsh1
from dectalk.ph.numeric_constants import FRAC_ONE

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_drwt01.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_drwt01_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_active_body() -> str:
    """Return the body of the *second* (active US English) filter_commands."""
    text = _read_drwt01_c()
    matches = list(
        re.finditer(
            r"static\s+void\s+filter_commands\s*\([^)]*\)\s*\{(.+?)^\}",
            text,
            re.DOTALL | re.MULTILINE,
        )
    )
    assert len(matches) >= 2, (
        f"expected two filter_commands definitions in ph_drwt01.c, found {len(matches)}"
    )
    return matches[-1].group(1)


def test_signature_matches_c() -> None:
    """Signature is ``static void filter_commands(PDPH_T, short f0in)``."""
    text = _read_drwt01_c()
    sig = re.search(
        r"static\s+void\s+filter_commands\s*\(\s*PDPH_T\s+\w+\s*,\s*short\s+f0in\s*\)",
        text,
    )
    assert sig is not None


def test_active_filter_is_two_pole() -> None:
    """The active body is the cascaded two-pole IIR (writes f0las1/f0las2)."""
    body = _extract_active_body()
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    stripped = re.sub(r"//.*", "", stripped)
    # Both filter memories are written (the two cascaded poles).
    assert "pDphsettar->f0las1 = f0out1" in stripped
    assert "pDphsettar->f0las2 = f0out2" in stripped
    # Second pole folds in the fast segmental gesture tarseg1 << F0SHFT.
    assert re.search(r"f0out1\s*\+\s*\(\s*pDphsettar->tarseg1\s*<<\s*F0SHFT\s*\)", stripped)
    # Output: f0 = f0out2 >> F0SHFT; f0prime = f0.
    assert re.search(r"pDph_t->f0\s*=\s*f0out2\s*>>\s*F0SHFT", stripped)
    assert re.search(r"pDph_t->f0prime\s*=\s*pDph_t->f0", stripped)


def test_active_filter_is_not_single_pole() -> None:
    """Guard against re-introducing the HLSYN single-pole smoother."""
    body = _extract_active_body()
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    stripped = re.sub(r"//.*", "", stripped)
    assert not re.search(r"pDph_t->f0\s*\+=\s*\(\s*f0in\s*-\s*pDph_t->f0\s*\)\s*>>\s*2", stripped)


# --- Python recurrence tests ------------------------------------------------


def _make_state(f0_lp_filter: int = 1536, baseline: int = 1070, tarseg1: int = 0) -> DphT:
    """A DphT wired with the hard-init filter coefficients + primed memories."""
    state = DphT()
    st = DphSettarSt()
    # Coefficients exactly as pht0draw hard-init sets them (ph_drwt01.c:2433).
    st.f0a2 = f0_lp_filter
    st.f0b = FRAC_ONE - f0_lp_filter
    st.f0a1 = st.f0a2 << F0SHFT
    # Filter memories primed to the declination baseline.
    st.f0las1 = baseline << F0SHFT
    st.f0las2 = baseline << F0SHFT
    st.tarseg1 = tarseg1
    state.pSTphsettar = st
    return state


def test_f0prime_tracks_f0() -> None:
    """The active filter sets ``f0prime = f0`` (no separate f0s recombination)."""
    state = _make_state()
    filter_commands(state, 1070)
    assert state.f0prime == state.f0


def test_primed_baseline_holds_steady() -> None:
    """Memories primed to baseline + f0in == baseline → f0 stays at baseline (±2)."""
    baseline = 1070
    state = _make_state(baseline=baseline)
    for _ in range(50):
        filter_commands(state, baseline)
    assert abs(state.f0 - baseline) <= 2


def test_converges_to_f0in_from_cold_start() -> None:
    """From zero memories, a constant f0in pulls f0 up toward f0in (dynamic range)."""
    state = DphT()
    st = DphSettarSt()
    st.f0a2 = 1536
    st.f0b = FRAC_ONE - 1536
    st.f0a1 = st.f0a2 << F0SHFT
    st.f0las1 = 0
    st.f0las2 = 0
    state.pSTphsettar = st

    f0in = 1200
    first = None
    for i in range(200):
        filter_commands(state, f0in)
        if i == 0:
            first = state.f0
    # Cold start begins far below the target, then climbs to ~f0in. Integer
    # truncation in the two cascaded poles biases the fixed point a few units
    # below f0in (it never overshoots).
    assert first is not None and first < f0in // 2
    assert f0in - 8 <= state.f0 <= f0in


def test_tarseg1_lifts_second_pole() -> None:
    """A non-zero tarseg1 fast-gesture raises the steady-state output."""
    base = _make_state(baseline=1070)
    for _ in range(60):
        filter_commands(base, 1070)
    base_f0 = base.f0

    lifted = _make_state(baseline=1070, tarseg1=50)
    for _ in range(60):
        filter_commands(lifted, 1070)
    assert lifted.f0 > base_f0


def test_matches_reference_recurrence() -> None:
    """Frame-by-frame agreement with an independent transcription of the C body."""
    state = _make_state(baseline=1070)
    st = state.pSTphsettar
    assert isinstance(st, DphSettarSt)

    # Independent reference state.
    f0a1, f0a2, f0b = st.f0a1, st.f0a2, st.f0b
    las1 = las2 = 1070 << F0SHFT
    tarseg1 = 0

    def _s16(x: int) -> int:
        x &= 0xFFFF
        return x - 0x10000 if x & 0x8000 else x

    for f0in in (1070, 1200, 1500, 900, 1070, 2000, 1070):
        filter_commands(state, f0in)
        out1 = _s16(mlsh1(f0a1, f0in) + mlsh1(f0b, las1))
        las1 = out1
        out2 = _s16(mlsh1(f0a2, out1 + (tarseg1 << F0SHFT)) + mlsh1(f0b, las2))
        las2 = out2
        ref_f0 = out2 >> F0SHFT
        assert state.f0 == ref_f0
        assert st.f0las1 == las1
        assert st.f0las2 == las2
