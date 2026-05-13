"""F0 gesture-decay table from ph_drwt02.c.

Translated from ``src/dapi/src/ph/ph_drwt02.c`` line 271:

.. code-block:: c

    const short gst_delta[9] = { 90, 80, 70, 60, 50, 43, 20, 0 };

The C array declares 9 entries but the initialiser provides only
8 values; C zero-fills the trailing entry. The Python port
mirrors the layout (9-tuple, last entry is 0).

The table is a decaying-multiplier table indexed by gesture
number (the n-th gesture from the start of a phrase). Used by
``set_tglst()`` to scale stress-rise / fall amounts as the
phrase progresses — earlier gestures get full amplitude (90),
later ones get progressively reduced (down to 0 after 7 gestures).
"""

from __future__ import annotations

from typing import Final

gst_delta: Final[tuple[int, ...]] = (90, 80, 70, 60, 50, 43, 20, 0, 0)
"""9-entry F0 gesture-decay multiplier table (Q-0 percentages)."""


__all__ = ["gst_delta"]
