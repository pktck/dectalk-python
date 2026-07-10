"""Full number emission from l_us_pr1.c::ls_proc_do_number.

Translated from ``src/dapi/src/lts/l_us_pr1.c``:

- :func:`ls_proc_do_number` — emit the phoneme sequence for a
  generic integer (up to 18 digits), with optional ordinal form.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import COMMA, VPSTART, WBOUND, USPhoneme
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.number_words import speak_digit_group
from dectalk.lts.phoneme_words import (
    pand,
    pbillion,
    pmillion,
    pquadrillion,
    pthousand,
    ptrillion,
    punits,
)
from dectalk.lts.proc_helpers import ls_proc_non_zero

_US_TH: int = int(USPhoneme.TH)
_BUF_LEN = 18  # 18 digits → up to quintillion-1


def _emit_group(emitter: LtsEmitter, buf: bytes, start: int) -> None:
    """Emit a 3-digit group from buf starting at ``start``."""
    d1 = buf[start] - ord("0")
    d2 = buf[start + 1] - ord("0")
    d3 = buf[start + 2] - ord("0")
    for p in speak_digit_group(d1, d2, d3):
        emitter.send_phone(p)


def _emit_separator(emitter: LtsEmitter, buf: bytes, after: int, oflag: bool) -> bool:
    """Emit the inter-magnitude separator and return True if we should bail.

    Returns True if the rest of the number is zero — caller bails out.
    """
    # Check whether anything remains after the current group.
    remaining_str = buf[after:_BUF_LEN]
    if not any(b != ord("0") for b in remaining_str):
        # No more non-zero digits.
        if oflag:
            emitter.send_phone(_US_TH)
        return True
    # Some digits remain.
    rest_after_top = buf[after + 1 : _BUF_LEN]
    if not any(b != ord("0") for b in rest_after_top):
        emitter.send_phone(VPSTART)
    elif buf[after] == ord("0"):
        emitter.send_phone_list(pand)
    else:
        emitter.send_phone(COMMA)
    return False


def ls_proc_do_number(
    emitter: LtsEmitter,
    digits: bytes,
    *,
    oflag: bool = False,
) -> bool:
    """Emit the phoneme sequence for an integer; return True if plural.

    Faithful translation of the main branch of:

    .. code-block:: c

        int ls_proc_do_number(LPTTS_HANDLE_T phTTS, LETTER *llp,
                                LETTER *rlp, int oflag) {
            // Right-justify the digits into buf[18].
            // For each non-zero magnitude (Q, T, B, M, K, H), emit the
            //   3-digit group + magnitude word, then a separator
            //   (VPSTART / pand / COMMA) before the next group.
            // Trailing 1- or 2-digit remainder is emitted as a
            //   speak_digit_group.
        }

    The C source supports >18 digits (long-form spelling) and
    comma-separated input; this Python port handles the common
    case: bare digit string up to 18 digits.

    Args:
        emitter: The LTS emitter state.
        digits: ASCII digit byte string (e.g. ``b"1234567"``).
        oflag: True to render as an ordinal (appends ``-th`` to a
            whole magnitude end).

    Returns:
        True if the number is plural (> 1), False otherwise.
    """
    if not digits or len(digits) > _BUF_LEN:
        return False
    # Validate all bytes are digits.
    if not all(ord("0") <= b <= ord("9") for b in digits):
        return False

    # Right-justify into an 18-byte buffer, '0'-padded on the left.
    buf = bytearray(b"0" * (_BUF_LEN - len(digits)) + digits)

    # Plural detection: if there's more than one non-zero digit
    # or a single non-zero digit > '1', plural.
    pflag = len(digits) != 1 or digits[0] != ord("1")
    if len(digits) == 1 and digits[0] == ord("1"):
        pflag = False

    # Magnitudes, in order: Quadrillions, Trillions, Billions, Millions, Thousands.
    magnitudes = (
        (0, 3, pquadrillion),
        (3, 6, ptrillion),
        (6, 9, pbillion),
        (9, 12, pmillion),
        (12, 15, pthousand),
    )

    out_emitted_magnitude = False
    bailed_out = False
    for start, after, word in magnitudes:
        if ls_proc_non_zero(bytes(buf[start:after]), 3):
            _emit_group(emitter, bytes(buf), start)
            emitter.send_phone(WBOUND)
            emitter.send_phone_list(word)
            out_emitted_magnitude = True
            if _emit_separator(emitter, bytes(buf), after, oflag=oflag):
                bailed_out = True
                break

    # Trailing hundreds-tens-units (buf[15..17]). The C source calls
    # ls_proc_do_digit_group(&buf[15], oflag) unconditionally when no
    # magnitude bail happened: the ordinal flag routes INTO the digit
    # group (pordin units / teens+TH / tens+IX+TH endings), it is NOT
    # a bare TH appended after the cardinal ("42nd" must render
    # "forty second", not "forty two-th"). The all-zero group also
    # goes through do_digit_group, which lands on punits[0]/pordin[0].
    if not bailed_out:
        d1 = buf[15] - ord("0")
        d2 = buf[16] - ord("0")
        d3 = buf[17] - ord("0")
        for p in speak_digit_group(d1, d2, d3, ordinal=oflag):
            emitter.send_phone(p)
    _ = out_emitted_magnitude

    return pflag


_SPELL_BYTES: frozenset[int] = frozenset((0xBC, 0xBD, 0xB2, 0xB3))
"""Latin-1 ``¼ ½ ² ³`` — do_number spells these rather than reading."""

_LONG_GROUP = 3
_LONG_MIN_REMAINING = 6


def _emit_digit_by_digit_grouped(emitter: LtsEmitter, word: bytes, end: int, schar: int) -> None:
    """Speak ``word[:end]`` digit-by-digit in 3-digit groups with COMMAs.

    Mirrors the ``ndig>18 || leading-zero`` branch of the C source:
    non-separator digits are read individually (``punits``), WBOUND
    between digits inside a group, COMMA after each full leading
    group while at least 6 digits remain.
    """
    ndig = sum(1 for b in word[:end] if b != schar)
    j = 0
    while ndig >= _LONG_MIN_REMAINING:
        k = 0
        while k < _LONG_GROUP:
            c = word[j]
            if c != schar:
                if k != 0:
                    emitter.send_phone(WBOUND)
                k += 1
                emitter.send_phone_list(punits[c - ord("0")])
            j += 1
        emitter.send_phone(COMMA)
        ndig -= _LONG_GROUP
    k = 0
    while j != end:
        c = word[j]
        if c != schar:
            if k != 0:
                emitter.send_phone(WBOUND)
            k += 1
            emitter.send_phone_list(punits[c - ord("0")])
        j += 1


def ls_proc_do_number_full(  # noqa: PLR0912, PLR0915 — mirrors the C control flow
    emitter: LtsEmitter,
    word: bytes,
    *,
    oflag: bool = False,
    schar: int = ord(","),
    fchar: int = ord("."),
) -> bool:
    """Faithful line-by-line port of C ``ls_proc_do_number``.

    Unlike :func:`ls_proc_do_number` (bare-digit fast path), this
    handles every branch of ``l_us_pr1.c:508``:

    - thousands separators (``schar``) skipped inside the integer,
    - ``ndig>18`` + separators → digit-by-digit with COMMA pauses,
    - ``ndig>18`` or leading-zero multi-digit → digit-by-digit in
      3-digit groups,
    - Latin-1 ``¼ ½ ² ³`` prefix/suffix (spelled, ``pand`` joined),
    - decimal fraction: ``ppoint`` + per-digit WBOUND reads,
    - exponent tail: ``ptt2tp`` ("times ten to the") + sign + recurse.

    Args:
        emitter: The LTS emitter state.
        word: The number slice exactly as the C caller would pass
            ``llp..rlp`` (digits, separators, optional fraction /
            exponent tail). Callers are responsible for bounding it
            (``ls_task_parse_number``-validated in the task layer).
        oflag: Render the integer as an ordinal.
        schar: Thousands-separator char (``,`` in US mode).
        fchar: Decimal-point char (``.`` in US mode).

    Returns:
        True if the number is plural (the C ``pflag``).
    """
    from dectalk.lts.phoneme_words import ppoint, ptt2tp  # noqa: PLC0415 — keep header stable
    from dectalk.lts.proc_emit import ls_proc_do_sign  # noqa: PLC0415 — cycle break
    from dectalk.lts.spell_emit import ls_spel_spell  # noqa: PLC0415 — cycle break

    n = len(word)
    i = 0
    # "This handles integer parts like 1/4 & 1/2 and superscripts."
    if i != n and word[i] in _SPELL_BYTES:
        ls_spel_spell(emitter, word[i:])
        return False
    pflag = False
    sflag = False
    ndig = 0
    while i != n and (_is_ascii_digit(word[i]) or word[i] == schar) and word[i] not in _SPELL_BYTES:
        if word[i] == schar:
            sflag = True
        else:
            ndig += 1
        i += 1
    end_int = i
    if ndig > _BUF_LEN and sflag:
        # Long with user commas: digit-by-digit, pause at each schar.
        j = 0
        while j != end_int:
            c = word[j]
            j += 1
            if c == schar:
                emitter.send_phone(COMMA)
            else:
                emitter.send_phone_list(punits[c - ord("0")])
                if j != end_int and word[j] != schar:
                    emitter.send_phone(WBOUND)
        pflag = True
    elif ndig > _BUF_LEN or (ndig > 1 and word[0] == ord("0")):
        _emit_digit_by_digit_grouped(emitter, word, end_int, schar)
        pflag = True
    elif ndig != 0:
        # Right-justify into an 18-byte buffer, skipping separators.
        buf = bytearray(_BUF_LEN)
        pos = _BUF_LEN
        j = end_int
        while j != 0:
            j -= 1
            c = word[j]
            if c != schar:
                pos -= 1
                buf[pos] = c
        if pos != _BUF_LEN - 1 or buf[_BUF_LEN - 1] != ord("1"):
            pflag = True
        while pos:
            pos -= 1
            buf[pos] = ord("0")
        magnitudes = (
            (0, 3, pquadrillion),
            (3, 6, ptrillion),
            (6, 9, pbillion),
            (9, 12, pmillion),
            (12, 15, pthousand),
        )
        bailed_out = False
        for start, after, mag_word in magnitudes:
            if ls_proc_non_zero(bytes(buf[start:after]), 3):
                _emit_group(emitter, bytes(buf), start)
                emitter.send_phone(WBOUND)
                emitter.send_phone_list(mag_word)
                if _emit_separator(emitter, bytes(buf), after, oflag=oflag):
                    bailed_out = True
                    break
        if not bailed_out:
            d1 = buf[15] - ord("0")
            d2 = buf[16] - ord("0")
            d3 = buf[17] - ord("0")
            for p in speak_digit_group(d1, d2, d3, ordinal=oflag):
                emitter.send_phone(p)
    # Tail: Latin-1 vulgar fraction / superscript after the integer.
    if i != n and word[i] in _SPELL_BYTES:
        emitter.send_phone_list(pand)
        ls_spel_spell(emitter, word[i : i + 1])
        i += 1
        pflag = True
    # Tail: decimal fraction digits.
    if i != n and word[i] == fchar:
        if i != 0:
            emitter.send_phone(WBOUND)
        emitter.send_phone_list(ppoint)
        i += 1
        while i != n and word[i] != ord("e"):
            c = word[i]
            if c != schar:
                emitter.send_phone(WBOUND)
                emitter.send_phone_list(punits[c - ord("0")])
            i += 1
        pflag = True
    # Tail: exponent ("must be an e").
    if i != n:
        emitter.send_phone_list(ptt2tp)
        i += 1
        if i != n:
            c = word[i]
            if c in (ord("-"), ord("+")):
                ls_proc_do_sign(emitter, c)
                i += 1
        ls_proc_do_number_full(emitter, word[i:], oflag=False, schar=schar, fchar=fchar)
        pflag = True
    return pflag


def _is_ascii_digit(b: int) -> bool:
    """C ``IS_DIGIT`` over a byte."""
    return ord("0") <= b <= ord("9")


__all__ = ["ls_proc_do_number", "ls_proc_do_number_full"]
