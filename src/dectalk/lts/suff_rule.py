"""``suff_rule`` suffix-rule struct from ls_dict.h.

Translated from ``src/dapi/src/lts/ls_dict.h``:

.. code-block:: c

    struct suff_rule {
        U32 next;
        U32 fc;
        unsigned char rule[256];
    };

The struct is a linked-list node in the suffix-rule table the LTS
suffix engine (``ls_suff.c``) walks when probing for a known
suffix on an unknown word. ``next`` is a byte offset to the next
candidate, ``fc`` is the form-class mask to apply on a hit, and
``rule`` is the (nul-terminated) suffix pattern itself.

The dictionary writer packs these rules with the ``next`` pointer
chains, so the Python side mirrors the layout but stores the rule
as a Python ``bytes`` to avoid the 256-byte tail-padding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

SUFF_RULE_TEXT_MAX: Final[int] = 256
"""Maximum bytes in the ``rule`` buffer (matches C array size)."""


@dataclass(slots=True)
class SuffRule:
    """One suffix-rule node in the LTS suffix table.

    Attributes:
        next: Byte offset (or table index) of the next candidate
            suffix in the chain. Zero means end-of-chain.
        fc: Form-class mask (FC_* bits) to apply when this rule
            matches.
        rule: The suffix pattern as a byte string — at most
            :data:`SUFF_RULE_TEXT_MAX` bytes; typically much
            shorter and nul-terminated in C.
    """

    next: int = 0
    fc: int = 0
    rule: bytes = b""


__all__ = [
    "SUFF_RULE_TEXT_MAX",
    "SuffRule",
]
