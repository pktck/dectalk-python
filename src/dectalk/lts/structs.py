"""Core LTS data structures from ls_defs.h.

Translated from ``src/dapi/src/lts/ls_defs.h``:

- :class:`Item` — input token with up to 4 font-encoded words
  (``i_nword`` + ``i_word[0..3]``).
- :class:`Phone` — linked-list node in a phoneme stream. The C
  struct uses a union for the plain (``p_c[6]``) vs index
  (``p_i[3]``) layouts; the Python class exposes the plain-layout
  fields (``p_flag``, ``p_stress``, ``p_sphone``, ``p_uphone``)
  plus the index-layout fields (``p_itype``, ``p_value``,
  ``p_iret``) as separate optional fields. ``p_fp``/``p_bp``
  link pointers become Python object references.
- :class:`Letter` — a single character in a word slice. The C
  struct has only ``l_ch``; the ``l_ip`` index pointer was removed
  in revision 011 (MGS 12/28/2000).
- :class:`Num` — sextet of (left,right) LETTER pointer pairs
  marking the integer, fractional, and exponent parts of a number.
- :class:`Graph` — a (grapheme-code, feature-bits) pair used by
  the rule engine in ls_rule.c.

The C ``#define`` aliases (``PREV``, ``NEXT``, ``LSISSTRESS``,
``LSISSBOUND``, ``LSISVOWEL``, ``LSNULL``) are exposed as small
helper functions.

These are pure data definitions — no behaviour. Functions that
operate on these structs live in separate modules so the data
shape can be tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# -- Phoneme-flag bits from ls_defs.h ---------------------------------------

PFDASH: Final[int] = 0x01
"""``[-]`` boundary marker."""

PFSTAR: Final[int] = 0x02
"""``[*]`` boundary marker."""

PFHASH: Final[int] = 0x04
"""``[#]`` boundary marker."""

PFPLUS: Final[int] = 0x08
"""``[+]`` boundary marker."""

PFSYLAB: Final[int] = 0x10
"""``[=]`` boundary marker (syllabic)."""

PFRFUSE: Final[int] = 0x20
"""Syllable refuses stress."""

PFLEFTC: Final[int] = 0x40
"""In left cluster."""

PFBLOCK: Final[int] = 0x80
"""Block vowel reductions."""

PFBOUND: Final[int] = PFDASH | PFSTAR | PFHASH
"""Any of ``[-]`` ``[*]`` ``[#]`` boundary markers."""

PFMORPH: Final[int] = PFDASH | PFSTAR | PFHASH | PFPLUS
"""Any morphological boundary marker including ``[+]``."""


@dataclass(slots=True)
class Item:
    """Input token with up to 4 font-encoded words.

    Faithful translation of:

    .. code-block:: c

        typedef struct ITEM_struct {
            short i_nword;       /* # of words (1-4) */
            short i_word[4];     /* The words */
        } ITEM;

    The ``i_word`` array stores up to 4 font-encoded values where
    ``i_word[0]`` is the primary code and the rest are extra
    payload (e.g. for index marks, INDEX_REPLY callbacks, etc.).

    Attributes:
        i_nword: Number of words present (1-4), or 0 for empty.
        i_word: 4-tuple of font-encoded short values.
    """

    i_nword: int = 0
    i_word: list[int] = field(default_factory=lambda: [0, 0, 0, 0])


@dataclass(slots=True)
class Phone:
    """Linked-list node in a phoneme stream.

    Faithful translation of:

    .. code-block:: c

        typedef struct PHONE {
            struct PHONE *p_fp;          // Link forward
            struct PHONE *p_bp;          // Link backward
            union {
                int p_c[6];              // Plain layout
                int p_i[3];              // Index layout
            } p_u;
        } PHONE;

    Plain layout (``p_c[0..5]``) is named:

    * ``p_flag`` = ``p_c[0]`` — PF* boundary/cluster flags
    * ``p_stress`` = ``p_c[1]`` — SNONE/SUN/SSEC/SPRI/S1LEFT/S2LEFT
    * ``p_sphone`` = ``p_c[2]`` — surface (stressed) US phoneme code
    * ``p_uphone`` = ``p_c[3]`` — underlying (unstressed) US phoneme code

    Index layout (``p_i[0..2]``):

    * ``p_itype`` = ``p_i[0]`` — INDEX / INDEX_REPLY type
    * ``p_value`` = ``p_i[1]`` — index value
    * ``p_iret`` = ``p_i[2]`` — return style

    Python exposes both layouts side-by-side; callers select the
    fields they need.

    Attributes:
        p_fp: Forward link to next PHONE, or ``None`` for the tail.
        p_bp: Backward link, or ``None`` for the head sentinel.
        p_flag: Boundary / cluster flags (PF* bits).
        p_stress: Stress class.
        p_sphone: Stressed allophone code.
        p_uphone: Unstressed allophone code.
        p_itype: Index marker type (for index-list nodes).
        p_value: Index value.
        p_iret: Index return style.
    """

    p_fp: Phone | None = None
    p_bp: Phone | None = None
    # Plain layout
    p_flag: int = 0
    p_stress: int = 0
    p_sphone: int = 0
    p_uphone: int = 0
    # Index layout (aliased onto the same C union; here we keep them
    # as separate fields since Python has no zero-cost unions).
    p_itype: int = 0
    p_value: int = 0
    p_iret: int = 0


@dataclass(slots=True)
class Letter:
    """A single character in a word slice.

    Faithful translation of:

    .. code-block:: c

        typedef struct LETTER_struct {
            short l_ch;     // The character code
        } LETTER;

    The original C struct also had an ``l_ip`` PHONE pointer for
    attaching an index list, but that was removed in revision 011
    (MGS 12/28/2000) as documented in ``ls_util.c``.

    Attributes:
        l_ch: 16-bit signed character code (Latin-1 byte values or
            grapheme codes depending on the pipeline stage).
    """

    l_ch: int = 0


@dataclass(slots=True)
class Num:
    """Number-reading bookkeeping pointers.

    Faithful translation of:

    .. code-block:: c

        typedef struct NUM_struct {
            LETTER *n_ilp;   // Integer part: left
            LETTER *n_irp;   // Integer part: right
            LETTER *n_flp;   // Fractional part: left
            LETTER *n_frp;   // Fractional part: right
            LETTER *n_elp;   // Exponent: left
            LETTER *n_erp;   // Exponent: right
        } NUM;

    Each pair (``*lp``, ``*rp``) bounds a sub-slice of the word
    being analysed as a number. Either pointer in a pair can be
    ``None`` to mean "this part is not present" (e.g. an integer
    with no fractional part has ``n_flp == n_frp == None``).

    Attributes:
        n_ilp: Left bound of the integer part.
        n_irp: Right bound of the integer part.
        n_flp: Left bound of the fractional part (or None).
        n_frp: Right bound of the fractional part (or None).
        n_elp: Left bound of the exponent (or None).
        n_erp: Right bound of the exponent (or None).
    """

    n_ilp: Letter | None = None
    n_irp: Letter | None = None
    n_flp: Letter | None = None
    n_frp: Letter | None = None
    n_elp: Letter | None = None
    n_erp: Letter | None = None


@dataclass(slots=True)
class Graph:
    """Grapheme + feature-bits pair for the rule engine.

    Faithful translation of:

    .. code-block:: c

        typedef struct GRAPH_struct {
            S16 g_graph;     // Grapheme code
            S16 g_feats;     // Set of features
        } GRAPH;

    The C source historically had a ``PHONE *g_ip`` field too,
    commented out in the current source. The Python port omits it.

    Attributes:
        g_graph: 16-bit grapheme code.
        g_feats: 16-bit feature-bit field.
    """

    g_graph: int = 0
    g_feats: int = 0


# -- LS_DEFS helper functions (#defines in C) -------------------------------


def prev(lsp: Phone) -> Phone | None:
    """``PREV(lsp)`` — return the backward-linked PHONE.

    C ``#define PREV(lsp) (lsp->p_bp)``.
    """
    return lsp.p_bp


def next_(lsp: Phone) -> Phone | None:  # ``next`` is a builtin in Python
    """``NEXT(lsp)`` — return the forward-linked PHONE.

    C ``#define NEXT(lsp) (lsp->p_fp)``.
    """
    return lsp.p_fp


# Spanish-specific stress bits from ls_defs.h.
LS_ANY_STRESS: Final[int] = 7
LS_STRESS_1: Final[int] = 1
LS_STRESS_2: Final[int] = 2
LS_STRESS_3: Final[int] = 4
LSSBOUND: Final[int] = 8
LSVOWEL: Final[int] = 16


def ls_is_stress(lsp: Phone) -> bool:
    """``LSISSTRESS(lsp)`` — any-stress predicate.

    C ``#define LSISSTRESS(lsp) (((lsp)->p_flag & LS_ANY_STRESS) != 0)``.
    """
    return (lsp.p_flag & LS_ANY_STRESS) != 0


def ls_is_sbound(lsp: Phone) -> bool:
    """``LSISSBOUND(lsp)`` — syllable-boundary predicate.

    C ``#define LSISSBOUND(lsp) (((lsp)->p_flag & LSSBOUND) != 0)``.
    """
    return (lsp.p_flag & LSSBOUND) != 0


def ls_is_vowel(lsp: Phone) -> bool:
    """``LSISVOWEL(lsp)`` — vowel predicate (Spanish/French stress code).

    C ``#define LSISVOWEL(lsp) (((lsp)->p_flag & LSVOWEL) != 0)``.
    """
    return (lsp.p_flag & LSVOWEL) != 0


__all__ = [
    "LSSBOUND",
    "LSVOWEL",
    "LS_ANY_STRESS",
    "LS_STRESS_1",
    "LS_STRESS_2",
    "LS_STRESS_3",
    "PFBLOCK",
    "PFBOUND",
    "PFDASH",
    "PFHASH",
    "PFLEFTC",
    "PFMORPH",
    "PFPLUS",
    "PFRFUSE",
    "PFSTAR",
    "PFSYLAB",
    "Graph",
    "Item",
    "Letter",
    "Num",
    "Phone",
    "ls_is_sbound",
    "ls_is_stress",
    "ls_is_vowel",
    "next_",
    "prev",
]
