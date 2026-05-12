"""Miscellaneous ls_defs.h atoms not covered by other modules.

Collected from ``src/dapi/src/lts/ls_defs.h`` — small constants
that the C source declares once and uses across the LTS pipeline
but aren't large enough to merit their own module.

The module groups them by topic:

- Walk direction (``FORW`` / ``BACK``)
- Two-phoneme markers (``TWOPH`` / ``MSKPH``)
- Cluster validity (``ILLEGAL`` / ``OK`` / ``TRYS``)
- DGC try marker (``DGC``)
- Suffix flags (``INGS`` / ``ERS`` / ``SSES``)
- Form-class phrase shortcuts (``VPHRASE`` / ``PPHRASE``)
- Dictionary search direction sentinels (``LOOK_HIGHER`` /
  ``LOOK_LOWER``)
- ``NOMAP`` — no ``lscrush`` remapping
"""

from __future__ import annotations

from typing import Final

from dectalk.dic.form_class_bits import FC_CHARACTER, FC_PREP, FC_VERB

# -- Walk direction ---------------------------------------------------------

FORW: Final[int] = 0
"""Forward walk through a PHONE list."""

BACK: Final[int] = 1
"""Backward walk through a PHONE list."""

# -- Two-phoneme combine markers --------------------------------------------

TWOPH: Final[int] = 0x80
"""Flag for ``[ab]`` (two-phoneme) entries — high bit on the phone byte."""

MSKPH: Final[int] = 0x7F
"""Mask used with :data:`TWOPH` to extract the underlying phone code."""

# -- ls_adju cluster validity ----------------------------------------------

ILLEGAL: Final[int] = 0
"""Cluster is illegal (cannot occur in valid English)."""

OK: Final[int] = 1
"""Cluster is legal in any position."""

TRYS: Final[int] = 2
"""Try for an ``s`` or ``S`` on the left of this cluster."""

# -- Try marker for unfamiliar clusters ------------------------------------

DGC: Final[int] = 1
"""``ls_adju`` ``DGC`` ("try stuff") sentinel — see ls_defs.h."""

# -- Suffix-rule enables (originally per-build #ifdef-able) -----------------

INGS: Final[int] = 1
"""Use the ``-ings`` (vs ``-in's``) splitting rule."""

ERS: Final[int] = 1
"""Use the ``-ers`` (vs root + 's') splitting rule."""

SSES: Final[int] = 1
"""Use the ``-ss-es`` (vs root + 's-es') splitting rule."""

# -- Form-class phrase shortcuts -------------------------------------------

VPHRASE: Final[int] = FC_VERB | FC_CHARACTER
"""Form-class mask for "verb phrase" tokens (V+character)."""

PPHRASE: Final[int] = FC_PREP | FC_CHARACTER
"""Form-class mask for "prepositional phrase" tokens (P+character)."""

# -- Dictionary search direction sentinels ----------------------------------

LOOK_HIGHER: Final[int] = 0xFFFF
"""Sentinel: continue searching at a higher dictionary level."""

LOOK_LOWER: Final[int] = 0xFFFE
"""Sentinel: continue searching at a lower dictionary level."""

# -- Misc -------------------------------------------------------------------

NOMAP: Final[int] = 0
"""``lscrush`` value meaning "no remapping for this character"."""


__all__ = [
    "BACK",
    "DGC",
    "ERS",
    "FORW",
    "ILLEGAL",
    "INGS",
    "LOOK_HIGHER",
    "LOOK_LOWER",
    "MSKPH",
    "NOMAP",
    "OK",
    "PPHRASE",
    "SSES",
    "TRYS",
    "TWOPH",
    "VPHRASE",
]
