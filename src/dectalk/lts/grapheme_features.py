"""Grapheme- and phoneme-level feature tables.

Translated from ``src/dapi/src/lts/l_us_con.c``:

- ``feats`` is the grapheme feature table (indexed by grapheme code from
  ``ls_rule.c``'s 1-based alphabet plus the GU/QU digraphs). Drives rule
  matching in ``ls_rule_add_graph`` and ``l_us_ru1.c``.
- ``pfeat`` is the phoneme feature table (indexed by allophone code,
  see :mod:`dectalk.include.phoneme_codes`). Drives sibilance / voicing /
  consonant-cluster decisions in ``ls_util.c``, ``ls_suff.c``,
  ``ls_adju.c``.

Bit layout follows ``ls_defs.h``:

Grapheme bits (``feats``):
    - :data:`FSEG`      0x0001  segment (not a special marker)
    - :data:`FVOC`      0x0002  vocalic
    - :data:`FCONS`     0x0004  consonantal
    - :data:`FHIGH`     0x0008  high vowel
    - :data:`FVOICE`    0x0010  voiced
    - :data:`FLIQ`      0x0020  liquid
    - :data:`FSIB`      0x0040  sibilant
    - :data:`FLTSVELAR` 0x0080  velar
    - :data:`FNAS`      0x0100  nasal
    - :data:`FCOR`      0x0400  coronal
    - :data:`FC`        0x0800  C feature (for the letter C only)
    - :data:`FL`        0x1000  L feature
    - :data:`FX`        0x2000  X feature
    - :data:`FR`        0x4000  R feature
    - :data:`FSYL`      0x8000  syllabic

Phoneme bits (``pfeat``):
    - :data:`PCONS`     0x0001  consonant
    - :data:`PVOC`      0x0002  vowel
    - :data:`PBOTH`     0x0004  both (semivowel-ish)
    - :data:`PVOICE`    0x0008  voiced
    - :data:`PSIB`      0x0010  sibilant
    - :data:`POBS`      0x0020  obstruent
    - :data:`PTD`       0x0040  T/D (alveolar stop)
    - :data:`PBACK`     0x0080  back articulation
"""

from __future__ import annotations

from typing import Final

# -- Grapheme feature bits --------------------------------------------------

FSEG: Final[int] = 0x0001
FVOC: Final[int] = 0x0002
FCONS: Final[int] = 0x0004
FHIGH: Final[int] = 0x0008
FVOICE: Final[int] = 0x0010
FLIQ: Final[int] = 0x0020
FSIB: Final[int] = 0x0040
FLTSVELAR: Final[int] = 0x0080
FNAS: Final[int] = 0x0100
FCOR: Final[int] = 0x0400
FC: Final[int] = 0x0800
FL: Final[int] = 0x1000
FX: Final[int] = 0x2000
FR: Final[int] = 0x4000
FSYL: Final[int] = 0x8000


# -- Phoneme feature bits ---------------------------------------------------

PCONS: Final[int] = 0x0001
PVOC: Final[int] = 0x0002
PBOTH: Final[int] = 0x0004
PVOICE: Final[int] = 0x0008
PSIB: Final[int] = 0x0010
POBS: Final[int] = 0x0020
PTD: Final[int] = 0x0040
PBACK: Final[int] = 0x0080


# -- feats[] grapheme feature table from l_us_con.c -------------------------
# 31 entries: index 0 is end-mark, 1..26 are letters A..Z, 27 is GU,
# 28 is QU, 29 is apostrophe, 30 is plus.

feats: Final[tuple[int, ...]] = (
    0x0000, 0x8003, 0x0015, 0x0805, 0x0415, 0x8003, 0x0005, 0x0095,
    0x0005, 0x800B, 0x0455, 0x0085, 0x1435, 0x0115, 0x0515, 0x8003,
    0x0005, 0x0005, 0x4035, 0x0045, 0x0405, 0x800B, 0x0015, 0x0415,
    0x2045, 0x0001, 0x0455, 0x0095, 0x0005, 0x0000, 0x0000,
)  # fmt: skip


# -- pfeat[] phoneme feature table from l_us_con.c --------------------------
# 120 entries: indexed by the US phoneme/control code (see
# :class:`dectalk.include.phoneme_codes.USPhoneme`). Codes 57..70 are
# placeholder allophone slots; 71..99 are NUL fillers; 100..119 are the
# control-code range (BLOCK_RULES, S2/S1/SEMPH, HAT_*, *BOUND, …) which
# all carry zero features.

pfeat: Final[tuple[int, ...]] = (
    0x0000, 0x000A, 0x000A, 0x000A, 0x000A, 0x000A, 0x000A, 0x000A,
    0x000A, 0x000A, 0x000A, 0x000A, 0x000A, 0x000A, 0x000A, 0x000C,
    0x000A, 0x000A, 0x000A, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0001, 0x0001, 0x0009, 0x0009, 0x0001, 0x0000, 0x0000, 0x0029,
    0x0029, 0x0009, 0x000C, 0x0000, 0x000C, 0x0021, 0x0029, 0x0021,
    0x0029, 0x0031, 0x0039, 0x0031, 0x0039, 0x0021, 0x0029, 0x0061,
    0x0069, 0x0021, 0x0029, 0x0001, 0x0001, 0x0000, 0x0011, 0x0019,
    0x0001, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
)  # fmt: skip


__all__ = [
    "FC",
    "FCONS",
    "FCOR",
    "FHIGH",
    "FL",
    "FLIQ",
    "FLTSVELAR",
    "FNAS",
    "FR",
    "FSEG",
    "FSIB",
    "FSYL",
    "FVOC",
    "FVOICE",
    "FX",
    "PBACK",
    "PBOTH",
    "PCONS",
    "POBS",
    "PSIB",
    "PTD",
    "PVOC",
    "PVOICE",
    "feats",
    "pfeat",
]
