"""``cm_util_init_type`` helper from cmd/cm_util.c.

Translated from ``src/dapi/src/cmd/cm_util.c`` lines 272-292.

:func:`cm_util_init_type` is the CMD-module init hook that loads
the per-language data tables. It clears ``loaded_languages`` (so a
re-init starts with a fresh chain) and calls :func:`usa_init` to
populate the chain with the US-English node.

The C source has a ``#ifdef MSDOS`` guard that skips both
statements on MSDOS — for Linux (``libtts_us.so``) the guard is
inactive and both run. The Python port targets Linux, so both run
unconditionally.
"""

from __future__ import annotations

from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.usa_init import usa_init


def cm_util_init_type(p_ksd_t: KsdT) -> None:
    """Clear ``loaded_languages`` and run the per-language init.

    Faithful translation of:

    .. code-block:: c

        void cm_util_init_type(PKSD_T pKsd_t) {
        #ifndef MSDOS
            pKsd_t->loaded_languages = 0;
            usa_init(pKsd_t);
        #endif
        }

    Args:
        p_ksd_t: Kernel shared-data struct to (re-)initialise.
    """
    p_ksd_t.loaded_languages = None  # C: pKsd_t->loaded_languages = 0
    usa_init(p_ksd_t)


__all__ = ["cm_util_init_type"]
