"""Tests for :mod:`dectalk.ph.parstochip_to_frames`."""

from __future__ import annotations

from dectalk.hlsyn.llsyn import LLFrame
from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_ABLADE,
    OUT_AG,
    OUT_AL,
    OUT_AN,
    OUT_AP,
    OUT_ATB,
    OUT_AV,
    OUT_B1,
    OUT_B2,
    OUT_B3,
    OUT_CNK,
    OUT_DC,
    OUT_DU,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_PH,
    OUT_PH2,
    OUT_PLACE,
    OUT_PS,
    OUT_T0,
    OUT_TLT,
    OUT_UE,
)
from dectalk.ph.parameter_tables import lineartilt
from dectalk.ph.parstochip_to_frames import (
    _build_hl_frame_from_parstochip,
    parstochip_to_llframe,
    parstochip_to_llframe_delayed,
    parstochip_to_llframe_via_hl,
    send_pars_delaypars,
)
from dectalk.ph.spdef_chip import SpdChip
from dectalk.vtm.spd_chip import default_us_paul_spd


def _empty_parstochip() -> list[int]:
    """64-cell parstochip buffer (the size phdraw uses)."""
    return [0] * 64


def test_default_input_produces_safe_frame() -> None:
    """All-zero parstochip should yield a silent frame with a sane F0 fallback."""
    frame = parstochip_to_llframe(_empty_parstochip())
    assert isinstance(frame, LLFrame)
    assert frame.AV == 0
    # F0 must be non-zero so the synthesizer source has a period to lock to;
    # OUT_T0=0 means pht0draw hasn't run yet.
    assert frame.F0 == 1220  # 122 Hz fallback (deciHz).


def test_pop_through_basic_cells() -> None:
    """Populated parstochip cells flow to the matching LLFrame fields."""
    p = _empty_parstochip()
    p[OUT_T0] = 1500
    p[OUT_AV] = 60
    p[OUT_AP] = 25
    p[OUT_F1] = 500
    p[OUT_B1] = 80
    p[OUT_F2] = 1500
    p[OUT_F3] = 2500
    p[OUT_FZ] = 280
    p[OUT_TLT] = 8
    p[OUT_A2] = 40
    frame = parstochip_to_llframe(p)
    assert frame.F0 == 1500
    assert frame.AV == 60
    assert frame.Ah == 25
    assert frame.F1 == 500
    assert frame.B1 == 80
    assert frame.F2 == 1500
    assert frame.F3 == 2500
    assert frame.FNZ == 280
    # OUT_TLT goes through the lineartilt[] remap (ph_romi.c lines 96-103):
    # lineartilt[8] == 23.
    assert frame.TL == 23
    assert frame.A2f == 40


def test_amplitude_clamped_to_80db() -> None:
    """Out-of-range parstochip values are clamped instead of overflowing."""
    p = _empty_parstochip()
    p[OUT_AV] = 1000
    p[OUT_AP] = 500
    p[OUT_A2] = -50
    frame = parstochip_to_llframe(p)
    assert frame.AV == 80
    assert frame.Ah == 80
    assert frame.A2f == 0


def test_formant_clamped_to_safe_synthesizer_range() -> None:
    """Formant frequencies clamp so the synth filter coefficients stay stable."""
    p = _empty_parstochip()
    p[OUT_F1] = 100000
    p[OUT_F2] = -42
    frame = parstochip_to_llframe(p)
    assert 100 <= frame.F1 <= 1300
    assert 500 <= frame.F2 <= 3000


def test_higher_formants_get_synth_neutral_defaults() -> None:
    """F4..F6 and B4..B6 fall back to LLFrame's neutral resting values.

    Without a :class:`~dectalk.vtm.spd_chip.SpdChip` the adapter emits
    the generic Klatt-1980 reference values; see the §3-themed tests
    below for the SpdChip-threaded behaviour.
    """
    frame = parstochip_to_llframe(_empty_parstochip())
    assert frame.F4 == 3500
    assert frame.B4 == 200
    assert frame.F5 == 4500
    assert frame.F6 == 5500


# -- Delayed adapter (ph_claus.c send_pars one-frame delay) -----------------


def test_delayed_first_call_falls_back_to_current() -> None:
    """With ``previous_parstochip=None`` the first emit mirrors the current frame.

    The C source's first call to ``send_pars()`` seeds ``delaypars[]`` with
    AV=TLT=T0=0 and writes the current frame's F1/B1/etc into delaypars
    *without* spcwrite'ing yet; the Python port collapses that to emit one
    frame populated from the current parstochip when the previous is None.
    """
    p = _empty_parstochip()
    p[OUT_F1] = 500
    p[OUT_AV] = 60
    frame = parstochip_to_llframe_delayed(p, None)
    assert frame.F1 == 500
    assert frame.AV == 60


def test_delayed_uses_previous_for_formant_slots() -> None:
    """Second-frame emit takes F1/B1/etc from previous, AV/TL/T0 from current."""
    prev = _empty_parstochip()
    prev[OUT_F1] = 500
    prev[OUT_F2] = 1500
    prev[OUT_AV] = 99  # should NOT appear in the output frame.
    cur = _empty_parstochip()
    cur[OUT_F1] = 700  # should NOT appear (delayed slot).
    cur[OUT_F2] = 1800  # should NOT appear.
    cur[OUT_AV] = 60  # should appear (real-time slot).
    cur[OUT_T0] = 1500  # should appear (real-time slot).
    frame = parstochip_to_llframe_delayed(cur, prev)
    # Delayed slots come from prev:
    assert frame.F1 == 500
    assert frame.F2 == 1500
    # Real-time slots come from cur:
    assert frame.AV == 60
    assert frame.F0 == 1500


def test_delayed_applies_lineartilt_to_current_tlt() -> None:
    """``parstochip[OUT_TLT]`` is run through ``lineartilt`` for the LLFrame ``TL``."""
    cur = _empty_parstochip()
    cur[OUT_TLT] = 5
    frame = parstochip_to_llframe_delayed(cur, _empty_parstochip())
    # lineartilt[5] == 17 (ph_romi.c lines 96-103).
    assert frame.TL == 17


# -- send_pars_delaypars: the vtm1-path packet builder (issue #275) ---------
#
# Mirrors ph_claus.c::send_pars lines 694-846 (active build): the emitted
# SPC voice packet takes OUT_AV / OUT_T0 from the current parstochip,
# OUT_TLT = lineartilt[current OUT_TLT], and every other slot from the
# previous frame's parstochip (the one-frame formant-side delay).

# Every packet slot send_pars fills from the *previous* frame in the
# active (non-NEW_VTM) build: ph_claus.c lines 786-846.
_DELAYED_SLOTS = (
    OUT_AP,
    OUT_F1,
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_B1,
    OUT_B2,
    OUT_B3,
    OUT_PH,
    OUT_DU,
    OUT_PH2,
)


def _numbered_parstochip(base: int) -> list[int]:
    """Parstochip whose cell ``i`` holds ``base + i`` (all cells distinct)."""
    return [base + i for i in range(64)]


def test_send_pars_delaypars_delayed_slots_from_previous() -> None:
    """AP/F1/A2-A6/AB/F2/F3/FZ/B1-B3 and PH/DU/PH2 come from the previous frame."""
    prev = _numbered_parstochip(1000)
    cur = _numbered_parstochip(2000)
    cur[OUT_TLT] = 5  # keep the LUT index in range.
    packet = send_pars_delaypars(cur, prev)
    for slot in _DELAYED_SLOTS:
        assert packet[slot] == prev[slot], f"slot {slot} not delayed"


def test_send_pars_delaypars_av_t0_from_current() -> None:
    """OUT_AV and OUT_T0 are the current frame's values (ph_claus.c 724/744)."""
    prev = _empty_parstochip()
    prev[OUT_AV] = 99  # must NOT appear.
    prev[OUT_T0] = 777  # must NOT appear.
    cur = _empty_parstochip()
    cur[OUT_AV] = 60
    cur[OUT_T0] = 328
    packet = send_pars_delaypars(cur, prev)
    assert packet[OUT_AV] == 60
    assert packet[OUT_T0] == 328


def test_send_pars_delaypars_applies_lineartilt_to_current_tlt() -> None:
    """OUT_TLT is the current frame's raw tilt through lineartilt[] (line 735)."""
    prev = _empty_parstochip()
    prev[OUT_TLT] = 31  # must NOT appear (not even LUT-mapped).
    cur = _empty_parstochip()
    cur[OUT_TLT] = 8
    packet = send_pars_delaypars(cur, prev)
    # lineartilt[8] == 23 (ph_romi.c lines 96-103).
    assert packet[OUT_TLT] == 23


def test_send_pars_delaypars_tilt_index_clamped() -> None:
    """Out-of-domain raw tilt clamps to the LUT bounds instead of raising."""
    cur_low = _empty_parstochip()
    cur_low[OUT_TLT] = -3
    assert send_pars_delaypars(cur_low, _empty_parstochip())[OUT_TLT] == lineartilt[0]
    cur_high = _empty_parstochip()
    cur_high[OUT_TLT] = 99
    assert send_pars_delaypars(cur_high, _empty_parstochip())[OUT_TLT] == lineartilt[-1]


def test_send_pars_delaypars_preserves_width_and_inputs() -> None:
    """The packet is a NEW list of the previous frame's width; inputs unmutated."""
    prev = _numbered_parstochip(100)
    cur = _numbered_parstochip(500)
    cur[OUT_TLT] = 0
    prev_copy = list(prev)
    cur_copy = list(cur)
    packet = send_pars_delaypars(cur, prev)
    assert len(packet) == len(prev)
    assert packet is not prev
    assert prev == prev_copy
    assert cur == cur_copy


# -- _build_hl_frame_from_parstochip unit conversions ----------------------
#
# Mirror the SPC-frame → HLFrame reader at vtm/vtmiont.c:720-750 (HLSYN build).
# phdraw writes the NEW_VTM area cells as raw "x100" / "x10" scaled integers
# (ph_draw.c:4159, 4280, 4282); the reader recovers the float-mm² / cmH2O
# values via the per-cell scale factors below.


def test_hl_frame_ag_scale_factor_100x() -> None:
    """``OUT_AG`` (mm²*100) maps to ``HLFrame.ag`` via ``*0.01``."""
    p = _empty_parstochip()
    p[OUT_AG] = 350  # 3.50 mm² (a typical modal-voicing glottal area)
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.ag == 3.5


def test_hl_frame_al_scale_factor_10x() -> None:
    """``OUT_AL`` (mm²*10) maps to ``HLFrame.al`` via ``*0.1``."""
    p = _empty_parstochip()
    p[OUT_AL] = 80  # 8.0 mm²
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.al == 8.0


def test_hl_frame_ab_sourced_from_ablade_with_10x_scale() -> None:
    """``HLFrame.ab`` is read from ``OUT_ABLADE`` (mm²*10) via ``*0.1``."""
    p = _empty_parstochip()
    p[OUT_ABLADE] = 45  # 4.5 mm²
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.ab == 4.5


def test_hl_frame_ap_sourced_from_cnk_with_100x_scale() -> None:
    """``HLFrame.ap`` is read from ``OUT_CNK`` (mm²*100) via ``*0.01``.

    Critical fix: ``OUT_AP`` carries aspiration *amplitude in dB*, not area.
    vtmiont.c:728 reads ``frame.ap`` from ``OUT_CNK`` (chink area).
    """
    p = _empty_parstochip()
    p[OUT_AP] = 60  # dB — must NOT appear as ap area.
    p[OUT_CNK] = 25  # 0.25 mm² — the correct ap source.
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.ap == 0.25
    assert hl.ap != 60.0


def test_hl_frame_an_scale_factor_10x() -> None:
    """``OUT_AN`` (mm²*10) maps to ``HLFrame.an`` via ``*0.1``."""
    p = _empty_parstochip()
    p[OUT_AN] = 30  # 3.0 mm²
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.an == 3.0


def test_hl_frame_ps_scale_factor_100x() -> None:
    """``OUT_PS`` (cmH2O*100) maps to ``HLFrame.ps`` via ``*0.01``."""
    p = _empty_parstochip()
    p[OUT_PS] = 800  # 8.0 cmH2O — typical subglottal pressure for modal voice.
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.ps == 8.0


def test_hl_frame_atb_signed_with_10x_scale() -> None:
    """``OUT_ATB`` reads via ``(short)`` cast then ``*0.1`` (vtmiont.c:738)."""
    p = _empty_parstochip()
    p[OUT_ATB] = 200  # 20.0 mm²
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.atb == 20.0
    # Negative input: simulate raw signed-int16 wrap.
    p[OUT_ATB] = 0xFFEC  # -20 as int16 → -2.0 after *0.1
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.atb == -2.0


def test_hl_frame_ue_signed_no_scale() -> None:
    """``OUT_UE`` reads via ``(short)`` cast with no scaling (vtmiont.c:730)."""
    p = _empty_parstochip()
    p[OUT_UE] = 0xFFFF  # -1 as int16
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.ue == -1.0


def test_hl_frame_dc_signed_no_scale() -> None:
    """``OUT_DC`` reads via ``(short)`` cast with no scaling (vtmiont.c:737)."""
    p = _empty_parstochip()
    p[OUT_DC] = 0xFFF0  # -16 as int16
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.dc == -16.0


def test_hl_frame_place_signed_no_scale() -> None:
    """``OUT_PLACE`` reads via ``(short)`` cast with no scaling (vtmiont.c:744)."""
    p = _empty_parstochip()
    p[OUT_PLACE] = 0xFFFE  # -2 as int16
    hl = _build_hl_frame_from_parstochip(p)
    assert hl.place == -2


# -- parstochip_to_llframe_via_hl integration --------------------------------


def _voiced_parstochip() -> list[int]:
    """A parstochip seeded with HLSyn cells representative of voiced vowel.

    Values are chosen so the HL→LL gating pipeline (``hlframe.py``) admits
    voicing (AV > 0). In particular:

    - ``OUT_AG = 200`` (mm²*100 → 2.0 mm²): glottal area sits between
      ``speaker.agMin`` and ``speaker.agm + speaker.agAVModalOffsetMax``
      so :func:`_source_amplitudes` produces non-zero NAV.
    - ``OUT_PS = 800`` (cmH2O*100 → 8.0 cmH2O): standard modal-voice
      subglottal pressure, well above ``speaker.AVPressureThreshold``.
    - ``OUT_T0 = 1220``: 122 Hz, adult-male F0.
    """
    p = [0] * 64
    p[OUT_T0] = 1220
    p[OUT_AG] = 200  # 2.0 mm²
    p[OUT_PS] = 800  # 8.0 cmH2O
    p[OUT_F1] = 500
    p[OUT_F2] = 1500
    p[OUT_F3] = 2500
    return p


def test_via_hl_produces_non_zero_av() -> None:
    """Voiced parstochip drives ``parstochip_to_llframe_via_hl`` to AV > 0.

    Regression guard for the §5a unit-conversion bug (issue #124): when
    ``HLFrame.ag`` was 100x too large, ``state.agx`` exceeded
    ``speaker.agAVModalOffsetMax + speaker.agm`` and
    :func:`_source_amplitudes` zero-clamped NAV, silencing voiced output.
    With the ``*0.01`` scale applied, the gating branch produces a
    positive NAV that propagates to ``LLFrame.AV``.
    """
    p = _voiced_parstochip()
    frame = parstochip_to_llframe_via_hl(p, previous_parstochip=None)
    assert isinstance(frame, LLFrame)
    assert frame.AV > 0, (
        f"voiced parstochip should produce non-zero AV; got {frame.AV}. "
        "This is the §5a regression guard (HLFrame area unit conversions)."
    )


def test_via_hl_silent_when_ag_above_modal_range() -> None:
    """Glottal area above the modal-offset cap zeros AV (gating works).

    Sanity-check the gating still fires when ``HLFrame.ag`` legitimately
    exceeds ``speaker.agAVModalOffsetMax + speaker.agm``. Without the
    unit-conversion fix every voiced frame fell into this branch.
    """
    p = _voiced_parstochip()
    # 200 mm² is unambiguously above any speaker.agAVModalOffsetMax cap.
    p[OUT_AG] = 20000  # → 200.0 mm² after *0.01
    frame = parstochip_to_llframe_via_hl(p, previous_parstochip=None)
    assert frame.AV == 0


def test_via_hl_ap_independent_of_out_ap_aspiration_db() -> None:
    """High ``OUT_AP`` (dB) must not bleed into ``HLFrame.ap`` (mm²).

    Before the fix, ``frame.ap`` was sourced from ``OUT_AP`` (dB) without
    scaling, so an aspiration-dB of 50 was interpreted as 50 mm² of
    posterior glottal area, materially distorting the TL correction.
    With the fix, ``frame.ap`` is sourced from ``OUT_CNK`` and unaffected
    by ``OUT_AP``.
    """
    p_no_aspiration = _voiced_parstochip()
    p_no_aspiration[OUT_AP] = 0
    p_aspiration = _voiced_parstochip()
    p_aspiration[OUT_AP] = 50  # heavy aspiration in dB
    f_quiet = parstochip_to_llframe_via_hl(p_no_aspiration, previous_parstochip=None)
    f_loud = parstochip_to_llframe_via_hl(p_aspiration, previous_parstochip=None)
    # Both frames should produce identical AV; OUT_AP must not be wired
    # into ``HLFrame.ap`` any more.
    assert f_quiet.AV == f_loud.AV


# -- SpdChip F4/B4/F5/B5 threading (VTM divergence audit §3) -----------------
#
# ``parstochip_to_llframe`` and ``parstochip_to_llframe_delayed`` historically
# emitted the generic Klatt-1980 reference values (F4=3500/B4=200/F5=4500/
# B5=250) for the cascade-4 / cascade-5 resonator poles even when the live
# pipeline already had Paul's voice-specific defaults loaded in a
# :class:`~dectalk.vtm.spd_chip.SpdChip`. Issue #159 wires the SpdChip
# through these adapters so the emitted ``LLFrame`` reflects the active
# voice. For US-Paul the chip words are F4=3303, B4=260, F5=3653,
# B5=330 -- the ``setspdef()`` derivations (F4/F5 pre-scaled by
# fnscale=4100; ph_vset.c:638/648/670) of the non-_8 ``paul[SPDEF]``
# table values 3300/260/3650/330 in ``p_us_vdf_dectalk43.c``.


def test_parstochip_to_llframe_uses_spd_chip_for_f4_b4_f5_b5() -> None:
    """When a SpdChip is supplied, F4/B4/F5/B5 come from r4cc/r4cb/r5cc/r5cb."""
    spd = default_us_paul_spd()
    frame = parstochip_to_llframe(_empty_parstochip(), spd_chip=spd)
    # Paul's voice-table values (non-_8 paul[SPDEF] in p_us_vdf_dectalk43.c).
    assert frame.F4 == spd.r4cc == 3303
    assert frame.B4 == spd.r4cb == 260
    assert frame.F5 == spd.r5cc == 3653
    assert frame.B5 == spd.r5cb == 330


def test_parstochip_to_llframe_paul_values_differ_from_klatt_1980_defaults() -> None:
    """Paul's SpdChip F4/B4/F5/B5 are distinct from the generic Klatt defaults.

    Regression guard for the §3 VTM audit fix: when the SpdChip is wired
    through, the emitted higher-formant cells must NOT match the
    Klatt-1980 reference values that the no-SpdChip fallback would emit.
    """
    spd = default_us_paul_spd()
    no_spd_frame = parstochip_to_llframe(_empty_parstochip())
    paul_frame = parstochip_to_llframe(_empty_parstochip(), spd_chip=spd)
    # Klatt-1980 reference defaults emitted by the fallback path.
    assert no_spd_frame.F4 == 3500
    assert no_spd_frame.B4 == 200
    assert no_spd_frame.F5 == 4500
    assert no_spd_frame.B5 == 250
    # Paul's voice-table values must NOT match the Klatt-1980 defaults.
    assert paul_frame.F4 != no_spd_frame.F4
    assert paul_frame.B4 != no_spd_frame.B4
    assert paul_frame.F5 != no_spd_frame.F5
    assert paul_frame.B5 != no_spd_frame.B5


def test_parstochip_to_llframe_no_spd_chip_preserves_klatt_defaults() -> None:
    """Backwards-compat: no-SpdChip call still emits the Klatt-1980 defaults."""
    frame = parstochip_to_llframe(_empty_parstochip())
    assert frame.F4 == 3500
    assert frame.B4 == 200
    assert frame.F5 == 4500
    assert frame.B5 == 250


def test_parstochip_to_llframe_delayed_uses_spd_chip_for_f4_b4_f5_b5() -> None:
    """Delayed adapter threads SpdChip F4/B4/F5/B5 through to the emitted frame."""
    spd = default_us_paul_spd()
    frame = parstochip_to_llframe_delayed(
        _empty_parstochip(), previous_parstochip=None, spd_chip=spd
    )
    assert frame.F4 == spd.r4cc == 3303
    assert frame.B4 == spd.r4cb == 260
    assert frame.F5 == spd.r5cc == 3653
    assert frame.B5 == spd.r5cb == 330


def test_parstochip_to_llframe_delayed_paul_values_differ_from_klatt_defaults() -> None:
    """Delayed adapter: Paul SpdChip values are distinct from Klatt-1980 defaults.

    Primary regression guard for issue #159: the legacy delayed adapter
    (the path the full pipeline actually uses) must emit SpdChip-derived
    higher-formant poles when a SpdChip is supplied, not the generic
    Klatt defaults.
    """
    spd = default_us_paul_spd()
    no_spd_frame = parstochip_to_llframe_delayed(_empty_parstochip(), previous_parstochip=None)
    paul_frame = parstochip_to_llframe_delayed(
        _empty_parstochip(), previous_parstochip=None, spd_chip=spd
    )
    # Klatt-1980 reference defaults via the fallback path.
    assert no_spd_frame.F4 == 3500
    assert no_spd_frame.B4 == 200
    assert no_spd_frame.F5 == 4500
    assert no_spd_frame.B5 == 250
    # Paul's voice-table values must NOT equal the Klatt-1980 defaults.
    assert paul_frame.F4 != no_spd_frame.F4
    assert paul_frame.B4 != no_spd_frame.B4
    assert paul_frame.F5 != no_spd_frame.F5
    assert paul_frame.B5 != no_spd_frame.B5


def test_parstochip_to_llframe_delayed_no_spd_chip_preserves_klatt_defaults() -> None:
    """Backwards-compat: delayed adapter with no SpdChip emits Klatt defaults."""
    frame = parstochip_to_llframe_delayed(_empty_parstochip(), previous_parstochip=None)
    assert frame.F4 == 3500
    assert frame.B4 == 200
    assert frame.F5 == 4500
    assert frame.B5 == 250


def test_parstochip_to_llframe_delayed_arbitrary_spd_chip_overrides_defaults() -> None:
    """A non-Paul SpdChip threads its own resonator-4/5 values through cleanly.

    Constructs a synthetic SpdChip with deliberately distinctive r4/r5
    values to confirm the adapter forwards whatever is supplied, rather
    than special-casing Paul or silently dropping the override.
    """
    custom = SpdChip(r4cc=3700, r4cb=210, r5cc=4600, r5cb=320)
    frame = parstochip_to_llframe_delayed(
        _empty_parstochip(), previous_parstochip=None, spd_chip=custom
    )
    assert frame.F4 == 3700
    assert frame.B4 == 210
    assert frame.F5 == 4600
    assert frame.B5 == 320
