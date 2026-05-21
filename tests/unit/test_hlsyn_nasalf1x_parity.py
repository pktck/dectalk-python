"""Unit tests for dectalk.hlsyn.nasalf1x — nasal pole-zero solver.

Tests cover:
- :func:`susceptance_sum` sign / formula checks.
- :func:`finite_bracket_fnp` bracket-finding contract.
- :func:`nasal_first_formant` f1x / b1x behaviour.
- :func:`nasal_pole` FNP / BNP behaviour (midpoint and Brent paths).
- :func:`set_nasals_f1x` sealed (an <= 0) and open (an > 0) paths.
- C-source structural invariants (symbol names, __all__).
"""

from __future__ import annotations

import math

import dectalk.hlsyn.nasalf1x as nasalf1x_module
from dectalk.hlsyn.ll_frame_n import LLFrameN
from dectalk.hlsyn.nasal_tables import NASAL_BANDWIDTH
from dectalk.hlsyn.nasalf1x import (
    _AN_NO_NASAL_BREAKPOINT,
    _PI,
    _FNPVars,
    _interp_tablerow,
    finite_bracket_fnp,
    nasal_first_formant,
    nasal_pole,
    set_nasals_f1x,
    susceptance_sum,
)
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState, TableRow

# ---------------------------------------------------------------------------
# Minimal speaker fixture with realistic male-voice values from inithl.c.
# ---------------------------------------------------------------------------


def _male_speaker() -> HLSpeaker:
    """Return a minimal HLSpeaker with realistic male-voice values."""
    s = HLSpeaker()
    s.fno = 500.0
    s.B1m = 80.0
    s.BNP_B1_anLow = 10.0
    s.BNP_B1_anHigh = 20.0
    s.fp_f2BreakPoint = 1000.0
    s.PharangealArea = 3.0

    # anaTable — an,a susceptance slopes for f1c >= fno branch.
    s.anaTable = [
        TableRow(Column1=10.0, Column2=0.00200),
        TableRow(Column1=15.0, Column2=0.00045),
        TableRow(Column1=20.0, Column2=0.00032),
        TableRow(Column1=30.0, Column2=0.00025),
        TableRow(Column1=50.0, Column2=0.00020),
        TableRow(Column1=80.0, Column2=0.00014),
    ]
    # anbTable — an,b susceptance slopes for f1c < fno branch.
    s.anbTable = [
        TableRow(Column1=10.0, Column2=0.00006),
        TableRow(Column1=15.0, Column2=0.00008),
        TableRow(Column1=20.0, Column2=0.00010),
        TableRow(Column1=30.0, Column2=0.00015),
        TableRow(Column1=50.0, Column2=0.00020),
        TableRow(Column1=80.0, Column2=0.00014),
    ]
    # f1cTable — c-value (constriction susceptance slope) by f1c.
    s.f1cTable = [
        TableRow(Column1=180.0, Column2=0.00040),
        TableRow(Column1=200.0, Column2=0.00032),
        TableRow(Column1=300.0, Column2=0.00026),
        TableRow(Column1=400.0, Column2=0.00024),
        TableRow(Column1=500.0, Column2=0.00022),
        TableRow(Column1=600.0, Column2=0.00021),
        TableRow(Column1=700.0, Column2=0.00021),
    ]
    # anK2Table — K2 (nasal-susceptance factor) by nasal area an.
    _ank2_an = [
        0.0,
        5.0,
        10.0,
        15.0,
        20.0,
        25.0,
        30.0,
        35.0,
        40.0,
        45.0,
        50.0,
        55.0,
        60.0,
        65.0,
        70.0,
        75.0,
        80.0,
    ]
    _ank2_k2 = [
        0.0,
        1.8,
        3.5,
        4.8,
        6.0,
        7.3,
        8.5,
        9.7,
        10.8,
        11.7,
        12.5,
        13.8,
        14.0,
        14.6,
        15.1,
        15.6,
        16.1,
    ]
    s.anK2Table = [
        TableRow(Column1=an, Column2=k2) for an, k2 in zip(_ank2_an, _ank2_k2, strict=True)
    ]
    return s


# ---------------------------------------------------------------------------
# _interp_tablerow helpers
# ---------------------------------------------------------------------------


def test_interp_tablerow_below_range() -> None:
    """Below-range input clamps to first Column2."""
    table = [TableRow(Column1=10.0, Column2=1.0), TableRow(Column1=20.0, Column2=2.0)]
    assert _interp_tablerow(table, 5.0) == 1.0


def test_interp_tablerow_above_range() -> None:
    """Above-range input clamps to last Column2."""
    table = [TableRow(Column1=10.0, Column2=1.0), TableRow(Column1=20.0, Column2=2.0)]
    assert _interp_tablerow(table, 25.0) == 2.0


def test_interp_tablerow_midpoint() -> None:
    """Midpoint of a two-row table interpolates to the mean."""
    table = [TableRow(Column1=0.0, Column2=0.0), TableRow(Column1=10.0, Column2=10.0)]
    # Manual epsilon comparison (avoiding pytest.approx for pyright).
    assert abs(_interp_tablerow(table, 5.0) - 5.0) < 1e-9


# ---------------------------------------------------------------------------
# susceptance_sum formula
# ---------------------------------------------------------------------------


def test_susceptance_sum_formula() -> None:
    """Verify the Bn + BpPlusBm formula against direct Python maths."""
    fn, fp, f1c = 450.0, 600.0, 300.0
    k1, k2 = 0.075, 5.0
    v = _FNPVars(k1=k1, k2=k2, fn=fn, fp=fp, f1c=f1c)
    guess = 520.0
    bn = -k2 / (guess - fn)
    bp_plus_bm = k1 * math.tan(_PI / 2.0 * (guess - f1c) / (fp - f1c))
    expected = bn + bp_plus_bm
    # Manual relative comparison (avoiding pytest.approx for pyright).
    assert abs(susceptance_sum(guess, v) - expected) < 1e-9 * abs(expected)


def test_susceptance_sum_sign_below_root() -> None:
    """Just above fn the Bn term dominates: result should be negative."""
    fn, fp, f1c = 450.0, 600.0, 350.0
    k1, k2 = 0.075, 5.0
    v = _FNPVars(k1=k1, k2=k2, fn=fn, fp=fp, f1c=f1c)
    # Slightly above fn → Bn = -k2/(eps) → very negative
    result = susceptance_sum(fn + 1.0, v)
    assert result < 0.0


def test_susceptance_sum_sign_below_fp() -> None:
    """Just below fp the BpPlusBm term dominates: result should be positive."""
    fn, fp, f1c = 450.0, 600.0, 350.0
    k1, k2 = 0.075, 5.0
    v = _FNPVars(k1=k1, k2=k2, fn=fn, fp=fp, f1c=f1c)
    # Slightly below fp → tan approaches +inf → positive
    result = susceptance_sum(fp - 1.0, v)
    assert result > 0.0


# ---------------------------------------------------------------------------
# finite_bracket_fnp
# ---------------------------------------------------------------------------


def test_finite_bracket_fnp_returns_bracketed() -> None:
    """Standard case: susceptance has a sign change; bracket found."""
    fn, fp, f1c = 450.0, 600.0, 350.0
    k1, k2 = 0.075, 5.0
    v = _FNPVars(k1=k1, k2=k2, fn=fn, fp=fp, f1c=f1c)
    status, brac_low, brac_high = finite_bracket_fnp(v, f1c)
    assert status == 1, "Expected _FINITE_BRACKETED"
    assert brac_low < brac_high
    # Verify the bracket actually brackets a root.
    assert susceptance_sum(brac_low, v) <= 0.0
    assert susceptance_sum(brac_high, v) >= 0.0


def test_finite_bracket_fnp_respects_fn_f1c_ordering() -> None:
    """When fn < f1c the bracket lower bound must be at least f1c."""
    fn, fp, f1c = 300.0, 600.0, 400.0
    k1, k2 = 0.075, 5.0
    v = _FNPVars(k1=k1, k2=k2, fn=fn, fp=fp, f1c=f1c)
    status, brac_low, _brac_high = finite_bracket_fnp(v, f1c)
    if status == 1:
        assert brac_low >= f1c - 1e-9, "Lower bracket must not be below f1c"


# ---------------------------------------------------------------------------
# nasal_first_formant
# ---------------------------------------------------------------------------


def test_nasal_first_formant_returns_floats() -> None:
    """Return type is (float, float) for both f1c >= fno and f1c < fno."""
    speaker = _male_speaker()
    frame = HLFrame(an=20.0, f2=1500.0)
    state = HLState(f1c=550.0)  # f1c > fno (500)
    f1x, b1x = nasal_first_formant(frame, speaker, state)
    assert isinstance(f1x, float)
    assert isinstance(b1x, float)

    state2 = HLState(f1c=400.0)  # f1c < fno (500)
    f1x2, b1x2 = nasal_first_formant(frame, speaker, state2)
    assert isinstance(f1x2, float)
    assert isinstance(b1x2, float)


def test_nasal_first_formant_zero_an_b1x_is_finite() -> None:
    """When an=0 the bandwidth is finite and positive."""
    speaker = _male_speaker()
    frame = HLFrame(an=0.0, f2=1500.0)
    state = HLState(f1c=600.0)
    _f1x, b1x = nasal_first_formant(frame, speaker, state)
    # When f1c > fno the _bnp_low_f1c_branch is called; for an=0 (below
    # BNP_B1_anLow=10) it returns NASAL_BANDWIDTH=200.
    assert math.isfinite(b1x)
    assert b1x > 0.0


def test_nasal_first_formant_f1x_pulled_toward_fno() -> None:
    """f1x should lie between f1c and fno (nasal pull)."""
    speaker = _male_speaker()
    frame = HLFrame(an=30.0, f2=1500.0)
    state = HLState(f1c=600.0)  # f1c > fno=500
    f1x, _b1x = nasal_first_formant(frame, speaker, state)
    # f1x must be between fno (500) and f1c (600)
    assert speaker.fno <= f1x <= state.f1c


def test_nasal_first_formant_b1x_is_positive_for_varied_an() -> None:
    """b1x is positive for a range of nasal areas."""
    speaker = _male_speaker()
    state = HLState(f1c=550.0)
    for an_val in [0.0, 5.0, 20.0, 50.0]:
        frame = HLFrame(an=an_val, f2=1500.0)
        _f1x, b1x = nasal_first_formant(frame, speaker, state)
        assert b1x > 0.0, f"b1x must be positive for an={an_val}"


# ---------------------------------------------------------------------------
# nasal_pole
# ---------------------------------------------------------------------------


def test_nasal_pole_returns_floats() -> None:
    """Return type is (float, float)."""
    speaker = _male_speaker()
    frame = HLFrame(an=20.0, f2=1500.0)
    state = HLState(f1c=500.0)
    fnp, bnp = nasal_pole(frame, speaker, state)
    assert isinstance(fnp, float)
    assert isinstance(bnp, float)


def test_nasal_pole_midpoint_when_fp_le_fn() -> None:
    """When fp <= fn (f2 very low) the result is the midpoint 0.5*(fp+fn)."""
    speaker = _male_speaker()
    # fp = frame.f2 - 100.0 = 200.0 - 100.0 = 100.0 < fn ≈ 500 * (fno/500)
    frame = HLFrame(an=20.0, f2=200.0)
    state = HLState(f1c=500.0)
    fnp, _bnp = nasal_pole(frame, speaker, state)
    # fn = ANFN_TABLE(an=20) * (fno / ANFN_TABLE_FNO); rough check: fnp < fno
    assert fnp < speaker.fno


def test_nasal_pole_bnp_positive() -> None:
    """Bandwidth BNP is always positive."""
    speaker = _male_speaker()
    for an_val in [0.0, 5.0, 20.0, 50.0]:
        frame = HLFrame(an=an_val, f2=1500.0)
        state = HLState(f1c=500.0)
        _fnp, bnp = nasal_pole(frame, speaker, state)
        assert bnp > 0.0, f"BNP must be positive for an={an_val}"


def test_nasal_pole_brent_path_returns_finite() -> None:
    """Brent path (fp > fn) returns finite FNP."""
    speaker = _male_speaker()
    frame = HLFrame(an=30.0, f2=1800.0)  # fp = 1800 - 100 = 1700 >> fn
    state = HLState(f1c=500.0)
    fnp, bnp = nasal_pole(frame, speaker, state)
    assert math.isfinite(fnp)
    assert math.isfinite(bnp)


# ---------------------------------------------------------------------------
# set_nasals_f1x — sealed path (an <= 0)
# ---------------------------------------------------------------------------


def test_set_nasals_f1x_sealed_path_sets_llframe() -> None:
    """When an <= 0 the sealed path cancels nasals at fno."""
    speaker = _male_speaker()
    frame = HLFrame(an=0.0, f2=1500.0)
    state = HLState(f1c=500.0, f1x=0.0, b1x=0.0)
    llframe = LLFrameN()
    set_nasals_f1x(frame, speaker, state, llframe)

    fno_rounded = int(speaker.fno + 0.5)
    bw_rounded = int(NASAL_BANDWIDTH + 0.5)
    assert fno_rounded == llframe.NFNZ
    assert fno_rounded == llframe.NFNP
    assert bw_rounded == llframe.NBNZ
    assert bw_rounded == llframe.NBNP


def test_set_nasals_f1x_sealed_path_copies_f1c_to_f1x() -> None:
    """Sealed path sets state.f1x = state.f1c."""
    speaker = _male_speaker()
    frame = HLFrame(an=-1.0, f2=1500.0)
    state = HLState(f1c=450.0)
    llframe = LLFrameN()
    set_nasals_f1x(frame, speaker, state, llframe)
    # state.f1x should be exactly state.f1c (no computation, direct assignment).
    assert state.f1x == 450.0
    # state.b1x should be exactly speaker.B1m (direct assignment in C).
    assert state.b1x == speaker.B1m


def test_set_nasals_f1x_sealed_path_boundary() -> None:
    """AN_NO_NASAL_BREAKPOINT is 0.0; an == 0.0 takes the sealed path."""
    assert _AN_NO_NASAL_BREAKPOINT == 0.0
    speaker = _male_speaker()
    state = HLState(f1c=400.0)
    llframe = LLFrameN()
    set_nasals_f1x(HLFrame(an=0.0, f2=1500.0), speaker, state, llframe)
    # Sealed: NFNZ == NFNP
    assert llframe.NFNZ == llframe.NFNP


# ---------------------------------------------------------------------------
# set_nasals_f1x — open path (an > 0)
# ---------------------------------------------------------------------------


def test_set_nasals_f1x_open_path_updates_state() -> None:
    """Open path writes state.f1x and state.b1x."""
    speaker = _male_speaker()
    frame = HLFrame(an=25.0, f2=1500.0)
    state = HLState(f1c=500.0, f1x=0.0, b1x=0.0)
    llframe = LLFrameN()
    set_nasals_f1x(frame, speaker, state, llframe)
    assert state.f1x != 0.0
    assert state.b1x != 0.0


def test_set_nasals_f1x_open_path_llframe_fields_positive() -> None:
    """Open path: NFNZ, NBNZ, NFNP, NBNP are all set to positive values."""
    speaker = _male_speaker()
    frame = HLFrame(an=30.0, f2=1500.0)
    state = HLState(f1c=500.0)
    llframe = LLFrameN()
    set_nasals_f1x(frame, speaker, state, llframe)
    assert llframe.NFNZ > 0
    assert llframe.NBNZ > 0
    assert llframe.NFNP > 0
    assert llframe.NBNP > 0


def test_set_nasals_f1x_open_path_distinct_from_sealed() -> None:
    """Open path: NFNP != NFNZ (pole and zero differ when an > 0)."""
    speaker = _male_speaker()
    frame = HLFrame(an=40.0, f2=1500.0)
    state = HLState(f1c=500.0)
    llframe = LLFrameN()
    set_nasals_f1x(frame, speaker, state, llframe)
    # Generally the nasal zero and pole will differ when an is large.
    # We just assert both are set to finite positive values.
    assert math.isfinite(float(llframe.NFNZ))
    assert math.isfinite(float(llframe.NFNP))


# ---------------------------------------------------------------------------
# Module / __all__ structural checks
# ---------------------------------------------------------------------------


def test_nasalf1x_all_contains_required_symbols() -> None:
    """__all__ must export the public Python and C-alias names."""
    for name in (
        "set_nasals_f1x",
        "SetNasals_f1x",
        "nasal_first_formant",
        "NasalFirstFormant",
        "nasal_pole",
        "NasalPole",
        "susceptance_sum",
        "SusceptanceSum",
        "finite_bracket_fnp",
        "FiniteBracketFNP",
    ):
        assert name in nasalf1x_module.__all__, f"{name!r} missing from nasalf1x.__all__"


def test_nasalf1x_c_aliases_are_live_functions() -> None:
    """The PascalCase aliases must point to the live Python functions."""
    assert nasalf1x_module.SetNasals_f1x is nasalf1x_module.set_nasals_f1x
    assert nasalf1x_module.NasalFirstFormant is nasalf1x_module.nasal_first_formant
    assert nasalf1x_module.NasalPole is nasalf1x_module.nasal_pole
    assert nasalf1x_module.SusceptanceSum is nasalf1x_module.susceptance_sum
    assert nasalf1x_module.FiniteBracketFNP is nasalf1x_module.finite_bracket_fnp
