"""Form-class (part-of-speech) name table from dic_comm.c.

Translated from ``src/dapi/src/dic/dic_comm.c``. ``form_class_strings``
is a 32-entry table mapping bit positions in the 32-bit
``fc_struct`` form-class mask to a human-readable POS abbreviation
(adj / adv / art / aux / be / ...).

The mask bits are ORed together when a word matches multiple
classes (e.g. ``"and"`` is conj | verb | func). ``print_fc`` walks
this table to render a mask as a space-separated list of names.
"""

from __future__ import annotations

from typing import Final

form_class_strings: Final[tuple[str, ...]] = (
    " adj",
    " adv",
    " art",
    " aux",
    " be",
    " bev",
    " conj",
    " ed",
    " have",
    " ing",
    " noun",
    " pos",
    " prep",
    " pron",
    " subj",
    " that",
    " to",
    " verb",
    " who",
    " neg",
    " intr",
    " ref",
    " part",
    " func",
    " cont",
    " char",
    " refr",
    " unused",
    " unused",
    " mark",
    " cont",
    " homo",
)
"""32-entry POS-abbreviation table (one per bit in fc_struct)."""


__all__ = ["form_class_strings"]
