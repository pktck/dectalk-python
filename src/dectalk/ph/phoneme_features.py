"""Per-phoneme feature bits from ph_defs.h.

Translated from ``src/dapi/src/ph/ph_defs.h``. These bit-flags are
the values stored in the per-language ``*_featb[]`` tables (one
``short`` per phoneme code) and returned by ``phone_feature()``
in :mod:`dectalk.ph.timing`. The PH module masks against these
constants when deciding allophone substitutions, F0 contour
adjustments, and timing rules.

Two distinct namespaces share the same 16-bit field, distinguished
by context:

- **Manner of articulation** (low byte): :data:`FSYLL`,
  :data:`FVOICD`, :data:`FVOWEL`, :data:`FSON1`, :data:`FSONOR`,
  :data:`FOBST`, :data:`FPLOSV`, :data:`FNASAL`, :data:`FCONSON`,
  :data:`FSONCON`, :data:`FSON2`, :data:`FBURST`, :data:`FSTMARK`,
  :data:`FSTOP`, :data:`FSEMIV`, :data:`FDIPTH`.
- **Place of articulation / F2-back flags** (low byte alt):
  :data:`FLABIAL`, :data:`FDENTAL`, :data:`FPALATL`, :data:`FALVEL`,
  :data:`FVELAR`, :data:`FGLOTTAL`, :data:`F2BACKI`, :data:`F2BACKF`.

The two sets overlap numerically (FSYLL = FLABIAL = 1, etc.); the
C source code accesses them through differently-named entries in
the per-language ``*_featb`` table. Distinct Python names mean
call sites read identically to the C source.
"""

from __future__ import annotations

from typing import Final

# -- Manner of articulation -------------------------------------------------

FSYLL: Final[int] = 0o1
"""Syllabic: vowels + /el/, /em/, /en/."""

FVOICD: Final[int] = 0o2
"""Voiced (regular, except /tq/ is [+voicd])."""

FVOWEL: Final[int] = 0o4
"""Vowels."""

FSON1: Final[int] = 0o10
"""[+sonor], except not /si/ and /h/."""

FSONOR: Final[int] = 0o20
"""[-obst], except /q/ is [-sonor, -obst]."""

FOBST: Final[int] = 0o40
"""Obstruent (regular, except /q/ is [-obst])."""

FPLOSV: Final[int] = 0o100
"""Plosives, excluding affricates."""

FNASAL: Final[int] = 0o200
"""Nasals."""

FCONSON: Final[int] = 0o400
"""[-syll], except for /si/ and /q/."""

FSONCON: Final[int] = 0o1000
"""Voiced liquids and glides: w, y, r, l, rx, lx."""

FSON2: Final[int] = 0o2000
"""/w, y, r, l, yu/, /m, n, ng, em, en/."""

FBURST: Final[int] = 0o4000
"""Plosives and affricates."""

FSTMARK: Final[int] = 0o10000
"""Stress markers [', `, !]."""

FSTOP: Final[int] = 0o20000
"""Plosives, affricates, and nasals."""

FSEMIV: Final[int] = 0o40000
"""Semivowels (Y, W, YX, WX)."""

FDIPTH: Final[int] = 0o100000
"""Diphthong-position vowels [i], [u], [yx], [wx]."""

# -- Place of articulation (alternate low-byte interpretation) --------------

FLABIAL: Final[int] = 0o1
"""Labial: p, b, m, f, v (same numeric value as :data:`FSYLL`,
selected by table context)."""

FDENTAL: Final[int] = 0o2
"""Dental: th, dh, d$."""

FPALATL: Final[int] = 0o4
"""Palatal: sh, zh, ch, jh."""

FALVEL: Final[int] = 0o10
"""Alveolar: t, d, n, en, s, z, tx (not l, r, dx)."""

FVELAR: Final[int] = 0o20
"""Velar: k, g, nx."""

FGLOTTAL: Final[int] = 0o40
"""Glottal: h, q, tq."""

F2BACKI: Final[int] = 0o100
"""F2-back initial: iy, y, yu."""

F2BACKF: Final[int] = 0o200
"""F2-back final: iy, y, ey (not ay, oy)."""

# -- Composite ----------------------------------------------------

BLADEAFFECTED: Final[int] = FDENTAL | FPALATL | FALVEL
"""Bladed (tongue-front) place — dental, palatal, or alveolar."""

# -- Word-feature high-byte flags (sentstruc upper bits) --------------------

WORDFEAT: Final[int] = 0xFFFF0000
"""Mask for the word-feature region of pDph_t->sentstruc[i]."""

F_TIME_RISE: Final[int] = 0o1000000
"""Time-rise marker."""

F_NOUN: Final[int] = 0o2000000
"""Part-of-speech tag: noun (used by stress assignment)."""

F_ADJ: Final[int] = 0o4000000
"""Part-of-speech tag: adjective."""

F_VERB: Final[int] = 0o10000000
"""Part-of-speech tag: verb."""

F_FUNC: Final[int] = 0o20000000
"""Part-of-speech tag: function word."""

F_IRESET: Final[int] = 0o4000000000
"""Index-reset marker (boundary that resets word/syllable counters)."""

FMAXIMUM: Final[int] = 0o10000000000
"""Highest assigned word-feature bit."""

FWBEND: Final[int] = 0o10000
"""Last phone of word (word-boundary end)."""

FHAT_ROOF: Final[int] = 0o100000
"""Hat-roof marker — used carefully by the intonation engine."""

# -- Front-vowel masks ------------------------------------------------------

MASKFRONT: Final[int] = 0o17
"""Mask for the front-vowel index field."""

__all__ = [
    "BLADEAFFECTED",
    "F2BACKF",
    "F2BACKI",
    "FALVEL",
    "FBURST",
    "FCONSON",
    "FDENTAL",
    "FDIPTH",
    "FGLOTTAL",
    "FHAT_ROOF",
    "FLABIAL",
    "FMAXIMUM",
    "FNASAL",
    "FOBST",
    "FPALATL",
    "FPLOSV",
    "FSEMIV",
    "FSON1",
    "FSON2",
    "FSONCON",
    "FSONOR",
    "FSTMARK",
    "FSTOP",
    "FSYLL",
    "FVELAR",
    "FVOICD",
    "FVOWEL",
    "FWBEND",
    "F_ADJ",
    "F_FUNC",
    "F_IRESET",
    "F_NOUN",
    "F_TIME_RISE",
    "F_VERB",
    "MASKFRONT",
    "WORDFEAT",
]
