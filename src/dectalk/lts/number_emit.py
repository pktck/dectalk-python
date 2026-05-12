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

    # Trailing hundreds-tens-units (buf[15..17]).
    if not bailed_out and ls_proc_non_zero(bytes(buf[15:_BUF_LEN]), 3):
        _emit_group(emitter, bytes(buf), 15)
        if oflag:
            emitter.send_phone(_US_TH)
    elif not bailed_out and not out_emitted_magnitude:
        # All zeros — emit "zero".
        emitter.send_phone_list(punits[0])

    return pflag


__all__ = ["ls_proc_do_number"]
