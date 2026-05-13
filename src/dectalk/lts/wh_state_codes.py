"""WH-word detection state codes from ls_defs.h.

Translated from ``src/dapi/src/lts/ls_defs.h`` lines 76-78.

The LTS rule engine tracks the WH-question-word state across a
clause to decide intonation contour shape (rising at end of WH-
question vs. falling at end of statement):

- :data:`UNK_WH` (0) — first word not yet examined.
- :data:`IS_WH` (1) — clause starts with what / where / when /
  why / who / how / which / whose / whom.
- :data:`NOT_WH` (2) — first word checked and isn't a WH-word.

The C source stores the state on ``pLts_t->wstate`` (an ``int``).
``ls_util_lts_init`` zeros it to :data:`UNK_WH` at clause start;
``ls_task_set_what_state`` flips it to :data:`IS_WH` or :data:`NOT_WH`
once the first word is examined.
"""

from __future__ import annotations

from typing import Final

UNK_WH: Final[int] = 0
"""WH-word state is unknown — first word not yet examined."""

IS_WH: Final[int] = 1
"""Clause begins with a WH-question word."""

NOT_WH: Final[int] = 2
"""Clause was examined and doesn't begin with a WH-word."""


__all__ = ["IS_WH", "NOT_WH", "UNK_WH"]
