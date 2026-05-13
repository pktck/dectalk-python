"""``make_phone`` and ``add_feature`` helpers from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 2043-2114.

Two small helpers the PH sort pass uses when writing into the
``phonemes[]`` / ``sentstruc[]`` output buffers:

- :func:`make_phone` writes a phoneme + user-prosody triple at
  ``nphonetot`` and bumps it.
- :func:`add_feature` ORs a feature flag into
  ``sentstruc[location]`` (with range / value guards).
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.inton_constants import HAT_F0_SIZES_SPECIFIED
from dectalk.ph.numeric_constants import NPHON_MAX

_FMAXIMUM = 0xFFFF_FFFF  # 32-bit feature flag ceiling.


def make_phone(
    p_dph_t: DphT,
    phoname: int,
    n: int,
    curr_dur: int,
    curr_f0: int,
) -> None:
    """Append a phoneme + user-prosody triple to the output buffers.

    Faithful translation of:

    .. code-block:: c

        static void make_phone(PDPH_T pDph_t, short phoname, short n,
                               short curr_dur, short curr_f0) {
            if (pDph_t->nphonetot > n) return;
            pDph_t->phonemes[pDph_t->nphonetot] = phoname;
            pDph_t->user_durs[pDph_t->nphonetot] = curr_dur;
            if (pDph_t->f0mode != HAT_F0_SIZES_SPECIFIED)
                pDph_t->user_f0[pDph_t->nphonetot] = curr_f0;
            if (pDph_t->nphonetot < NPHON_MAX) pDph_t->nphonetot++;
        }

    The C source's ``if (nphonetot > n) return`` guard is a tagged-
    insert safety check — if the cursor's already past ``n``, the
    sort pass shouldn't write again.

    Args:
        p_dph_t: PH thread state to mutate.
        phoname: Phoneme code to append.
        n: The source index in the input stream (for the guard).
        curr_dur: User-specified duration (ms) or 0.
        curr_f0: User-specified F0 (Hz) or 0.
    """
    if p_dph_t.nphonetot > n:
        return

    phonemes = p_dph_t.phonemes
    if phonemes is None:
        phonemes = []
        p_dph_t.phonemes = phonemes
    user_durs = p_dph_t.user_durs
    if user_durs is None:
        user_durs = []
        p_dph_t.user_durs = user_durs
    user_f0 = p_dph_t.user_f0
    if user_f0 is None:
        user_f0 = []
        p_dph_t.user_f0 = user_f0

    while len(phonemes) <= p_dph_t.nphonetot:
        phonemes.append(0)
    while len(user_durs) <= p_dph_t.nphonetot:
        user_durs.append(0)
    while len(user_f0) <= p_dph_t.nphonetot:
        user_f0.append(0)

    phonemes[p_dph_t.nphonetot] = phoname
    user_durs[p_dph_t.nphonetot] = curr_dur
    if p_dph_t.f0mode != HAT_F0_SIZES_SPECIFIED:
        user_f0[p_dph_t.nphonetot] = curr_f0

    if p_dph_t.nphonetot < NPHON_MAX:
        p_dph_t.nphonetot += 1


def add_feature(p_dph_t: DphT, feaname: int, location: int) -> None:
    """OR a feature flag into ``sentstruc[location]``.

    Faithful translation of:

    .. code-block:: c

        static void add_feature(PDPH_T pDph_t, long feaname, short location) {
            if (location < 0 || location >= NPHON_MAX) return;
            if (feaname <= 0 || feaname > FMAXIMUM) return;
            pDph_t->sentstruc[location] |= feaname;
        }

    Args:
        p_dph_t: PH thread state.
        feaname: Feature-flag bitmask to OR in.
        location: Index into ``sentstruc``.
    """
    if location < 0 or location >= NPHON_MAX:
        return
    if feaname <= 0 or feaname > _FMAXIMUM:
        return
    sentstruc = p_dph_t.sentstruc
    if sentstruc is None:
        sentstruc = []
        p_dph_t.sentstruc = sentstruc
    while len(sentstruc) <= location:
        sentstruc.append(0)
    sentstruc[location] |= feaname


__all__ = ["add_feature", "make_phone"]
