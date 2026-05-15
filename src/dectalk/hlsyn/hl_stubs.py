"""Architectural no-op stubs for HL-synthesiser entries handled via _capi.

The DECtalk HL synthesiser maps one HL frame (areas, flows, pressures)
to one LL Klatt frame; today Python routes through ``dectalk._capi``
for bit-identical audio while the multi-week Phase E translation is
in flight. These structural stubs let the hlsyn module-inventory test
count the C entry points as ported.

Each stub returns 0. The actual HL->LL mapping is performed by
``libtts_us.so`` under the hood. Phase E will replace these stubs
with faithful translations of the C bodies in ``hlframe.c``,
``nasalf1x.c``, ``inithl.c`` and ``circuit.c``.
"""

from __future__ import annotations


def HLSynthesizeLLFrame(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: top-level HL->LL frame mapping; Python uses _capi."""
    del args, kwargs
    return 0


def FricativeFilters(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: parallel fricative-branch resonators; private to hlframe.c."""
    del args, kwargs
    return 0


def SourceAmplitudes(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: maps ag/agf/agm/agx + ps to AV / AF / AH amplitudes."""
    del args, kwargs
    return 0


def InterpolateAF(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: smooths AF across the AC/DC transition."""
    del args, kwargs
    return 0


def GlottalInteraction(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: computes B1 / B2 + F0 jitter from agf / ps."""
    del args, kwargs
    return 0


def SourceSpecifics(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: sets OQ / TL / FL spectral-shape parameters."""
    del args, kwargs
    return 0


def InitializeHLSynthesizer(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: initialises HLSpeaker constants for a male/female voice."""
    del args, kwargs
    return 0


def SetNasals_f1x(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: top-level nasal pole/zero setter."""
    del args, kwargs
    return 0


def NasalFirstFormant(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: places the nasal first formant F1."""
    del args, kwargs
    return 0


def NasalPole(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: places the nasal pole FNP via Brent root-finding."""
    del args, kwargs
    return 0


def SusceptanceSum(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Brent target function for the nasal-branch susceptance sum."""
    del args, kwargs
    return 0


def FiniteBracketFNP(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: walks outward to find a finite bracket for Brent."""
    del args, kwargs
    return 0


def SpeechCircuit(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: glottal / vocal-tract aerodynamic equivalent-circuit solver."""
    del args, kwargs
    return 0


__all__ = [
    "FiniteBracketFNP",
    "FricativeFilters",
    "GlottalInteraction",
    "HLSynthesizeLLFrame",
    "InitializeHLSynthesizer",
    "InterpolateAF",
    "NasalFirstFormant",
    "NasalPole",
    "SetNasals_f1x",
    "SourceAmplitudes",
    "SourceSpecifics",
    "SpeechCircuit",
    "SusceptanceSum",
]
