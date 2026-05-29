"""US-Paul SPD_CHIP defaults and factory.

Re-exports :class:`~dectalk.ph.spdef_chip.SpdChip` (the dataclass mirror
of the C ``SPD_CHIP`` struct from ``viphdefs.h``) and adds a factory that
returns the US-English Paul-voice chip defaults.

The chip-format ``SPD_CHIP`` block is built by ``setspdef()``
(``ph/ph_vset.c`` lines 541-791 -- it is *open* source, not in the
closed ``libttsapi.so``) from ``curspdef[]``, the SPDEF voice row after
the tune delta is added (``ph_vset.c:464`` ``curspdef[i] = newspdef[i]
+ tunespdef[i]``). The downstream synth (``vtm1.c::read_speaker_
definition``, ported in :mod:`dectalk.vtm.seed_speaker_state`) reads the
chip fields straight back out.

**Active build configuration.** The shipped x86_64 Linux oracle compiles
with ``VDF_DECTALK_43`` defined and ``HLSYN`` / ``CHANGES_AFTER_V43`` /
``LOWCOMPUTE`` / ``LOW_COST_VERSION`` / ``SW_VOLUME`` / ``FP_VTM`` *all
undefined* (``src/dectalkf.h`` -> ``dectalkf_klsyn.h``: ``#define HLSYN``
is commented out, only ``#ifdef EPSON_ARM7`` re-enables it;
``#define VDF_DECTALK_43`` is active; ``ph_vdefi.d`` confirms the
build pulled ``p_us_vdf_dectalk43.c`` + ``p_us_vdf_oldtune.c``).
Consequently:

* The voice row is the non-``_8`` ``paul`` from
  ``p_us_vdf_dectalk43.c`` (``ph_vset.c:454-457`` selects the non-``_8``
  ``voidef[voice]`` rows at the US sample rate, 11025 Hz >= 8763).
* ``paul_tune`` in ``p_us_vdf_oldtune.c`` is all zeros, so
  ``curspdef`` == the raw ``paul`` row.
* The retired HLSYN file ``p_us_vdf1.c`` ``paul_8`` (GF=55 GH=55 GV=60
  GN=71 G1=71 G2=65 G3=65 G4=66 LO=70 with HLSYN glottal areas) is
  **not** the live path; the previous version of this module sourced
  those stale values.

``setspdef()`` transform for the active (plain) build -- the branches
taken with the macros above all undefined::

    afgain  <- GF                       (verbatim)
    apgain  <- GH                       (verbatim)
    azgain  <- GV                       (verbatim, non-LOWCOMPUTE)
    rnpgain <- GN                       (verbatim)
    r5ca    <- G1                        (verbatim)
    r4ca    <- G2                        (verbatim)
    r3ca    <- G3                        (verbatim)
    r2ca    <- G4                        (verbatim, non-LOW_COST_VERSION)
    r1ca    <- LO                        (verbatim)
    osgain  <- SPD_OS (output gain mult) (0 for the dectalk43 paul row)
    r4cc    <- B4                        (cascade-4 bandwidth)
    r5cc    <- B5                        (cascade-5 bandwidth)
    r4pb    <- F7   r5pb <- F8           (parallel-formant freqs)
    t0jit   <- LA << 3
    nopen1  <- 4000 + 160*(100 - RI)
    nopen2  <- NF * 4
    aturb   <- BR + 9                    (non-CHANGES_AFTER_V43)
    r4cb    <- (F4 * fnscale) >> 12      (cascade-4 centre, scaled)
    r5cb    <- (F5 * fnscale) >> 12
    fnscale <- (200 - HS) * 41
    sex     <- SEX (1 = MALE, 0 = FEMALE)
    speaker <- 0 (Paul is the canonical zero-index voice)

This module is the *gain lever* for the ``DECTALK_USE_VTM1=1`` synth
path (``vtm1.c`` integer Klatt, the synthesiser the shipped
``libtts_us.so`` runs). The gain fields below now carry the active
dectalk43 ``paul`` values so per-source amplitudes (AV / AF / AP / the
cascade resonator gains) match the C oracle.

.. note::

   The non-gain ``setspdef`` derivations -- ``fnscale = (200-HS)*41``
   (this module keeps the Q12-unity ``4096`` that the pure-Python
   formant path in :func:`dectalk.api.speak._render_clause_full`
   relies on), ``nopen1 = 4000 + 160*(100-RI)``, ``aturb = BR + 9``,
   and the ``(F * fnscale) >> 12`` formant-centre scaling -- are *not*
   applied here yet. They drive formant frequency / open-quotient /
   breathiness rather than per-source amplitude, and are tracked
   separately from this voice/amplitude work.
"""

from __future__ import annotations

# Re-export the shared dataclass so callers only need this module.
from dectalk.ph.spdef_chip import SpdChip

__all__ = ["SpdChip", "default_us_paul_spd"]

# ---------------------------------------------------------------------------
# US-English Paul-voice constants
#
# Source: the active ``paul`` row in
# ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf_dectalk43.c`` (lines 383-423,
# the non-``_8`` row selected at >= 8763 Hz) plus the all-zero
# ``paul_tune`` delta from ``p_us_vdf_oldtune.c``. The "C value"
# annotation lists the SPDEF slot literal so the trail back to the
# source is one ``rg`` away.
# ---------------------------------------------------------------------------

# --- Gain fields (the voice/amplitude lever) -------------------------------
# These are the verbatim ``setspdef`` copies in the active build; they
# feed ``seed_speaker_state`` -> ``amptable[]`` -> per-source synth gain.
_PAUL_R5CA: int = 68  # G1 (C value: 68)
_PAUL_R4CA: int = 60  # G2 (C value: 60)
_PAUL_R3CA: int = 48  # G3 (C value: 48)
_PAUL_R2CA: int = 64  # G4 (C value: 64)
_PAUL_R1CA: int = 86  # LO (C value: 86)
_PAUL_AFGAIN: int = 70  # GF (C value: 70)
_PAUL_APGAIN: int = 70  # GH (C value: 70)
_PAUL_AZGAIN: int = 65  # GV (C value: 65)
_PAUL_RNPGAIN: int = 74  # GN (C value: 74)
# osgain <- SPD_OS. The dectalk43 paul row's output-gain multiplier is 0
# (the old ``-1`` came from the FP_VTM-only branch of the retired
# ``p_us_vdf.c`` / HLSYN ``paul_8`` files). vtm1.c:1046 only adjusts the
# overall gain ``if (SpeakerGain != 0)``, so 0 is the C no-op default.
_PAUL_OSGAIN: int = 0

# --- Formant / structural fields (non-gain; OUT OF SCOPE for this lever) ----
# These are *deliberately left at the previous values* (sourced from
# ``p_us_vdf1.c`` ``paul_8``). This module's Python convention stores the
# cascade-4/5 *frequencies* in ``r4cc``/``r5cc`` and *bandwidths* in
# ``r4cb``/``r5cb`` -- the inverse of the C ``setspdef`` chip layout
# (``r4cc <- B4``, ``r4cb <- (F4*fnscale)>>12``) -- and
# :func:`dectalk.ph.parstochip_to_frames.parstochip_to_llframe` reads
# ``r4cc`` as the emitted F4. The active dectalk43 paul formants
# (F4=3300 B4=260 F5=3650 B5=330 F7=3350 F8=3850) differ from these
# paul_8 values, but re-sourcing them is a *formant*-parity change with
# its own SpdChip-semantics reconciliation, separate from this
# voice/amplitude (gain) lever. Tracked as follow-up.
_PAUL_R4CC: int = 3400  # paul_8 F4 (frequency, per Python r4cc convention)
_PAUL_R4CB: int = 260  # paul_8 B4 (bandwidth)
_PAUL_R5CC: int = 4300  # paul_8 F5
_PAUL_R5CB: int = 280  # paul_8 B5
_PAUL_R4PB: int = 3400  # paul_8 F7 -- frequency despite "pb" name
_PAUL_R5PB: int = 4800  # paul_8 F8 -- frequency despite "pb" name
# fnscale = 4096 (Q12 unity). The active ``setspdef`` computes
# ``(200-HS)*41 = 4100`` for HS=100, but the pure-Python formant path
# (``speak._render_clause_full`` -> phdraw ``frac4mul(F, fnscale)``)
# is keyed to the Q12-unity ``4096`` identity; keep it here so the
# formant trajectory is unchanged. Reconciling 4096 vs 4100 is a
# formant-parity concern outside this amplitude lever.
_PAUL_FNSCALE: int = 4096
_PAUL_SEX: int = 1  # MALE


def default_us_paul_spd() -> SpdChip:
    """Return a fresh :class:`SpdChip` initialised with US-Paul chip defaults.

    The gain fields (``afgain``/``apgain``/``azgain``/``rnpgain`` and the
    cascade resonator gains ``r1ca``..``r5ca``) plus ``osgain`` are the
    *active* values: the non-``_8`` ``paul`` row from
    ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf_dectalk43.c`` (the table the
    shipped binary links, selected at the 11025 Hz US sample rate), run
    through the plain-build ``setspdef()`` gain copies. ``paul_tune`` is
    all zeros, so no tune delta applies.

    ``fnscale`` is kept at ``4096`` (Q12 unity) for the pure-Python
    formant path; see the module note for the ``(200-HS)*41``
    reconciliation deferred to formant-parity work.

    Returns:
        A new :class:`SpdChip` instance with the active US-Paul chip
        defaults.
    """
    return SpdChip(
        r4cb=_PAUL_R4CB,
        r4cc=_PAUL_R4CC,
        r5cb=_PAUL_R5CB,
        r5cc=_PAUL_R5CC,
        r4pb=_PAUL_R4PB,
        r5pb=_PAUL_R5PB,
        t0jit=0,
        r5ca=_PAUL_R5CA,
        r4ca=_PAUL_R4CA,
        r3ca=_PAUL_R3CA,
        r2ca=_PAUL_R2CA,
        r1ca=_PAUL_R1CA,
        nopen1=0,
        nopen2=0,
        aturb=0,
        fnscale=_PAUL_FNSCALE,
        afgain=_PAUL_AFGAIN,
        rnpgain=_PAUL_RNPGAIN,
        azgain=_PAUL_AZGAIN,
        apgain=_PAUL_APGAIN,
        notused=0,
        osgain=_PAUL_OSGAIN,
        speaker=0,  # Paul = speaker index 0
        sex=_PAUL_SEX,
    )
