"""Bidirectional glyph ↔ allophone-code lookup from dic_comm.c.

Translated from ``src/dapi/src/dic/dic_comm.c``:

- :func:`toph` — DECtalk-ASCII glyph → allophone code. Raises on
  unknown glyphs (the C source ``exit(1)``s with a diagnostic).
- :func:`from_ph` — allophone code → glyph byte. Returns the first
  matching glyph in ``ptab[]`` order, or the last glyph's byte if
  no match (matching the C source's loop-falls-through behaviour).
"""

from __future__ import annotations

from dectalk.dic.ptab import ptab_us

_PHONE_TO_GLYPH: dict[int, str] = {}
for _glyph, _code in ptab_us.items():
    # ``from_ph`` walks ``ptab[]`` linearly and stops at the first
    # match; we mirror that by NOT overwriting later entries (so the
    # earliest-listed glyph for a given code wins).
    if _code not in _PHONE_TO_GLYPH:
        _PHONE_TO_GLYPH[_code] = _glyph


class UnknownGlyphError(KeyError):
    """Raised when :func:`toph` receives a glyph not in :data:`ptab_us`."""


def toph(glyph: str | int) -> int:
    r"""Return the allophone code for a DECtalk-ASCII glyph byte.

    Faithful translation of:

    .. code-block:: c

        unsigned char toph(unsigned char c) {
            PTAB *ptp;
            if (c == 0) return c;
            ptp = &ptab[0];
            while (ptp < &ptab[NPTAB] && ptp->p_graph != c) ++ptp;
            if (ptp == &ptab[NPTAB]) {
                printf("Bad phone == %02X\\n", c);
                exit(1);
            }
            return ptp->p_phone;
        }

    Args:
        glyph: Either a single-character str glyph (``'e'``, ``'@'``,
            etc.) or its int byte value.

    Returns:
        The allophone-code int that the LTS/PH pipeline uses for
        that glyph.

    Raises:
        UnknownGlyphError: if the glyph isn't in :data:`ptab_us`.
    """
    if isinstance(glyph, int):
        if glyph == 0:
            return 0
        key = chr(glyph)
    else:
        key = glyph
    try:
        return ptab_us[key]
    except KeyError as exc:
        msg = f"Bad phone == {key!r} (0x{ord(key):02x})"
        raise UnknownGlyphError(msg) from exc


def from_ph(code: int) -> str:
    """Return the DECtalk-ASCII glyph for an allophone code.

    Faithful translation of:

    .. code-block:: c

        unsigned char from_ph(unsigned char c) {
            PTAB *ptp = &ptab[0];
            while (ptp < &ptab[NPTAB] && ptp->p_phone != c) ++ptp;
            return ptp->p_graph;
        }

    The C source's loop falls off the end if no match; ``ptp`` then
    points one past the array. ``ptp->p_graph`` reads adjacent
    memory — undefined behaviour. In practice the last entry in
    ``ptab[]`` is ``{ '-', SBOUND }``, so a no-match call typically
    returns ``'-'`` on common platforms. Python mirrors this by
    returning ``'-'`` for codes not in the inverse map.

    Args:
        code: Allophone-code int.

    Returns:
        The first DECtalk-ASCII glyph (string of length 1) whose
        ``p_phone`` field equals ``code``, or ``'-'`` if no glyph
        matches.
    """
    return _PHONE_TO_GLYPH.get(code, "-")


__all__ = ["UnknownGlyphError", "from_ph", "toph"]
