"""Dictionary entry struct from ttsapi.h.

Translated from ``src/dapi/src/api/ttsapi.h``. A ``dic_entry`` is
one row in the main / user dictionary: a feature-class header
followed by a NUL-terminated grapheme text. The phoneme string
trails the text in C memory, addressed by walking past the NUL.

The Python port stores the grapheme text and phoneme string as
separate bytes fields, sidestepping the C contiguous-buffer
layout while preserving the data shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DicEntry:
    """One dictionary entry: feature class + grapheme + phonemes.

    Faithful translation of:

    .. code-block:: c

        struct dic_entry {
            unsigned int fc[1];        // feature class bits
            unsigned char text[128];   // NUL-terminated grapheme
        };
        // (Phoneme string lives just past text[strlen(text)+1].)

    The C struct uses a flexible ``text[128]`` buffer that holds both
    the grapheme and the phoneme string back-to-back, separated by a
    NUL. The Python port models them as two distinct bytes fields:

    Attributes:
        fc: Feature-class flag bits (one 32-bit value in C).
        text: Grapheme text as bytes (no trailing NUL).
        phoneme: Phoneme pronunciation as bytes (no trailing NUL).
    """

    fc: int = 0
    text: bytes = b""
    phoneme: bytes = b""


@dataclass(slots=True)
class DicEntryList:
    """A list of DicEntry items (the loaded dictionary).

    Wraps a Python list with two indexed views the LTS binary-search
    expects:

    - :attr:`entries`: list of :class:`DicEntry` in sort order.
    - :attr:`length`: number of entries (used as the binary-search
      upper bound).
    """

    entries: list[DicEntry] = field(default_factory=list[DicEntry])

    @property
    def length(self) -> int:
        """Return the number of dictionary entries (binary-search bound)."""
        return len(self.entries)


__all__ = ["DicEntry", "DicEntryList"]
