"""English plural-suffix selection from ls_util.c.

Translated from ``src/dapi/src/lts/ls_util.c``:

- :func:`ls_util_pluralize` — given the last emitted phoneme code,
  return the sequence of phoneme codes for the English plural
  suffix:

    * after a sibilant consonant (e.g. ``s``, ``z``, ``sh``,
      ``ch``, ``j``): ``IX Z`` (the schwa-Z of "buses", "watches")
    * after a voiceless consonant (other than sibilants):
      ``S`` (the unvoiced S of "cats", "books")
    * after a voiced consonant or a vowel: ``Z`` (the voiced Z of
      "dogs", "boys")
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import US_TOT_ALLOPHONES, USPhoneme
from dectalk.lts.grapheme_features import PCONS, PSIB, PVOICE, pfeat

_US_IX: int = int(USPhoneme.IX)
_US_Z: int = int(USPhoneme.Z)
_US_S: int = int(USPhoneme.S)


def ls_util_pluralize(last_phone: int) -> list[int]:
    """Return the phoneme sequence for the English plural suffix.

    Faithful translation of:

    .. code-block:: c

        void ls_util_pluralize(LPTTS_HANDLE_T phTTS) {
            int feats = 0;
            if (pLts_t->lphone < US_TOT_ALLOPHONES)
                feats = pfeat[pLts_t->lphone];
            if ((feats & (PCONS|PSIB)) == (PCONS|PSIB)) {
                ls_util_send_phone(phTTS, US_IX);
                ls_util_send_phone(phTTS, US_Z);
            } else {
                if ((feats & (PCONS|PVOICE)) == PCONS) {
                    ls_util_send_phone(phTTS, US_S);
                } else {
                    ls_util_send_phone(phTTS, US_Z);
                }
            }
        }

    Args:
        last_phone: The previous phoneme code (``pLts_t->lphone``).
            Codes >= ``US_TOT_ALLOPHONES`` are treated as having
            no features (per the C ``if (lphone < TOT_ALLOPHONES)``
            guard).

    Returns:
        A list of US allophone codes: ``[IX, Z]``, ``[S]``, or
        ``[Z]`` depending on the previous phoneme's features.
    """
    feats = pfeat[last_phone] if last_phone < US_TOT_ALLOPHONES else 0

    # Sibilant + consonant → schwa-Z (e.g. "buses")
    if (feats & (PCONS | PSIB)) == (PCONS | PSIB):
        return [_US_IX, _US_Z]
    # Voiceless consonant (no PVOICE bit) → S (e.g. "cats")
    if (feats & (PCONS | PVOICE)) == PCONS:
        return [_US_S]
    # Voiced consonant or vowel → Z (e.g. "dogs", "boys")
    return [_US_Z]


__all__ = ["ls_util_pluralize"]
