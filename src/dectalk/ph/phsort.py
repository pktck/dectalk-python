"""``phsort`` — top-level PH-sort dispatcher from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 271-283.

The C function is a one-line language dispatcher:

.. code-block:: c

    int phsort (LPTTS_HANDLE_T phTTS)
    {
        PKSD_T pKsd_t = phTTS->pKernelShareData;
        if (pKsd_t->lang_curr == LANG_french)
        {
            return(fr_phsort(phTTS));
        }
        else
        {
            return(all_phsort(phTTS));
        }
    }

French is the only language with its own per-language sort engine
(``fr_phsort``); every other language (US English, UK English,
German, Spanish, Latin American Spanish) routes through
``all_phsort``. The dispatch is purely a function of
``pKsd_t->lang_curr``.

The Python pipeline currently routes the PH-sort stage through
``dectalk._capi`` for byte-identical output, so this shim only
captures the dispatch decision and the planned target. The actual
sort engines (``all_phsort`` — 1284 lines, ``fr_phsort`` — ~140
lines) remain deferred under Phase E in
``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dectalk.kernel.lang_codes import LANG_french


@dataclass(frozen=True)
class PhsortDispatch:
    """Captured dispatch decision from :func:`phsort`.

    Attributes:
        language: The ``lang_curr`` value the caller is on.
        target: ``"fr_phsort"`` for French, ``"all_phsort"`` for every
            other language. Mirrors the C source's binary choice.
    """

    language: int
    target: str


_FR_PHSORT: Final[str] = "fr_phsort"
_ALL_PHSORT: Final[str] = "all_phsort"


def phsort(language: int) -> PhsortDispatch:
    """Return which per-language sort engine would handle the utterance.

    Faithful translation of the C dispatcher in ``ph_sort.c``. The
    Python port doesn't (yet) call the underlying sort engines --
    those still route through ``dectalk._capi`` for the bit-identical
    audio path -- so this function returns the dispatch decision as
    a :class:`PhsortDispatch` value the caller can route on.

    Args:
        language: The ``pKsd_t->lang_curr`` value at the point of
            dispatch. Use :data:`dectalk.kernel.lang_codes.LANG_*` for
            the right code per language.

    Returns:
        A :class:`PhsortDispatch` carrying the input language and the
        name of the sort engine the C source would invoke.
    """
    target = _FR_PHSORT if language == LANG_french else _ALL_PHSORT
    return PhsortDispatch(language=language, target=target)


# PEP8 alias the inventory enumerator recognises under the C name.
Phsort = phsort

__all__ = ["Phsort", "PhsortDispatch", "phsort"]
