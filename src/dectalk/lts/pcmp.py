"""Phone-list prefix comparator from lsa_util.c.

Translated from ``src/dapi/src/lts/lsa_util.c``:

- :func:`lsa_util_pcmp` — compare the leading ``p_len`` phones of a
  ``PHONE`` linked list against a fixed byte pattern. Returns ``True``
  iff the list begins with that pattern.
"""

from __future__ import annotations

from collections.abc import Sequence


def lsa_util_pcmp(
    phones: Sequence[int],
    pattern: bytes | str,
    p_len: int | None = None,
) -> bool:
    """Return ``True`` iff ``phones`` starts with ``pattern[:p_len]``.

    Faithful translation of:

    .. code-block:: c

        int lsa_util_pcmp(PHONE *fpp, PHONE *lpp,
                          char *p, unsigned short p_len) {
            PHONE *pp = fpp;
            int i;
            for (i = 0; i < p_len; i++) {
                if (pp == lpp || pp->p_sphone != p[i])
                    break;
                pp = pp->p_fp;
            }
            if (i != p_len) return FALSE;
            return TRUE;
        }

    The C function walks a linked list of PHONE structs via
    ``pp->p_fp`` and compares each ``pp->p_sphone`` byte against the
    pattern. Reaching the sentinel ``lpp`` (one past the end) before
    consuming ``p_len`` characters means "no match", as does any
    byte mismatch.

    The Python version takes a flat sequence of ``p_sphone`` values
    in place of the linked list — the ``lpp`` sentinel maps to "end
    of sequence". Identical behaviour.

    Args:
        phones: Sequence of phoneme byte codes (the ``p_sphone``
            values of the PHONE list, in order).
        pattern: Byte pattern (or str) to match against the start.
        p_len: Number of bytes from ``pattern`` to compare. Defaults
            to ``len(pattern)``.

    Returns:
        ``True`` iff ``phones[:p_len]`` equals ``pattern[:p_len]``
        byte-for-byte.
    """
    pat = pattern.encode("latin-1", errors="replace") if isinstance(pattern, str) else pattern
    n = len(pat) if p_len is None else p_len
    if n > len(phones) or n > len(pat):
        return False
    return all(phones[i] == pat[i] for i in range(n))


__all__ = ["lsa_util_pcmp"]
