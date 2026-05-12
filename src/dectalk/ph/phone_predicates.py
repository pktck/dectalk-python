"""Phone-range predicates from ph_defs.h.

Translated from ``src/dapi/src/ph/ph_defs.h`` lines 778-781 — the
four range-check macros the PH main loop (``phmain.c``) uses to
classify control phones into structural buckets:

- :func:`isbound` — ``WBOUND..VPSTART``: word / phrase boundary
- :func:`ispause` — ``VPSTART..EXCLAIM``: pause-bearing boundary
- :func:`issmark` — ``WBOUND..EXCLAIM``: any sentence-mark phone
- :func:`isdelim` — ``COMMA..EXCLAIM``: clause delimiter

All four take a phone code (one of the :mod:`dectalk.include.
phoneme_codes` constants) and return :class:`bool`. The
endpoints are inclusive.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import (
    COMMA,
    EXCLAIM,
    VPSTART,
    WBOUND,
)


def isbound(ph: int) -> bool:
    """Return True iff ``ph`` is a word/phrase boundary marker.

    Faithful translation of:

    .. code-block:: c

        #define isbound(ph) ((ph) >= WBOUND && (ph) <= VPSTART)
    """
    return WBOUND <= ph <= VPSTART


def ispause(ph: int) -> bool:
    """Return True iff ``ph`` is a pause-bearing boundary.

    Faithful translation of:

    .. code-block:: c

        #define ispause(ph) ((ph) >= VPSTART && (ph) <= EXCLAIM)
    """
    return VPSTART <= ph <= EXCLAIM


def issmark(ph: int) -> bool:
    """Return True iff ``ph`` is any sentence-mark phone.

    Faithful translation of:

    .. code-block:: c

        #define issmark(ph) ((ph) >= WBOUND && (ph) <= EXCLAIM)
    """
    return WBOUND <= ph <= EXCLAIM


def isdelim(ph: int) -> bool:
    """Return True iff ``ph`` is a clause delimiter.

    Faithful translation of:

    .. code-block:: c

        #define isdelim(ph) ((ph) >= COMMA && (ph) <= EXCLAIM)
    """
    return COMMA <= ph <= EXCLAIM


__all__ = [
    "isbound",
    "isdelim",
    "ispause",
    "issmark",
]
