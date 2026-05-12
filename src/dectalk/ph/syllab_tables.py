"""Syllabification constant tables for US English.

Translated from ``src/dapi/src/ph/p_us_sy1.c``. These three tables are
consulted by the phoneme syllabifier (``ph_syllab`` in ``ph/syllab.c``)
to decide where syllable boundaries fall:

- :data:`ascky_check` — sparse 111-entry table that flips an internal
  flag for "sounded" phonemes (vowels + voiced consonants) and stays
  zero for stress/control codes; consulted via ``ascky_check[code]``.
  Each non-zero byte is an ASCII glyph standing for the phoneme that
  the C code uses for debug-print, not as data; behaviour only depends
  on zero vs. non-zero.
- :data:`common_affixes` — list of pre-syllabified affix patterns
  ("sElvz", "stAn", "gr@f", "ples", …) that the syllabifier checks
  for at word ends. Phoneme glyphs follow DECtalk's ASCII-phoneme
  convention (E=EH, A=AY, I=IH, R=ER, etc.).
- :data:`syl_vowels` — string of single-byte phoneme glyphs that
  count as vowels for syllable-nucleus detection.
- :data:`syl_cons` — list of allowable syllable-onset consonant
  clusters, ordered longest-first. The C scanner walks this list
  matching the longest cluster after a vowel.
"""

from __future__ import annotations

from typing import Final

# ``ascky_check`` indexed by phoneme-byte value; non-zero means
# "sounded" (vowel or voiced consonant). The C source uses the actual
# ASCII letter for the phoneme as the marker for debugging, but only
# zero/non-zero matters at runtime.

ascky_check: Final[bytes] = bytes((
    0,    ord("i"), ord("I"), ord("e"), ord("E"),
    ord("@"), ord("a"), ord("A"), ord("W"), ord("^"),
    ord("c"), ord("o"), ord("O"), ord("U"), ord("u"),
    ord("R"), ord("Y"), ord("x"), ord("|"), 0,
    0, 0, 0, 0, ord("w"),
    ord("y"), ord("r"), ord("l"), ord("h"), 0,
    0, ord("m"), ord("n"), ord("G"), ord("L"),
    0, ord("N"), ord("f"), ord("v"), ord("T"),
    ord("D"), ord("s"), ord("z"), ord("S"), ord("Z"),
    ord("p"), ord("b"), ord("t"), ord("d"), ord("k"),
    ord("g"), ord("&"), ord("Q"), ord("q"), ord("C"),
    ord("J"), 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0, ord(" "), 0, 0, 0,
    0, 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0, 0, 0, 0, 0,
    0,
))  # fmt: skip


# Word-end affix patterns the syllabifier matches against. The C
# source terminates the array with NULL — we drop the trailing NULL.

common_affixes: Final[tuple[str, ...]] = (
    "sElvz", "kwIst", "flEks", "sfir", "stAn", "gr@f", "ples", "plen",
    "skop", "baks", "ston", "wRT", "lxnd", "l@nd", "k@st", "fI|S",
    "h@nd", "yard", "kcpf", "mxnt", "mEnt", "sElf", "st@t", "SI|p",
    "sAt", "vIl", "b@k", "bot", "lAf", "lAk", "pAp", "wck", "wcS",
    "wUd", "wRk", "kek", "bcl", "bEl", "del", "hIl", "hol", "hUd",
    "l|s", "m@n", "mxn", "mor", "nEk", "n|s", "Sap", "Z|n", "S|n",
    "tel", "tin", "tAm", "wRd", "wer", "wIl", "wAz", "b@g", "k@p",
    "kar", "k@t", "dxm", "flA", "mxn", "m@n", "mEn", "n^t", "pad",
    "ek", "bO", "de", "fL", "|J", "sc", "we",
)  # fmt: skip


# Single-byte phoneme glyphs that count as syllable nuclei.

syl_vowels: Final[str] = "a@AeEiIoOuU^WRc|xLN"


# Consonant onsets the syllabifier accepts, in match order
# (longest-first within each leading-phone group).

syl_cons: Final[tuple[str, ...]] = (
    "spl", "spr", "str", "skw", "skl", "skr",
    " Sm", " SL",
    "pl", "pr",
    "bl", "br",
    "fl", "fr",
    "tw", "tr",
    "dw", "dr",
    "Tw", "Tr",
    "kw", "kl", "kr",
    "gw", "gl", "gr",
    "sw", "sl", "sp", "st", "sk", "sm", "sn",
    "Sw", "Sl", "Sr",
    " Y",
    "y", "f", "t", "d", "T", "k", "g", "s",
    "S", "p", "w", "l", "r", "h", "D", "z",
    "Z", "C", "J", "n", "m", "v", "b",
)  # fmt: skip


__all__ = ["ascky_check", "common_affixes", "syl_cons", "syl_vowels"]
