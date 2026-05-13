"""Voice-definition snapshot helper from ph_vset.c.

Translated from ``src/dapi/src/ph/ph_vset.c`` lines 511-518.

The :func:`saveval` function copies the current speaker
definition (``curspdef``) into the saved-value scratch
(``var_val``) so the engine can later restore it after temporary
voice modifications (e.g. ``[:dv ap 110]`` ap-override).

Both arrays are ``SPDEF`` (39) shorts.
"""

from __future__ import annotations

from dectalk.include.cmd_codes import SPDEF
from dectalk.ph.dph_t import DphT


def saveval(p_dph_t: DphT) -> None:
    """Copy ``curspdef[0..SPDEF-1]`` into ``var_val[0..SPDEF-1]``.

    Faithful translation of:

    .. code-block:: c

        void saveval(PDPH_T pDph_t) {
            register int i;
            for (i = 0; i < SPDEF; ++i)
                pDph_t->var_val[i] = pDph_t->curspdef[i];
        }

    The Python port grows ``var_val`` to ``SPDEF`` entries if it's
    shorter; if ``curspdef`` is shorter than ``SPDEF`` the trailing
    entries are zero-filled (matching C behaviour for uninitialised
    array tails).

    Args:
        p_dph_t: PH thread-state instance to mutate.
    """
    # Pre-size both arrays to SPDEF entries.
    while len(p_dph_t.var_val) < SPDEF:
        p_dph_t.var_val.append(0)
    while len(p_dph_t.curspdef) < SPDEF:
        p_dph_t.curspdef.append(0)

    for i in range(SPDEF):
        p_dph_t.var_val[i] = p_dph_t.curspdef[i]


__all__ = ["saveval"]
