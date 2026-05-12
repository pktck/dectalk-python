"""Per-language table pointers from kernel.h.

Translated from ``src/dapi/src/include/kernel.h``. The kernel
maintains two related structs that aggregate the per-language data
tables:

- :class:`DtpcLanguageTables` — linked-list node of language
  tables loaded into the engine. Each node owns one language's
  ascky / reverse-ascky / arpabet / typing / error tables.
- :class:`LangTables` — per-language table-pointer struct the
  kernel indexes by language ID (``pKsd_t->lang_tables[lang]``).

In the C source these struct fields are ``unsigned char _far *``
pointers into static data tables. The Python port uses
``bytes | None`` / ``list[bytes] | None`` so callers can attach
the actual tables when the language is loaded.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DtpcLanguageTables:
    """One loaded language's data tables (one node in a linked list).

    Faithful translation of:

    .. code-block:: c

        struct dtpc_language_tables {
            struct dtpc_language_tables far *link;
            int lang_id;
            unsigned char far *lang_ascky;
            int lang_ascky_size;
            unsigned int far *lang_reverse_ascky;
            unsigned char far *lang_arpabet;
            int lang_arpa_size;
            int lang_arpa_case;
            const unsigned char far * far *lang_typing;
            const unsigned char far * far *lang_error;
        };

    The ``link`` pointer becomes a Python ``DtpcLanguageTables | None``
    reference for the linked-list traversal.

    Attributes:
        link: Next node in the linked list, or None at the tail.
        lang_id: Language ID (one of the ``LANG_*`` codes).
        lang_ascky: ASCKY-to-phoneme table (per-character mapping).
        lang_ascky_size: Length of ``lang_ascky``.
        lang_reverse_ascky: Inverse mapping (phoneme → ASCKY).
        lang_arpabet: ARPABET-to-phoneme table.
        lang_arpa_size: Length of ``lang_arpabet``.
        lang_arpa_case: Case sensitivity flag for the ARPABET parser.
        lang_typing: Two-level ``typing`` table (one row per character).
        lang_error: Two-level ``error`` table for diagnostics.
    """

    link: DtpcLanguageTables | None = None
    lang_id: int = 0
    lang_ascky: bytes | None = None
    lang_ascky_size: int = 0
    lang_reverse_ascky: list[int] | None = None
    lang_arpabet: bytes | None = None
    lang_arpa_size: int = 0
    lang_arpa_case: int = 0
    lang_typing: list[bytes] | None = None
    lang_error: list[bytes] | None = None


@dataclass(slots=True)
class LangTables:
    """Per-language table-pointer struct indexed by language ID.

    Faithful translation of:

    .. code-block:: c

        typedef struct language_tables {
            unsigned char far *lang_ascky;
            unsigned char far * far *lang_arpa;
            unsigned char far *char_map;
            unsigned char far *char_types;
            unsigned char far *char_lower;
            unsigned char far *char_upper;
            unsigned char far *char_feat;
            unsigned char far * far *type_table;
            unsigned char far * far *error_table;
        } LANG_TABLES;

    Used by the kernel ``ASCKY_MAP`` / ``ARPA_MAP`` /
    ``CHAR_TYPES`` etc. macros to dispatch on the currently active
    language.

    Attributes:
        lang_ascky: Per-character ASCKY mapping for this language.
        lang_arpa: Two-level ARPABET mapping.
        char_map: Lower-case character-folding map.
        char_types: Per-character type bits (alpha / digit / etc.).
        char_lower: Lower-case folding table.
        char_upper: Upper-case folding table.
        char_feat: Character feature bits.
        type_table: Two-level type-conversion table.
        error_table: Two-level error-message table.
    """

    lang_ascky: bytes | None = None
    lang_arpa: list[bytes] | None = None
    char_map: bytes | None = None
    char_types: bytes | None = None
    char_lower: bytes | None = None
    char_upper: bytes | None = None
    char_feat: bytes | None = None
    type_table: list[bytes] | None = None
    error_table: list[bytes] | None = None


__all__ = ["DtpcLanguageTables", "LangTables"]
