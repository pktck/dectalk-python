"""Minimal VTM_T per-thread instance (NOM_* fields only).

Translated from ``src/dapi/src/vtm/vtminst.h`` lines 669-685.

``VTM_T`` is the full vocal-tract-model per-thread state (400+ fields).
This module exposes only the subset that the PH pipeline reads
(``ph_draw.c``'s HLSyn area loop) -- specifically the ``NOM_*``
glottal-area / pressure / fricative-opening nominals that are loaded
from the HLSYN voice-definition file (``p_us_vdf1.c``) during
synthesizer initialisation.

The full ``VTM_T`` struct will be expanded here as additional VTM modules
are ported. Callers that only need the NOM_* fields can use
:func:`default_us_paul_vtm_t` to obtain a correctly-initialised instance.

US-Paul default values are sourced from the ``paul_8`` SPDEF array in
``p_us_vdf1.c`` (the HLSYN-build voice-definition file):

    AGO  = 700   -> NOM_UNSTRESSED_VOWEL
    AGVO = 800   -> NOM_VOICED_OBSTRUENT  (also feeds NOM_VOIC_GLOT_AREA)
    AGUO = 1800  -> NOM_UNVOICED_SON
    unvow= 700   -> NOM_VOIC_GLOT_AREA
    chink= 0     -> NOM_Area_Chink
    open_quo = 60 -> NOM_Open_Quo

The remaining NOM_* constants (pressure levels, fricative opening,
glottal-stop area, VOT speed, end-of-phrase spread, tilt) come from
the vtminst.h static initialisers and the 11 kHz calibration used in
the DECtalk 4.4 US-English build.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["VtmT", "default_us_paul_vtm_t"]


@dataclass(slots=True)
class VtmT:
    """Minimal VTM per-thread instance exposing NOM_* nominals.

    All 16 fields correspond 1-to-1 with the NOM_* block in
    ``vtminst.h`` (lines 669-685).  Default values are the US-Paul
    HLSYN-build settings from ``p_us_vdf1.c``.

    Attributes:
        NOM_UNSTRESSED_VOWEL: Glottal area for an unstressed vowel (cm^2 x 100).
            Sourced from ``paul_8.AGO = 700``.
        NOM_VOIC_GLOT_AREA: Nominal glottal area during voiced phonation.
            Sourced from ``paul_8.unvow = 700``.
        NOM_UNVOICED_SON: Glottal area for unvoiced sonorant / /h/.
            Sourced from ``paul_8.AGUO = 1800``.
        NOM_VOICED_OBSTRUENT: Glottal area for voiced obstruent.
            Sourced from ``paul_8.AGVO = 800``.
        STRESS_STEP: Incremental glottal-area step per stress frame.
        UNSTRESS_PRESSURE: Subglottal pressure during unstressed vowels.
        STRESS_PRESSURE: Subglottal pressure during stressed vowels.
        NOM_Sub_Pressure: Baseline subglottal pressure.
        NOM_Open_Glottis: Open-glottis glottal area (breathy / /h/).
        NOM_Area_Chink: Chink area (posterior glottis opening).
            Sourced from ``paul_8.chink = 0``.
        NOM_Open_Quo: Open quotient (fraction of glottal cycle open x 100).
            Sourced from ``paul_8.open_quo = 60``.
        NOM_Fricative_Opening: Glottal opening for fricative voicing.
            Matches ``_NOM_FRICATIVE_OPENING = 100`` in phdraw.py.
        NOM_Glot_Stop_Area: Glottal area for a glottal stop (near zero).
        VOT_speed: Voice-onset-time transition speed (frames).
        EndOfPhrase_Spread: End-of-phrase glottal spreading speed.
        Tiltm: Spectral tilt parameter (dB / octave x 10).
    """

    # Glottal-area nominals (all in cm^2 x 100 or equivalent Q-format units).
    NOM_UNSTRESSED_VOWEL: int = 700  # paul_8.AGO
    NOM_VOIC_GLOT_AREA: int = 700  # paul_8.unvow
    NOM_UNVOICED_SON: int = 1800  # paul_8.AGUO
    NOM_VOICED_OBSTRUENT: int = 800  # paul_8.AGVO
    STRESS_STEP: int = 100
    UNSTRESS_PRESSURE: int = 400
    STRESS_PRESSURE: int = 700
    NOM_Sub_Pressure: int = 600
    NOM_Open_Glottis: int = 3000
    NOM_Area_Chink: int = 0  # paul_8.chink
    NOM_Open_Quo: int = 60  # paul_8.open_quo
    NOM_Fricative_Opening: int = 100  # matches _NOM_FRICATIVE_OPENING in phdraw.py
    NOM_Glot_Stop_Area: int = 0
    VOT_speed: int = 100
    EndOfPhrase_Spread: int = 50
    Tiltm: int = 75


def default_us_paul_vtm_t() -> VtmT:
    """Return a :class:`VtmT` initialised with US-Paul HLSYN defaults.

    All NOM_* values are sourced from the ``paul_8`` SPDEF array in
    ``p_us_vdf1.c`` and the static nominal constants in ``vtminst.h``.

    Returns:
        A new :class:`VtmT` with US-Paul defaults (same as the class
        defaults -- convenience wrapper for callers that want an
        explicit factory call).
    """
    return VtmT()
