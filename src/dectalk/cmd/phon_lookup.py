"""ASCII-phoneme byte lookup from cm_phon.c.

Translated from ``src/dapi/src/cmd/cm_phon.c``:

- :func:`cm_phon_lookup_asc` — pure variant of the linear search
  through the per-language ``ascky`` (ASCII-phoneme) array. Returns
  the index of ``ph`` in the array, or ``-1`` if not found.
"""

from __future__ import annotations

from dectalk.include.usa_ascky import usa_ascky


def cm_phon_lookup_asc(ph: int, ascky: bytes = usa_ascky) -> int:
    """Return the index of ``ph`` in ``ascky``, or ``-1``.

    Faithful translation of:

    .. code-block:: c

        int cm_phon_lookup_asc(LPTTS_HANDLE_T phTTS, unsigned int ph) {
            unsigned char *ascky = pKsd_t->ascky;
            int size = pKsd_t->ascky_size;
            for (i = 0; i < size; i++) {
                if (ph == ascky[i]) {
                    PUSH_PHONE = i;
                    return TRUE;
                }
            }
            return FALSE;
        }

    The C source returns 1 (TRUE) on hit and writes the index to
    a global PUSH_PHONE; the Python port returns the index directly
    on hit and ``-1`` on miss, since callers can choose what to
    do with it.

    Defaults the ``ascky`` table to the US English variant
    (:data:`usa_ascky`); callers wanting another language pass their
    own.

    Args:
        ph: ASCII byte value to look up.
        ascky: Lookup table (defaults to US).

    Returns:
        The 0-based index of ``ph`` in ``ascky``, or ``-1`` if no
        entry matches.
    """
    for i, entry in enumerate(ascky):
        if entry == ph:
            return i
    return -1


__all__ = ["cm_phon_lookup_asc"]
