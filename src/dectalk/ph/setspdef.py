"""Per-voice speaker-definition reload — ``setspdef`` from ``ph_vset.c``.

Translated from ``src/dapi/src/ph/ph_vset.c`` lines 541-831 (function
``setspdef``), the bridge that converts a user-format ``SPDEF`` voice row
(``curspdef[]``) into (a) the PH-side speaker scalars on ``DPH_T`` and
(b) the ``SPD_CHIP`` block streamed to the vocal-tract model.

Build-variant notes (the PARITY-METHOD §3 checklist):

* The oracle build defines **no** ``HLSYN`` / ``CHANGES_AFTER_V43`` /
  ``LOWCOMPUTE`` / ``NEW_VOLUME`` / ``SW_VOLUME`` / ``SOFTWARE_VOLUME``,
  so the active branches are the plain ones: ``f0minimum = AP * 10``
  (line 617), ``spdeftltoff = (SM * 25) / 100`` (line 625),
  ``aturb = BR + 9`` (line 722), ``afgain = GF`` / ``apgain = GH``
  (lines 770-771), ``azgain = GV`` (line 748).
* ``PC_SAMPLE_RATE == 11025`` selects the ``> 4950`` F4/F5 zap
  thresholds (lines 653, 690).
* The ``usevoice`` tune-table addition (``curspdef[i] = newspdef[i] +
  tunespdef[i]``, ph_vset.c line 464) draws from
  ``p_us_vdf_oldtune.c`` on this build (``ph_vdefi.c`` line 115: no
  HLSYN, no CHANGES_AFTER_V43, no FP_VTM) — whose non-``_8`` rows are
  **all zero** at 11025 Hz (the only non-zero literals sit behind
  ``#if PC_SAMPLE_RATE == 22050``). The per-voice tune add is therefore
  a no-op and ``curspdef`` equals the raw ``p_us_vdf_dectalk43.c`` row.

The chip factory follows the Python port's swapped frequency/bandwidth
field convention: the *frequency* lands in ``r4cc``/``r5cc`` and the
*bandwidth* in ``r4cb``/``r5cb`` (see ``dectalk/vtm/spd_chip.py``,
"Field-name convention caveat" — only the values matter for parity;
every consumer compensates).

C speaker numbering (``ph_main.c`` lines 461-470 ``voidef[]`` order,
matching ``c_us_cde.h`` ``voice_names[]``): 0=paul, 1=betty, 2=harry,
3=frank, 4=dennis, 5=kit, 6=ursula, 7=rita, 8=wendy, 9=val.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from dectalk.include.cmd_codes import (
    SPD_AP,
    SPD_AS,
    SPD_B4,
    SPD_B5,
    SPD_BF,
    SPD_BR,
    SPD_F4,
    SPD_F5,
    SPD_FT,
    SPD_G1,
    SPD_G2,
    SPD_G3,
    SPD_G4,
    SPD_GF,
    SPD_GH,
    SPD_GN,
    SPD_GV,
    SPD_HR,
    SPD_HS,
    SPD_LA,
    SPD_LO,
    SPD_LX,
    SPD_NF,
    SPD_OS,
    SPD_P4,
    SPD_P5,
    SPD_PR,
    SPD_QU,
    SPD_RI,
    SPD_SEX,
    SPD_SM,
    SPD_SR,
)
from dectalk.ph.inton_constants import ZAPB, ZAPF
from dectalk.ph.spdef_chip import SpdChip

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dectalk.ph.dph_t import DphT

# ``ph_vset.c`` line 653 (PC_SAMPLE_RATE == 11025 branch): F4/F5 chip
# frequencies above this are zapped to ZAPF/ZAPB.
_ZAP_THRESHOLD_11KHZ: Final[int] = 4950

# C speaker index by public voice name (``ph_main.c`` lines 461-470;
# ``c_us_cde.h`` ``voice_names[]``). ``willy`` is the public-API name
# for the ``wendy`` SPDEF row (see ``ph/voice_definitions.py``), and
# ``chris`` aliases Paul's row/slot on this non-HLSYN build.
C_SPEAKER_INDEX: Final[dict[str, int]] = {
    "paul": 0,
    "betty": 1,
    "harry": 2,
    "frank": 3,
    "dennis": 4,
    "kit": 5,
    "ursula": 6,
    "rita": 7,
    "wendy": 8,
    "willy": 8,
    "val": 9,
    "chris": 0,
}


def seed_dph_scalars(p_dph_t: DphT, row: Sequence[int]) -> None:
    """Seed the PH-side speaker scalars from a ``SPDEF`` voice row.

    Faithful translation of the ``pDph_t``-side assignments in
    ``setspdef`` (``ph_vset.c`` lines 556-639). These are the scalars
    ``phdraw`` / ``pht0draw`` / ``phinton`` / ``gettar`` consult per
    frame; the chip-side block is built separately by
    :func:`spd_chip_from_row`.

    Line-by-line C mapping (all in ``ph_vset.c``):

    ==============================  =======================================
    Python field                    C derivation
    ==============================  =======================================
    ``malfem``                      ``curspdef[SPD_SEX]``            (556)
    ``last_lang``                   ``0`` — force table reload       (560)
    ``f0_dep_tilt``                 ``curspdef[SPD_FT]``             (607)
    ``assertiveness``               ``curspdef[SPD_AS] * 41``        (608)
    ``f0_lp_filter``                ``1500 + 15 * curspdef[SPD_QU]`` (610)
    ``size_hat_rise``               ``curspdef[SPD_HR] * 10``        (611)
    ``scale_str_rise``              ``curspdef[SPD_SR]``             (612)
    ``f0minimum``                   ``curspdef[SPD_AP] * 10``        (617,
                                    non-HLSYN branch; the ``-12`` fudge
                                    at 615 is HLSYN/post-v43 only — the
                                    #260 wrong-variant defect)
    ``f0scalefac``                  ``curspdef[SPD_PR] * 41``        (619)
    ``f0basefall``                  ``curspdef[SPD_BF] * 10``        (620)
    ``spdeflaxprcnt``               ``curspdef[SPD_LX] * 41``        (621)
    ``spdeftltoff``                 ``(curspdef[SPD_SM] * 25) / 100``(625,
                                    non-HLSYN branch; C integer division)
    ``spdefb1off``                  ``((BR * BR) >> 1) + 4096``  (629-630)
    ``fnscale``                     ``(200 - curspdef[SPD_HS]) * 41``(638)
    ==============================  =======================================

    Args:
        p_dph_t: PH thread-state instance to mutate.
        row: ``SPDEF`` voice row (``curspdef`` content; the raw
            ``p_us_vdf_dectalk43.c`` row — the active tune-table add is
            all-zero, see module docstring).
    """
    p_dph_t.malfem = row[SPD_SEX]
    # eab: init last_lang to a bad value so gettar reloads the
    # (now possibly sex-switched) target tables on the next call.
    p_dph_t.last_lang = 0
    p_dph_t.f0_dep_tilt = row[SPD_FT]
    p_dph_t.assertiveness = row[SPD_AS] * 41
    p_dph_t.f0_lp_filter = 1500 + 15 * row[SPD_QU]
    p_dph_t.size_hat_rise = row[SPD_HR] * 10
    p_dph_t.scale_str_rise = row[SPD_SR]
    p_dph_t.f0minimum = row[SPD_AP] * 10
    p_dph_t.f0scalefac = row[SPD_PR] * 41
    p_dph_t.f0basefall = row[SPD_BF] * 10
    p_dph_t.spdeflaxprcnt = row[SPD_LX] * 41
    # C integer division; SM is non-negative in every voice row so
    # Python ``//`` matches C ``/`` truncation.
    p_dph_t.spdeftltoff = (row[SPD_SM] * 25) // 100
    p_dph_t.spdefb1off = ((row[SPD_BR] * row[SPD_BR]) >> 1) + 4096
    p_dph_t.fnscale = (200 - row[SPD_HS]) * 41


def spd_chip_from_row(row: Sequence[int], speaker: int = 0) -> SpdChip:
    """Build the ``SPD_CHIP`` block from a ``SPDEF`` voice row.

    Faithful translation of the ``spdef->*`` assignments in ``setspdef``
    (``ph_vset.c`` lines 557-790, active non-HLSYN / non-LOWCOMPUTE /
    11025 Hz branches), returning the block in the Python port's swapped
    freq/bw field convention (frequency in ``r4cc``/``r5cc``, bandwidth
    in ``r4cb``/``r5cb`` — see module docstring).

    For Paul's row this reproduces
    :func:`dectalk.vtm.spd_chip.default_us_paul_spd` exactly (the
    oracle-packet-verified block from issue #284).

    Args:
        row: ``SPDEF`` voice row (see :func:`seed_dph_scalars`).
        speaker: C speaker number for the ``speaker`` bookkeeping word
            (``curspdef[SPD_NM]``, written by ``usevoice``; see
            :data:`C_SPEAKER_INDEX`). Not consumed by the synthesis
            loop — ``vtm1.c`` line 1895 only copies it back into
            ``uiCurrentSpeaker``.

    Returns:
        A fully-derived :class:`SpdChip` for the voice.
    """
    fnscale = (200 - row[SPD_HS]) * 41  # line 638

    # F4 cascade chip word (lines 640-660): pre-scale by fnscale unless
    # the row zaps the formant; oversize frequencies zap both words.
    f4_chip = ZAPF if row[SPD_F4] == ZAPF else (row[SPD_F4] * fnscale) >> 12
    b4_chip = row[SPD_B4]
    if f4_chip > _ZAP_THRESHOLD_11KHZ:
        f4_chip = ZAPF
        b4_chip = ZAPB

    # F5 cascade chip word (lines 662-698): same shape as F4.
    f5_chip = ZAPF if row[SPD_F5] == ZAPF else (row[SPD_F5] * fnscale) >> 12
    b5_chip = row[SPD_B5]
    if f5_chip > _ZAP_THRESHOLD_11KHZ:
        f5_chip = ZAPF
        b5_chip = ZAPB

    return SpdChip(
        # Swapped convention: bandwidth in r4cb/r5cb, frequency in
        # r4cc/r5cc (C layout is the reverse; values are what matter).
        r4cb=b4_chip,
        r4cc=f4_chip,
        r5cb=b5_chip,
        r5cc=f5_chip,
        r4pb=row[SPD_P4],  # line 699: F7 -> parallel-4 frequency
        r5pb=row[SPD_P5],  # line 700: F8 -> parallel-5 frequency
        t0jit=row[SPD_LA] << 3,  # line 701: LA -> T0 jitter
        r5ca=row[SPD_G1],  # line 703
        r4ca=row[SPD_G2],  # line 704
        r3ca=row[SPD_G3],  # line 705
        r2ca=row[SPD_G4],  # line 710 (non-NEW_VOLUME branch)
        r1ca=row[SPD_LO],  # line 713
        nopen1=4000 + 160 * (100 - row[SPD_RI]),  # line 717
        nopen2=row[SPD_NF] * 4,  # line 718
        aturb=row[SPD_BR] + 9,  # line 722 (non-HLSYN branch)
        fnscale=fnscale,
        afgain=row[SPD_GF],  # line 770 (non-HLSYN, non-post-v43)
        rnpgain=row[SPD_GN],  # line 749
        azgain=row[SPD_GV],  # line 748 (non-LOWCOMPUTE)
        apgain=row[SPD_GH],  # line 771
        notused=0,
        osgain=row[SPD_OS],  # line 789
        speaker=speaker,  # line 790: curspdef[SPD_NM]
        sex=row[SPD_SEX],  # line 557
    )


__all__ = ["C_SPEAKER_INDEX", "seed_dph_scalars", "spd_chip_from_row"]
