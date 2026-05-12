"""Short-word and wh-word LTS dictionaries.

Translated from ``src/dapi/src/lts/l_us_con.c``:

- :data:`sdic` — a tiny "stop-word" dictionary the LTS engine consults
  before running full rules. Entries are function words whose
  pronunciation depends on prosody (``for``, ``and``, ``to``) plus
  ``mwizi`` (Swahili for "good"? a debugging easter-egg).
- :data:`whdic` — the wh-word list used for question-detection in
  prosody.

Both tables share the packed-record format:

    sdic record:
        <size>          one byte: total record length including this byte
        <name chars>    ASCII letters
        <EOS=0>         end-of-name marker
        <optional flags>
        <phonemes>...   phoneme codes (and optional control codes)
        <SIL=0>         end-of-phonemes marker

The sdic flags ``SPECIALWORD`` (120) and ``PPSTART`` (112) embed inline
in the phoneme stream and tag function-word boundaries for prosody.

whdic records have no phoneme stream — just a name and a SIL — because
they're matched by name only (question-mode prosody fires when any
whdic word starts an utterance).

Both tables terminate with a single 0 byte after the last record.
"""

from __future__ import annotations

from typing import Final

# sdic: short function-word dictionary.
# Entries: for, and, mwizi, to.

sdic: Final[bytes] = bytes((
    0x09, 0x66, 0x6F, 0x72, 0x00, 0x78, 0x70, 0x25, 0x0F, 0x00, 0x0A, 0x61,
    0x6E, 0x64, 0x00, 0x78, 0x70, 0x05, 0x20, 0x30, 0x00, 0x0C, 0x6D, 0x77,
    0x69, 0x7A, 0x69, 0x00, 0x70, 0x31, 0x0A, 0x2D, 0x01, 0x00, 0x08, 0x74,
    0x6F, 0x00, 0x78, 0x70, 0x2F, 0x0D, 0x00, 0x00,
))  # fmt: skip


# whdic: wh-word list for question-mode prosody.
# Entries: what, when, where, why, who, how, which, whose, whom.

whdic: Final[bytes] = bytes((
    0x06, 0x77, 0x68, 0x61, 0x74, 0x00, 0x00, 0x06, 0x77, 0x68, 0x65, 0x6E,
    0x00, 0x00, 0x07, 0x77, 0x68, 0x65, 0x72, 0x65, 0x00, 0x00, 0x05, 0x77,
    0x68, 0x79, 0x00, 0x00, 0x05, 0x77, 0x68, 0x6F, 0x00, 0x00, 0x05, 0x68,
    0x6F, 0x77, 0x00, 0x00, 0x07, 0x77, 0x68, 0x69, 0x63, 0x68, 0x00, 0x00,
    0x07, 0x77, 0x68, 0x6F, 0x73, 0x65, 0x00, 0x00, 0x06, 0x77, 0x68, 0x6F,
    0x6D, 0x00, 0x00, 0x00,
))  # fmt: skip


__all__ = ["sdic", "whdic"]
