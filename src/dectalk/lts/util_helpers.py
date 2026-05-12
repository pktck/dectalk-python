"""Pure helper functions from the LTS utility layer.

Translated from ``src/dapi/src/lts/ls_util.c``. These helpers
operate on word slices (input character arrays) without mutating
any TTS handle, so they're directly portable to Python.

- :func:`ls_util_is_year` — classify a 4-digit ASCII string as a
  year (rejects strings with leading ``'0'``, an embedded ``"00"``
  pair right after the first digit, or non-digit characters / the
  Latin-1 fraction characters ¼ / ½).
- :func:`ls_util_is_white` — return True iff a font-encoded
  ``i_word[0]`` is one of the recognised whitespace characters
  (space, NBSP, LF, CR, FF) in the PFASCII font.
- :func:`ls_util_is_index` — return True iff the font-encoded
  ``i_word[0]`` is one of the index-marker control codes.
- :func:`ls_util_is_dot` — return True iff the font-encoded
  ``i_word[0]`` is a literal ``.`` in the PFASCII font.
- :func:`ls_util_is_clause` — return True iff the value bits of
  ``i_word[0]`` index a clause-terminating character in
  :data:`char_types`.
- :func:`ls_util_is_aword` — return True iff a letter slice is
  non-empty, all-alphabetic, and contains at least one vowel.
"""

from __future__ import annotations

from dectalk.cmd.char_types_table import MARK_clause, char_types
from dectalk.include.cmd_codes import (
    INDEX,
    INDEX_BOOKMARK,
    INDEX_NOISE,
    INDEX_REPLY,
    INDEX_SENTENCE,
    INDEX_START,
    INDEX_STOP,
    INDEX_VOLUME,
    INDEX_WORDPOS,
    PFASCII,
    PFONT,
    PSFONT,
    PVALUE,
)
from dectalk.lts.char_features import is_alpha, is_vowel

_FRACTION_QUARTER = 0xBC  # Latin-1 ¼
_FRACTION_HALF = 0xBD  # Latin-1 ½

_LF = 0x0A
_FF = 0x0C
_CR = 0x0D
_NBSP = 0xA0
_SPACE = ord(" ")

_PFASCII_BITS = PFASCII << PSFONT  # 0x0000 — font field for plain ASCII
_PERIOD_CODE = (PFASCII << PSFONT) | ord(".")  # font-encoded '.'

_INDEX_CODES = frozenset(
    {
        INDEX,
        INDEX_REPLY,
        INDEX_BOOKMARK,
        INDEX_WORDPOS,
        INDEX_START,
        INDEX_STOP,
        INDEX_SENTENCE,
        INDEX_VOLUME,
        INDEX_NOISE,
    },
)


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


def ls_util_is_white(i_word0: int) -> bool:
    """Return True iff a font-encoded value is whitespace.

    Faithful translation of:

    .. code-block:: c

        int ls_util_is_white(ITEM *ip) {
            int c;
            if ((ip->i_word[0]&PFONT) == (PFASCII<<PSFONT)) {
                c = ip->i_word[0] & PVALUE;
                if (c==' ' || c==0xA0 || c==LF || c==CR || c==FF)
                    return TRUE;
            }
            return FALSE;
        }

    The C comment is explicit that HT (0x09) and VT (0x0B) are *not*
    whitespace in this sense: they get treated like comma and force
    a phoneme flush rather than just a word boundary. Hence we only
    accept space, NBSP, LF, CR, FF here.

    Args:
        i_word0: First word of an ITEM (16-bit font-encoded value).

    Returns:
        ``True`` iff the font is PFASCII and the value is one of
        the whitespace bytes that ``ls_task_do_right_punct`` would
        emit a WBOUND for.
    """
    if (i_word0 & PFONT) != _PFASCII_BITS:
        return False
    value = i_word0 & PVALUE
    return value in (_SPACE, _NBSP, _LF, _CR, _FF)


def ls_util_is_dot(i_word0: int) -> bool:
    """Return True iff a font-encoded value is a period in PFASCII font.

    Faithful translation of:

    .. code-block:: c

        int ls_util_is_dot(PLTS_T pLts_t) {
            if (pLts_t->citem.i_word[0] == ((PFASCII<<PSFONT)|'.'))
                return TRUE;
            return FALSE;
        }

    Args:
        i_word0: First word of the current ITEM (16-bit font-encoded).

    Returns:
        ``True`` iff ``i_word0 == (PFASCII << PSFONT) | '.'`` (i.e.
        a literal ``.`` character in the plain-ASCII font).
    """
    return i_word0 == _PERIOD_CODE


def ls_util_is_clause(i_word0: int) -> bool:
    """Return True iff a font-encoded value is clause-terminating punctuation.

    Faithful translation of:

    .. code-block:: c

        int ls_util_is_clause(PLTS_T pLts_t) {
            if (char_types[pLts_t->citem.i_word[0]&PVALUE] & MARK_clause)
                return TRUE;
            return FALSE;
        }

    The 8-bit value (after masking off the font field) indexes
    :data:`char_types`; the result tests the :data:`MARK_clause` bit
    that marks `.`, `?`, `!` as clause-ending punctuation.

    Args:
        i_word0: First word of the current ITEM (16-bit font-encoded).

    Returns:
        ``True`` iff the low-byte value of ``i_word0`` is a
        clause-terminating character per :data:`char_types`.
    """
    return bool(char_types[i_word0 & PVALUE] & MARK_clause)


def ls_util_is_aword(word: str | bytes) -> bool:
    """Return True iff every character is alpha AND at least one is a vowel.

    Faithful translation of:

    .. code-block:: c

        int ls_util_is_aword(LETTER *llp, LETTER *rlp) {
            int flag = FALSE;
            if (llp >= rlp) return FALSE;
            while (llp != rlp) {
                if (!IS_ALPHA(llp->l_ch)) return FALSE;
                if (IS_VOWEL(llp->l_ch))  flag = TRUE;
                ++llp;
            }
            return flag;
        }

    Empty input returns ``False``. The vowel/alpha bits come from
    :data:`ls_char_feat` so the function is Latin-1 aware (e.g. ``é``,
    ``ñ`` are treated as alphabetic).

    Args:
        word: Word slice as str (ASCII / Latin-1) or bytes.

    Returns:
        ``True`` iff the word is non-empty, every character is
        alphabetic, and at least one character is a vowel.
    """
    word_bytes = word.encode("latin-1", errors="replace") if isinstance(word, str) else word
    if not word_bytes:
        return False
    has_vowel = False
    for c in word_bytes:
        if not is_alpha(c):
            return False
        if is_vowel(c):
            has_vowel = True
    return has_vowel


def ls_util_is_index(i_word0: int) -> bool:
    """Return True iff a font-encoded value is an index marker.

    Faithful translation of:

    .. code-block:: c

        int ls_util_is_index(ITEM *ip) {
            if (   ip->i_word[0]==INDEX
                || ip->i_word[0]==INDEX_REPLY
                || ip->i_word[0]==INDEX_BOOKMARK
                || ip->i_word[0]==INDEX_WORDPOS
                || ip->i_word[0]==INDEX_START
                || ip->i_word[0]==INDEX_STOP
                || ip->i_word[0]==INDEX_SENTENCE
                || ip->i_word[0]==INDEX_VOLUME
                || ip->i_word[0]==INDEX_NOISE)
                return TRUE;
            return FALSE;
        }

    The OSF/Win32 ``//#ifdef _WIN32`` in the C source is commented
    out, so the extended INDEX_* family applies on every platform.

    Args:
        i_word0: First word of an ITEM (16-bit font-encoded value).

    Returns:
        ``True`` iff ``i_word0`` matches one of the recognised
        index-marker control codes.
    """
    return i_word0 in _INDEX_CODES


__all__ = [
    "ls_util_is_aword",
    "ls_util_is_clause",
    "ls_util_is_dot",
    "ls_util_is_index",
    "ls_util_is_white",
    "ls_util_is_year",
]
