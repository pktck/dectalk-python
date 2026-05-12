"""Word-extraction helper from cm_text.c.

Translated from ``src/dapi/src/cmd/cm_text.c``:

- :func:`cm_text_get_word` — pull the next word out of a clause
  buffer. Two modes:

  * ``which=0`` (full): skip leading whitespace, then copy until a
    non-clause-non-hyphenated punctuation boundary; the C source
    treats ``-`` and ``.`` as in-word characters, plus a punctuation
    char is kept if the *next* char isn't space/clause-terminator.
  * ``which=1`` (abbreviation lookup): skip leading whitespace, then
    copy until the next whitespace (only ``-`` is kept). Used by the
    abbreviation-dictionary search.

  In both modes the control byte ``0x82`` is silently dropped.
"""

from __future__ import annotations

from dectalk.cmd.char_types_table import MARK_clause, MARK_punct, MARK_space, char_types

_CONTROL_DROP = 0x82  # GL 02/07/1997 — strip this Telnet-style control byte


def _is_space_or_clause(c: int) -> bool:
    return bool(char_types[c] & (MARK_space | MARK_clause))


def cm_text_get_word(
    clausebuf: bytes,
    which: int,
    start: int = 0,
) -> bytes:
    r"""Return the next word from ``clausebuf`` starting at ``start``.

    Faithful translation of:

    .. code-block:: c

        unsigned char *cm_text_get_word(unsigned char *clausebuf,
                                         unsigned char *buf,
                                         int which) {
            int i = 0, j = 0;
            while ((char_types[clausebuf[i]] & MARK_space) != 0) i++;
            if (which == 0) {
                while (((char_types[clausebuf[i]] & (MARK_space | MARK_clause)) == 0
                          && clausebuf[i] != '\0')
                       || clausebuf[i] == '-'
                       || clausebuf[i] == '.'
                       || ((char_types[clausebuf[i]] & MARK_punct) != 0
                          && clausebuf[i+1] != '\0'
                          && (char_types[clausebuf[i+1]] & (MARK_space|MARK_clause)) == 0)) {
                    if (clausebuf[i] != 0x82) buf[j++] = clausebuf[i];
                    i++;
                }
            } else {
                while ((char_types[clausebuf[i]] & MARK_space) == 0
                          && clausebuf[i] != '\0'
                       || clausebuf[i] == '-') {
                    if (clausebuf[i] != 0x82) buf[j++] = clausebuf[i];
                    i++;
                }
            }
            buf[j] = '\0';
            return buf;
        }

    The C function takes an output buffer pointer and returns it;
    Python returns the extracted word as bytes directly.

    Args:
        clausebuf: NUL-terminated buffer (bytes; a trailing NUL is
            assumed and the scan stops on a NUL byte just like C).
        which: ``0`` for full word extraction, ``1`` for the
            abbreviation-lookup mode.
        start: Starting position in ``clausebuf`` (default 0). Used
            when the caller needs to extract the *next* word after a
            previous call.

    Returns:
        The extracted word as bytes (no trailing NUL).
    """
    i = start
    buf_len = len(clausebuf)

    # Skip leading whitespace (or '\0' to end).
    while i < buf_len and clausebuf[i] != 0 and (char_types[clausebuf[i]] & MARK_space):
        i += 1

    out = bytearray()
    if which == 0:
        while i < buf_len and clausebuf[i] != 0:
            c = clausebuf[i]
            # The big disjunction from the C source — three ways to stay in the word:
            in_word = (
                (char_types[c] & (MARK_space | MARK_clause)) == 0
                or c == ord("-")
                or c == ord(".")
                or (
                    (char_types[c] & MARK_punct) != 0
                    and i + 1 < buf_len
                    and clausebuf[i + 1] != 0
                    and not _is_space_or_clause(clausebuf[i + 1])
                )
            )
            if not in_word:
                break
            if c != _CONTROL_DROP:
                out.append(c)
            i += 1
    else:
        while i < buf_len and clausebuf[i] != 0:
            c = clausebuf[i]
            in_word = (char_types[c] & MARK_space) == 0 or c == ord("-")
            if not in_word:
                break
            if c != _CONTROL_DROP:
                out.append(c)
            i += 1

    return bytes(out)


__all__ = ["cm_text_get_word"]
