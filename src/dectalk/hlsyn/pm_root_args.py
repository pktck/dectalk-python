"""``PmRootFunctionArgs`` payload struct from hlsyn/circuit.c.

Translated from the file-private ``PmRootFunctionArgs`` ``typedef
struct`` in ``src/dapi/src/hlsyn/circuit.c`` (lines 58-72). The C
source uses this as the ``void *`` payload threaded through
:c:func:`Brent` / :c:func:`BrentBracket` into
:c:func:`PmRootFunction`, so a typed Python dataclass replaces the
``void *`` cast at the call site (see :mod:`dectalk.hlsyn.brent`).

The fields fall into three groups:

- Frame-level aerodynamic state interpolated by
  :c:func:`SpeechCircuit`: ``ag`` (glottal area), ``acx``
  (oral-constriction area), ``an`` (nasal area), ``ap``
  (post-velar / lip area), ``ue`` (volume-expansion shunt flow),
  ``ps`` (subglottal source pressure), ``Cg`` (glottal compliance),
  ``Cw`` (wall compliance).
- Speaker-level constants captured once: ``rootTwoOverRho``
  (``sqrt(2/rho)``, pre-computed to ``41.885390829169``) and
  ``Lg`` (glottal duct length).
- Time-step precomputations for the implicit-Euler solve:
  ``A`` and ``B`` from the linearised ``newUw = A * newPm - B``
  equation (see :c:func:`SpeechCircuit` docstring in
  ``circuit.c``).

CamelCase field names are kept verbatim to preserve C-source
parity; ``# ruff: noqa: N815`` disables the
:pep:`8` mixed-case rule for this file only.
"""
# ruff: noqa: N815

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PmRootFunctionArgs:
    """Payload threaded through Brent's method into ``pm_root_function``.

    Faithful translation of the ``PmRootFunctionArgs`` struct from
    ``src/dapi/src/hlsyn/circuit.c``:

    .. code-block:: c

        typedef struct
          {
          float rootTwoOverRho;
          float ag;
          float acx;
          float an;
          float ap;
          float ue;
          float ps;
          float Lg;
          float Cg;
          float Cw;
          float A;
          float B;
          } PmRootFunctionArgs;

    The C source uses ``void *`` to opaquely thread this through
    ``Brent`` / ``BrentBracket``; the Python port takes a typed
    ``PmRootFunctionArgs`` directly.

    Attributes:
        rootTwoOverRho: ``sqrt(2 / rho)``, pre-computed to
            ``41.885390829169`` in :c:func:`SpeechCircuit`.
        ag: Glottal area (CGS, cm^2).
        acx: Oral-constriction area (CGS, cm^2).
        an: Nasal-opening area (CGS, cm^2), non-negative.
        ap: Post-velar / lip area (CGS, cm^2), non-negative.
        ue: Shunt flow due to volume expansion (CGS).
        ps: Subglottal source pressure (CGS).
        Lg: Glottal duct length.
        Cg: Glottal compliance, non-negative.
        Cw: Wall compliance, non-negative.
        A: ``newCw / (Rw * newCw + deltaT/2)`` -- the linearised
            ``newUw = A * newPm - B`` coefficient.
        B: ``(oldCw * oldPcw + oldUw * deltaT/2) / (Rw * newCw +
            deltaT/2)`` -- the corresponding bias term.
    """

    rootTwoOverRho: float = 0.0
    ag: float = 0.0
    acx: float = 0.0
    an: float = 0.0
    ap: float = 0.0
    ue: float = 0.0
    ps: float = 0.0
    Lg: float = 0.0
    Cg: float = 0.0
    Cw: float = 0.0
    A: float = 0.0
    B: float = 0.0


__all__ = ["PmRootFunctionArgs"]
