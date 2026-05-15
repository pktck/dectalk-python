"""Static helper that zeros / writes default values to unused LL-frame slots.

Translated from ``src/dapi/src/hlsyn/hlframe.c`` lines 741-792
(``UnusedLLParameters``). The HL synthesiser does not drive every field
of the N-prefixed ``LLFrame``; this helper fills the unused slots with
fixed values so the downstream LL Klatt synthesiser sees a consistent
frame.

Constants ``REMOVE_FORMANT = 1000`` and ``REMOVE_BANDWIDTH = 200`` come
from ``src/dapi/src/hlsyn/hlsyn.h`` (the comments there note the actual
values do not matter -- ``NFTP`` and ``NFTZ`` are set equal to one
another, eliminating the tracheal pole/zero pair).
"""

from __future__ import annotations

from dectalk.hlsyn.ll_frame_n import LLFrameN

REMOVE_FORMANT: int = 1000
"""Sentinel formant frequency used to cancel a pole/zero pair (see hlsyn.h)."""

REMOVE_BANDWIDTH: int = 200
"""Sentinel bandwidth used to cancel a pole/zero pair (see hlsyn.h)."""


def unused_ll_parameters(llframe: LLFrameN) -> None:
    """Zero / default-fill the LL-frame slots the HL layer does not drive.

    Mirrors ``UnusedLLParameters`` in ``hlframe.c``:

    - The tracheal pole/zero pair (``NFTP``/``NFTZ``, ``NBTP``/``NBTZ``)
      is eliminated by setting frequencies equal to one another and
      bandwidths equal to one another.
    - LF-source-only parameter ``NSQ`` is zeroed (only the Klatt natural
      source is used in HLSYN).
    - ``NFL`` (flutter) is zeroed -- HLSYN does not set it.
    - First-formant modifier ``NDF1`` is zeroed (the C comment also
      mentions ``DB1`` but that line is commented out in the source, so
      we follow suit).
    - Parallel-voiced-source amplitudes ``NANV`` / ``NA1V`` / ``NA2V`` /
      ``NA3V`` / ``NA4V`` / ``NATV`` are zeroed (the special parallel
      voiced synthesiser is not used by HLSYN).
    - ``NB6`` is set to 1000 (not used in LL but aesthetically pinned).

    Args:
        llframe: The :class:`LLFrameN` to clean up in place.
    """
    llframe.NFTP = REMOVE_FORMANT
    llframe.NFTZ = REMOVE_FORMANT
    llframe.NBTP = REMOVE_BANDWIDTH
    llframe.NBTZ = REMOVE_BANDWIDTH

    llframe.NSQ = 0

    llframe.NFL = 0

    llframe.NDF1 = 0

    llframe.NANV = 0
    llframe.NA1V = 0
    llframe.NA2V = 0
    llframe.NA3V = 0
    llframe.NA4V = 0
    llframe.NATV = 0

    llframe.NB6 = 1000


# Alias under the original C-source name for inventory tests.
UnusedLLParameters = unused_ll_parameters

__all__ = ["UnusedLLParameters", "unused_ll_parameters"]
