"""``pht0draw`` F0 contour generator from ph_drwt02.c.

Translated from ``src/dapi/src/ph/ph_drwt02.c``:

- MALE branch: lines 765-1507 (``malfem == MALE``).
- FEMALE branch: lines 1508-2167 (``else``).

Per-frame F0 (fundamental period) computation for the PH pipeline.
Called once per 6.4 ms frame from the per-frame driver loop, between
``phsettar`` and ``phdraw``, mirroring ``ph_claus.c`` lines 488-498.

High-level flow (mirrored by both MALE and FEMALE branches):

1. **Hard init** (``nf0ev <= -2``): Reset all F0 state — filter
   memories, target accumulators, glottal-stop timer, cosine-jitter
   phases, etc.
2. **Soft init** (``nf0ev == -1``): Set clause-type-dependent
   ``beginfall``/``endfall``, advance timing state for the new clause.
3. **F0 command loop**: Consume F0 event records from ``f0tar`` /
   ``f0type`` / ``f0length`` / ``f0tim`` (populated by ``phinton``)
   while the current frame time ``nfram >= dtimf0``. Each record is
   dispatched on its type: ``USER``, ``F0_RESET``, ``STEP``,
   ``GLIDE``, ``GLOTTAL``, or ``IMPULSE``.
4. **Impulse envelope**: Triangle-shaped ramp over ``nimp`` frames.
5. **Segmental tracking**: Advance ``np_drawt0``/``phocur`` whenever
   the allophone-duration accumulator ``nframs`` overflows
   ``segdur + extrad``. Look up the per-phoneme F0 segmental target
   in ``us_f0msegtars`` (MALE) or ``us_f0fsegtars`` (FEMALE) and set
   ``tarseg`` / ``tarseg1``.
6. **Glottal-stop gesture**: Call ``set_tglst`` to advance the
   gesture timer; apply the F0 dip (60 Hz *linear ramp* centred on
   ``tglstp``). FEMALE additionally writes ``avglstop`` for the
   downstream AV reduction.
7. **Filter** the commands: ``filter_seg_commands`` (2-pole IIR on
   ``tarseg``) and ``filter_commands`` (1-pole IIR on the hat+impulse
   sum), then add ``f0s`` to get ``f0prime``.
8. **Flutter** (pseudo-jitter): Two cosine waves at ~3 Hz and ~5 Hz
   add ±1 Hz flutter to ``f0prime``. FEMALE adds an extra
   ``f0flutter``-scaled jitter on EXCLAIM clauses.
9. **Scale** ``f0prime`` by ``f0scalefac`` from the speaker
   definition, clamp to ``[LOWEST_F0, HIGHEST_F0]``.
10. **Emit** ``parstochip[OUT_T0] = f0prime`` (HLSYN path stores
    ``f0prime`` directly, not the muldv period).

Key MALE/FEMALE differences (faithful to the C source):

- Hard init constants: MALE ``newnote=1000``, FEMALE ``newnote=1600``.
  FEMALE additionally clears ``glotalize``/``glide_step`` and
  ``f0slas1``/``f0slas2`` in the hard-init block.
- Soft init: MALE switches on ``clausetype`` to reset
  ``clausepos``/``dcommacnt`` for DECLARATIVE / EXCLAIM / QUESTION;
  FEMALE omits the switch. FEMALE sets ``f0slas1``/``f0slas2``=0
  again here and double-zeros ``nframs``.
- F0 command loop STEP: MALE clears ``delimp`` alongside ``tarimp``
  when cancelling an impulse of opposite sign; FEMALE clears only
  ``tarimp``. GLOTTAL: MALE guards with ``lang_curr != LANG_french``;
  FEMALE has no guard (US lang_curr is never french in the binary).
- Impulse envelope: MALE compares ``nimpcnt < (nimp>>1)``,
  FEMALE compares ``nimpcnt <= (nimp>>1)`` — one extra ramp-up frame.
- Segmental tables: MALE uses ``us_f0msegtars[phocur & 0xff]``;
  FEMALE uses ``2*us_f0fsegtars[phocur & PVALUE]`` under HLSYN.
- Segmental voicing check: MALE inspects ``phocur`` for the
  ``FVOICD`` test; FEMALE inspects ``allophons[np_drawt0-1]`` (the
  PREVIOUS phoneme — a long-standing distinction in the C source).
- Glottal-stop dip: FEMALE writes ``avglstop = max(0, 6-dtglst)``
  for ``dtglst <= 5``; MALE does not touch ``avglstop``.
- Flutter: FEMALE adds an extra ``mlsh1(pseudojitter, f0flutter)``
  on EXCLAIMCLAUSE; MALE only flips the sign of ``addjit``.
- Scale: MALE uses ``f0scalefac+1000`` on EXCLAIM; FEMALE uses
  ``f0scalefac+500``.

Build flags assumed active: ``HLSYN``, ``ENGLISH_US``, ``ACNA``.
The non-US language table branches and ``CREEKMALE``/``CREEKFEMALE``
debug toggles are absent from the production HLSYN build and are
therefore not ported.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PVALUE
from dectalk.ph.cosine_tilt_tables import getcosine_tab
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FSTRESS
from dectalk.ph.filter_commands import filter_commands
from dectalk.ph.filter_seg_commands import filter_seg_commands
from dectalk.ph.getcosine import (
    DELAY_SEG_LOWPASS,
    F0SHFT,
    HIGHEST_F0,
    LOWEST_F0,
    TWOPI,
)
from dectalk.ph.inton_constants import SINGING, TIME_VALUE_SPECIFIED
from dectalk.ph.linear_interp import linear_interp
from dectalk.ph.math_helpers import mlsh1
from dectalk.ph.numeric_constants import FRAC_ONE, MALE
from dectalk.ph.param_indices import OUT_T0
from dectalk.ph.phoneme_features import FPLOSV, FVOICD
from dectalk.ph.set_tglst import set_tglst
from dectalk.ph.set_user_target import set_user_target
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_f0_segtars import us_f0fsegtars, us_f0msegtars
from dectalk.ph.utterance_constants import (
    DECLARATIVE,
    EXCLAIMCLAUSE,
    F0_RESET,
    GEN_SIL,
    GLIDE,
    GLOTTAL,
    IMPULSE,
    QUESTION,
    STEP,
    USER,
)

# ---------------------------------------------------------------------------
# Local constants (from ph_drwt02.c lines 242-246)
# ---------------------------------------------------------------------------

# F0 filter parameters
_F_SEG_LOWPASS: Final[int] = 3000
"""Nominal cutoff freq of the segmental 1-pole low-pass (Hz*10)."""

# Trig constants for cosine-jitter oscillators
_TWOPI: Final[int] = TWOPI  # 4096 — re-exported from getcosine.py

# The cosine3 and cosine5 oscillator increments per frame.
# ~5 Hz @ 156.25 frames/sec → 5/156.25*4096 ≈ 131;  ~3 Hz → 79.
_COS5_INC: Final[int] = 131
_COS3_INC: Final[int] = 79

# Flutter scale factor (700 ≡ ~10% flutter → ±1 Hz per getcosine unit).
_FLUTTER_SCALE: Final[int] = 700


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def pht0draw(ph_tts: TtsHandle) -> None:
    """Generate the next per-frame F0 value and write ``parstochip[OUT_T0]``.

    Faithful translation of:

    .. code-block:: c

        void pht0draw(LPTTS_HANDLE_T phTTS)        // ph_drwt02.c line 765

    The function mutates ``ph_tts.p_ph_thread_data`` (a :class:`DphT`)
    in place; specifically it writes:

    - ``parstochip[OUT_T0]`` — the F0 value passed to the synthesiser.
    - ``f0prime`` — the unscaled output F0 before chip output.
    - ``f0`` — the smoothed hat+impulse baseline.
    - ``f0s`` — the smoothed segmental adjustment.
    - ``avglstop`` — glottal-stop amplitude reduction flag
      (FEMALE branch only).

    Build flags: ``HLSYN`` active (so ``OUT_T0 = f0prime``, not
    ``muldv(400, 1000, f0prime)``).  Non-US language table branches
    fall back to the US tables (matching the C default).

    The MALE and FEMALE branches differ in initialisation constants,
    several control-flow comparisons, the segmental F0 table choice,
    and the EXCLAIM-clause flutter / scale tweaks. See the module
    docstring for a per-section diff.

    Args:
        ph_tts: Engine handle; ``p_ph_thread_data`` must be a
            :class:`DphT` instance with ``pSTphsettar`` set to a
            :class:`DphSettarSt` instance.
    """
    p_dph_t = ph_tts.p_ph_thread_data
    if not isinstance(p_dph_t, DphT):
        return

    pdphsettar = p_dph_t.pSTphsettar
    if not isinstance(pdphsettar, DphSettarSt):
        return

    # C: pKsd_t = phTTS->pKernelShareData; (not used in HLSYN US path)

    if p_dph_t.malfem == MALE:
        _pht0draw_male(p_dph_t, pdphsettar)
    else:
        _pht0draw_female(p_dph_t, pdphsettar)


def _pht0draw_male(p_dph_t: DphT, pdphsettar: DphSettarSt) -> None:  # noqa: PLR0912, PLR0915
    """MALE branch of pht0draw — ph_drwt02.c lines 765-1507."""
    # Local temporaries mirroring C auto vars.
    f0seg: int = 0
    f0in: int = 0
    pseudojitter: int = 0

    # -------------------------------------------------------------------
    # 1. Hard init (nf0ev <= -2)
    # ph_drwt02.c lines 795-860
    # -------------------------------------------------------------------
    if p_dph_t.nf0ev <= -2:  # noqa: PLR2004 — hard-init sentinel matches C source
        p_dph_t.clausepos = 0
        pdphsettar.phocur = GEN_SIL

        pdphsettar.nframb = 0
        pdphsettar.basetime = 0
        pdphsettar.basecntr = 0
        pdphsettar.f0delta = 0

        # eab 4/11/97 — cosine oscillator phases initialised here.
        pdphsettar.timecos10 = 0
        pdphsettar.timecos15 = 0
        pdphsettar.timecosvib = 0

        # Glottal-stop gesture timer: start far in the past so it has
        # no effect until the first genuine glottal-stop event.
        pdphsettar.tglstp = -200

        # Filter memories.
        pdphsettar.tarhat = 0
        pdphsettar.tarimp = 0
        pdphsettar.delimp = 0

        # 2nd-order filter coefficients from speaker definition.
        # f0a2 = f0_lp_filter; f0b = FRAC_ONE - f0a2;
        # f0a1 = f0a2 << F0SHFT
        pdphsettar.f0a2 = p_dph_t.f0_lp_filter
        pdphsettar.f0b = FRAC_ONE - pdphsettar.f0a2
        pdphsettar.f0a1 = pdphsettar.f0a2 << F0SHFT

        # Segmental filter coefficients.
        pdphsettar.f0sa2 = _F_SEG_LOWPASS
        pdphsettar.f0sb = FRAC_ONE - pdphsettar.f0sa2
        pdphsettar.f0sa1 = pdphsettar.f0sa2 << F0SHFT

        # Singing / user-target state.
        pdphsettar.newnote = 1000
        pdphsettar.delnote = 0
        pdphsettar.delcum = 0
        pdphsettar.f0start = p_dph_t.f0
        pdphsettar.vibsw = 0

        # Advance to soft-init state.
        p_dph_t.nf0ev = -1

    # -------------------------------------------------------------------
    # 2. Soft init (nf0ev == -1)
    # ph_drwt02.c lines 862-980
    # -------------------------------------------------------------------
    if p_dph_t.nf0ev == -1:
        pdphsettar.nimpcnt = 0
        pdphsettar.tarimp = 0
        p_dph_t.enddrop = 0

        # Clause-type-dependent state reset.
        # C: switch (pDph_t->clausetype)
        # Case 1 (COMMACLAUSE) is a deliberate no-op per the BATS 704
        # comment in the C source.
        if p_dph_t.clausetype in (DECLARATIVE, EXCLAIMCLAUSE, QUESTION):
            p_dph_t.clausepos = 0
            p_dph_t.dcommacnt = 0
        # default: pass

        # Segmental filter output reset.
        pdphsettar.f0slas1 = 0
        pdphsettar.f0slas2 = 0

        pdphsettar.nframb = 0
        pdphsettar.basetime = 0
        pdphsettar.basecntr = 0
        pdphsettar.f0delta = 0
        p_dph_t.special_phrase = 0

        # Raise baseline for first sentence of a paragraph.
        if p_dph_t.newparagsw != 0:
            pdphsettar.beginfall += 120
            pdphsettar.endfall += 70
            p_dph_t.newparagsw = 0

        # Time from frame 0 to first F0 command.
        pdphsettar.dtimf0 = p_dph_t.f0tim[0] if p_dph_t.f0tim else 0

        # Allophone pointer state.
        pdphsettar.np_drawt0 = -1
        pdphsettar.npg = -1
        p_dph_t.nf0ev = 0

        # Frame counters.
        pdphsettar.nframs = 0
        pdphsettar.nfram = 0
        pdphsettar.nframg = 6 - ((p_dph_t.f0_lp_filter - 1300) >> 8)

        if p_dph_t.f0mode < SINGING:
            pdphsettar.nfram = pdphsettar.nframs >> 1
        else:
            pdphsettar.nfram = 0  # Start note slightly early if singing.

        pdphsettar.nframs = 0

        # Extra time for early gesture start (anticipation / VOT delay).
        pdphsettar.extrad = -DELAY_SEG_LOWPASS

        # Segment-duration accumulators.
        pdphsettar.segdur = 0
        pdphsettar.segdrg = 0
        p_dph_t.lastallo = 0
        p_dph_t.keepallo = 0

        # Glottalisation state.
        p_dph_t.glotalize = 0
        pdphsettar.glide_step = 0
        pdphsettar.glide_tot = 0
        pdphsettar.glide_inc = 0
        pdphsettar.tarhat = 0
        p_dph_t.addjit = 305

    # End of initialization.

    # -------------------------------------------------------------------
    # 3. F0 command loop
    # ph_drwt02.c lines 982-1124
    # -------------------------------------------------------------------
    f0tar = p_dph_t.f0tar
    f0type = p_dph_t.f0type
    f0length = p_dph_t.f0length
    f0tim = p_dph_t.f0tim

    while pdphsettar.nfram >= pdphsettar.dtimf0 and p_dph_t.nf0ev < p_dph_t.nf0tot:
        pdphsettar.f0command = f0tar[p_dph_t.nf0ev]
        pdphsettar.type = f0type[p_dph_t.nf0ev]
        pdphsettar.nfram -= pdphsettar.dtimf0
        pdphsettar.length = f0length[p_dph_t.nf0ev]

        if p_dph_t.f0mode == TIME_VALUE_SPECIFIED:
            pdphsettar.dtimf0 = f0tim[p_dph_t.nf0ev]
            p_dph_t.nf0ev += 1
            cmd_ref: list[int] = [pdphsettar.f0command]
            set_user_target(p_dph_t, cmd_ref)
            pdphsettar.f0command = cmd_ref[0]
        else:
            p_dph_t.nf0ev += 1
            # Guard against nf0ev running past the end of f0tim.
            if p_dph_t.nf0ev < len(f0tim):
                pdphsettar.dtimf0 = f0tim[p_dph_t.nf0ev]
            else:
                pdphsettar.dtimf0 = 0

            cmd_type = pdphsettar.type

            if cmd_type == USER:
                cmd_ref = [pdphsettar.f0command]
                set_user_target(p_dph_t, cmd_ref)
                pdphsettar.f0command = cmd_ref[0]

            elif cmd_type == F0_RESET:
                # Go to bottom of hat pattern; reset glide.
                pdphsettar.tarhat = 0
                p_dph_t.glotalize = 0
                pdphsettar.glide_step = 0
                pdphsettar.glide_tot = 0
                pdphsettar.glide_inc = 0

            elif cmd_type == STEP:
                # ENGLISH_UK would break here; we skip that branch.
                pdphsettar.tarhat += pdphsettar.f0command
                # Cancel previous impulse if step is of opposite sign.
                if pdphsettar.f0command < 0:
                    if pdphsettar.tarimp > 0:
                        pdphsettar.tarimp = 0
                        pdphsettar.delimp = 0
                elif pdphsettar.tarimp < 0:
                    pdphsettar.tarimp = 0
                    pdphsettar.delimp = 0

            elif cmd_type == GLIDE:
                pdphsettar.glide_step = pdphsettar.f0command
                length = pdphsettar.length
                if length != 0:
                    pdphsettar.glide_inc = pdphsettar.glide_step // length
                else:
                    pdphsettar.glide_inc = 0

            elif cmd_type == GLOTTAL:
                # ENGLISH_UK would break here; we skip that branch.
                # lang_curr != LANG_french check omitted (always True on US).
                p_dph_t.enddrop = -pdphsettar.f0command
                p_dph_t.glotalize = 1

            elif cmd_type == IMPULSE:
                pdphsettar.tarimp = 0
                nimp = pdphsettar.length
                pdphsettar.nimp = nimp
                if nimp != 0:
                    pdphsettar.delimp = (pdphsettar.f0command // nimp) << 1
                else:
                    pdphsettar.delimp = 0
                pdphsettar.nimpcnt = 0

        # Loop back to look for more f0 commands.

    # -------------------------------------------------------------------
    # 4. Impulse envelope — triangle ramp over nimp frames.
    # ph_drwt02.c lines 1126-1153
    # -------------------------------------------------------------------
    if pdphsettar.nimpcnt == pdphsettar.nimp:
        pdphsettar.nimpcnt = 0
        pdphsettar.tarimp = 0
        pdphsettar.delimp = 0
        pdphsettar.nimp = 0
    elif pdphsettar.nimpcnt < (pdphsettar.nimp >> 1):
        pdphsettar.tarimp += pdphsettar.delimp
        pdphsettar.nimpcnt += 1
    else:
        pdphsettar.nimpcnt += 1
        pdphsettar.tarimp -= pdphsettar.delimp

    # -------------------------------------------------------------------
    # 5. Segmental tracking — advance phone when nframs >= segdur+extrad
    # ph_drwt02.c lines 1155-1245
    # -------------------------------------------------------------------
    # nframb is incremented here (before set_tglst), matching C source.
    pdphsettar.nframb += 1

    if pdphsettar.nframs >= (pdphsettar.segdur + pdphsettar.extrad) and pdphsettar.np_drawt0 < (
        p_dph_t.nallotot - 1
    ):
        pdphsettar.nframs -= pdphsettar.segdur
        pdphsettar.np_drawt0 += 1
        np = pdphsettar.np_drawt0

        # Advance allophone pointer (bounds-guarded).
        if 0 <= np < len(p_dph_t.allodurs):
            pdphsettar.segdur = p_dph_t.allodurs[np]
        else:
            pdphsettar.segdur = 0

        if 0 <= np < len(p_dph_t.allophons):
            pdphsettar.phocur = p_dph_t.allophons[np]

        # EAB long-standing bug fix: first phoneme was cheated on duration.
        if np == 1:
            pdphsettar.nframs = -DELAY_SEG_LOWPASS

        # Peek at the next phoneme for extrad and feature tests.
        if np < p_dph_t.nallotot and 0 <= np + 1 < len(p_dph_t.allophons):
            pdphsettar.phonex_drawt0 = p_dph_t.allophons[np + 1]

        # Look up segmental F0 target.
        # HLSYN active: use us_f0msegtars (the modern table).
        # Both US and non-US fonts use the same table — the C default
        # branch falls through to the US table for unknown fonts.
        code = pdphsettar.phocur & PVALUE
        f0seg = us_f0msegtars[code] if 0 <= code < len(us_f0msegtars) else 0

        # extrad: anticipate or delay the start of the next gesture.
        pdphsettar.extrad = -DELAY_SEG_LOWPASS  # Default: V-V, start early.

        # Delay rise for upcoming voiceless segment until boundary.
        next_is_voiceless = (phone_feature(pdphsettar.phonex_drawt0) & FVOICD) == 0
        if 0 <= np + 1 < len(p_dph_t.allophons) and next_is_voiceless:
            pdphsettar.extrad = 0  # All of rise during voiceless.

        # Delay fall from voiceless plosive until VOT.
        if (phone_feature(pdphsettar.phocur) & FVOICD) == 0:
            # Voiceless current segment.
            pdphsettar.tarseg1 = f0seg  # Fast gesture — 1 filter pole.
            pdphsettar.tarseg = 0
            pdphsettar.extrad = 1  # -V fric: fall starts at voicing onset.
            if (phone_feature(pdphsettar.phocur) & FPLOSV) != 0:
                # -V plosive: assume VOT ≈ 32 ms (5 frames).
                pdphsettar.extrad = 5
                if 0 <= np < len(p_dph_t.allofeats) and (p_dph_t.allofeats[np] & FSTRESS) == 0:
                    pdphsettar.extrad = 3
        else:
            # Voiced current segment: slow, use both segmental filter poles.
            pdphsettar.tarseg = f0seg
            pdphsettar.tarseg1 = 0

    # -------------------------------------------------------------------
    # 6. Glottal-stop gesture (set_tglst)
    # ph_drwt02.c lines 1247-1268
    # -------------------------------------------------------------------
    set_tglst(p_dph_t)

    # -------------------------------------------------------------------
    # 7. Filter and compose f0prime
    # ph_drwt02.c lines 1269-1315
    # -------------------------------------------------------------------
    if p_dph_t.f0mode < SINGING:
        # Increment glide accumulator.
        pdphsettar.glide_tot += pdphsettar.glide_inc
        pdphsettar.glide_step -= pdphsettar.glide_inc

        # Cancel glide_inc when target is reached.
        if pdphsettar.glide_inc > 0:
            if pdphsettar.glide_step <= pdphsettar.glide_inc:
                pdphsettar.glide_inc = 0
        elif pdphsettar.glide_inc < 0 and pdphsettar.glide_step >= pdphsettar.glide_inc:
            pdphsettar.glide_inc = 0

        # Build f0in = f0minimum + hat + impulse.
        f0in = p_dph_t.f0minimum + pdphsettar.tarhat + pdphsettar.tarimp

        # Decay segmental target at 98% per frame (mlsh1(tarseg, 16064)).
        pdphsettar.tarseg = mlsh1(pdphsettar.tarseg, 16064)
        filter_seg_commands(p_dph_t, pdphsettar.tarseg)

        # Add glide (HLSYN active: the ``#if defined(HLSYN)`` branch).
        f0in += pdphsettar.glide_tot

        # Apply 1-pole IIR to hat+impulse+glide.
        filter_commands(p_dph_t, f0in)

        p_dph_t.f0prime = p_dph_t.f0 + p_dph_t.f0s

    else:
        # SINGING / user-specified modes: linear interpolation.
        linear_interp(p_dph_t)

    # -------------------------------------------------------------------
    # 8. Glottal-stop F0 dip
    # ph_drwt02.c lines 1319-1336
    # F0 dip: 60 Hz linear ramp in 8 frames each direction about tglstp.
    # -------------------------------------------------------------------
    dtglst = pdphsettar.nframg - pdphsettar.tglstp
    if dtglst < 0:
        dtglst = -dtglst
    if dtglst <= 7:  # noqa: PLR2004 — C literal "7" frames glottal-stop half-width
        p_dph_t.f0prime += (dtglst * 70) - 550

    # -------------------------------------------------------------------
    # 9. Flutter (cosine pseudo-jitter at ~3 Hz and ~5 Hz)
    # ph_drwt02.c lines 1339-1368
    # -------------------------------------------------------------------
    if p_dph_t.f0mode < SINGING:
        pdphsettar.timecos5 += _COS5_INC
        if pdphsettar.timecos5 > _TWOPI:
            pdphsettar.timecos5 -= _TWOPI
        pdphsettar.timecos3 += _COS3_INC
        if pdphsettar.timecos3 > _TWOPI:
            pdphsettar.timecos3 -= _TWOPI

        idx5 = pdphsettar.timecos5 >> 6
        idx3 = pdphsettar.timecos3 >> 6
        pseudojitter = getcosine_tab[idx5] - getcosine_tab[idx3]

        # "FLUTTER" spdef parameter, 10% → ±1 Hz.
        p_dph_t.f0prime += mlsh1(pseudojitter, _FLUTTER_SCALE)

        if p_dph_t.clausetype == EXCLAIMCLAUSE:
            p_dph_t.addjit = -p_dph_t.addjit

    # -------------------------------------------------------------------
    # 10. Scale by speaker f0scalefac
    # ph_drwt02.c lines 1372-1393
    # -------------------------------------------------------------------
    if p_dph_t.f0mode < SINGING:
        if p_dph_t.clausetype == EXCLAIMCLAUSE:
            p_dph_t.f0prime = p_dph_t.f0minimum + _frac4mul_ph(
                p_dph_t.f0prime - p_dph_t.f0minimum,
                p_dph_t.f0scalefac + 1000,
            )
        else:
            p_dph_t.f0prime = p_dph_t.f0minimum + _frac4mul_ph(
                p_dph_t.f0prime - p_dph_t.f0minimum,
                p_dph_t.f0scalefac,
            )

    # Clamp to legal F0 bounds.
    if p_dph_t.f0prime > HIGHEST_F0:
        p_dph_t.f0prime = HIGHEST_F0
    elif p_dph_t.f0prime < LOWEST_F0:
        p_dph_t.f0prime = LOWEST_F0

    # SINGING mode: convert from Middle C = 256 Hz to A = 440 Hz scale.
    if p_dph_t.f0mode == SINGING:
        p_dph_t.f0prime = _frac4mul_ph(p_dph_t.f0prime, 4190)

    # -------------------------------------------------------------------
    # 11. Emit parstochip[OUT_T0]
    # ph_drwt02.c lines 1397-1409
    # HLSYN path: store f0prime directly (not the period muldv result).
    # -------------------------------------------------------------------
    if len(p_dph_t.parstochip) > OUT_T0:
        p_dph_t.parstochip[OUT_T0] = p_dph_t.f0prime

    # -------------------------------------------------------------------
    # 12. Increment time counters
    # ph_drwt02.c lines 1493-1497
    # -------------------------------------------------------------------
    pdphsettar.nfram += 1
    pdphsettar.nframs += 1
    pdphsettar.nframg += 1


# ---------------------------------------------------------------------------
# FEMALE branch
# ---------------------------------------------------------------------------


def _pht0draw_female(p_dph_t: DphT, pdphsettar: DphSettarSt) -> None:  # noqa: PLR0912, PLR0915
    """FEMALE branch of pht0draw — ph_drwt02.c lines 1508-2167.

    Mirrors :func:`_pht0draw_male` step-for-step; see the module
    docstring for the curated MALE/FEMALE diff.
    """
    # Local temporaries mirroring C auto vars.
    f0seg: int = 0
    f0in: int = 0
    pseudojitter: int = 0

    # -------------------------------------------------------------------
    # 1. Hard init (nf0ev <= -2)
    # ph_drwt02.c lines 1511-1570
    # -------------------------------------------------------------------
    if p_dph_t.nf0ev <= -2:  # noqa: PLR2004 — hard-init sentinel matches C source
        p_dph_t.clausepos = 0
        pdphsettar.phocur = GEN_SIL

        # Question — FEMALE hard init clears glide/glotalize up-front
        # (MALE does this only in soft init).
        p_dph_t.glotalize = 0
        pdphsettar.glide_step = 0

        pdphsettar.nframb = 0
        pdphsettar.basetime = 0
        pdphsettar.basecntr = 0
        pdphsettar.f0delta = 0

        # eab 4/11/97 — cosine oscillator phases.
        pdphsettar.timecos10 = 0
        pdphsettar.timecos15 = 0
        pdphsettar.timecosvib = 0

        # Glottal-stop gesture timer.
        pdphsettar.tglstp = -200

        # eab 7/22/98 changed to >>1 to account for female-voice scaling:
        # FEMALE sets the segmental filter averages here as well as
        # in soft init (defensive; matches the C source).
        pdphsettar.f0slas1 = 0
        pdphsettar.f0slas2 = 0

        pdphsettar.tarhat = 0
        pdphsettar.tarimp = 0
        pdphsettar.delimp = 0

        # 2nd-order filter coefficients from speaker definition.
        pdphsettar.f0a2 = p_dph_t.f0_lp_filter
        pdphsettar.f0b = FRAC_ONE - pdphsettar.f0a2
        pdphsettar.f0a1 = pdphsettar.f0a2 << F0SHFT

        # Segmental filter coefficients.
        pdphsettar.f0sa2 = _F_SEG_LOWPASS
        pdphsettar.f0sb = FRAC_ONE - pdphsettar.f0sa2
        pdphsettar.f0sa1 = pdphsettar.f0sa2 << F0SHFT

        # Singing / user-target state. FEMALE: newnote = 1600 (vs MALE 1000).
        pdphsettar.newnote = 1600
        pdphsettar.delnote = 0
        pdphsettar.delcum = 0
        pdphsettar.f0start = p_dph_t.f0
        pdphsettar.vibsw = 0

        # Advance to soft-init state.
        p_dph_t.nf0ev = -1

    # -------------------------------------------------------------------
    # 2. Soft init (nf0ev == -1)
    # ph_drwt02.c lines 1573-1650
    # -------------------------------------------------------------------
    if p_dph_t.nf0ev == -1:
        pdphsettar.nimpcnt = 0
        pdphsettar.tarimp = 0
        p_dph_t.enddrop = 0

        pdphsettar.nframb = 0
        pdphsettar.basetime = 0
        pdphsettar.basecntr = 0
        pdphsettar.f0delta = 0
        p_dph_t.special_phrase = 0

        # Raise baseline for first sentence of a paragraph.
        if p_dph_t.newparagsw != 0:
            pdphsettar.beginfall += 120
            pdphsettar.endfall += 70
            p_dph_t.newparagsw = 0

        # Time from frame 0 to first F0 command.
        pdphsettar.dtimf0 = p_dph_t.f0tim[0] if p_dph_t.f0tim else 0

        # Allophone pointer state.
        pdphsettar.np_drawt0 = -1
        pdphsettar.npg = -1
        p_dph_t.nf0ev = 0

        # Frame counters — set, then re-derive nfram from nframs.
        pdphsettar.nframs = 0
        pdphsettar.nfram = 0
        pdphsettar.nframg = 6 - ((p_dph_t.f0_lp_filter - 1300) >> 8)

        if p_dph_t.f0mode < SINGING:
            pdphsettar.nfram = pdphsettar.nframs >> 1
        else:
            pdphsettar.nfram = 0  # Start note slightly early if singing.

        # FEMALE: zero the segmental filter averages AGAIN here (after the
        # nfram derivation) and re-zero nframs. Faithfully mirrors the
        # double assignment in the C source.
        pdphsettar.f0slas1 = 0
        pdphsettar.f0slas2 = 0
        pdphsettar.nframs = 0

        # Extra time for early gesture start (anticipation / VOT delay).
        pdphsettar.extrad = -DELAY_SEG_LOWPASS

        # Segment-duration accumulators.
        pdphsettar.segdur = 0
        pdphsettar.segdrg = 0
        p_dph_t.lastallo = 0
        p_dph_t.keepallo = 0

        # Glottalisation state.
        p_dph_t.glotalize = 0
        pdphsettar.glide_step = 0
        pdphsettar.glide_tot = 0
        pdphsettar.glide_inc = 0
        pdphsettar.tarhat = 0
        p_dph_t.addjit = 305

    # End of initialization.

    # -------------------------------------------------------------------
    # 3. F0 command loop
    # ph_drwt02.c lines 1661-1766
    # -------------------------------------------------------------------
    f0tar = p_dph_t.f0tar
    f0type = p_dph_t.f0type
    f0length = p_dph_t.f0length
    f0tim = p_dph_t.f0tim

    while pdphsettar.nfram >= pdphsettar.dtimf0 and p_dph_t.nf0ev < p_dph_t.nf0tot:
        pdphsettar.f0command = f0tar[p_dph_t.nf0ev]
        pdphsettar.type = f0type[p_dph_t.nf0ev]
        pdphsettar.nfram -= pdphsettar.dtimf0
        pdphsettar.length = f0length[p_dph_t.nf0ev]

        if p_dph_t.f0mode == TIME_VALUE_SPECIFIED:
            pdphsettar.dtimf0 = f0tim[p_dph_t.nf0ev]
            p_dph_t.nf0ev += 1
            cmd_ref: list[int] = [pdphsettar.f0command]
            set_user_target(p_dph_t, cmd_ref)
            pdphsettar.f0command = cmd_ref[0]
        else:
            p_dph_t.nf0ev += 1
            # Guard against nf0ev running past the end of f0tim.
            if p_dph_t.nf0ev < len(f0tim):
                pdphsettar.dtimf0 = f0tim[p_dph_t.nf0ev]
            else:
                pdphsettar.dtimf0 = 0

            cmd_type = pdphsettar.type

            if cmd_type == USER:
                cmd_ref = [pdphsettar.f0command]
                set_user_target(p_dph_t, cmd_ref)
                pdphsettar.f0command = cmd_ref[0]

            elif cmd_type == F0_RESET:
                # Go to bottom of hat pattern; reset glide.
                pdphsettar.tarhat = 0
                p_dph_t.glotalize = 0
                pdphsettar.glide_step = 0
                pdphsettar.glide_tot = 0
                pdphsettar.glide_inc = 0

            elif cmd_type == STEP:
                # lang_curr != LANG_british check omitted (always True on US).
                pdphsettar.tarhat += pdphsettar.f0command
                # Cancel previous impulse if step is of opposite sign.
                # FEMALE does NOT clear delimp here (only tarimp); this is
                # a faithful difference vs the MALE branch.
                if pdphsettar.f0command < 0:
                    if pdphsettar.tarimp > 0:  # noqa: PLR1730 — mirror C nested-if
                        pdphsettar.tarimp = 0
                elif pdphsettar.tarimp < 0:
                    pdphsettar.tarimp = 0

            elif cmd_type == GLIDE:
                pdphsettar.glide_step = pdphsettar.f0command
                length = pdphsettar.length
                if length != 0:
                    pdphsettar.glide_inc = pdphsettar.glide_step // length
                else:
                    pdphsettar.glide_inc = 0

            elif cmd_type == GLOTTAL:
                # lang_curr != LANG_british check omitted (always True on US).
                # FEMALE: no LANG_french guard — sets enddrop/glotalize
                # unconditionally on the US path.
                p_dph_t.enddrop = -pdphsettar.f0command
                p_dph_t.glotalize = 1

            elif cmd_type == IMPULSE:
                pdphsettar.tarimp = 0
                nimp = pdphsettar.length
                pdphsettar.nimp = nimp
                if nimp != 0:
                    pdphsettar.delimp = (pdphsettar.f0command // nimp) << 1
                else:
                    pdphsettar.delimp = 0
                pdphsettar.nimpcnt = 0

        # Loop back to look for more f0 commands.

    # -------------------------------------------------------------------
    # 4. Impulse envelope — triangle ramp over nimp frames.
    # ph_drwt02.c lines 1771-1789. FEMALE uses ``<=`` (one extra ramp-up
    # frame) where MALE uses ``<``.
    # -------------------------------------------------------------------
    pdphsettar.nframb += 1

    if pdphsettar.nimpcnt == pdphsettar.nimp:
        pdphsettar.nimpcnt = 0
        pdphsettar.tarimp = 0
        pdphsettar.delimp = 0
        pdphsettar.nimp = 0
    elif pdphsettar.nimpcnt <= (pdphsettar.nimp >> 1):
        pdphsettar.tarimp += pdphsettar.delimp
        pdphsettar.nimpcnt += 1
    else:
        pdphsettar.nimpcnt += 1
        pdphsettar.tarimp -= pdphsettar.delimp

    # -------------------------------------------------------------------
    # 5. Segmental tracking — advance phone when nframs >= segdur+extrad
    # ph_drwt02.c lines 1794-1869
    # -------------------------------------------------------------------
    if pdphsettar.nframs >= (pdphsettar.segdur + pdphsettar.extrad) and pdphsettar.np_drawt0 < (
        p_dph_t.nallotot - 1
    ):
        pdphsettar.nframs -= pdphsettar.segdur
        pdphsettar.np_drawt0 += 1
        np = pdphsettar.np_drawt0

        if 0 <= np < len(p_dph_t.allodurs):
            pdphsettar.segdur = p_dph_t.allodurs[np]
        else:
            pdphsettar.segdur = 0

        if 0 <= np < len(p_dph_t.allophons):
            pdphsettar.phocur = p_dph_t.allophons[np]

        # EAB long-standing bug fix: first phoneme was cheated on duration.
        if np == 1:
            pdphsettar.nframs = -DELAY_SEG_LOWPASS

        # Peek at the next phoneme for extrad and feature tests.
        if np < p_dph_t.nallotot and 0 <= np + 1 < len(p_dph_t.allophons):
            pdphsettar.phonex_drawt0 = p_dph_t.allophons[np + 1]

        # Look up segmental F0 target.
        # HLSYN active: use 2*us_f0fsegtars (the FEMALE table).
        # Non-US language branches fall through to the US table as in
        # the C default.
        code = pdphsettar.phocur & PVALUE
        f0seg = 2 * us_f0fsegtars[code] if 0 <= code < len(us_f0fsegtars) else 0

        # extrad: anticipate or delay the start of the next gesture.
        pdphsettar.extrad = -DELAY_SEG_LOWPASS  # Default: V-V, start early.

        # Delay rise for upcoming voiceless segment until boundary.
        next_is_voiceless = (phone_feature(pdphsettar.phonex_drawt0) & FVOICD) == 0
        if 0 <= np + 1 < len(p_dph_t.allophons) and next_is_voiceless:
            pdphsettar.extrad = 0  # All of rise during voiceless.

        # FEMALE: voicing check examines the *previous* allophone, not
        # ``phocur``. This mirrors ph_drwt02.c line 1853.
        prev_index = np - 1
        if 0 <= prev_index < len(p_dph_t.allophons):
            prev_phoneme = p_dph_t.allophons[prev_index]
        else:
            prev_phoneme = 0
        prev_is_voiceless = (phone_feature(prev_phoneme) & FVOICD) == 0

        if prev_is_voiceless:
            # Previous voiceless segment: gesture fast — one filter pole.
            pdphsettar.tarseg1 = f0seg
            pdphsettar.tarseg = 0
            pdphsettar.extrad = 1  # -V fric: fall starts at voicing onset.
            if (phone_feature(pdphsettar.phocur) & FPLOSV) != 0:
                # -V plosive: assume VOT ≈ 32 ms (5 frames).
                pdphsettar.extrad = 5
                if 0 <= np < len(p_dph_t.allofeats) and (p_dph_t.allofeats[np] & FSTRESS) == 0:
                    pdphsettar.extrad = 3
        else:
            # Voiced previous segment: slow, use both segmental filter poles.
            pdphsettar.tarseg = f0seg
            pdphsettar.tarseg1 = 0

    # -------------------------------------------------------------------
    # 6. Glottal-stop gesture (set_tglst)
    # ph_drwt02.c line 1874
    # -------------------------------------------------------------------
    set_tglst(p_dph_t)

    # -------------------------------------------------------------------
    # 7. Filter and compose f0prime
    # ph_drwt02.c lines 1879-1980
    # -------------------------------------------------------------------
    if p_dph_t.f0mode < SINGING:
        # Increment glide accumulator.
        pdphsettar.glide_tot += pdphsettar.glide_inc
        pdphsettar.glide_step -= pdphsettar.glide_inc

        # Cancel glide_inc when target is reached.
        if pdphsettar.glide_inc > 0:
            if pdphsettar.glide_step <= pdphsettar.glide_inc:
                pdphsettar.glide_inc = 0
        elif pdphsettar.glide_inc < 0 and pdphsettar.glide_step >= pdphsettar.glide_inc:
            pdphsettar.glide_inc = 0

        # Build f0in = f0minimum + hat + impulse.
        f0in = p_dph_t.f0minimum + pdphsettar.tarhat + pdphsettar.tarimp

        # Decay segmental target at 98% per frame.
        pdphsettar.tarseg = mlsh1(pdphsettar.tarseg, 16064)
        filter_seg_commands(p_dph_t, pdphsettar.tarseg)

        # Add glide (HLSYN active: the ``#if defined(HLSYN)`` branch).
        f0in += pdphsettar.glide_tot

        # Apply 1-pole IIR to hat+impulse+glide.
        filter_commands(p_dph_t, f0in)

        p_dph_t.f0prime = p_dph_t.f0 + p_dph_t.f0s

    else:
        # SINGING / user-specified modes: linear interpolation.
        linear_interp(p_dph_t)

    # -------------------------------------------------------------------
    # 8. Glottal-stop F0 dip + avglstop AV reduction.
    # ph_drwt02.c lines 1985-2005.
    # FEMALE additionally writes ``avglstop`` for the downstream AV path.
    # -------------------------------------------------------------------
    dtglst = pdphsettar.nframg - pdphsettar.tglstp
    if dtglst < 0:
        dtglst = -dtglst
    if dtglst <= 7:  # noqa: PLR2004 — C literal "7" frames glottal-stop half-width
        p_dph_t.f0prime += (dtglst * 70) - 550

    # Reduce AV somewhat (ugly code, but F0 computed before AV).
    if dtglst <= 5:  # noqa: PLR2004 — C literal "5" frames AV-reduction half-width
        p_dph_t.avglstop = 6 - dtglst
    else:
        p_dph_t.avglstop = 0

    # -------------------------------------------------------------------
    # 9. Flutter (cosine pseudo-jitter at ~3 Hz and ~5 Hz)
    # ph_drwt02.c lines 2008-2029.
    # FEMALE adds an extra f0flutter-scaled jitter on EXCLAIM clauses.
    # -------------------------------------------------------------------
    if p_dph_t.f0mode < SINGING:
        pdphsettar.timecos5 += _COS5_INC
        if pdphsettar.timecos5 > _TWOPI:
            pdphsettar.timecos5 -= _TWOPI
        pdphsettar.timecos3 += _COS3_INC
        if pdphsettar.timecos3 > _TWOPI:
            pdphsettar.timecos3 -= _TWOPI

        idx5 = pdphsettar.timecos5 >> 6
        idx3 = pdphsettar.timecos3 >> 6
        pseudojitter = getcosine_tab[idx5] - getcosine_tab[idx3]

        # eab 4/16/98 higher flutter for female voice (700, hard-coded).
        p_dph_t.f0prime += mlsh1(pseudojitter, _FLUTTER_SCALE)

        if p_dph_t.clausetype == EXCLAIMCLAUSE:
            # FEMALE: extra f0flutter-scaled jitter on exclamations.
            p_dph_t.f0prime += mlsh1(pseudojitter, p_dph_t.f0flutter)
            p_dph_t.addjit = -p_dph_t.addjit

    # -------------------------------------------------------------------
    # 10. Scale by speaker f0scalefac
    # ph_drwt02.c lines 2036-2046.
    # FEMALE uses ``f0scalefac+500`` on EXCLAIM (MALE uses +1000).
    # -------------------------------------------------------------------
    if p_dph_t.f0mode < SINGING:
        if p_dph_t.clausetype == EXCLAIMCLAUSE:
            p_dph_t.f0prime = p_dph_t.f0minimum + _frac4mul_ph(
                p_dph_t.f0prime - p_dph_t.f0minimum,
                p_dph_t.f0scalefac + 500,
            )
        else:
            p_dph_t.f0prime = p_dph_t.f0minimum + _frac4mul_ph(
                p_dph_t.f0prime - p_dph_t.f0minimum,
                p_dph_t.f0scalefac,
            )

    # Clamp to legal F0 bounds.
    if p_dph_t.f0prime > HIGHEST_F0:
        p_dph_t.f0prime = HIGHEST_F0
    elif p_dph_t.f0prime < LOWEST_F0:
        p_dph_t.f0prime = LOWEST_F0

    # SINGING mode: convert from Middle C = 256 Hz to A = 440 Hz scale.
    if p_dph_t.f0mode == SINGING:
        p_dph_t.f0prime = _frac4mul_ph(p_dph_t.f0prime, 4190)

    # -------------------------------------------------------------------
    # 11. Emit parstochip[OUT_T0]
    # ph_drwt02.c lines 2067-2072.
    # HLSYN path: store f0prime directly (not the muldv period result).
    # -------------------------------------------------------------------
    if len(p_dph_t.parstochip) > OUT_T0:
        p_dph_t.parstochip[OUT_T0] = p_dph_t.f0prime

    # -------------------------------------------------------------------
    # 12. Increment time counters
    # ph_drwt02.c lines 2155-2157
    # -------------------------------------------------------------------
    pdphsettar.nfram += 1
    pdphsettar.nframs += 1
    pdphsettar.nframg += 1


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _frac4mul_ph(x: int, y: int) -> int:
    """Q12 fixed-point multiply matching ``frac4mul`` in ph_defs.h.

    ``frac4mul(x, y)`` in the C source is ``((x) * (S32)(y)) >> 12``
    where both operands are widened to 32-bit before the shift. The
    result is truncated toward zero (arithmetic right-shift in C on
    two's-complement machines).

    Faithful translation of:

    .. code-block:: c

        #define frac4mul(x, y) (((x) * (S32)(y)) >> 12)

    Args:
        x: First factor (treated as signed 32-bit).
        y: Second factor (treated as signed 32-bit).

    Returns:
        ``(x * y) >> 12`` with arithmetic shift (truncates toward
        negative infinity on negative products, matching the C ``>>``
        on two's-complement platforms).
    """
    return (x * y) >> 12


__all__ = ["pht0draw"]
