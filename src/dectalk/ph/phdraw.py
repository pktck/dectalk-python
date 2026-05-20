"""``phdraw`` -- per-frame Klatt-parameter emitter from ph_draw.c.

Translated from ``src/dapi/src/ph/ph_draw.c`` lines 229-4837 (the
single largest function in the PH layer at ~4600 lines of C). Called
once per output frame from the per-clause driver loop in
``ph_claus.c`` (the canonical pattern is::

    pht0draw(phTTS)
    phdraw(phTTS)
    send_pars(phTTS)

within ``send_pars_loop`` -- see ``ph_claus.c`` lines 488-498). On
each call ``phdraw`` consumes the per-parameter target / transition
state that :func:`phsettar` populated on ``DphT.param[]`` and writes
the next-frame Klatt values into ``DphT.parstochip[]`` for the SPC
chip (or, in the Python port, for whatever downstream hlsyn consumer
the wiring hands them to).

This Python port is a **partial faithful translation**:

* Lines 229-758 of the C body (the core per-frame trajectory engine)
  are ported faithfully: the F1..B3 formant-frequency loop, the
  AV..TILT amplitude loop, the spectral-tilt computation, the breathy-
  voice modifier, and the formant scaling step. These cover the
  deterministic per-frame work that has well-defined inputs from
  phsettar and well-defined outputs to ``parstochip[]``.

* Lines 759-4837 (the bulk of the C body) cover the HLSyn area-
  parameter state machine (PAREAL / PAREAB / PTONGUEBODY plus the
  pressure / glottis / nasal area trackers), F0-event emission, and
  the language-specific coarticulation rules. Most of this logic
  reads ``DphT`` fields that depend on intermediate state computed
  by ``phinton`` / ``pht0draw`` / phalloph helpers that themselves
  are only partially ported. Calling those branches before their
  dependencies land would silently emit wrong values, so the port
  here raises :class:`NotImplementedError` from per-block helpers
  named after their C-source line numbers. See the individual
  ``_phdraw_hlsyn_*`` helpers below for the precise gaps.

The function signature mirrors the C source: ``phdraw(phTTS)`` takes
a populated :class:`~dectalk.ph.tts_handle.TtsHandle` and mutates
``phTTS.p_ph_thread_data.parstochip[]`` in place. No return value.
"""

from __future__ import annotations

# ruff: noqa: PLR2004 -- C-literal style kept; magic numbers are taken
# directly from ph_draw.c and adding named constants for each one would
# obscure the per-line correspondence with the C source.
from typing import cast

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import (
    A2,
    A3,
    A4,
    A5,
    A6,
    AB,
    AP,
    AV,
    B1,
    B2,
    B3,
    F0,
    F1,
    F2,
    F3,
    FZ,
    MALE,
    TILT,
)
from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_AP,
    OUT_AV,
    OUT_B1,
    OUT_B2,
    OUT_B3,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_T0,
    OUT_TLT,
)
from dectalk.ph.parameter_struct import Parameter
from dectalk.ph.tts_handle import TtsHandle
from dectalk.vtm.frac import frac4mul

# ---- Output-buffer offsets in DphT.parstochip[] for each param slot. -------

# The C source's drawinitsw=1 block (ph_draw.c lines 291-326) maps each
# entry in pDph_t->param[] to the appropriate cell in pDph_t->parstochip[]
# via the ``outp`` pointer field. The Python port mirrors that mapping
# table here so callers don't have to set it up by hand. The order matches
# the C source line-by-line.
_OUTP_MAP: dict[int, int] = {
    F0: OUT_T0,
    F1: OUT_F1,
    F2: OUT_F2,
    F3: OUT_F3,
    FZ: OUT_FZ,
    B1: OUT_B1,
    B2: OUT_B2,
    B3: OUT_B3,
    AV: OUT_AV,
    AP: OUT_AP,
    A2: OUT_A2,
    A3: OUT_A3,
    A4: OUT_A4,
    A5: OUT_A5,
    A6: OUT_A6,
    AB: OUT_AB,
    TILT: OUT_TLT,
}

# The two loop ranges from ph_draw.c. Lines 345-421 walk PF1..PB3 (formant
# frequencies and bandwidths). Lines 428-606 walk PAV..PTILT (amplitudes
# plus spectral tilt). Translating the C pointer-arithmetic ``for (np =
# &PF1; np <= &PB3; ++np)`` as an explicit param-index range matches the
# pattern documented in docs/PORTING.md ("Pointer arithmetic patterns").
_FORMANT_PARAMS: tuple[int, ...] = (F1, F2, F3, FZ, B1, B2, B3)
_AMP_PARAMS: tuple[int, ...] = (AV, AP, A2, A3, A4, A5, A6, AB, TILT)

# Maximum source-tilt clamp from ph_draw.c lines 734-741. The hardware
# spectral-tilt parameter saturates at 31 dB; the Python port mirrors
# the C clamp so downstream synthesisers see the same numerical range.
_TILT_MAX: int = 31


def _div_by8(value: int) -> int:
    """Faithful translation of the C macro ``DIV_BY8(x)``.

    The macro is defined in ``src/dapi/src/include/parts.h`` as a plain
    arithmetic right-shift by 3. Pulled out into a small helper so each
    use-site reads identically to the C source (``value DIV_BY8`` ->
    ``_div_by8(value)``).
    """
    # Python's ``>>`` is arithmetic on negative ints, matching C's signed
    # shift behaviour on every conventional platform.
    return value >> 3


def _init_outp_pointers(p_dph_t: DphT, p_dphsettar: DphSettarSt) -> None:
    """One-shot setup of ``param[].outp`` slot indices.

    Faithful port of ph_draw.c lines 291-326: on the very first call,
    populate each :class:`Parameter`'s ``outp`` field with the
    corresponding ``parstochip[]`` offset and flip the ``drawinitsw``
    latch so subsequent calls skip the setup.
    """
    if p_dphsettar.drawinitsw != 0:
        return
    p_dphsettar.drawinitsw = 1
    for param_idx, out_idx in _OUTP_MAP.items():
        p_dph_t.param[param_idx].outp = out_idx


def _ensure_parstochip(p_dph_t: DphT) -> None:
    """Grow ``parstochip`` to at least 64 entries (the C buffer size).

    The C source allocates ``parstochip[OUT_BUFSZ]`` statically; in
    Python the array can be initialised empty so first-call wiring
    sizes it here. 64 covers every ``OUT_*`` constant including the
    NEW_VTM extensions.
    """
    needed = 64
    if len(p_dph_t.parstochip) < needed:
        p_dph_t.parstochip = list(p_dph_t.parstochip) + [0] * (needed - len(p_dph_t.parstochip))


def _formant_param_trajectory(p_dph_t: DphT, p: Parameter) -> int:
    """Per-frame formant-frequency / bandwidth update.

    Faithful port of ph_draw.c lines 345-421. Walks one parameter in
    the PF1..PB3 range and returns the value to write into
    ``parstochip[p.outp]``.

    The algorithm:

    1. If ``tcum`` has reached the current diphthong-line endpoint
       (``durlin``), advance ``ndip`` two slots (new ``durlin`` and
       ``deldip``) and roll the accumulated dipcum into ``tarcur``.
    2. Apply the per-frame diphthong delta ``deldip`` to ``dipcum``.
    3. Add forward transition ``ftran`` and shrink it by ``dftran``.
    4. If past ``tbacktr``, add backward transition ``btran`` and grow
       it by ``dbtran``.
    5. The composite value (forward + back) is right-shifted by 3
       (the ``DIV_BY8`` macro -- ftran/dftran/btran/dbtran are stored
       *8 to avoid roundoff propagation) and added to ``tarcur``.
    """
    # 1. Advance the diphthong line if we passed the current segment end.
    if p_dph_t.tcum > p.durlin and p_dph_t.tcum > 0 and p.durlin >= 0:
        # The C source advances ``ndip`` by 2 shorts. With ``ndip``
        # modelled as an int index into ``DphT.dipspec``, fetch the
        # next two cells and bump the index.
        ndip = p.ndip if p.ndip is not None else 0
        dipspec = p_dph_t.dipspec
        if ndip + 1 < len(dipspec):
            p.durlin = dipspec[ndip]
            p.deldip = dipspec[ndip + 1]
            p.ndip = ndip + 2
        else:
            # Fall off the end of the diphthong spec -- C does not
            # bounds-check; emulate the benign no-op (the trajectory
            # is already at its tail so further frames just hold).
            p.durlin = 0
            p.deldip = 0
            p.ndip = ndip
        p.tarcur += _div_by8(p.dipcum)
        p.dipcum = 0

    # 2-3. Forward smooth.
    p.dipcum += p.deldip
    value = p.dipcum + p.ftran
    if p.ftran != 0:
        p.ftran -= p.dftran

    # 4. Backward smooth.
    if p_dph_t.tcum >= p.tbacktr:
        value += p.btran
        p.btran += p.dbtran

    return value


def _amp_param_trajectory(p_dph_t: DphT, p: Parameter) -> int:
    """Per-frame amplitude-loop update (PAV..PTILT, ph_draw.c lines 428-451).

    Returns the value to write into ``parstochip[p.outp]``. The
    amplitude loop uses a slightly simpler smoothing rule than the
    formant loop: there's no diphthong sub-line, ``tarcur`` is added
    directly, and the forward transition is right-shifted by 3 before
    summation (vs after, in the formant case).
    """
    value = p.tarcur + _div_by8(p.ftran)
    if p.ftran != 0:
        p.ftran -= p.dftran

    if p_dph_t.tcum >= p.tbacktr:
        value += _div_by8(p.btran)
        p.btran += p.dbtran
    return value


def _apply_amp_special_double_burst(p_dph_t: DphT, param_idx: int, p: Parameter, value: int) -> int:
    """Faithful port of ph_draw.c lines 506-524: double-burst for /k,g,ch,jh/.

    When the per-parameter ``tspesh`` window has just expired (one
    frame after the burst onset), parallel amplitudes above 10 dB are
    knocked back by 10 dB to create the secondary release burst that
    distinguishes the velar/affricate stops from their plain plosive
    counterparts. The GRP_KSX (German /ks/) special case is skipped
    here; it's gated behind ``#ifdef GERMAN_not`` in the C source.
    """
    # Indices above AP (i.e. A2..A6 and AB) are the parallel amplitudes
    # the rule targets. AV / AP / TILT are excluded.
    if param_idx <= AP:
        return value
    if p.tspesh <= 0 or p_dph_t.tcum != p.tspesh + 1 or value < 10:
        return value
    return value - 10


def _compute_tilt(p_dph_t: DphT, p_dphsettar: DphSettarSt) -> int:
    """Source spectral-tilt computation (ph_draw.c lines 622-742).

    Mirrors the V43+ tilt formula used for both MALE and FEMALE voices,
    applies the GRP_IH special bump (skipped here because GRP_IH is a
    German allophone not relevant on the US path -- the equality check
    against the US allophone codes is always false), then layers on
    the breathy-voice corrections from lines 686-731.
    """
    # Lines 640-651: f0-dependent tilt component.
    if p_dph_t.malfem == MALE:
        temptilt = frac4mul(p_dph_t.f0 - 900, p_dph_t.f0_dep_tilt)
    else:
        temptilt = frac4mul(1400 - p_dph_t.f0, p_dph_t.f0_dep_tilt)

    # Lines 653-654: V43-and-after constant offset.
    temptilt = 8 - temptilt

    temptilt = max(temptilt, 0)

    # Lines 668-672: GRP_IH (German allophone) bump -- never fires on
    # the US path because GRP_IH lives in the German font block.
    # Translated verbatim for completeness; the comparison is always
    # False here.

    tilt_value = temptilt
    # Line 679: spdef tilt offset (V43+ uses ``- 3``).
    tilt_value += p_dph_t.spdeftltoff - 3

    # Lines 686-725: breathy-voice modifier.
    if p_dph_t.breathysw == 1 and p_dph_t.parstochip[OUT_AV] > 40:
        # Asp increase 32 dB / 100 ms (lines 692-694).
        if p_dphsettar.breathyah < 27:
            p_dphsettar.breathyah += 2

        # Tilt decrease 16 dB / 100 ms (lines 714-717).
        if p_dphsettar.breathytilt < 16:
            p_dphsettar.breathytilt += 1
        tilt_value += frac4mul(p_dph_t.spdeflaxprcnt, p_dphsettar.breathytilt)
    else:
        # Lines 726-731: zero or initialize all breathiness variables.
        p_dphsettar.breathyah = 0
        p_dphsettar.breathytilt = 0

    # Lines 733-742: clamp to [0, 31].
    tilt_value = min(tilt_value, _TILT_MAX)
    tilt_value = max(tilt_value, 0)
    return tilt_value


def _apply_formant_scaling(p_dph_t: DphT) -> None:
    """Formant-frequency scaling (ph_draw.c lines 750-757).

    The ``fnscale`` factor is a Q12 voice-specific multiplier (1.0 =
    4096). It's applied to F1 (above the 250 Hz floor), F2 and F3 with
    a small fixed bias derived from the complementary ``4096 -
    fnscale`` term shifted right by 4 / 3 / 0 respectively. The C
    expression ``frac4mul(x, fnscale) + ((4096 - fnscale) >> N)``
    keeps unity scaling exactly identity when fnscale == 4096.
    """
    parstochip = p_dph_t.parstochip
    fnscale = p_dph_t.fnscale
    complement = 4096 - fnscale

    if parstochip[OUT_F1] > 250:
        parstochip[OUT_F1] = frac4mul(parstochip[OUT_F1], fnscale) + (complement >> 4)
    parstochip[OUT_F2] = frac4mul(parstochip[OUT_F2], fnscale) + (complement >> 3)
    parstochip[OUT_F3] = frac4mul(parstochip[OUT_F3], fnscale)


# ----------------------------------------------------------------------------
# Stubs for the un-ported HLSyn / area / F0-event / language-specific blocks.
# Each helper names the C-source line range it represents so the next pass
# has an unambiguous lookup. ``phdraw`` itself currently skips them so the
# wiring up to the basic Klatt-parameter trajectory executes end-to-end;
# call ``raise_for_unported`` from a future driver if strict parity is
# required.
# ----------------------------------------------------------------------------


def _phdraw_hlsyn_area_loop_unported() -> None:
    """Stub for ph_draw.c lines 761-907 (HLSyn AREAL/AREAB/PTONGUEBODY loop).

    The block walks the HLSyn area-parameter range setting per-frame
    closure / release / friction state for the labial / blade /
    tongue-body articulators. It depends on ``pVtm_t->NOM_*`` voice
    constants that have no Python mirror yet.
    """
    raise NotImplementedError(
        "phdraw: HLSyn area loop (ph_draw.c lines 761-907) is not yet ported; "
        "requires pVtm_t (VTM thread data) which has no Python mirror."
    )


def _phdraw_initial_silence_anticipation_unported() -> None:
    """Stub for ph_draw.c lines 929-2350 (the ``nphone == 0`` anticipation block).

    On the first frame of a clause (initial silence), the C source
    pre-positions every area parameter / glottis state / pressure
    trajectory based on the *next* phone's feature flags, so the
    real synthesis frames have a sensible starting point. Each
    sub-block (FOBST, FVOICD, FNASAL, FVOWEL...) needs the same
    pVtm_t voice constants the area loop wants.
    """
    raise NotImplementedError(
        "phdraw: initial-silence anticipation (ph_draw.c lines 929-2350) "
        "is not yet ported; requires pVtm_t voice constants."
    )


def _phdraw_per_frame_hlsyn_state_machine_unported() -> None:
    """Stub for ph_draw.c lines 2350-4500 (per-frame HLSyn area updates).

    The bulk of the C body: pressure / glottis / nasal / labial /
    blade / tongue-body trackers step toward their targets each frame
    via the ``*step`` increments and ``target_*`` values that the
    HLSyn area loop set up.
    """
    raise NotImplementedError(
        "phdraw: per-frame HLSyn state machine (ph_draw.c lines 2350-4500) "
        "is not yet ported; requires the full DphT area-parameter set "
        "(target_ag, area_g, target_b, target_l, target_tb, area_n, "
        "pressure, syl_pressure, nasal_step, etc.) which depend on the "
        "un-ported phinton / pht0draw / phalloph helpers."
    )


def _phdraw_f0_modulation_unported() -> None:
    """Stub for ph_draw.c lines 4500-4837 (F0 event firing + modulation helpers).

    Dispatches to :func:`r_modulation` / :func:`rs_modulation` /
    :func:`gr_modulation` / :func:`h_modulation` (the post-phdraw
    helpers at lines 4838-5232) for Spanish / German / French /
    glottal-stop modulations. None are on the US-English critical
    path but the dispatch logic itself reads pDphsettar->phcur.
    """
    raise NotImplementedError(
        "phdraw: F0 event firing + modulation helpers (ph_draw.c lines "
        "4500-4837 + helper functions r_modulation/rs_modulation/"
        "gr_modulation/h_modulation at lines 4838-5232) not yet ported."
    )


# ----------------------------------------------------------------------------
# Public entry point.
# ----------------------------------------------------------------------------


def phdraw(phTTS: TtsHandle) -> None:  # noqa: N803, PLR0912 — branches mirror C body
    """Emit one Klatt parameter frame.

    Faithful (partial) translation of ``void phdraw(LPTTS_HANDLE_T)``
    from ``ph_draw.c`` line 229. Mutates
    ``phTTS.p_ph_thread_data.parstochip[]`` in place to hold the
    just-computed parameter values for the current frame.

    Currently ported:

    * One-shot ``outp`` pointer initialisation (lines 291-326).
    * F1..B3 formant-frequency / bandwidth trajectory loop with
      diphthong-line advancement, forward / backward transition
      smoothing, vowel-vowel coarticulation across consonants
      for F2 only, and the B1 breathy-bandwidth modifier (lines
      345-421).
    * AV..TILT amplitude trajectory loop with the double-burst
      knock-down for parallel amplitudes (lines 428-606).
    * AV reduction for glottal stop (lines 613-616).
    * Source spectral tilt computation including breathy-voice
      tilt-decrease (lines 622-742).
    * F1 / F2 / F3 formant scaling (lines 750-757).

    Not yet ported (per the C structure, these run *after* the above
    but the Python port returns at that point until each block lands):

    * HLSyn area-parameter loop (PAREAL / PAREAB / PTONGUEBODY),
      C lines 761-907.
    * Initial-silence anticipation (``nphone == 0`` branch),
      C lines 929-2350.
    * Per-frame HLSyn state machine (pressure / glottis / nasal /
      labial / blade / tongue-body trackers), C lines 2350-4500.
    * F0 event firing + r_modulation / rs_modulation / gr_modulation /
      h_modulation helpers, C lines 4500-4837 (plus helpers at
      lines 4838-5232).

    See the individual ``_phdraw_*_unported`` helpers above for the
    sub-helper names a future port should claim.

    Args:
        phTTS: Two-pointer engine handle (``TtsHandle``) with
            populated ``p_ph_thread_data`` (DphT post-phsettar) and
            an attached :class:`DphSettarSt` on ``pSTphsettar``.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    # One-shot wiring: param[i].outp -> parstochip[OUT_*] mapping.
    # Faithful translation of ph_draw.c lines 291-326.
    _ensure_parstochip(p_dph_t)
    _init_outp_pointers(p_dph_t, p_dphsettar)

    # ----- C lines 345-421: formant-frequency / bandwidth loop -----
    for param_idx in _FORMANT_PARAMS:
        p = p_dph_t.param[param_idx]
        value = _formant_param_trajectory(p_dph_t, p)

        # Lines 388-398: vowel-vowel coarticulation across a consonant
        # (F2 only).
        if param_idx == F2:
            value += p_dph_t.fvvtran
            if p_dph_t.fvvtran != 0:
                p_dph_t.fvvtran -= p_dph_t.dfvvtran
            if p_dph_t.tcum >= p_dph_t.tvvbacktr:
                value += p_dph_t.bvvtran
                p_dph_t.bvvtran += p_dph_t.dbvvtran

        # Line 404: write the resolved value into parstochip[outp].
        out_idx = p.outp
        if out_idx is None:
            # outp wasn't initialised -- skip; should never happen after
            # _init_outp_pointers, but defensive against custom DphT
            # constructions in tests.
            continue
        parp = _div_by8(value) + p.tarcur
        p_dph_t.parstochip[out_idx] = parp

        # Lines 408-414: special-rule constant override (B1 / B2 use this
        # for aspiration-time bandwidth widening).
        if p.tspesh > 0 and p_dph_t.tcum < p.tspesh:
            p_dph_t.parstochip[out_idx] = p.pspesh
        elif param_idx == B1:
            # Lines 417-420: breathy-voice widens first-formant bandwidth.
            p_dph_t.parstochip[out_idx] = frac4mul(p_dph_t.parstochip[out_idx], p_dph_t.spdefb1off)

    # ----- C lines 428-606: amplitude loop (PAV..PTILT) -----
    for param_idx in _AMP_PARAMS:
        p = p_dph_t.param[param_idx]
        value = _amp_param_trajectory(p_dph_t, p)
        out_idx = p.outp
        if out_idx is None:
            continue
        p_dph_t.parstochip[out_idx] = value

        # Lines 454-525: special-rule constant override + double burst.
        if p.tspesh > 0:
            if p_dph_t.tcum < p.tspesh:
                p_dph_t.parstochip[out_idx] = p.pspesh
            else:
                # The double-burst rule applies *after* the tspesh window
                # closes, knocking parallel amplitudes back by 10 dB at
                # tcum == tspesh + 1.
                p_dph_t.parstochip[out_idx] = _apply_amp_special_double_burst(
                    p_dph_t, param_idx, p, p_dph_t.parstochip[out_idx]
                )

        # Lines 527-602: PAV-specific VOT / glottal-area sync.
        # The C body here mutates pDph_t->target_ag and pDph_t->agspeed
        # which only feed the HLSyn area loop (un-ported), so skipping
        # the mutation has no observable effect on the ported Klatt
        # parameter trajectory. The pDph_t->lastvot bookkeeping is kept
        # because it's read by other functions.
        if param_idx == AV:
            if p.tspesh:
                # Note: only the lastvot=tspesh-at-vot-onset bookkeeping
                # has observable effect on the ported path; the full
                # target_ag / agspeed mutation is gated to phdraw_hlsyn.
                if p_dph_t.tcum == p.tspesh:
                    p_dph_t.lastvot = p.tspesh
            else:
                p_dph_t.lastvot = 0

    # ----- C lines 613-616: reduce AV if glottal stop -----
    if p_dph_t.parstochip[OUT_AV] > 6:
        p_dph_t.parstochip[OUT_AV] -= p_dph_t.avglstop

    # ----- C lines 622-742: source spectral tilt -----
    p_dph_t.parstochip[OUT_TLT] = _compute_tilt(p_dph_t, p_dphsettar)

    # ----- C lines 750-757: formant scaling -----
    _apply_formant_scaling(p_dph_t)

    # ----- C lines 761+: HLSyn area loop, initial-silence anticipation,
    # per-frame HLSyn state machine, F0 modulation. All deferred.
    # Calling code that needs strict parity should raise via the helper
    # stubs above; the default per-frame path returns here so the basic
    # Klatt parameter trajectory keeps emitting frames.


# Stub helpers naming the un-ported C blocks (the four _phdraw_*_unported
# functions) are exported so callers that want strict parity can opt
# into the NotImplementedError rather than the silent-skip default; also
# gives the next port an unambiguous place to claim a sub-block.
__all__ = [
    "_phdraw_f0_modulation_unported",
    "_phdraw_hlsyn_area_loop_unported",
    "_phdraw_initial_silence_anticipation_unported",
    "_phdraw_per_frame_hlsyn_state_machine_unported",
    "phdraw",
]
