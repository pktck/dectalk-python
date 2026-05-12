"""Function-verbs lookup table for the LTS Kurzweil hack.

Translated from the ``const verb_words_t verbs[6]`` table in
``src/dapi/src/lts/ls_task.c`` (under ``#ifdef ENGLISH_US``). The C
source comment calls it "a hack" — it lists the six high-frequency
function verbs (are/had/is/was/were/will) along with their pre-resolved
phoneme strings and a 32-bit feature-class word. The LTS engine
consults this list in ``ls_task_lookup_first_verbs`` to skip the
normal rule pass for these words.

Each entry is a ``VerbWord(word, phones, features)`` triple matching
the C struct (with the trailing phone-array padded to length 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dectalk.include.phoneme_codes import S2, USPhoneme

_SIL = 0


@dataclass(frozen=True, slots=True)
class VerbWord:
    """One entry: orthographic form, phoneme sequence (5 ints, SIL-padded), feature word."""

    word: str
    phones: tuple[int, int, int, int, int]
    features: int


# Translated verbatim from ls_task.c lines 4527-4536 (ENGLISH_US branch).
verbs: Final[tuple[VerbWord, ...]] = (
    VerbWord(
        "are",
        (S2, int(USPhoneme.AA), int(USPhoneme.R), _SIL, _SIL),
        0x00820020,
    ),
    VerbWord(
        "had",
        (int(USPhoneme.HX), S2, int(USPhoneme.EH), int(USPhoneme.D), _SIL),
        0x00820100,
    ),
    VerbWord(
        "is",
        (S2, int(USPhoneme.IH), int(USPhoneme.Z), _SIL, _SIL),
        0x00820020,
    ),
    VerbWord(
        "was",
        (int(USPhoneme.W), S2, int(USPhoneme.AX), int(USPhoneme.Z), _SIL),
        0x00820020,
    ),
    VerbWord(
        "were",
        (int(USPhoneme.W), S2, int(USPhoneme.RR), _SIL, _SIL),
        0x00820020,
    ),
    VerbWord(
        "will",
        (int(USPhoneme.W), S2, int(USPhoneme.IH), int(USPhoneme.LX), _SIL),
        0x00820408,
    ),
)


__all__ = ["VerbWord", "verbs"]
