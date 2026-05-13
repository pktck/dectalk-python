"""``durlookup`` table-walking lookup from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 1990-2020.

Walks a length-prefixed ``short table[]`` of pattern entries,
comparing each entry's key against an input symbol pattern. The
table layout is::

    [len_0, key_0_0, key_0_1, ..., EOS, payload_0_0, ..., payload_0_{len_0-K},
     len_1, key_1_0, ..., EOS, payload_1_0, ...,
     ...,
     0]                                  # end-of-table sentinel

Each entry begins with a one-word ``len`` that covers all words
after the leading ``len`` itself (key + EOS + payload). A zero
``len`` marks the end of the table. The key is compared against
the input symbol stream until either:

- a mismatch is found (skip to next entry), or
- the input symbol hits ``GEN_SIL`` (end of input pattern — no
  match, skip), or
- the table key terminates with ``EOS`` (full key match — return
  the index just past the ``EOS``, which is the start of the
  entry's phoneme payload).

Returns the index into ``table`` of the start of the matched
entry's payload, or ``None`` if no entry matches.
"""

from __future__ import annotations

from dectalk.include.dectalk import EOS
from dectalk.ph.dph_t import DphT
from dectalk.ph.utterance_constants import GEN_SIL


def durlookup(
    p_dph_t: DphT | None,
    symbol: list[int],
    table: list[int],
) -> int | None:
    """Return the index of the matched entry's payload, or ``None``.

    Faithful translation of:

    .. code-block:: c

        short *durlookup(PDPH_T pDph_t, short *symbol, short table[]) {
            short *lp;
            short *cp;
            short *tp;
            int   len;

            tp = &table[0];                 /* Start at the start. */
            while ((len = *tp++) != 0) {    /* 0 => end of table.  */
                lp = symbol;
                cp = tp;                    /* Start of text. */
                for (;;) {
                    if (*lp != *cp++)         /* Lose match process */
                        break;
                    if (*lp == GEN_SIL)       /* Input string end reached */
                        break;
                    if (*cp == EOS)           /* Win. */
                        return (++cp);        /* Return phonemes. */
                    ++lp;
                }
                tp += len;                  /* Next. */
            }
            return (NULL);
        }

    The ``p_dph_t`` argument is unused (the C source carries it for
    API consistency with the rest of the PH module — typically for
    debug-tracing through commented-out diagnostics).

    Pointer semantics in the C version: ``cp = tp`` aliases the
    cursor into ``table`` at the start of the entry's key; ``cp++``
    advances after the comparison; ``return (++cp)`` returns the
    cursor advanced one past the ``EOS`` sentinel — i.e. the start
    of the payload. The Python port returns the equivalent integer
    index into ``table``.

    Args:
        p_dph_t: PH thread state (unused; kept for API consistency).
        symbol: Input phoneme pattern; the C code reads until it
            hits :data:`GEN_SIL` or finds a match/mismatch.
        table: Length-prefixed lookup table. Each entry is
            ``[len, key..., EOS, payload...]``; the table itself is
            terminated by a zero-length entry.

    Returns:
        The index into ``table`` of the start of the matched
        entry's payload (the word just after the ``EOS``), or
        ``None`` if no entry matches.
    """
    del p_dph_t  # Unused, kept for API parity with the C signature.

    tp = 0  # Index into ``table``, mirrors C's ``tp`` pointer.
    while True:
        length = table[tp]
        tp += 1
        if length == 0:
            # 0 => end of table.
            return None

        lp = 0  # Index into ``symbol``.
        cp = tp  # Cursor into ``table``, mirrors ``cp = tp``.
        while True:
            # ``if (*lp != *cp++)`` — read then advance cp.
            cp_val = table[cp]
            cp += 1
            if symbol[lp] != cp_val:
                break
            if symbol[lp] == GEN_SIL:
                # Input string end reached — abandon this entry.
                break
            if table[cp] == EOS:
                # Win — return the index just past EOS.
                cp += 1
                return cp
            lp += 1

        tp += length  # Next entry.


__all__ = ["durlookup"]
