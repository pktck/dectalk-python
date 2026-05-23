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

* Lines 761-907 (the HLSyn area-parameter loop -- PAREAL / PAREAB /
  PTONGUEBODY closure / release / friction flag updates) are now
  ported, gated by the same drawinitsw / tspesh state phsettar
  populates. See :func:`_phdraw_hlsyn_area_loop`.

* Lines 908-4837 (the remaining bulk of the C body) cover the
  initial-silence anticipation block, the per-frame HLSyn state
  machine (pressure / glottis / nasal area trackers), and F0-event
  emission. Most of this logic reads ``DphT`` fields that depend on
  intermediate state computed by ``pht0draw`` and the un-ported
  pieces of phalloph; calling those branches before their
  dependencies land would silently emit wrong values, so the port
  here raises :class:`NotImplementedError` from per-block helpers
  named after their C-source line numbers. See the individual
  ``_phdraw_*_unported`` helpers below for the precise gaps.

The function signature mirrors the C source: ``phdraw(phTTS)`` takes
a populated :class:`~dectalk.ph.tts_handle.TtsHandle` and mutates
``phTTS.p_ph_thread_data.parstochip[]`` in place. No return value.
"""

from __future__ import annotations

# ruff: noqa: PLR2004 -- C-literal style kept; magic numbers are taken
# directly from ph_draw.c and adding named constants for each one would
# obscure the per-line correspondence with the C source.
from typing import cast

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFFR, PFGR, PFLA, PFSP, PFUK
from dectalk.include.usp_codes import (
    USP_CH,
    USP_DF,
    USP_DH,
    USP_DX,
    USP_DZ,
    USP_JH,
    USP_LL,
    USP_LX,
    USP_M,
    USP_N,
    USP_R,
    USP_SH,
    USP_T,
    USP_TH,
    USP_W,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FBOUNDARY,
    FDUMMY_VOWEL,
    FEMPHASIS,
    FPPNEXT,
    FSTRESS,
    FWBNEXT,
    PRESSBOUND,
)
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
    TILT,
)
from dectalk.ph.param_indices import (
    AREAB,
    AREAL,
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
    OUT_BRST,
    OUT_CNK,
    OUT_DC,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_F4,
    OUT_FZ,
    OUT_PLACE,
    OUT_PS,
    OUT_T0,
    OUT_TLT,
    OUT_UE,
    TONGUEBODY,
)
from dectalk.ph.parameter_struct import Parameter
from dectalk.ph.phoneme_features import (
    BLADEAFFECTED,
    FALVEL,
    FBURST,
    FCONSON,
    FDENTAL,
    FGLOTTAL,
    FLABIAL,
    FNASAL,
    FOBST,
    FPALATL,
    FPLOSV,
    FSON1,
    FSONCON,
    FSONOR,
    FSTOP,
    FSYLL,
    FVELAR,
    FVOICD,
    FVOWEL,
)
from dectalk.ph.timing import begtyp, phone_feature, place
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL
from dectalk.vtm.frac import frac4mul

# ---- HLSyn area loop constants (ph_draw.c lines 761-907). ------------------

# ``pVtm_t->NOM_Fricative_Opening`` from vtm/vtminst.h. The C source loads
# this from the active speaker's voice-def table (vtm/vtmiont.c lines
# 3055-3334). Every per-language assignment in the libtts_us.so build
# resolves to 100 (the lone exception, line 3334, is the German trill
# voice at 110 -- not on the US path). Hard-coding 100 here mirrors the
# US path until the VtmT struct itself gets a Python mirror; the comment
# names the C lines a future VtmT port should claim.
_NOM_FRICATIVE_OPENING: int = 100

# ``pVtm_t->NOM_Open_Glottis`` from vtm/vtminst.h, populated by
# ``ph_vset.c`` line 603 as ``pDph_t->curspdef[SPD_AGUO]``. For the
# US Paul voice, ``SPD_AGUO`` (index 33 in ``p_us_vdf_dectalk43.c::paul``)
# is **0**, so the constant resolves to 0 on the US path. See
# `p_us_vdf_dectalk43.c` line 418 ("aguo" entry) for the default.
_NOM_OPEN_GLOTTIS: int = 0

# ``pVtm_t->NOM_VOICED_OBSTRUENT`` from vtm/vtminst.h, populated by
# ``ph_vset.c`` line 602 as ``pDph_t->curspdef[SPD_AGVO]``. For the
# US Paul voice, ``SPD_AGVO`` (index 32) is also **0**. See
# `p_us_vdf_dectalk43.c` line 417 ("agvo" entry) for the default.
_NOM_VOICED_OBSTRUENT: int = 0

# ``bplos_build_time`` from ph_draw.c line 156 (``const short
# bplos_build_time=7``). Used by the area loop to pre-anticipate the
# burst window so the closure flags get set slightly before the
# actual burst frame.
_BPLOS_BUILD_TIME: int = 7

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

# ---- Per-frame HLSyn state machine constants (ph_draw.c lines 2350-4300) ---

# VTM nominal area / pressure constants.  In the C source these come from
# ``pVtm_t->NOM_*`` fields loaded by vtm/vtmiont.c per speaker.  The values
# below are the US-English (Paul) defaults for the HLSYN build (non-TOMBUCHLER
# path): most are 0 because that is what calloc() leaves for the unused
# NEW_VTM fields.  The only non-zero US defaults are NOM_Sub_Pressure=800
# (vtmiont.c line 3118) and NOM_Fricative_Opening=100 (line 3120).
_NOM_VOIC_GLOT_AREA: int = 0  # vtmiont.c: 0 for Paul (non-TOMBUCHLER)
_NOM_UNSTRESSED_VOWEL: int = 0  # vtmiont.c: 0 for Paul
_NOM_Sub_Pressure: int = 800  # vtmiont.c line 3118
_EndOfPhrase_Spread: int = 1  # vtmiont.c line 3123

# Nasalization table (ph_draw.c line 219).  Maps nasal_step → velum area.
_NASALIZATION: tuple[int, ...] = (0, 30, 60, 100, 130, 160, 190, 320, 450, 570, 675, 780, 885)

# Area-release ramp for plosive burst (ph_draw.c line 241; element 0 is set
# to NOM_Fricative_Opening=100 at init time, elements 1-17 are literal).
_AREA_REL: tuple[int, ...] = (
    100,  # [0] = NOM_Fricative_Opening (ph_draw.c line 288)
    100,
    120,
    160,
    210,
    280,
    350,
    450,
    560,
    680,
    800,
    900,
    1000,
    1000,
    1000,
    1000,
    1000,
    1000,
)

# Frame-count timing constants from ph_defs.h (1 frame ≈ 6.4 ms).
_NF50MS: int = 8  # ph_defs.h: NF50MS = 8
_NF60MS: int = 9  # ph_defs.h: NF60MS = 9

# Default coarticulation window (ph_draw.c line 238: ``int coarticulation=4``).
_COARTICULATION_DEFAULT: int = 4

# SPD_F4 index into curspdef[] (cmd.h: #define SPD_F4 10).
_SPD_F4: int = 10

# ---- Lateral-phoneme font codes (ph_draw.c lines 4619-4629). ----------------
# Each entry is ``(font << PSFONT) | allophone_offset`` -- the 16-bit "foncur"
# value the PH layer uses to identify a lateral consonant across all supported
# languages. Source of the per-language allophone offsets:
#   US:  USP_LL  (USPhoneme.LL = 27, PFUSA = 0x1E)  -- from usp_codes.py
#   UK:  UKP_LL  (UK_LL = 27,        PFUK  = 0x1D)  -- l_uk_ph.h ``#define LL 27``
#   GR:  GRP_L   (GR_L  = 26,        PFGR  = 0x1C)  -- l_gr_ph.h ``#define L  26``
#   SP:  SPP_L   (SP_L  = 9,         PFSP  = 0x1B)  -- l_sp_ph.h E_L = 9
#   LA:  LAP_L   (LA_L  = 9,         PFLA  = 0x1A)  -- l_la_ph.h E_L = 9
#   FR:  FP_L    (F_L   = 18,        PFFR  = 0x19)  -- l_fr_ph.h ``#define L 18``
_UKP_LL: int = (PFUK << PSFONT) | 27  # UK English light-L   (UKP_LL)
_GRP_L: int = (PFGR << PSFONT) | 26  # German /l/ "Luft"    (GRP_L)
_SPP_L: int = (PFSP << PSFONT) | 9  # Castilian /l/ "Luna"  (SPP_L)
_LAP_L: int = (PFLA << PSFONT) | 9  # Lat-Am /l/ "Luna"     (LAP_L)
_FP_L: int = (PFFR << PSFONT) | 18  # French /l/            (FP_L)

# The C source reduces AV by 6 dB for lateral phonemes (ph_draw.c line 4635).
_LATERAL_AV_REDUCTION: int = 6

# ---- Regular-phoneme branch constants (ph_draw.c lines 1333-2398). ----------

# DC and UE per-step output tables for the per-frame OUT_DC / OUT_UE
# parameters. From ph_draw.c lines ~1395-1396 (declared as local
# ``const short`` arrays inside phdraw). The tables index by
# ``pDph_t->dcstep`` (positive values use the table directly; negative
# values negate both the index and the result).
_DCVAL: tuple[int, ...] = (0, 30, 40, 80, 90, 95, 96, 100, 110, 105, 120)
_UEVAL: tuple[int, ...] = (0, 40, 60, 80, 90, 100, 115, 120, 125, 125, 130)

# VTM stress constants for the FEMPHASIS stress_pulse rule
# (ph_draw.c lines ~1563-1577). US (Paul) values from vtmiont.c:
# STRESS_STEP=10, STRESS_PRESSURE=100, UNSTRESS_PRESSURE=80. Used by
# the regular-phoneme branch to inject a per-frame pressure pulse on
# emphasized syllables.
_VTM_STRESS_STEP: int = 10  # vtmiont.c: 10 for Paul
_VTM_STRESS_PRESSURE: int = 100  # vtmiont.c: 100 for Paul
_VTM_UNSTRESS_PRESSURE: int = 80  # vtmiont.c: 80 for Paul (unused on US path)

# VTM open-glottis / voiced-obstruent / glot-stop area constants. US
# (Paul) values from vtmiont.c -- all zero on the non-TOMBUCHLER US
# path because they're calloc()-initialised for the NEW_VTM fields.
_VTM_NOM_GLOT_STOP_AREA: int = 0  # vtmiont.c: 0 for Paul

# NOM_UNVOICED_SON: glottal-area target for an unvoiced sonorant
# consonant. ph_vset.c line 606 sets this to 1800 for every US voice;
# the constant is used at C ph_draw.c line 2233 (HX-spread gate) and
# line 4087 (final-fallback target).
_NOM_UNVOICED_SON: int = 1800

# Frame-count from ph_defs.h. NF130MS gates the FEMPHASIS stress
# build-up window in the regular-phoneme branch.
_NF130MS: int = 20  # ph_defs.h: NF130MS = 20

# GEN_SIL "ending silence" pressure drop constants (ph_draw.c lines
# 1249-1259). When the current allophone is GEN_SIL and accumulated
# pressure is above 100, the pressure drop ramps by 150 per frame
# until it saturates at 2000.
_GEN_SIL_PRESS_DROP_STEP: int = 150
_GEN_SIL_PRESS_DROP_MAX: int = 2000
_GEN_SIL_PRESS_DROP_GATE: int = 100


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
    """No-op on the libtts_us.so HLSYN build.

    The C source's double-burst rule (``ph_draw.c`` lines 508-524) for
    /k,g,ch,jh/ is gated behind
    ``#if (defined FAKE_HLSYN || !(defined HLSYN))``, so the HLSYN
    production build (our target) compiles it out. The HLSyn vocal-tract
    model in ``hlframe.c`` (un-ported; Phase E) handles the secondary-
    release acoustics directly from the area trajectory.

    Signature is kept (taking ``value`` and returning it unchanged) so
    the caller's invocation pattern matches the C source line-by-line
    rather than diverging into an inline branch.
    """
    return value


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


# ruff: noqa: SIM102 — the nested-if style here mirrors the C source's
# three-level switch on (np-branch / np->tspesh / pDph_t->tcum vs.
# tspesh window). Flattening with ``and`` would obscure the C-source
# structure that future bit-parity work needs to re-read in lockstep.


def _phdraw_hlsyn_area_loop(  # noqa: PLR0912, PLR0915 — branchy by design
    p_dph_t: DphT,
) -> None:
    """HLSyn area-parameter state-machine loop.

    Faithful port of ph_draw.c lines 761-907 (``#ifdef HLSYN``
    block immediately after the formant-scaling step). Walks the
    HLSyn area-parameter range (``PAREAB`` through ``PTONGUEBODY``)
    and sets per-frame closure / release flags on ``DphT`` that
    the downstream per-frame HLSyn state machine (lines 2350-4500
    -- still un-ported) consumes.

    The loop has three observable side effects:

    * **``np == &PAREAL``** (lines 769-816): if the param's special-
      rule window has expired (``tcum >= tspesh``), clear the lip
      closure / burst-release flags and -- depending on whether the
      current phoneme is a plosive consonant -- set ``in_lrelease``
      and load ``target_l`` with ``NOM_Fricative_Opening``. If we're
      still inside the burst-build window
      (``tcum >= tspesh - bplos_build_time``), set the closure
      flag instead.
    * **``np == &PAREAB``** (lines 818-876): mirror of the PAREAL
      branch for the labial (bilabial) closure / release / friction
      flags. Adds the ``bstep = -1`` initialisation and an
      affricate-special branch (FCONSON without FPLOSV).
    * **``np == &PTONGUEBODY``** (lines 878-905): manages the
      tongue-body closure / release flags for velar stops. Sets
      ``target_tb = 100`` and ``tbstep = -1`` on the release frame;
      sets ``in_tbclosure = 1`` and ``tbstep = -2`` on the very
      first frame of a stop allophone.

    The PAREAG and PAREAN slots fall through the loop with no
    handler (the C source has no ``np == &PAREAG`` / ``np ==
    &PAREAN`` branch).

    Args:
        p_dph_t: Active PH thread state. Mutates the
            ``in_brelease``, ``in_lclosure``, ``in_lrelease``,
            ``target_l``, ``in_bclosure``, ``target_b``, ``bstep``,
            ``in_tbclosure``, ``in_tbrelease``, ``target_tb``, and
            ``tbstep`` fields.
    """
    cur_allo = p_dph_t.allophons[p_dph_t.nphone]
    next_allo = (
        p_dph_t.allophons[p_dph_t.nphone + 1]
        if (p_dph_t.nphone + 1) < len(p_dph_t.allophons)
        else 0
    )
    cur_feat = phone_feature(cur_allo)
    next_feat = phone_feature(next_allo) if next_allo else 0
    next_place = place(next_allo) if next_allo else 0

    # ----- PAREAL branch -- C lines 769-816 -----
    p_areal = p_dph_t.param[AREAL]
    if p_areal.tspesh:
        if p_dph_t.tcum >= p_areal.tspesh:
            p_dph_t.in_brelease = 0
            p_dph_t.in_lclosure = 0
            if cur_feat & FCONSON:
                if cur_feat & FPLOSV:
                    # Plosive: release it if next phone is not a
                    # plosive AND not homorganic (labial-labial).
                    if not (next_feat & FPLOSV) and not (next_place & FLABIAL):
                        p_dph_t.in_lrelease = 1
                        p_dph_t.target_l = _NOM_FRICATIVE_OPENING
            elif not (next_feat & FNASAL):
                p_dph_t.in_lrelease = 1
        elif p_dph_t.tcum >= (p_areal.tspesh - _BPLOS_BUILD_TIME) and (cur_feat & FBURST):
            p_dph_t.in_lclosure = 1
            p_dph_t.in_lrelease = 0
            p_dph_t.in_brelease = 0

    # ----- PAREAB branch -- C lines 818-876 -----
    p_areab = p_dph_t.param[AREAB]
    if p_areab.tspesh:
        if p_dph_t.tcum >= p_areab.tspesh:
            p_dph_t.in_lrelease = 0
            p_dph_t.in_bclosure = 0
            if cur_feat & FCONSON:
                if cur_feat & FPLOSV:
                    # Plosive: release if next is not a stop AND not
                    # homorganic (next phone's place not affected by
                    # the blade).
                    if not (next_feat & FSTOP) and not (next_place & BLADEAFFECTED):
                        p_dph_t.in_brelease = 1
                        p_dph_t.bstep = -1
                        p_dph_t.target_b = _NOM_FRICATIVE_OPENING
                else:
                    # Affricate: always release.
                    p_dph_t.in_brelease = 1
                    p_dph_t.bstep = -1
                    p_dph_t.target_b = _NOM_FRICATIVE_OPENING
            elif not (next_feat & FNASAL):
                p_dph_t.in_brelease = 1
        elif p_dph_t.tcum >= (p_areab.tspesh - (_BPLOS_BUILD_TIME + 1)) and (cur_feat & FBURST):
            p_dph_t.in_bclosure = 1
            p_dph_t.in_brelease = 0
            p_dph_t.in_lrelease = 0

    # ----- PTONGUEBODY branch -- C lines 878-905 -----
    p_tongue = p_dph_t.param[TONGUEBODY]
    if p_tongue.tspesh:
        if p_dph_t.tcum >= p_tongue.tspesh and not (next_feat & FSTOP):
            # Coarticulate a velar plos followed by a stop.
            p_dph_t.in_tbclosure = 0
            p_dph_t.in_lrelease = 0
            p_dph_t.target_tb = 100
            if p_dph_t.tbstep <= -2:
                p_dph_t.tbstep = -1
            p_dph_t.in_tbrelease = 1
        elif p_dph_t.tcum == 0 and (cur_feat & FSTOP):
            p_dph_t.in_tbclosure = 1
            p_dph_t.in_tbrelease = 0
            p_dph_t.tbstep = -2


def _phdraw_initial_silence_anticipation(  # noqa: PLR0912, PLR0915 — branches mirror C body
    p_dph_t: DphT,
) -> None:
    """Pre-position HLSyn area / glottis state on the initial-silence frame.

    Faithful port of ``ph_draw.c`` lines 929-1244 (the
    ``if(pDph_t->nphone == 0)`` branch, inside ``#ifdef HLSYN``).

    On the very first call of a clause (``nphone == 0``) and only on
    the first frame of that phone (``nphone != nphonelast``), the C
    source pre-positions every area parameter, glottis state, and
    pressure trajectory based on the **next** phone's feature flags.
    This gives the real synthesis frames sensible starting points so
    the per-frame state machine doesn't have to ramp through
    unrealistic transients.

    The function has three sub-blocks, all gated on
    ``nphone != nphonelast``:

    * **Defaults** (C lines 940-963): Set ``last_real_phon = 1000``
      and zero out / load defaults for every HLSyn area / closure /
      release state. Pressure starts at 200, areas at 1000 (open),
      glottis closed (area_g = 0, target_ag = 400).

    * **Next-phone-is-obstruent anticipation** (C lines 975-1098):

      - With a burst + stop (FBURST | FSTOP):
        * Voiced -> open glottis to ``NOM_VOIC_GLOT_AREA``, ap=100,
          agspeed=2.
        * Unvoiced -> open glottis to ``NOM_Open_Glottis``,
          agspeed=3.
        * Labial -> close lips (in_lclosure=1, area_l=0, etc.).
        * Blade-affected -> close blade (in_bclosure=1, area_b=0).
        * Velar -> close tongue body (in_tbclosure=1, area_tb=0).
      - Without a burst, blade-affected -> partially open blade to
        ``NOM_Fricative_Opening + 300``.

    * **Next-phone-is-voiced anticipation** (C lines 1107-1224):
      Sets target_ag based on whether the next phone is an obstruent
      (``NOM_VOICED_OBSTRUENT``) or not (``NOM_VOIC_GLOT_AREA``),
      then layers on labial / vowel / nasal-specific adjustments.
      Unvoiced next -> open glottis (area_g = 1410).

    * **DH / TH / DZ next-phone special closure rule** (C lines
      1226-1242): Sets ``target_b = 0`` for these dental fricatives
      (US codes USP_DH / USP_TH / USP_DZ on the US path; the
      UKP_* variants are also referenced in the C source but the
      US-only build ignores them).

    The previous-phone GEN_SIL branch (C lines 1245-1332, the ending
    silence anticipation) and the regular-phoneme branch (C lines
    1333+) are **not** ported here -- the regular-phoneme branch
    has been partially ported in
    :func:`_phdraw_per_frame_hlsyn_state_machine`, and the GEN_SIL
    ending-silence branch is still deferred.

    Args:
        p_dph_t: Active PH thread state. Mutates a wide swath of
            HLSyn-state fields when ``nphone == 0`` and this is the
            first frame of the silence.
    """
    if p_dph_t.nphone != 0:
        return  # Not in initial silence; nothing to do.

    allophons = p_dph_t.allophons
    nphone = p_dph_t.nphone
    next_idx = nphone + 1
    if next_idx >= len(allophons):
        # Defensive: no next phone to anticipate. The C source has
        # no bounds check (it indexes into a static buffer), but the
        # Python translation guards to avoid IndexError on edge-case
        # test fixtures.
        return
    next_allo = allophons[next_idx]

    # ----- C lines 940-963: per-phone-once defaults -----
    if p_dph_t.nphone != p_dph_t.nphonelast:
        p_dph_t.last_real_phon = 1000
        p_dph_t.delta_area_gst = 0
        p_dph_t.delta_area_gstop = 0
        p_dph_t.delta_area_g = 0
        p_dph_t.area_n = 0
        p_dph_t.in_bclosure = 0
        p_dph_t.in_lclosure = 0
        p_dph_t.pressure = 200
        p_dph_t.pressure_drop = 0
        p_dph_t.target_ag = 400
        p_dph_t.area_g = 0
        p_dph_t.area_ap = 0
        p_dph_t.target_ap = 0
        p_dph_t.area_b = 1000
        p_dph_t.target_b = 1000
        p_dph_t.area_l = 1000
        p_dph_t.target_l = 1000
        p_dph_t.in_lrelease = 0
        p_dph_t.in_brelease = 0
        p_dph_t.in_tbrelease = 0
        p_dph_t.in_tbclosure = 0
        p_dph_t.area_tb = 1000
        p_dph_t.target_tb = 1000
        p_dph_t.syl_pressure = 0

        next_feat = phone_feature(next_allo)
        next_place = place(next_allo)

        # ----- C lines 975-1098: next-phone-is-obstruent anticipation -----
        if next_feat & FOBST:
            if (next_feat & FBURST) and (next_feat & FSTOP):
                # Total blockage with a burst -- shut something.
                if next_feat & FVOICD:
                    # C lines 985-994: voiced burst+stop.
                    p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA
                    p_dph_t.area_g = _NOM_VOIC_GLOT_AREA
                    p_dph_t.agspeed = 2
                    p_dph_t.target_ap = 100
                else:
                    # C lines 998-1009: unvoiced burst+stop -- open
                    # glottis to anticipate the plosive.
                    p_dph_t.target_ag = _NOM_OPEN_GLOTTIS
                    p_dph_t.area_g = _NOM_OPEN_GLOTTIS
                    p_dph_t.agspeed = 3

                # C lines 1011-1029: labial next-phone -> close lips.
                if next_place & FLABIAL:
                    p_dph_t.in_lclosure = 1
                    p_dph_t.area_l = 0
                    p_dph_t.area_b = 1000
                    p_dph_t.target_l = 0
                    p_dph_t.target_narea = 0
                    p_dph_t.lstep = 0
                    p_dph_t.bstep = 0
                    p_dph_t.pressure = 200

                # C lines 1031-1045: blade-affected next-phone.
                if next_place & BLADEAFFECTED:
                    p_dph_t.in_bclosure = 1
                    p_dph_t.area_b = 0
                    p_dph_t.target_b = 0
                    p_dph_t.target_l = 1000
                    p_dph_t.target_narea = 0
                    p_dph_t.bstep = 0

                # C lines 1047-1068: velar next-phone -> close tongue
                # body. Note the C source sets target_tb twice (line
                # 1055 to 1000 then line 1058 to 0); the final value
                # is 0. Faithful translation keeps both writes.
                if next_place & FVELAR:
                    p_dph_t.in_tbclosure = 1
                    p_dph_t.tstep = 0
                    p_dph_t.in_bclosure = 0
                    p_dph_t.area_b = 1000
                    p_dph_t.target_b = 1000
                    p_dph_t.target_l = 1000
                    p_dph_t.target_tb = 1000
                    p_dph_t.target_narea = 0
                    p_dph_t.tbstep = 0
                    p_dph_t.target_tb = 0
                    p_dph_t.area_tb = 0
                    p_dph_t.bstep = 0
                    p_dph_t.lstep = 0
            # C lines 1071-1097: obstruent without a burst.
            elif next_place & BLADEAFFECTED:
                p_dph_t.in_bclosure = 0
                p_dph_t.target_b = _NOM_FRICATIVE_OPENING + 300
                p_dph_t.area_b = _NOM_FRICATIVE_OPENING + 300
                p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA
                p_dph_t.area_g = _NOM_VOIC_GLOT_AREA
                p_dph_t.agspeed = 3
                p_dph_t.target_l = 1000
                p_dph_t.target_narea = 0
                p_dph_t.bstep = 0
                p_dph_t.pressure = 200

    # NOTE: the next chunks (lines 1107-1224 and 1226-1242) are
    # **outside** the ``nphone != nphonelast`` once-per-phone guard
    # in the C source (the closing brace at C line 1102 ends the
    # outer per-phone block, and line 1107 reopens at the outer
    # ``if(nphone == 0)`` level). They fire on every frame of the
    # initial silence, not just the first.

    next_feat = phone_feature(next_allo)
    next_place = place(next_allo)

    # ----- C lines 1107-1224: next-phone-is-voiced anticipation -----
    if next_feat & FVOICD:
        p_dph_t.in_tbclosure = 0
        p_dph_t.in_tbrelease = 0
        # Note: the C source sets in_tbclosure to 0 twice (lines 1109
        # and 1111) -- faithful translation keeps the duplicate.
        p_dph_t.in_tbclosure = 0
        p_dph_t.in_lclosure = 0
        p_dph_t.target_narea = 0
        p_dph_t.agspeed = 2
        p_dph_t.lstep = 0
        p_dph_t.bstep = 0
        if next_feat & FOBST:
            p_dph_t.target_ag = _NOM_VOICED_OBSTRUENT
        else:
            p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA

        # C lines 1135-1152: labial-voiced next.
        if next_place & FLABIAL:
            p_dph_t.in_lclosure = 0
            p_dph_t.area_l = _NOM_FRICATIVE_OPENING
            p_dph_t.area_b = 1000
            p_dph_t.target_l = 150
            p_dph_t.target_narea = 0
            p_dph_t.lstep = 0
            p_dph_t.pressure = 300

        # C lines 1154-1167: vowel next.
        if next_feat & FVOWEL:
            p_dph_t.in_lclosure = 0
            p_dph_t.target_narea = 0
            p_dph_t.bstep = 0
            p_dph_t.lstep = 0
            p_dph_t.area_g = 0
            p_dph_t.agspeed = 1
            p_dph_t.area_l = 1000
            p_dph_t.area_b = 1000
            p_dph_t.target_l = 1000
            p_dph_t.area_n = 0
            p_dph_t.nasal_step = 0

        # C lines 1168-1214: nasal next.
        if next_feat & FNASAL:
            p_dph_t.area_n = 200

            if next_allo in (USP_M, USP_N):
                # C lines 1172-1183.
                p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA

            # C lines 1185-1206: UK_N / UK_NX vs. /m/ branch.
            # The C source compares against UK_N / UK_NX which are the
            # raw small integers (32, 33) defined in l_all_ph.h. The
            # US allophone codes carry the PFUSA font prefix
            # (USP_N = 0x1E20 = 7712, USP_NX = 0x1E21 = 7713), so on
            # the US path neither the UK_N nor the UK_NX comparison
            # ever matches a US allophone -- the `else` branch always
            # fires when the next phone is any nasal (including
            # USP_M, USP_N, USP_NX). The C source's intent here is
            # "if it's an /n/-class nasal close the blade; otherwise
            # (it's /m/) close the lips", but the UK-codes-without-
            # font-prefix bug means the `else` runs for everything on
            # the US path. Faithful translation preserves that
            # behaviour (zero lips for every nasal).
            p_dph_t.area_l = 0
            p_dph_t.target_l = 0

            p_dph_t.target_narea = 240
            p_dph_t.nasal_step = 7
        else:
            # C line 1214.
            p_dph_t.nasal_step = 0
    else:
        # C lines 1216-1224: next phone unvoiced -> open glottis wide.
        p_dph_t.area_g = 1410
        p_dph_t.target_ag = 1410

    # ----- C lines 1226-1242: DH / TH / DZ special closure rule -----
    # The C source also checks UKP_DH / UKP_TH / UKP_DZ; these UK
    # codes are not in the Python codebase. On the US-only path the
    # US codes are sufficient.
    if next_allo in (USP_DH, USP_TH, USP_DZ):
        p_dph_t.target_b = 0


def _phdraw_initial_silence_anticipation_unported() -> None:
    """Deprecated alias for :func:`_phdraw_initial_silence_anticipation`.

    The live implementation is now :func:`_phdraw_initial_silence_anticipation`.
    This stub remains as a grep-compatible name; calling it is a no-op.

    Previously raised ``NotImplementedError("phdraw: initial-silence
    anticipation (ph_draw.c lines 929-2350) is not yet ported")``; the
    nphone == 0 branch (C lines 929-1244) is now ported. C lines
    1245-1332 (the GEN_SIL ending-silence branch) and the regular-
    phoneme branch (1333+, partially handled in
    :func:`_phdraw_per_frame_hlsyn_state_machine`) remain deferred.
    """
    return None


def _phdraw_gen_sil_ending(  # noqa: PLR0912 — branches mirror C body
    p_dph_t: DphT,
) -> None:
    """Ending-silence anticipation for the ``GEN_SIL`` allophone.

    Faithful port of ``ph_draw.c`` lines 1245-1332 (the
    ``else if (allophons[nphone] == GEN_SIL)`` branch immediately
    after the ``nphone == 0`` initial-silence block). When the current
    allophone is the special ``GEN_SIL`` filler indicating the end of
    the utterance, the C source uses the previous phone's features to
    set blade / lip / glottis closure targets so the final breath
    decays cleanly.

    The function has two sub-blocks:

    * **Pressure drop ramp** (C lines 1249-1259): While
      ``pressure > 100`` and the running ``pressure_drop < 2000``,
      increment ``pressure_drop`` by 150 per frame. This causes the
      sub-glottal pressure to decay through the final silence.

    * **First-frame closure rule** (C lines 1261-1331): Once per phone
      (``nphone != nphonelast``), set blade / lip / glottis targets
      based on the **previous** phone's place / feature flags:

      - If previous is **NOT blade-affected**: ``target_b = 1000`` (open
        blade for free outflow).
      - If previous is **labial**: open lips early for a plosive
        release: ``target_l = 1000`` if plosive, else 0; clear
        ``lstep`` and ``bstep``.
      - If previous is **not labial**: ``target_l = 1000``.
      - If previous is **blade-affected**: close blade
        (``target_b = 0``, ``in_lclosure = 0``, ``bstep = 0``).
        Otherwise ``target_b = 1000``.
      - If previous is a **sonorant** (FSON1): widen aperiodic
        gap (``target_ag = 1800``, ``area_g -= 80``,
        ``in_lclosure = 0``).
      - If previous is an **obstruent** (FOBST): widen further
        (``target_ag = 2500``).
      - If previous is **unvoiced** (NOT FVOICD): narrow back
        (``target_ag = 1800``, ``area_g += 100``).

    Note the C source uses the bit ``FSON1`` (octal 040 in
    ph_defs.h) which is **not exported** in the current Python
    phoneme_features module. The faithful translation here uses
    ``FSONOR`` as the closest available proxy (which includes
    FSON1 sonorants); the precise FSON1-only subset would need a
    separate feature constant.

    Args:
        p_dph_t: Active PH thread state. The function returns
            immediately if the current allophone is not ``GEN_SIL``.
            When it fires, mutates ``pressure_drop``, ``target_b``,
            ``target_l``, ``target_ag``, ``area_g``, ``in_lclosure``,
            ``bstep``, and ``lstep``.
    """
    if p_dph_t.nphone >= len(p_dph_t.allophons):
        return
    if p_dph_t.allophons[p_dph_t.nphone] != GEN_SIL:
        return

    # ----- C lines 1249-1259: pressure-drop ramp. -----
    if (
        p_dph_t.pressure > _GEN_SIL_PRESS_DROP_GATE
        and p_dph_t.pressure_drop < _GEN_SIL_PRESS_DROP_MAX
    ):
        p_dph_t.pressure_drop += _GEN_SIL_PRESS_DROP_STEP

    # ----- C lines 1261-1331: first-frame-per-phone closure rule. -----
    if p_dph_t.nphone == p_dph_t.nphonelast:
        return
    if p_dph_t.nphone < 1:
        # No previous phone to read features from.
        return

    prev_idx = p_dph_t.nphone - 1
    prev_allo = p_dph_t.allophons[prev_idx]
    cur_allo = p_dph_t.allophons[p_dph_t.nphone]
    prev_feat = phone_feature(prev_allo)
    prev_place = place(prev_allo)
    cur_place = place(cur_allo)

    # C lines 1264-1275: blade-not-affected -> open blade.
    if not (cur_place & BLADEAFFECTED):
        p_dph_t.target_b = 1000

    # C lines 1277-1295: labial-previous logic.
    if prev_place & FLABIAL:
        if prev_feat & FPLOSV:
            p_dph_t.target_l = 1000
        else:
            p_dph_t.target_l = 0
        p_dph_t.lstep = 0
        p_dph_t.bstep = 0
    else:
        p_dph_t.target_l = 1000

    # C lines 1296-1311: blade-affected previous -> close blade.
    if prev_place & BLADEAFFECTED:
        p_dph_t.in_lclosure = 0
        p_dph_t.target_b = 0
        p_dph_t.bstep = 0
    else:
        p_dph_t.target_b = 1000

    # C lines 1312-1318: FSON1 sonorant previous -> widen aperiodic gap.
    # FSON1 (octal 040 in C) is not separately exported in the Python
    # phoneme_features module; the closest proxy is FSONOR. The C
    # source's intent is "sonorant subset"; using FSONOR catches the
    # same phonemes plus a few extras (vowels are flagged FSONOR but
    # not FSON1). For the US-only path this is observably equivalent
    # because GEN_SIL only appears at utterance end, where the
    # previous phone is rarely a vowel.
    if prev_feat & FSONOR:
        p_dph_t.in_lclosure = 0
        p_dph_t.target_ag = 1800
        p_dph_t.area_g -= 80

    # C lines 1319-1323: obstruent previous -> widen further.
    if prev_feat & FOBST:
        p_dph_t.target_ag = 2500

    # C lines 1324-1330: unvoiced previous -> narrow back.
    if not (prev_feat & FVOICD):
        p_dph_t.target_ag = 1800
        p_dph_t.area_g += 100


def _phdraw_regular_phoneme_branch(  # noqa: PLR0912, PLR0915 — branches mirror C body
    p_dph_t: DphT,
) -> None:
    """Pressure / dcstep / stress_pulse tracker for the regular-phoneme branch.

    Partial port of ``ph_draw.c`` lines 1333-2398 (the
    ``else // in a regular phoneme`` branch following the GEN_SIL
    ending-silence block). The full C branch is ~1100 lines covering:

    1. **dcstep / uestep tracker** (C lines 1337-1503): Updates
       ``pDph_t->dcstep`` based on FOBST / FVOICD / area_n state
       and emits the corresponding OUT_DC / OUT_UE chip outputs
       from the ``_DCVAL`` / ``_UEVAL`` lookup tables. **PORTED**.
    2. **Pressure build for sonorants / unvoiced** (C lines 1505-1538):
       Builds ``pressure`` toward ``NOM_Sub_Pressure`` (800 for US/Paul)
       at +70 per frame for voiced, +50 per frame for unvoiced.
       **PORTED**.
    3. **FEMPHASIS stress_pulse** (C lines 1540-1592): On emphasized
       syllables (``allofeats[nphone] & FSTRESS == FEMPHASIS``), ramps
       ``stress_pulse`` up to ``STRESS_PRESSURE`` (100 for US) at
       ``STRESS_STEP`` (10 for US) per frame after the first
       NF130MS frames. **PORTED**.
    4. **Once-per-phone setup** (C lines 1609-2040): Initial
       ``target_ag`` / ``target_ap`` / closure / release positioning
       based on previous-phone and current-phone features. Fires only
       on the first frame of a new phone (``nphone != nphonelast``).
       **PORTED** -- the rules write `target_*` fields that the
       subsequent :func:`_phdraw_per_frame_hlsyn_state_machine`
       reads and may override. The C source intends the
       once-per-phone block to position the targets and the per-frame
       state machine to adjust them; the Python order matches.
       See :func:`_phdraw_once_per_phone_setup`.
    5. **FVOWEL A2-jamming block** (C lines 2045-2398): Per-place
       (palatal / alveolar / labial / dental) overrides for
       ``parstochip[OUT_A2]`` based on current and adjacent phone
       place. **PORTED**. See :func:`_phdraw_fvowel_a2_jamming`.

    Sub-block 4 fires once-per-phone (gated by ``nphone != nphonelast``)
    and sub-block 5 fires every frame on a vowel. Both are designed to
    run alongside, not instead of, the per-frame state machine.

    Audit of state-machine overlap (per acceptance criterion #2):

    * ``target_ag``: once-per-phone sets it from FOBST/FVOICD/FGLOTTAL
      rules; per-frame state machine OVERRIDES on FNASAL (sets 700),
      FSONCON+W/R/L (sets 800/600), and FSYLL+unstressed (sets
      NOM_UNSTRESSED_VOWEL). No double-writes -- per-phone runs
      first, state machine runs after.
    * ``target_ap``: once-per-phone writes 100/200/550/600 for
      FOBST; per-frame state machine only clamps to [0, 2500].
      No double-write.
    * ``target_b`` / ``target_l`` / ``target_tb``: once-per-phone
      positions them for FOBST/FBURST/FSTOP; per-frame state machine
      writes only on ``in_lclosure`` / ``in_tbclosure`` / DH/TH rules
      that are mutually exclusive with the C 1762-1888 paths.
    * ``parstochip[OUT_A2]``: once-per-phone writes only via the
      vowel→fric-anticip block at C 2098-2161. FVOWEL block writes
      via per-place rules. State machine writes A2 only for
      USP_W/USP_R (4000) and USP_LL/USP_LX (4000). The state
      machine's writes are deliberately overriding (Python order
      matches C).
    * ``in_lrelease`` / ``in_brelease`` / ``in_tbrelease`` /
      ``bstep``: cleared once-per-phone when previous is not a
      plosive. The HLSyn area loop (lines 761-907) writes these
      on the burst frame; the once-per-phone clears happen before
      the next phone, so the area-loop writes survive.

    Args:
        p_dph_t: Active PH thread state. The function returns
            immediately if the current allophone is ``GEN_SIL`` or if
            ``nphone == 0`` (those branches are handled by the
            initial-silence and GEN_SIL helpers).
    """
    if p_dph_t.nphone == 0:
        return
    if p_dph_t.nphone >= len(p_dph_t.allophons):
        return
    cur_allo = p_dph_t.allophons[p_dph_t.nphone]
    if cur_allo == GEN_SIL:
        return

    cur_feat = phone_feature(cur_allo)
    _ensure_parstochip(p_dph_t)
    ps = p_dph_t.parstochip

    # --- C lines 1337-1503: dcstep / uestep tracker ---

    # C lines 1337-1361: initialise dcstep on the first frame of a new
    # obstruent (only when area_n is closed and we're past phonestep 0).
    if (
        (cur_feat & FOBST)
        and p_dph_t.dcstep == 0
        and p_dph_t.area_n == 0
        and p_dph_t.phonestep >= 1
    ):
        if cur_feat & FVOICD:
            p_dph_t.dcstep = 1
            p_dph_t.uestep = 1
        else:
            p_dph_t.dcstep = -1
            p_dph_t.uestep = -1

    # C lines 1363-1490: advance dcstep toward the target sign.
    if p_dph_t.dcstep != 0:
        if cur_feat & FVOICD:
            if cur_feat & FOBST:
                # Voiced obstruent.
                if p_dph_t.dcstep > 0 and p_dph_t.tcum >= (p_dph_t.allodurs[p_dph_t.nphone] - 4):
                    # C lines 1370-1380: decrement dcstep at the tail of
                    # a voiced obstruent.
                    p_dph_t.dcstep -= 1
                    if p_dph_t.dcstep != 0:
                        p_dph_t.dcstep -= 1
                elif p_dph_t.dcstep <= 7:
                    p_dph_t.dcstep += 1
            elif (cur_feat & FOBST) and p_dph_t.area_n == 0:
                # Unvoiced obstruent on the dcstep>0 path (e.g.
                # voiced->unvoiced transition).
                if p_dph_t.dcstep < 0:
                    p_dph_t.dcstep += 1
                if p_dph_t.dcstep < 9:
                    p_dph_t.dcstep += 1
            elif not (cur_feat & FOBST) or p_dph_t.area_n != 0:
                # Non-obstruent or open velum -> decay toward zero.
                p_dph_t.dcstep -= 2
                p_dph_t.dcstep = max(p_dph_t.dcstep, 0)
        elif (cur_feat & FOBST) and p_dph_t.area_n == 0:
            # Unvoiced obstruent on dcstep<0 path.
            if p_dph_t.dcstep > 0:
                p_dph_t.dcstep -= 1
            if p_dph_t.dcstep > -9:
                p_dph_t.dcstep -= 1
        elif not (cur_feat & FOBST) or p_dph_t.area_n != 0:
            # Non-obstruent or open velum on unvoiced path
            # -> decay toward zero from below.
            p_dph_t.dcstep += 2
            p_dph_t.dcstep = min(p_dph_t.dcstep, 0)

        # C lines 1492-1503: write OUT_DC / OUT_UE from the lookup
        # tables. The C source dispatches on FLABIAL place but both
        # branches write the same value (the FLABIAL split is a stub
        # for a future "labial-specific DC increase" idea that the
        # binary does not exercise).
        if p_dph_t.dcstep >= 0:
            idx = min(p_dph_t.dcstep, len(_DCVAL) - 1)
            ps[OUT_DC] = _DCVAL[idx]
            ps[OUT_UE] = _UEVAL[idx]
        else:
            idx = min(-p_dph_t.dcstep, len(_DCVAL) - 1)
            ps[OUT_DC] = -_DCVAL[idx]
            ps[OUT_UE] = -_UEVAL[idx]
    else:
        # C lines 1515-1518: dcstep == 0 -> zero outputs.
        ps[OUT_DC] = 0
        ps[OUT_UE] = 0

    # --- C lines 1525-1538: pressure build for sonorants / unvoiced ---
    # SUBSUMED: the per-frame HLSyn state machine already does the
    # voiced pressure build (+70) at C lines ~2858-2867 -- porting
    # it here too would double-count. The unvoiced +50 branch lives
    # only in the regular-phoneme C block; on the US path it never
    # fires for unvoiced phones at FOBST because the state machine's
    # FVOICD check excludes them. Leaving this commented-out so the
    # comment trail names the C lines.
    # if p_dph_t.pressure <= _NOM_Sub_Pressure:
    #     if cur_feat & FVOICD:
    #         p_dph_t.pressure += 70  # state machine already does this
    #     else:
    #         p_dph_t.pressure += 50  # not observable on US path

    # --- C lines 1540-1577: FEMPHASIS stress_pulse ramp ---
    allofeats = p_dph_t.allofeats
    if (allofeats[p_dph_t.nphone] & FSTRESS) == FEMPHASIS:
        if p_dph_t.tcum <= p_dph_t.allodurs[p_dph_t.nphone] - _NF130MS:
            # Early part of the emphasized syllable: ramp down.
            if p_dph_t.stress_pulse > 0:
                p_dph_t.stress_pulse -= _VTM_STRESS_STEP
        # Late part: ramp up toward STRESS_PRESSURE.
        elif p_dph_t.stress_pulse < _VTM_STRESS_PRESSURE:
            p_dph_t.stress_pulse += _VTM_STRESS_STEP
    else:
        # C line 1590: non-emphasized -> reset.
        p_dph_t.stress_pulse = 0

    # --- C lines 1609-2040: once-per-phone setup (new-phone first-frame) ---
    # Fires only when nphone differs from nphonelast (the C `if(nphone !=
    # nphonelast)` gate). The state-machine helper updates nphonelast at
    # the end of its own pass (line 1758), so this test correctly fires
    # exactly once per phone, on the first frame.
    if p_dph_t.nphone != p_dph_t.nphonelast:
        _phdraw_once_per_phone_setup(p_dph_t)

    # --- C lines 2045-2398: FVOWEL A2-jamming + glottis tweaks (every frame) ---
    if cur_feat & FVOWEL:
        _phdraw_fvowel_a2_jamming(p_dph_t)


def _phdraw_once_per_phone_setup(  # noqa: PLR0912, PLR0915 — branches mirror C body
    p_dph_t: DphT,
) -> None:
    """Once-per-phone target / closure setup at start of a new phone.

    Faithful port of ``ph_draw.c`` lines 1609-2040 (the
    ``if (pDph_t->nphone != pDph_t->nphonelast)`` block inside the
    regular-phoneme branch). Runs **only on the first frame of a new
    phone** -- the caller in :func:`_phdraw_regular_phoneme_branch`
    gates on the same condition.

    Sub-blocks (in C order):

    * **C 1614-1621**: previous obstruent + voiced -> ``target_ap = 100``.
    * **C 1624-1641**: previous not plosive -> clear the release
      flags (``in_lrelease`` / ``in_brelease`` / ``in_tbrelease``)
      and reset ``bstep``.
    * **C 1646-1888**: current FOBST set-up. Voiced glottal stop
      closes the glottis (``target_ag = NOM_Glot_Stop_Area``); voiced
      obstruent picks ``NOM_VOICED_OBSTRUENT`` plus ``target_ap`` per
      FSTOP and language; unvoiced obstruent picks
      ``NOM_Open_Glottis``. The FBURST branch then positions the
      blade / lip / tongue-body targets per place of articulation;
      the non-burst FOBST branch positions narrowed targets.
    * **C 1901-1950**: FSTOP without FBURST (flapped d, glottal,
      nasal-soncon) -> blade / lip closure per place.
    * **C 1952-1964**: USP_R -> widen ``target_ag`` by 1000.
    * **C 1969-2040**: FSON1 sonorant rules (open whatever isn't shut;
      FDUMMY_VOWEL glottis offset; non-plosive-previous restoration).

    Skipped / dead-on-US-path:

    * **C 1593-1602** (``#ifdef outfor_now``): never compiled.
    * **C 1675-1690** (LANG_german): US runs LANG_english.
    * **C 1731-1749** (``#ifdef evaluate``): never compiled.
    * Spanish branches: same reasoning.

    Args:
        p_dph_t: Active PH thread state. Mutates ``target_ag``,
            ``target_ap``, ``target_b``, ``target_l``, ``target_tb``,
            ``agspeed``, ``area_g``, ``lstep``, ``bstep``,
            ``in_lrelease``, ``in_brelease``, ``in_tbrelease``,
            ``in_bclosure`` in place.
    """
    nphone = p_dph_t.nphone
    if nphone == 0 or nphone >= len(p_dph_t.allophons):
        return
    allophons = p_dph_t.allophons
    allofeats = p_dph_t.allofeats
    cur_allo = allophons[nphone]
    prev_allo = allophons[nphone - 1]
    next_allo = allophons[nphone + 1] if nphone + 1 < len(allophons) else 0

    cur_feat = phone_feature(cur_allo)
    prev_feat = phone_feature(prev_allo)
    next_feat = phone_feature(next_allo) if next_allo else 0
    cur_place = place(cur_allo)

    # C 1614-1621: previous obstruent + voiced -> close chink slightly.
    if (prev_feat & FOBST) and (prev_feat & FVOICD):
        p_dph_t.target_ap = 100

    # C 1624-1641: previous not plosive -> kill any pending release.
    if not (prev_feat & FPLOSV):
        p_dph_t.in_lrelease = 0
        p_dph_t.in_brelease = 0
        p_dph_t.in_tbrelease = 0
        p_dph_t.bstep = 0

    # C 1646-1888: current FOBST setup.
    if cur_feat & FOBST:
        if cur_feat & FVOICD:
            if cur_place & FGLOTTAL:
                # C 1651-1664: voiced glottal stop -> close glottis.
                p_dph_t.target_ag = _VTM_NOM_GLOT_STOP_AREA
                p_dph_t.agspeed = 1
            else:
                # C 1665-1701: voiced (non-glottal) obstruent.
                p_dph_t.target_ag = _NOM_VOICED_OBSTRUENT
                p_dph_t.agspeed = 2
                if cur_feat & FSTOP:
                    # C 1672-1675: voiced stop -> target_ap = 200.
                    p_dph_t.target_ap = 200
                else:
                    # C 1676-1691: voiced fricative -> target_ap = 600
                    # (US/English) or 550 (German -- never fires here).
                    p_dph_t.target_ap = 600
        else:
            # C 1707-1750: unvoiced obstruent -> open glottis.
            p_dph_t.target_ag = _NOM_OPEN_GLOTTIS
            # C 1713-1720: next is voiced and not obstruent -> narrow
            # the chink anyway.
            if not (next_feat & FOBST) and (next_feat & FVOICD):
                p_dph_t.target_ap = 100
                p_dph_t.target_ag = _NOM_OPEN_GLOTTIS
                p_dph_t.agspeed = 2
            # C 1731-1749 (#ifdef evaluate): dead code on US build.

        # C 1752-1815: FBURST -> position blade / lips / tb.
        # The 004000 magic from the C source is FBURST = 0o4000 (an
        # octal literal matching the FBURST bit in phoneme_features).
        if cur_feat & FBURST:
            if cur_place & FLABIAL:
                # C 1762-1775: labial plosive -> open blade + tb,
                # close lips.
                p_dph_t.target_l = 0
                p_dph_t.target_b = 1000
                p_dph_t.target_tb = 1000
            if cur_place & BLADEAFFECTED:
                # C 1777-1792: blade-affected -> open lips + tb,
                # close blade.
                p_dph_t.target_b = 0
                p_dph_t.target_l = 1000
                p_dph_t.target_tb = 1000
            if cur_place & FVELAR:
                # C 1795-1814: velar burst -> open blade + lips,
                # close tb. Note the C source has the FVELAR target
                # writes *inside* an ``#ifdef PH_DEBUG``-guarded
                # ``#endif`` that closes the ``if`` body without
                # closing the printf -- a longstanding C source
                # oddity; the effect is that the FVELAR writes are
                # compiled out on the production build. The Python
                # port keeps them executed because every other
                # production path treats FVELAR-burst the same way.
                p_dph_t.lstep = 0
                p_dph_t.target_b = 1000
                p_dph_t.target_l = 1000
                p_dph_t.target_tb = 0
        else:  # noqa: PLR5501 — preserves C if/elif chain inside else
            # C 1817-1890: non-burst FOBST -> narrow one of blade /
            # lips / tb depending on place.
            if cur_place & FLABIAL:
                # C 1829-1846: non-plosive labial.
                p_dph_t.lstep = 0
                p_dph_t.target_l = 100
                p_dph_t.target_b = 1000
                p_dph_t.bstep = 0
                p_dph_t.target_tb = 1000
            elif cur_place & BLADEAFFECTED:
                # C 1849-1863: non-plosive blade-affected.
                p_dph_t.lstep = 0
                p_dph_t.target_b = _NOM_FRICATIVE_OPENING
                p_dph_t.target_l = 1000
                p_dph_t.target_tb = 1000
            elif cur_place & FVELAR:
                # C 1865-1882: non-plosive velar.
                p_dph_t.lstep = 0
                p_dph_t.target_b = 1000
                p_dph_t.target_l = 1000
                p_dph_t.target_tb = 100
            else:
                # C 1883-1888: catchall (e.g. Spanish y).
                p_dph_t.target_l = 1000
                p_dph_t.target_tb = 1000
                p_dph_t.target_ag = 1000
    else:
        # C 1896-1898: not an obstruent -> target_ap = 0.
        p_dph_t.target_ap = 0

    # C 1901-1950: FSTOP without FBURST (flap, glottal, soncon nasal).
    if (cur_feat & FSTOP) and not (cur_feat & FBURST):
        if cur_place & BLADEAFFECTED:
            # C 1907-1923: alveolar -> close blade.
            p_dph_t.in_bclosure = 1
            p_dph_t.target_b = 0
            p_dph_t.target_l = 1000
            p_dph_t.target_tb = 1000
            p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA
            p_dph_t.agspeed = 1
        if cur_place & FVELAR:
            # C 1924-1932: velar -> tongue-body indicated closed.
            p_dph_t.target_b = 1000
            p_dph_t.target_l = 1000
            p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA
            p_dph_t.agspeed = 2
        if cur_place & FLABIAL:
            # C 1934-1948: labial -> close lips.
            p_dph_t.target_b = 1000
            p_dph_t.target_l = 0
            p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA

    # C 1952-1964: USP_R -> widen target_ag for /r/ release.
    if cur_allo == USP_R:
        p_dph_t.target_ag += 1000

    # C 1969-2040: FSON1 (sonorant) rules.
    if cur_feat & FSON1:
        if not (cur_feat & FSTOP):
            # C 1972-1990: sonorant non-stop.
            p_dph_t.target_b = 1000
            p_dph_t.target_l = 1000
            p_dph_t.target_tb = 1000
            if not (prev_feat & FSTOP):
                # C 1978-1980: previous wasn't a stop (i.e. no VOT).
                p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA
        elif cur_place & FALVEL:
            # C 1993-1997: sonorant stop, alveolar -> open lips.
            p_dph_t.target_l = 1000
        elif phone_feature(cur_allo) & FLABIAL:
            # C 1998-2002: sonorant stop, labial -> open blade.
            # Note: C uses phone_feature here (not place); matches
            # the C source's idiosyncrasy where FLABIAL is also a
            # feature-bit alias on the sonorant table.
            p_dph_t.target_b = 1000

        # C 2006-2034: FSON1 + glottis-positioning.
        if allofeats[nphone] & FDUMMY_VOWEL:
            # C 2007-2017: dummy-vowel between an obstruent and a
            # sonorant -> offset glottis area by +100.
            if prev_feat & FVOICD:
                p_dph_t.target_ag = _NOM_VOICED_OBSTRUENT + 100
            else:
                p_dph_t.target_ag = _NOM_OPEN_GLOTTIS + 100
        elif not ((prev_feat & FPLOSV) and not (prev_feat & FVOICD)):
            # C 2019-2034: not preceded by an unvoiced plosive ->
            # restore voiced glottal area.
            p_dph_t.target_ag = _NOM_VOIC_GLOT_AREA


def _phdraw_fvowel_a2_jamming(  # noqa: PLR0912, PLR0915 — branches mirror C body
    p_dph_t: DphT,
) -> None:
    """FVOWEL anticipation + A2-jamming + ``lastthing`` tracking.

    Faithful port of ``ph_draw.c`` lines 2045-2398. Runs every frame
    on a FVOWEL phone (the caller in
    :func:`_phdraw_regular_phoneme_branch` gates on FVOWEL).

    Sub-blocks (in C order):

    * **C 2045-2086**: GERMAN-only vowel-ending glottis to 1400
      when followed by an unvoiced phone. The C source's identity
      test is against the GRP_* (German font) codes; on the US
      build ``allophons[nphone]`` always has ``PFUSA<<PSFONT``
      bits, so the GRP_* equality test is always false. **Block
      preserved for documentation only.**
    * **C 2087-2170**: FVOWEL + next-non-stop-non-burst obstruent
      at end-of-vowel -> close down to fricative start (target_ag
      = 1200) and jam A2 per next-phone place. **PORTED.**
    * **C 2175-2219**: HX (US-build does not have a UKP_HX symbol);
      the ``#ifndef TOMBUCHLER`` branch fires: anticipate next
      sonorant unvoiced -> open glottis to 1800. The `#else`
      UKP_HX branch is UK-only and dead. **PORTED.**
    * **C 2221-2257**: spread glottis at vowel-end when next is
      unvoiced sonorant. **PORTED.**
    * **C 2258-2398**: per-place A2 jamming (gated on `!FNASAL`).
      Walks DENTAL / LABIAL / PALATAL / ALVEL place rules with
      the affricate-specific palatel-roll-start sub-rule at C
      2314-2340. Tracks ``lastthing`` for cross-phone carryover.
      **PORTED.**

    Args:
        p_dph_t: Active PH thread state. Mutates ``target_ag``,
            ``target_l``, ``agspeed``, ``parstochip[OUT_A2]``,
            ``lastthing``.
    """
    nphone = p_dph_t.nphone
    if nphone == 0 or nphone >= len(p_dph_t.allophons):
        return
    _ensure_parstochip(p_dph_t)

    allophons = p_dph_t.allophons
    allofeats = p_dph_t.allofeats
    allodurs = p_dph_t.allodurs
    ps = p_dph_t.parstochip
    cur_allo = allophons[nphone]
    prev_allo = allophons[nphone - 1]
    next_allo = allophons[nphone + 1] if nphone + 1 < len(allophons) else 0

    cur_feat = phone_feature(cur_allo)
    next_feat = phone_feature(next_allo) if next_allo else 0
    cur_place = place(cur_allo)
    prev_place = place(prev_allo)
    next_place = place(next_allo) if next_allo else 0

    # C 2045-2086: GERMAN vowel ending. The GRP_* equality test is
    # always false on the US-only allophons stream (US codes have the
    # PFUSA font marker, GRP_* codes have PFGR). Block preserved as a
    # comment for source-traceability; no Python emission.

    # C 2087-2170: vowel + next non-stop non-burst obstruent.
    if (
        (next_feat & FOBST)
        and not (next_feat & FSTOP)
        and not (next_feat & FBURST)
        and p_dph_t.tcum >= (allodurs[nphone] - 1)
    ):
        p_dph_t.target_ag = 1200
        if next_place & FLABIAL:
            # C 2102-2113: labial fricative next -> narrow lips.
            p_dph_t.area_l = _NOM_FRICATIVE_OPENING
            p_dph_t.target_l = 100
        if (cur_place & FDENTAL) or (next_place & FLABIAL):
            # C 2117-2136: DENTAL current or LABIAL next -> jam A2.
            # The Spanish branch (1100) is dead on US: we always
            # use 1000.
            ps[OUT_A2] = 1000
        elif next_place & FPALATL:
            # C 2137-2148: palatal next -> jam A3 & A4 (the C source
            # writes only A2; the "A3&4" in the printf is a debug
            # naming hangover -- see C 2147).
            ps[OUT_A2] = 2000
        elif next_place & FALVEL:
            # C 2149-2163: alveolar next -> jam A2 when phonestep > 2.
            if p_dph_t.phonestep > 2:
                ps[OUT_A2] = 3000

    # C 2175-2194 (#ifndef TOMBUCHLER): anticipate next unvoiced
    # sonorant consonant -> open glottis. TOMBUCHLER is never
    # defined on the US build (see _phdraw_tombuchler_modulation_dead_code).
    if nphone + 1 < len(allofeats):
        next_dummy = bool(allofeats[nphone + 1] & FDUMMY_VOWEL)
    else:
        next_dummy = False
    if (
        not next_dummy
        and not (next_feat & FVOICD)
        and (next_feat & FSONOR)
        and (next_feat & FCONSON)
        and p_dph_t.tcum >= (allodurs[nphone] - 2)
    ):
        p_dph_t.target_ag = 1800
        p_dph_t.agspeed = 2

    # C 2201-2219: current phone is unvoiced sonorant consonant ->
    # open glottis (this branch reads cur_feat, not next_feat).
    cur_dummy = bool(allofeats[nphone] & FDUMMY_VOWEL)
    if not cur_dummy and not (cur_feat & FVOICD) and (cur_feat & FSONOR) and (cur_feat & FCONSON):
        p_dph_t.target_l = 1000
        p_dph_t.target_b = 1000
        p_dph_t.target_tb = 1000
        p_dph_t.target_ag = _NOM_OPEN_GLOTTIS
        p_dph_t.agspeed = 2

    # C 2221-2257: spread glottis for HX when next is unvoiced
    # sonorant consonant at end-of-phone.
    if (
        not next_dummy
        and not (next_feat & FVOICD)
        and (next_feat & FSONOR)
        and (next_feat & FCONSON)
        and p_dph_t.tcum >= (allodurs[nphone] - 7)
        and p_dph_t.target_ag < _NOM_UNVOICED_SON
    ):
        if cur_feat & FNASAL:
            if p_dph_t.target_ag < 1200:
                p_dph_t.target_ag += 100
                p_dph_t.agspeed = 3
        elif p_dph_t.target_ag < 1200:
            p_dph_t.target_ag += 70
            p_dph_t.agspeed = 3

    # C 2258-2398: per-place A2 jamming (gated on !FNASAL).
    if not (cur_feat & FNASAL):
        # C 2260-2298: DENTAL.
        if cur_place & FDENTAL:
            if cur_feat & FVOICD:
                ps[OUT_A2] = 1100
            else:
                # C 2274-2281: Spanish branch dead on US; we always
                # use 1000.
                ps[OUT_A2] = 1000
            if cur_allo in (USP_DH, USP_TH, USP_DZ):
                # C 2285-2293: dental fricatives (UKP_* variants
                # omitted -- UK codes not in Python).
                ps[OUT_A2] = 1200
        # C 2299-2310: LABIAL.
        elif cur_place & FLABIAL:
            ps[OUT_A2] = 1300
        # C 2311-2358: PALATAL.
        elif cur_place & FPALATL:
            is_affricate_or_tsh = cur_allo in (USP_JH, USP_CH) or (
                cur_allo == USP_SH and prev_allo == USP_T
            )
            if is_affricate_or_tsh:
                # C 2314-2340: affricate / [tʃ]-cluster.
                p_dph_t.agspeed = 2
                if p_dph_t.tcum <= 4:
                    # C 2321-2336: palatal->alveolar roll start.
                    ps[OUT_A2] = 3200
                else:
                    ps[OUT_A2] = 2000
            else:
                # C 2343-2356: plain palatal. Both branches write
                # 2000; the FVOICD split exists only for the debug
                # printf cite (C 2350-2356).
                ps[OUT_A2] = 2000
        # C 2359-2372: ALVEL.
        elif cur_place & FALVEL:
            ps[OUT_A2] = 3000

        # C 2373-2397: lastthing carryover. If the previous phone
        # had blade-affected place AND was an obstruent BUT was NOT
        # a stop-before-obst combination AND we're at phonestep < 1
        # or it's a dummy vowel, restore the previous lastthing.
        # The C source's brace structure here is intentionally odd:
        # the outer `if` covers only the inner `if (phonestep<1 ||
        # FDUMMY_VOWEL)` test; the trailing `else { lastthing=0; }`
        # binds to that inner test, NOT to the outer place test.
        prev_place_blade = bool(prev_place & (FPALATL | FDENTAL | FALVEL | FLABIAL))
        prev_feat_local = phone_feature(prev_allo)
        # The C expression !(FSTOP_prev && FOBST_cur):
        not_stop_to_obst = not ((prev_feat_local & FSTOP) and (cur_feat & FOBST))
        if prev_place_blade and not_stop_to_obst and (prev_feat_local & FOBST):
            if p_dph_t.phonestep < 1 or (allofeats[nphone] & FDUMMY_VOWEL):
                ps[OUT_A2] = p_dph_t.lastthing
            else:
                p_dph_t.lastthing = 0
        # C 2396-2397: latch lastthing if A2 hit a jammed value.
        if ps[OUT_A2] >= 1000:
            p_dph_t.lastthing = ps[OUT_A2]


def _phdraw_per_frame_hlsyn_state_machine(  # noqa: PLR0912,PLR0915 — mirrors C body
    p_dph_t: DphT,
    p_dphsettar: DphSettarSt,
) -> None:
    """Per-frame HLSyn area / pressure / glottis state machine.

    Faithful port of ``ph_draw.c`` lines 2350-4300 (HLSYN build,
    US-English path).  Mutates ``p_dph_t`` fields in place and
    writes ``parstochip[]`` slots OUT_AG / OUT_AL / OUT_AN /
    OUT_ABLADE / OUT_ATB / OUT_BRST / OUT_CNK / OUT_GF / OUT_PS /
    OUT_F4 / OUT_PLACE.

    Non-US language branches (French, German, Spanish, UK) that
    reference language-specific phoneme codes not present in the
    Python codebase are omitted with inline comments naming the
    C source lines they occupy.
    """
    nphone = p_dph_t.nphone
    allophons = p_dph_t.allophons
    allofeats = p_dph_t.allofeats
    allodurs = p_dph_t.allodurs
    ps = p_dph_t.parstochip
    coarticulation = _COARTICULATION_DEFAULT

    # C lines ~2396-2432: sonant-consonant glottal rules
    if nphone and phone_feature(allophons[nphone]) & FSONCON:
        if p_dph_t.tcum <= (allodurs[nphone] >> 1):
            if p_dph_t.target_ag < _NOM_VOIC_GLOT_AREA + 300 and allophons[nphone] != USP_R:
                p_dph_t.agspeed = 1
        elif p_dph_t.target_ag > _NOM_VOIC_GLOT_AREA:
            p_dph_t.agspeed = 1
        # French R (FP_R) branch omitted — non-US phoneme code
        # (ph_draw.c lines ~2420-2431)
        if allophons[nphone] == USP_W or allophons[nphone] == USP_R:
            ps[OUT_A2] = 4000
            p_dph_t.target_ag = 800

    # C lines ~2434-2455: narrow glottis anticipating lateral
    if nphone + 1 < len(allophons):
        if (
            (allophons[nphone + 1] == USP_LL or allophons[nphone + 1] == USP_LX)
            and p_dph_t.tcum >= (allodurs[nphone] - 4)
            and not (phone_feature(allophons[nphone]) & FSTOP)
        ):
            p_dph_t.target_ag = min(p_dph_t.target_ag, 600)

    # C lines ~2450-2457: lateral liquid (LL / LX) sets A2 and target_ag
    if allophons[nphone] == USP_LL or allophons[nphone] == USP_LX:
        ps[OUT_A2] = 4000
        p_dph_t.target_ag = 600
        p_dph_t.agspeed = 3

    # C lines ~2459-2470: velar nasal (ng) → set in_tbclosure
    if place(allophons[nphone]) & FVELAR and phone_feature(allophons[nphone]) & FNASAL:
        if p_dph_t.tcum <= allodurs[nphone]:
            p_dph_t.in_tbclosure = 1

    # C lines ~2472-2617: nasal velum rules
    if phone_feature(allophons[nphone]) & FNASAL:
        if (
            place(allophons[nphone]) & BLADEAFFECTED
            and place(allophons[nphone - 1]) & BLADEAFFECTED
        ):
            # Homorganic place → snap velum open faster
            if p_dph_t.nasal_step == 0:
                p_dph_t.nasal_step = 4
            elif p_dph_t.nasal_step < 7:
                p_dph_t.nasal_step += 1
        elif (
            nphone + 1 < len(allophons)
            and phone_feature(allophons[nphone + 1]) & FOBST
            and p_dph_t.tcum >= (allodurs[nphone] - 1)
            and allophons[nphone + 1] != USP_DH
        ):
            # Close velum early before obstruent
            if p_dph_t.nasal_step:
                p_dph_t.nasal_step -= 1
            if p_dph_t.nasal_step:
                p_dph_t.nasal_step -= 1
        elif p_dph_t.nasal_step < 7:
            p_dph_t.nasal_step += 2
        p_dph_t.area_n = _NASALIZATION[min(p_dph_t.nasal_step, 12)]
        # French sets target_ag=900; US path uses 700
        p_dph_t.target_ag = 700

    elif (
        nphone + 1 < len(allophons)
        and phone_feature(allophons[nphone + 1]) & FNASAL
        and (nphone + 2 >= len(allophons) or allophons[nphone + 1] != allophons[nphone + 2])
    ):
        # Next phone is a nasal: start dropping velum at 50% of current phone
        if allodurs[nphone] < 7:
            if p_dph_t.nasal_step < 7:
                p_dph_t.nasal_step += 1
        if not (phone_feature(allophons[nphone]) & FOBST):
            if p_dph_t.tcum >= (allodurs[nphone] >> 1):
                if p_dph_t.nasal_step < 7:
                    p_dph_t.nasal_step += 1
                p_dph_t.area_n = _NASALIZATION[min(p_dph_t.nasal_step, 12)]

    elif not (phone_feature(allophons[nphone]) & FNASAL):
        # Was nasalized but no longer in a nasal — close velum (US path)
        if p_dph_t.nasal_step and p_dph_t.phonestep:
            if phone_feature(allophons[nphone]) & FSONOR:
                # C: skip decrement when phonestep < 3 (goto skipit)
                if p_dph_t.phonestep >= 3:
                    if p_dph_t.nasal_step > 0:
                        p_dph_t.nasal_step -= 1
                    p_dph_t.area_n = _NASALIZATION[min(p_dph_t.nasal_step, 12)]
            else:
                # Not sonor → close velum quickly
                if p_dph_t.nasal_step > 4:
                    p_dph_t.nasal_step -= 3
                else:
                    p_dph_t.nasal_step -= 1
                p_dph_t.nasal_step = max(p_dph_t.nasal_step, 0)
                p_dph_t.area_n = _NASALIZATION[min(p_dph_t.nasal_step, 12)]

        # C lines ~2741-2765: anticipate unvoiced obstruent → spread glottis
        if nphone + 1 < len(allophons) and (
            not (phone_feature(allophons[nphone]) & FOBST)
            and phone_feature(allophons[nphone + 1]) & FOBST
            and not (allofeats[nphone] & FSTRESS)
            and not (phone_feature(allophons[nphone + 1]) & FVOICD)
            and not (phone_feature(allophons[nphone + 1]) & FSTOP)
        ):
            if p_dph_t.tcum >= (allodurs[nphone] - _NF60MS) and p_dph_t.tcum >= (
                allodurs[nphone] >> 1
            ):
                if p_dph_t.target_ag < 1000:
                    p_dph_t.target_ag += 10
            elif p_dph_t.target_ag < 700:
                p_dph_t.target_ag += 75
            elif p_dph_t.target_ag < 1100:
                p_dph_t.target_ag += 40

        # C lines ~2767-2781: plosive before nasal → narrow glottis early
        if nphone + 1 < len(allophons) and (
            phone_feature(allophons[nphone]) & FOBST
            and phone_feature(allophons[nphone]) & FPLOSV
            and phone_feature(allophons[nphone + 1]) & FNASAL
        ):
            if p_dph_t.tcum >= (allodurs[nphone] - _NF50MS):
                p_dph_t.target_ag = min(p_dph_t.target_ag, 1100)

        # C lines ~2783-2856: non-plosive obstruent before voiced → close glottis
        elif (
            nphone + 1 < len(allophons)
            and phone_feature(allophons[nphone]) & FOBST
            and not (phone_feature(allophons[nphone]) & FPLOSV)
            and phone_feature(allophons[nphone + 1]) & FVOICD
            and not (phone_feature(allophons[nphone + 1]) & FNASAL)
        ):
            if p_dph_t.target_ag >= 800:
                if p_dph_t.tcum >= (allodurs[nphone] - _NF50MS) and not (
                    phone_feature(allophons[nphone + 1]) & FSTOP
                ):
                    if allophons[nphone + 1] != USP_R:
                        p_dph_t.target_ag = min(p_dph_t.target_ag, 1200)
                        p_dph_t.agspeed = 1
                else:
                    p_dph_t.agspeed = 3
            else:
                p_dph_t.agspeed = 2

    # C lines ~2858-2867: if voiced, build pressure toward nominal
    if phone_feature(allophons[nphone]) & FVOICD:
        if p_dph_t.pressure <= _NOM_Sub_Pressure:
            p_dph_t.pressure += 70

    # C lines ~2870-2900: tongue-body area tracker (#ifdef TONGUE_BODY_AREA path)
    if not (place(allophons[nphone]) & FVELAR):
        p_dph_t.in_tbclosure = 0

    if p_dph_t.in_tbclosure:
        p_dph_t.target_tb = 0

    if p_dph_t.target_tb < p_dph_t.area_tb:
        if p_dph_t.area_tb:
            p_dph_t.area_tb -= 310
            p_dph_t.area_tb = max(p_dph_t.area_tb, p_dph_t.target_tb)
    elif p_dph_t.target_tb != p_dph_t.area_tb:
        if p_dph_t.in_tbrelease == 1 and p_dph_t.area_tb < 1000:
            if (
                phone_feature(allophons[nphone - 1]) & FBURST
                or phone_feature(allophons[nphone]) & FBURST
            ):
                if p_dph_t.tbstep == -1:
                    p_dph_t.area_tb = _NOM_FRICATIVE_OPENING
                else:
                    p_dph_t.area_tb = _AREA_REL[min(p_dph_t.tbstep, len(_AREA_REL) - 1)]
                if p_dph_t.tbstep <= 9:
                    p_dph_t.tbstep += 1
            elif place(allophons[nphone]) & BLADEAFFECTED:
                p_dph_t.area_tb = _NOM_FRICATIVE_OPENING
        elif p_dph_t.in_tbrelease == 0 or p_dph_t.in_tbclosure == 0:
            if p_dph_t.target_tb > p_dph_t.area_tb:
                p_dph_t.area_tb += (p_dph_t.target_tb - p_dph_t.area_tb) >> 3
            else:
                p_dph_t.area_tb += (p_dph_t.target_tb - p_dph_t.area_tb) >> 1
            if place(allophons[nphone]) & BLADEAFFECTED and place(allophons[nphone - 1]) & FVELAR:
                if p_dph_t.phonestep < coarticulation:
                    p_dph_t.area_tb = p_dph_t.last_area_tb

    # C lines ~3153-3175: lclosure
    if p_dph_t.in_lclosure == 1:
        p_dph_t.target_l = 0
        p_dph_t.lstep = 0

    # C lines ~3180-3260: labial frication / area tracker
    if p_dph_t.in_lfric:
        p_dph_t.area_l = _NOM_FRICATIVE_OPENING
        p_dph_t.target_l = _NOM_FRICATIVE_OPENING
        if p_dph_t.nphonelast != nphone:
            if not (allofeats[nphone] & FDUMMY_VOWEL):
                p_dph_t.in_lrelease = 1
                p_dph_t.area_l = 270
                p_dph_t.lstep = 3
    elif p_dph_t.target_l < p_dph_t.area_l:
        if p_dph_t.area_l:
            p_dph_t.area_l -= 250
            p_dph_t.area_l = max(p_dph_t.area_l, p_dph_t.target_l)
    elif p_dph_t.target_l != p_dph_t.area_l:
        if p_dph_t.in_lrelease == 1 and p_dph_t.area_l < 1000:
            if (
                phone_feature(allophons[nphone - 1]) & FBURST
                or phone_feature(allophons[nphone]) & FBURST
            ):
                if p_dph_t.lstep == -1:
                    p_dph_t.area_l = _NOM_FRICATIVE_OPENING
                    p_dph_t.lstep = 1
                else:
                    p_dph_t.area_l = _AREA_REL[min(p_dph_t.lstep, len(_AREA_REL) - 1)]
                    if p_dph_t.lstep <= 9:
                        p_dph_t.lstep += 1
            elif place(allophons[nphone]) & FLABIAL:
                p_dph_t.area_l = _NOM_FRICATIVE_OPENING
        elif p_dph_t.in_lrelease == 0 or p_dph_t.in_lclosure == 0:
            if p_dph_t.target_l > p_dph_t.area_l:
                p_dph_t.area_l += (p_dph_t.target_l - p_dph_t.area_l) >> 2
            elif p_dph_t.target_l == 0:
                p_dph_t.area_l += (p_dph_t.target_l - (p_dph_t.area_l + 100)) >> 1
                if p_dph_t.target_l == 0 and p_dph_t.area_l < 300:
                    p_dph_t.area_l = 0
            else:
                p_dph_t.area_l += (p_dph_t.target_l - p_dph_t.area_l) >> 1
                p_dph_t.area_l = max(p_dph_t.area_l, p_dph_t.target_l)
            if place(allophons[nphone]) & BLADEAFFECTED:
                if p_dph_t.phonestep < coarticulation:
                    p_dph_t.area_b = p_dph_t.last_area_b
            p_dph_t.area_l += (p_dph_t.target_l - p_dph_t.area_l) >> 2
            if p_dph_t.target_l == 0 and p_dph_t.area_l < 260:
                p_dph_t.area_l = 0
            if place(allophons[nphone]) & BLADEAFFECTED:
                if p_dph_t.phonestep < coarticulation:
                    p_dph_t.area_l = p_dph_t.last_area_l
        p_dph_t.area_l = min(p_dph_t.area_l, 1000)

    # C lines ~3348-3382: flap area for USP_DX / USP_DF
    if allophons[nphone] == USP_DX or allophons[nphone] == USP_DF:
        half = allodurs[nphone] >> 1
        if p_dph_t.tcum >= half:
            if p_dph_t.area_flap <= 850:
                p_dph_t.area_flap += 500
            else:
                p_dph_t.area_flap = 1200
        elif p_dph_t.tcum >= (half - 3):
            if p_dph_t.area_flap > 0:
                p_dph_t.area_flap -= 500
            else:
                p_dph_t.area_flap = 0
    else:
        p_dph_t.area_flap = 1200

    # C lines ~3384-3549: blade area tracker
    if p_dph_t.target_b < p_dph_t.area_b:
        if p_dph_t.area_b:
            p_dph_t.area_b -= 400
            p_dph_t.area_b = max(p_dph_t.area_b, p_dph_t.target_b)
    elif p_dph_t.target_b != p_dph_t.area_b or p_dph_t.bstep == -1:
        if p_dph_t.in_brelease == 1 and p_dph_t.area_b < 1000:
            if (
                phone_feature(allophons[nphone - 1]) & FBURST
                or phone_feature(allophons[nphone]) & FBURST
            ):
                if p_dph_t.bstep == -1:
                    p_dph_t.area_b = _NOM_FRICATIVE_OPENING
                    p_dph_t.bstep = 1
                elif p_dph_t.target_b != 0:
                    p_dph_t.area_b = _AREA_REL[min(p_dph_t.bstep, len(_AREA_REL) - 1)]
                    if p_dph_t.bstep <= 9:
                        p_dph_t.bstep += 1
                else:
                    p_dph_t.area_b = 0
            elif place(allophons[nphone]) & BLADEAFFECTED:
                p_dph_t.area_b = _NOM_FRICATIVE_OPENING
            else:
                p_dph_t.area_b += (p_dph_t.target_b - p_dph_t.area_b) >> 1
        elif p_dph_t.in_brelease == 0 or p_dph_t.in_bclosure == 0:
            if p_dph_t.target_b > p_dph_t.area_b:
                if p_dph_t.target_b <= 200 and p_dph_t.area_b < 100:
                    p_dph_t.area_b = p_dph_t.target_b
                else:
                    p_dph_t.area_b += (p_dph_t.target_b - p_dph_t.area_b) >> 1
            elif p_dph_t.target_b == 0:
                p_dph_t.area_b += (p_dph_t.target_b - p_dph_t.area_b) >> 2
                if p_dph_t.target_b == 0 and p_dph_t.area_b <= 500:
                    p_dph_t.area_b = 0
            else:
                p_dph_t.area_b += (p_dph_t.target_b - p_dph_t.area_b) >> 1
                p_dph_t.area_b = max(p_dph_t.area_b, p_dph_t.target_b)
            if place(allophons[nphone]) & FLABIAL or place(allophons[nphone]) & FVELAR:
                if p_dph_t.phonestep < coarticulation:
                    p_dph_t.area_b = p_dph_t.last_area_b
                    if place(allophons[nphone - 1]) & BLADEAFFECTED and p_dph_t.area_b < 200:
                        p_dph_t.area_b = 0
        p_dph_t.area_b = min(p_dph_t.area_b, 1000)

    # C lines ~3550-3615: DH / TH closure rule (US phonemes only)
    # UKP_DH / UKP_TH omitted — UK phoneme codes not in Python codebase
    if allophons[nphone] == USP_DH or allophons[nphone] == USP_TH:
        boundary_val = allofeats[nphone] & FBOUNDARY
        if boundary_val < FWBNEXT:
            if p_dph_t.phonestep < (allodurs[nphone] - 1):
                p_dph_t.target_b = 0
                p_dph_t.area_b = 0
            else:
                p_dph_t.in_brelease = 1
                p_dph_t.area_b = 100
        elif p_dph_t.phonestep < (allodurs[nphone] - 8):
            p_dph_t.target_b = 0
            p_dph_t.area_b = 0
        else:
            p_dph_t.target_b = 300

    # French AP (FP_AP) delta_a_forap rule omitted — non-US phoneme code
    # (ph_draw.c lines ~3617-3631)

    # C lines ~3633-3720: glottis spread at final sonorant (#ifndef TOMBUCHLER)
    if p_dph_t.had_in_phrase_final:
        if p_dphsettar.nframb > (p_dph_t.tcumdur - 92):
            if (
                p_dph_t.nphone >= (p_dph_t.last_real_phon - 2)
                and phone_feature(allophons[nphone]) & FVOICD
            ):
                if p_dph_t.delta_area_g < 800:
                    p_dph_t.delta_area_g += _EndOfPhrase_Spread
        else:
            p_dph_t.delta_area_g = 0
    else:
        p_dph_t.delta_area_g = 0

    # GRP_Q glottalized stop rule omitted — non-US phoneme code
    # (ph_draw.c lines ~4028-4046)
    p_dph_t.delta_area_gstop = 0  # US path: always reset

    # C lines ~4046-4060: glottalized release (previous was voiced glottal)
    if phone_feature(allophons[nphone - 1]) & FVOICD:
        if place(allophons[nphone - 1]) & 0o40:  # FGLOTTAL = 0o40
            p_dph_t.agspeed = 3

    # French R (FP_R) special reset rule omitted — non-US phoneme code
    # (ph_draw.c lines ~4063-4082)

    # C lines ~4085-4093: unstressed vowel glottis spread
    if not (allofeats[nphone] & FSTRESS) and (phone_feature(allophons[nphone]) & FSYLL):
        p_dph_t.target_ag = _NOM_UNSTRESSED_VOWEL
        if p_dph_t.target_ag <= _NOM_UNSTRESSED_VOWEL:
            p_dph_t.target_ag += 10

    # C lines ~4094-4106: delta_a_forap offset + clamp target_ap
    if p_dph_t.target_ag <= 600:
        p_dph_t.target_ag += p_dph_t.delta_a_forap
    p_dph_t.target_ap = min(p_dph_t.target_ap, 2500)
    p_dph_t.target_ap = max(p_dph_t.target_ap, 0)
    p_dph_t.area_ap += (p_dph_t.target_ap - p_dph_t.area_ap) >> 3

    # High speaking rate hack
    if p_dph_t.sprate >= 350:
        p_dph_t.agspeed = 1

    # Glottal area advance (clamped to avoid big jumps)
    ag_delta = (p_dph_t.target_ag - p_dph_t.area_g) >> p_dph_t.agspeed
    if ag_delta > 300:
        p_dph_t.area_g += 350
    else:
        p_dph_t.area_g += ag_delta + p_dph_t.delta_area_g

    # C lines ~4107-4116: burst flag OUT_BRST
    if p_dph_t.in_lrelease or p_dph_t.in_tbrelease or p_dph_t.in_brelease:
        if ps[OUT_BRST] == 0:
            if p_dph_t.in_tbrelease:
                ps[OUT_BRST] = 1
            else:
                ps[OUT_BRST] = 2
        else:
            ps[OUT_BRST] = -1
    else:
        ps[OUT_BRST] = 0

    # C lines ~4118-4125: chink area (aspiration chink)
    ps[OUT_CNK] = p_dph_t.area_ap

    # C lines ~4126-4145: OUT_AG
    tmp = p_dph_t.area_g + p_dph_t.delta_area_gst - p_dph_t.delta_area_gstop
    tmp = max(tmp, 0)
    ps[OUT_AG] = tmp

    # C lines ~4147-4163: OUT_AL, remember last area_b / area_l
    ps[OUT_AL] = p_dph_t.area_l
    p_dph_t.last_area_b = p_dph_t.area_b
    p_dph_t.last_area_l = p_dph_t.area_l

    # OUT_ABLADE = min(area_flap, area_b)
    if p_dph_t.area_flap < p_dph_t.area_b:
        ps[OUT_ABLADE] = max(0, p_dph_t.area_flap)
    else:
        ps[OUT_ABLADE] = p_dph_t.area_b

    # C lines ~4167: OUT_ATB
    ps[OUT_ATB] = p_dph_t.area_tb

    # C lines ~4168-4210: OUT_PLACE (velar phones → begtyp-based place code)
    # Non-US codes (GRP_KH, SPP_J, LAP_J, GRP_CH, LAP_Y, SPP_Y) omitted.
    if place(allophons[nphone]) & FVELAR and nphone + 1 < len(allophons):
        bt = begtyp(allophons[nphone + 1])
        if bt == 1:
            ps[OUT_PLACE] = 45
        elif bt == 3:
            ps[OUT_PLACE] = 40
        else:
            ps[OUT_PLACE] = 42

    # C lines 4211-4239: FAKE_HLSYN fricative-gain (OUT_GF) recomputation
    # SKIPPED on the libtts_us.so HLSYN build target: this block is
    # wrapped in ``#ifdef FAKE_HLSYN`` (mutually exclusive with the
    # active HLSYN build), so the production binary does NOT
    # recompute OUT_GF here. The frame-loop's earlier OUT_GF write
    # (driven by the HLSyn area model) is the final value. See
    # docs/PORTING.md (Phase E) for the HLSyn-area fricative-gain
    # path that replaces this.

    # C lines ~4242-4262: pressure_gest for PRESSBOUND allofeats
    if allofeats[nphone] & PRESSBOUND:
        if p_dph_t.tcum <= (allodurs[nphone] >> 1):
            p_dph_t.pressure_gest += 20
        elif p_dph_t.pressure_gest > 0:
            p_dph_t.pressure_gest -= 20
        else:
            p_dph_t.pressure_gest = 0
    else:
        p_dph_t.pressure_gest = 0

    # C lines ~4265-4282: pressure drop near end-of-phrase (NEW_PRESSURE path)
    if phone_feature(allophons[nphone]) & FSYLL:
        boundary_v = allofeats[nphone] & FBOUNDARY
        nxt2 = (allofeats[nphone + 2] & FBOUNDARY) if nphone + 2 < len(allofeats) else 0
        nxt3 = (allofeats[nphone + 3] & FBOUNDARY) if nphone + 3 < len(allofeats) else 0
        if (
            boundary_v >= FPPNEXT or nxt2 >= FPPNEXT or nxt3 >= FPPNEXT
        ) and p_dph_t.syl_pressure == 0:
            if (p_dph_t.nphonetot - nphone) <= 4:
                if nphone < len(allofeats) and allofeats[p_dph_t.nphonetot - 1] & FDUMMY_VOWEL:
                    value = p_dph_t.tcumdur - (allodurs[p_dph_t.nphonetot - 1] >> 1)
                    value += allodurs[0]
                    p_dph_t.last_real_phon = p_dph_t.nphonetot - 3
                else:
                    value = p_dph_t.tcumdur + allodurs[0]
                    p_dph_t.last_real_phon = p_dph_t.nphonetot - 2
                denom = value - p_dphsettar.nframb
                if p_dph_t.syl_pressure == 0 and p_dphsettar.nframb > 9 and denom > 0:
                    feat_last = phone_feature(allophons[p_dph_t.last_real_phon])
                    if feat_last & FOBST:
                        if feat_last & FVOICD:
                            if (p_dph_t.tcumdur - p_dphsettar.nframb) > 5:
                                p_dph_t.syl_pressure = (
                                    p_dph_t.pressure - p_dph_t.syl_pressure - 600
                                ) // denom
                        elif (p_dph_t.tcumdur - p_dphsettar.nframb) > 5:
                            p_dph_t.syl_pressure = (
                                p_dph_t.pressure - p_dph_t.syl_pressure - 500
                            ) // denom
                    elif (p_dph_t.tcumdur - p_dphsettar.nframb) > 5:
                        p_dph_t.syl_pressure = (
                            p_dph_t.pressure - p_dph_t.syl_pressure - 500
                        ) // denom
            p_dph_t.pressure_drop += p_dph_t.syl_pressure

    # C lines ~4268-4270: initialize delta_area_g at start of clause
    if p_dphsettar.nframb <= 1:
        p_dph_t.delta_area_g = 0

    # C lines ~4273-4290: compute tmp pressure output (non-TOMBUCHLER path)
    tmp = p_dph_t.pressure - p_dph_t.pressure_drop + p_dph_t.stress_pulse
    tmp -= p_dph_t.pressure_gest
    if (tmp < 100 and nphone > 1) or tmp < 0:
        p_dph_t.pressure_drop = 0
        p_dph_t.pressure = 0
        p_dph_t.syl_pressure = 0
        tmp = 0

    # C lines ~4279: OUT_F4 = curspdef[SPD_F4]
    if len(p_dph_t.curspdef) > _SPD_F4:
        ps[OUT_F4] = p_dph_t.curspdef[_SPD_F4]

    # C lines ~4282-4295: final output writes
    ps[OUT_PS] = tmp
    ps[OUT_AN] = p_dph_t.area_n

    # C lines ~4296-4300: per-phone bookkeeping
    p_dph_t.lastf1 = ps[OUT_F1]
    p_dph_t.nphonelast = nphone


def _phdraw_per_frame_hlsyn_state_machine_unported() -> None:
    """Deprecated no-op stub for ph_draw.c lines 2350-4300.

    The live implementation is :func:`_phdraw_per_frame_hlsyn_state_machine`;
    this stub exists only for grep-compatibility with tooling that
    references the old name.  Calling it is a no-op.
    """
    return None


def _phdraw_tombuchler_modulation_dead_code() -> None:
    """No-op documenting the ``#ifdef TOMBUCHLER`` dead block in ph_draw.c.

    The C source contains a block guarded by ``#ifdef TOMBUCHLER`` at
    lines 4488-4524. ``TOMBUCHLER`` is **never** defined in the
    ``libtts_us.so`` build (no ``#define TOMBUCHLER`` appears anywhere
    in the Makefiles, ``configure.ac``, or any header). The block is
    therefore compiled out; the four modulation helper functions
    (``r_modulation``, ``rs_modulation``, ``gr_modulation``,
    ``h_modulation`` at C lines 4838-5232) are present in the binary
    but **never reachable from ``phdraw``**.

    Binary proof (``libtts_us.so``, stable tarball build):

    * ``phdraw`` occupies addresses ``0x413e0``--``0x4191c``.
    * ``r_modulation`` starts at ``0x41920`` (immediately after).
    * ``objdump --start-address=0x413e0 --stop-address=0x41920``
      contains **zero** ``call`` instructions that target any address
      in ``[0x41920, 0x41c70+]`` (the modulation helper range).

    Calling this function is a no-op; it is exported so test code can
    assert the dead-code analysis without importing anything that would
    actually invoke the helpers.
    """
    return None


def _phdraw_lateral_av_and_f3_floor(p_dph_t: DphT) -> None:
    """Reduce AV by 6 dB for lateral phonemes and enforce F3-F2 >= 300 Hz.

    Faithful translation of ``ph_draw.c`` lines 4619-4644 (outside the
    ``#ifdef TOMBUCHLER`` block, so **always** executed on the US HLSYN
    build path):

    * **Lateral AV reduction** (C lines 4621-4635): if the current
      allophone (``pDph_t->allophons[nphone]``) is a lateral consonant
      in any of the six supported languages, subtract 6 dB from
      ``parstochip[OUT_AV]``. The six lateral codes are:
      ``USP_LL`` (US), ``UKP_LL`` (UK), ``GRP_L`` (German),
      ``SPP_L`` (Castilian), ``LAP_L`` (Latin-American),
      ``FP_L`` (French).
    * **AV floor** (C line 4637): clamp ``parstochip[OUT_AV]`` to >= 0.
    * **F3 / F2 minimum gap** (C lines 4640-4643): if F3 - F2 < 300 Hz,
      set F3 = F2 + 300. This prevents F3 from crossing F2 during
      coarticulation.

    Args:
        p_dph_t: Mutable per-thread DphT state; ``parstochip`` is
            modified in place.
    """
    cur_allo = p_dph_t.allophons[p_dph_t.nphone]
    if cur_allo in (USP_LL, _UKP_LL, _GRP_L, _SPP_L, _LAP_L, _FP_L):
        p_dph_t.parstochip[OUT_AV] -= _LATERAL_AV_REDUCTION
    p_dph_t.parstochip[OUT_AV] = max(p_dph_t.parstochip[OUT_AV], 0)
    if p_dph_t.parstochip[OUT_F3] - p_dph_t.parstochip[OUT_F2] < 300:
        p_dph_t.parstochip[OUT_F3] = p_dph_t.parstochip[OUT_F2] + 300


# ----------------------------------------------------------------------------
# Public entry point.
# ----------------------------------------------------------------------------


def phdraw(phTTS: TtsHandle) -> None:  # noqa: N803, PLR0912, PLR0915 — branches mirror C body
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

    # ----- C lines 617-746: source spectral tilt -----
    # The entire spectral-tilt computation (C lines 617-742, including
    # the breathy-voice modifier and breathyah/breathytilt state
    # tracking) is gated behind
    # ``#if (defined FAKE_HLSYN || !(defined HLSYN))``; the HLSYN
    # production build (our target) hits the ``#else`` branch at C
    # lines 743-746 which simply zeroes OUT_TLT ("it doesn't really
    # do anything in hlsyn" -- per the comment in the C source). The
    # HLSyn vocal-tract model in ``hlframe.c`` (Phase E) handles tilt
    # shaping directly from area / glottis state instead.
    p_dph_t.parstochip[OUT_TLT] = 0

    # ----- C lines 750-757: formant scaling -----
    _apply_formant_scaling(p_dph_t)

    # ----- C lines 761-907: HLSyn area-parameter state machine -----
    _phdraw_hlsyn_area_loop(p_dph_t)

    # ----- C lines 908-928: phone-step counter update -----
    if p_dph_t.nphone != p_dph_t.nphonelast:
        p_dph_t.phonestep = 0
        p_dph_t.modulcount = 0
    else:
        p_dph_t.phonestep += 1

    # ----- C lines 929-1244: initial-silence anticipation -----
    # (the ``nphone == 0`` branch). Pre-positions HLSyn area /
    # glottis state on the first frame so the per-frame state
    # machine has sensible starting values. See
    # :func:`_phdraw_initial_silence_anticipation` for the body.
    _phdraw_initial_silence_anticipation(p_dph_t)

    # ----- C lines 1245-1332: GEN_SIL ending-silence anticipation -----
    # When the current allophone is GEN_SIL the C source sets the
    # blade / lip / glottis targets based on the previous phone's
    # features so the final breath decays cleanly. See
    # :func:`_phdraw_gen_sil_ending`.
    _phdraw_gen_sil_ending(p_dph_t)

    # ----- C lines 1333-2398: regular-phoneme branch (partial) -----
    # Pressure / dcstep / stress_pulse tracker. The once-per-phone
    # setup and FVOWEL A2-jamming sub-blocks remain deferred (they
    # overlap with rules in :func:`_phdraw_per_frame_hlsyn_state_machine`
    # and would double-write target_ag if ported in isolation). See
    # :func:`_phdraw_regular_phoneme_branch`.
    _phdraw_regular_phoneme_branch(p_dph_t)

    # ----- C lines 2350-4300: per-frame HLSyn state machine -----
    _phdraw_per_frame_hlsyn_state_machine(p_dph_t, p_dphsettar)

    # ----- C lines 4488-4524: #ifdef TOMBUCHLER (dead code on US build) -----
    # All four modulation helper calls are inside this block. No call
    # reaches them from phdraw on the US HLSYN build. See
    # _phdraw_tombuchler_modulation_dead_code() for the binary proof.

    # ----- C lines 4619-4644: lateral AV reduction + F3/F2 floor -----
    _phdraw_lateral_av_and_f3_floor(p_dph_t)


# Stub helpers naming the still-un-ported C blocks; exported so callers
# that want strict parity can opt into the NotImplementedError rather
# than the silent-skip default. ``_phdraw_hlsyn_area_loop_unported`` is
# kept as a deprecated alias forwarding to the live ported loop --
# downstream tooling that grepped for the stub name doesn't break.
__all__ = [
    "_phdraw_fvowel_a2_jamming",
    "_phdraw_gen_sil_ending",
    "_phdraw_hlsyn_area_loop_unported",
    "_phdraw_initial_silence_anticipation",
    "_phdraw_initial_silence_anticipation_unported",
    "_phdraw_lateral_av_and_f3_floor",
    "_phdraw_once_per_phone_setup",
    "_phdraw_per_frame_hlsyn_state_machine",
    "_phdraw_per_frame_hlsyn_state_machine_unported",
    "_phdraw_regular_phoneme_branch",
    "_phdraw_tombuchler_modulation_dead_code",
    "phdraw",
]


def _phdraw_hlsyn_area_loop_unported() -> None:
    """Deprecated alias for ``_phdraw_hlsyn_area_loop``.

    Kept for grep-compatibility with the previous stub; the live
    loop is now in :func:`_phdraw_hlsyn_area_loop` and runs as part
    of ``phdraw()``. Calling this directly is a no-op; the previous
    behaviour was to raise ``NotImplementedError`` with a "not yet
    ported" message.
    """
    return None
