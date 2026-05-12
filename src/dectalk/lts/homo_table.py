"""Homograph disambiguation rules from ls_homo.h.

Translated from ``src/dapi/src/lts/ls_homo.h``. The table is the
US-English output of the rule generator (``ls_homo_us.tab`` →
``ls_homo.h``) used by the homograph disambiguator: each rule
matches words whose part-of-speech mask covers both ``h_suffix``
and ``h_context`` against neighbouring words' form-class bits,
then selects ``h_select`` and eliminates ``h_elim`` from the
candidate set.

The fields hold ``FC_*`` masks from
:mod:`dectalk.dic.form_class_bits` (e.g. ``FC_NOUN = 0x400``,
``FC_VERB = 0x20000``); see the ``homo_rule`` struct in
``ls_homo.h``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

MAX_HOMO_RULE: Final[int] = 27
"""Total number of homograph rules (``MAX_HOMO_RULE`` in ls_homo.h)."""


@dataclass(frozen=True, slots=True)
class HomoRule:
    """One homograph disambiguation rule.

    Faithful translation of:

    .. code-block:: c

        struct homo_rule {
            S32 h_suffix;
            S32 h_context;
            S32 h_select;
            S32 h_elim;
        };

    Attributes:
        h_suffix: FC mask describing the suffix-derived form classes
            this rule applies to. Zero means the rule fires solely
            on neighbour context.
        h_context: FC mask describing the form classes the left- or
            right-neighbour word must carry for this rule to fire.
        h_select: FC mask of form classes to retain on the target
            word when the rule matches.
        h_elim: FC mask of form classes to drop from the target word
            when the rule matches.
    """

    h_suffix: int
    h_context: int
    h_select: int
    h_elim: int


homo_table: Final[tuple[HomoRule, ...]] = (
    HomoRule(0x00000080, 0x00000000, 0x00000000, 0x00000400),
    HomoRule(0x00000080, 0x00000004, 0x00000001, 0x00000000),
    HomoRule(0x00000200, 0x00000000, 0x00000000, 0x00000400),
    HomoRule(0x00000200, 0x00000004, 0x00000001, 0x00000000),
    HomoRule(0x00000002, 0x00000000, 0x00000001, 0x00000000),
    HomoRule(0x00020001, 0x00000000, 0x00000000, 0x00000400),
    HomoRule(0x00020400, 0x00000000, 0x00000000, 0x00000001),
    HomoRule(0x00000401, 0x00000000, 0x00000000, 0x00020000),
    HomoRule(0x00000000, 0x00000020, 0x00000001, 0x00000000),
    HomoRule(0x00000000, 0x00100000, 0x00020000, 0x00000000),
    HomoRule(0x00000000, 0x00010000, 0x00020000, 0x00000000),
    HomoRule(0x00000000, 0x00040000, 0x00000000, 0x00000400),
    HomoRule(0x00000000, 0x00000100, 0x00000080, 0x00000000),
    HomoRule(0x00000000, 0x00000020, 0x00000080, 0x00000000),
    HomoRule(0x00000000, 0x00000010, 0x00000080, 0x00000000),
    HomoRule(0x00000000, 0x00000008, 0x00020000, 0x00000000),
    HomoRule(0x00000000, 0x00000100, 0x00020000, 0x00000000),
    HomoRule(0x00000000, 0x00000020, 0x00020000, 0x00000000),
    HomoRule(0x00000000, 0x00000010, 0x00020000, 0x00000000),
    HomoRule(0x00000000, 0x00000800, 0x00000400, 0x00000000),
    HomoRule(0x00000000, 0x00002000, 0x00020000, 0x00000000),
    HomoRule(0x00000000, 0x00001000, 0x00000000, 0x00020000),
    HomoRule(0x00000000, 0x00000004, 0x00000000, 0x00020000),
    HomoRule(0x00000000, 0x00000004, 0x00000400, 0x00000000),
    HomoRule(0x00000000, 0x00000001, 0x00000000, 0x00020000),
    HomoRule(0x00000000, 0x00000001, 0x00000400, 0x00000000),
    HomoRule(0x00000000, 0x00020000, 0x00000400, 0x00000000),
)
"""27-entry ``homo_table`` from ``ls_homo.h`` (verbatim values)."""


__all__ = [
    "MAX_HOMO_RULE",
    "HomoRule",
    "homo_table",
]
