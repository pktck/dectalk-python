"""Dictionary-tool data structures from dic.h.

Translated from ``src/dapi/src/dic/dic.h``. These structs are
used by the dictionary compiler and inspection utilities — not by
the runtime TTS engine. They model the dictionary build's
intermediate representation: a header, a (spelling, pronunciation,
form-class, semantics, frequency, comment) dictionary entry, and
a request-descriptor.

These are dataclasses for parity / future Phase F work; the
Python TTS runtime accesses dictionaries through the
:mod:`dectalk.dic.dic_entry` runtime structs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

S_LEN: Final[int] = 40
"""Maximum spelling-field length in :class:`Dic` (chars)."""

P_LEN: Final[int] = 40
"""Maximum pronunciation-field length in :class:`Dic` (chars)."""

C_LEN: Final[int] = 80
"""Maximum comment-field length in :class:`Dic` (chars)."""


@dataclass(slots=True)
class ItemDsc:
    """Item descriptor — used by dictionary-tool request routines.

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            unsigned short buffer_length;
            unsigned short item_code;
            unsigned long *buffer;
            unsigned long *transfer_size;
        } ITEM_DSC;
    """

    buffer_length: int = 0
    item_code: int = 0
    buffer: list[int] = field(default_factory=list[int])
    transfer_size: int = 0


@dataclass(slots=True)
class DicObjHeader:
    """Database object file header (508-byte fixed layout).

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            unsigned long no_of_entries;
            unsigned long creation;
            unsigned long modified;
            unsigned char dummy[500];
        } DIC_OBJ_HEADER;
    """

    no_of_entries: int = 0
    creation: int = 0
    modified: int = 0
    dummy: bytes = field(default_factory=lambda: b"\x00" * 500)


@dataclass(slots=True)
class Dic:
    """Internal dictionary entry used by tools.

    Faithful translation of:

    .. code-block:: c

        typedef struct dic {
            struct dic *flink;
            char spelling[S_LEN];
            char pronunciation[P_LEN];
            unsigned long form_class;
            unsigned long semantic_class[31];
            unsigned long frequency;
            char comment[C_LEN];
        } DIC;

    Attributes:
        flink: Forward link (Python references replace C ``*flink``).
        spelling: Orthographic spelling, up to :data:`S_LEN` chars.
        pronunciation: Phonetic spelling, up to :data:`P_LEN` chars.
        form_class: 32-bit form-class bitmask (``FC_*`` flags).
        semantic_class: 31-quadword bitmask array of semantic features.
        frequency: Word frequency per million.
        comment: Free-text comment, up to :data:`C_LEN` chars.
    """

    flink: Dic | None = None
    spelling: bytes = b""
    pronunciation: bytes = b""
    form_class: int = 0
    semantic_class: list[int] = field(default_factory=lambda: [0] * 31)
    frequency: int = 0
    comment: bytes = b""


@dataclass(slots=True)
class Grammar:
    """Form-class + semantic subset of a Dic entry.

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            unsigned long form_class;
            unsigned long semantic_class[31];
        } GRAMMAR;

    Used by certain parsing / display routines that don't need the
    full :class:`Dic` payload.
    """

    form_class: int = 0
    semantic_class: list[int] = field(default_factory=lambda: [0] * 31)


# -- BIT[] fast bit-shift lookup ------------------------------------------
#
# dic.h defines a 32-entry table where BIT[i] = 1 << i. Python's bit-shift
# is cheap so the table isn't strictly necessary, but exposing it preserves
# parity with C-style indexing.

BIT: Final[tuple[int, ...]] = tuple(1 << i for i in range(32))
"""32-entry ``1 << i`` lookup matching dic.h ``unsigned long BIT[32]``."""


__all__ = [
    "BIT",
    "C_LEN",
    "P_LEN",
    "S_LEN",
    "Dic",
    "DicObjHeader",
    "Grammar",
    "ItemDsc",
]
