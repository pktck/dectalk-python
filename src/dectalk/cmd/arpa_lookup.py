"""ARPABET 2-byte phoneme lookup from cm_phon.c.

Translated from ``src/dapi/src/cmd/cm_phon.c``:

- :func:`cm_phon_lookup_arpa` — pure variant of the C source's
  ARPABET lookup. Returns a 3-way classification:

  * ``2`` — full 2-byte ARPA match (e.g. ``iy``, ``ae``);
  * ``1`` — 1-byte match (the ARPA entry's second byte is space);
  * ``0`` — no match.
"""

from __future__ import annotations

from dectalk.include.phoneme_stream import SLOT_TO_CODE
from dectalk.lts.char_features import ls_lower as par_lower

_ARPA_SLOT_LEN = 2  # each slot is exactly 2 bytes


def _build_arpa_bytes() -> bytes:
    """Reconstruct the C ``usa_arpa[]`` byte layout from :data:`SLOT_TO_CODE`.

    The C source uses a flat ``unsigned char[]`` of (ph1, ph2) pairs;
    we build it by sorting the dict's keys by code, padding to fill
    code-slots that lack an entry. This is mostly for parity testing —
    callers usually pass a slot key directly.
    """
    max_code = max(SLOT_TO_CODE.values())
    arr = bytearray(_ARPA_SLOT_LEN * (max_code + 1))  # init to zero
    for slot, code in SLOT_TO_CODE.items():
        if len(slot) == _ARPA_SLOT_LEN:
            arr[_ARPA_SLOT_LEN * code] = slot[0]
            arr[_ARPA_SLOT_LEN * code + 1] = slot[1]
    return bytes(arr)


_USA_ARPA: bytes = _build_arpa_bytes()


def cm_phon_lookup_arpa(
    ph1: int,
    ph2: int,
    arpa: bytes = _USA_ARPA,
    *,
    case_sensitive: bool = False,
) -> tuple[int, int]:
    """Classify a 2-byte ARPABET sequence in ``arpa``.

    Faithful translation of:

    .. code-block:: c

        int cm_phon_lookup_arpa(LPTTS_HANDLE_T phTTS,
                                 unsigned int ph1, unsigned int ph2) {
            if (pKsd_t->arpa_case == FALSE) {
                ph1 = par_lower[ph1];
                ph2 = par_lower[ph2];
            }
            for (i = 0; i < size; i += 2) {
                if (ph1 == arpa[i] && ph2 == arpa[i+1]) {
                    PUSH_PHONE = i/2;
                    return 2;
                }
            }
            for (i = 0; i < size; i += 2) {
                if (ph1 == arpa[i] && arpa[i+1] == ' ') {
                    PUSH_PHONE = i/2;
                    return 1;
                }
            }
            return 0;
        }

    The C source returns 0/1/2 to indicate how many bytes matched,
    and writes the phoneme code to the global PUSH_PHONE. The
    Python port returns ``(match_len, phone_code)`` directly.

    Args:
        ph1: First ARPABET byte.
        ph2: Second ARPABET byte.
        arpa: ARPA table (defaults to US).
        case_sensitive: If False (the default), inputs are
            lower-cased via ``par_lower`` (matches the C
            ``arpa_case == FALSE`` branch).

    Returns:
        A tuple ``(match_len, phone_code)``:

        * ``(2, code)`` on a 2-byte match;
        * ``(1, code)`` on a 1-byte match (ARPA entry is ``ph1``+space);
        * ``(0, -1)`` on no match.
    """
    if not case_sensitive:
        ph1 = par_lower[ph1]
        ph2 = par_lower[ph2]
    space = ord(" ")
    # First pass: look for exact 2-byte match.
    for i in range(0, len(arpa), 2):
        if i + 1 >= len(arpa):
            break
        if ph1 == arpa[i] and ph2 == arpa[i + 1]:
            return 2, i // 2
    # Second pass: look for 1-byte match (ph1 + space).
    for i in range(0, len(arpa), 2):
        if i + 1 >= len(arpa):
            break
        if ph1 == arpa[i] and arpa[i + 1] == space:
            return 1, i // 2
    return 0, -1


__all__ = ["cm_phon_lookup_arpa"]
