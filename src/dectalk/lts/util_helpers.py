"""Pure helper functions from the LTS utility layer.

Translated from ``src/dapi/src/lts/ls_util.c``. These helpers
operate on word slices (input character arrays) without mutating
any TTS handle, so they're directly portable to Python.

- :func:`ls_util_is_year` — classify a 4-digit ASCII string as a
  year (rejects strings with leading ``'0'``, an embedded ``"00"``
  pair right after the first digit, or non-digit characters / the
  Latin-1 fraction characters ¼ / ½).
"""

from __future__ import annotations

_FRACTION_QUARTER = 0xBC  # Latin-1 ¼
_FRACTION_HALF = 0xBD  # Latin-1 ½


def ls_util_is_year(word: str | bytes) -> bool:
    """Return True iff ``word`` is a plausible 4-digit year.

    Faithful translation of:

    .. code-block:: c

        int ls_util_is_year(LETTER *llp, LETTER *rlp) {
            // count digits; reject if any non-digit
            while (tlp1 != rlp) {
                if (!IS_DIGIT(tlp1->l_ch)) return FALSE;
                ++ndig; ++tlp1;
            }
            // BATS #412 — no embedded ½ / ¼
            if ((rlp-1)->l_ch==0xBC || (rlp-1)->l_ch==0xBD) return FALSE;
            if (ndig != 4) return FALSE;
            // No leading '0', no embedded '00' pair after first digit
            if (llp->l_ch == '0') return FALSE;
            if ((llp+1)->l_ch=='0' && (llp+2)->l_ch=='0') return FALSE;
            return TRUE;
        }

    Args:
        word: Word slice as str (ASCII) or bytes (Latin-1).

    Returns:
        ``True`` iff exactly 4 ASCII digits, doesn't start with ``'0'``,
        doesn't have ``"00"`` immediately after the first digit, and the
        last byte isn't Latin-1 ¼ (0xBC) or ½ (0xBD).
    """
    word_bytes = word.encode("latin-1", errors="replace") if isinstance(word, str) else word

    # Iterate digit-check
    for c in word_bytes:
        if not (ord("0") <= c <= ord("9")):
            # Special case for the BATS #412 trailing-fraction check —
            # the C version exits early on non-digit, BUT then checks
            # the last byte for ¼/½. Replicate: if the only non-digit
            # is a trailing fraction, the C code already returned
            # FALSE on the !IS_DIGIT check. The fraction check applies
            # when the word DOES consist of digits + a trailing fraction
            # (e.g. "1¼"), but that case is also rejected by the
            # !IS_DIGIT loop. The fraction check in the C source is
            # therefore vestigial in this isolated function.
            return False

    # Trailing fraction explicitly rejected (matches BATS #412 even
    # though the digit loop already returned FALSE in our path).
    if word_bytes and word_bytes[-1] in (_FRACTION_QUARTER, _FRACTION_HALF):
        return False

    year_length = 4
    if len(word_bytes) != year_length:
        return False

    if word_bytes[0] == ord("0"):
        return False

    # Reject "X00Y" where the "00" sits right after the first digit.
    return not (word_bytes[1] == ord("0") and word_bytes[2] == ord("0"))


__all__ = ["ls_util_is_year"]
