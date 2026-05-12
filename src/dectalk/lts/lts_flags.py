"""LTS flags / dict-hit / homograph constants from ls_data.h.

Translated from ``src/dapi/src/lts/ls_data.h``. Three small groups
of constants the LTS word-table maintenance uses:

- **Dict-hit codes** (:data:`MAIN_DICT_HIT` / :data:`USER_DICT_HIT`
  / :data:`FOREIGH_DICT_HIT`): which dictionary matched the word
  (note: ``FOREIGH`` is the C source's typo for ``FOREIGN``).
- **Homograph flags** (:data:`WORD_IS_HOMOGRAPH` / :data:`HOMO_PRIMARY`
  / :data:`HOMO_SECONDARY`): set when a word has multiple
  pronunciations and the parser has chosen one.
- **LTS pipeline state flags** (:data:`LTS_FLAG_DONE` /
  :data:`LTS_FLAG_HOMOGRAPH` / :data:`LTS_FLAG_IS_PHONES` /
  :data:`LTS_FLAG_DICT_HIT_TYPE`): per-word ``lts_flags`` field
  values.
- :data:`MAX_WORDS` — capacity of the new-LTS word array.
"""

from __future__ import annotations

from typing import Final

# -- Dict-hit codes ---------------------------------------------------------

MAIN_DICT_HIT: Final[int] = 1
"""Word matched the main dictionary."""

USER_DICT_HIT: Final[int] = 2
"""Word matched the user dictionary."""

FOREIGH_DICT_HIT: Final[int] = 3
"""Word matched the foreign-language dictionary (note: spelled
``FOREIGH`` in ls_data.h — preserved verbatim)."""

# -- Homograph flags --------------------------------------------------------

WORD_IS_HOMOGRAPH: Final[int] = 0x01
"""This word has multiple pronunciations (set on dict match)."""

HOMO_PRIMARY: Final[int] = 0x02
"""Parser chose the primary pronunciation."""

HOMO_SECONDARY: Final[int] = 0x04
"""Parser chose the secondary pronunciation."""

# -- LTS pipeline state flags -----------------------------------------------

LTS_FLAG_DONE: Final[int] = 0x00000001
"""This word's LTS pass is complete."""

LTS_FLAG_HOMOGRAPH: Final[int] = 0x00000006
"""Bit mask covering the homograph-primary / homograph-secondary state."""

LTS_FLAG_IS_PHONES: Final[int] = 0x00000008
"""This word's output is already a phoneme string (skip LTS rules)."""

LTS_FLAG_DICT_HIT_TYPE: Final[int] = 0x00000030
"""Bit mask covering the dict-hit code (MAIN / USER / FOREIGH)."""

# -- Word array capacity ----------------------------------------------------

MAX_WORDS: Final[int] = 500
"""Capacity of the per-LTS-thread ``word_info[]`` array (NEW_LTS build)."""


__all__ = [
    "FOREIGH_DICT_HIT",
    "HOMO_PRIMARY",
    "HOMO_SECONDARY",
    "LTS_FLAG_DICT_HIT_TYPE",
    "LTS_FLAG_DONE",
    "LTS_FLAG_HOMOGRAPH",
    "LTS_FLAG_IS_PHONES",
    "MAIN_DICT_HIT",
    "MAX_WORDS",
    "USER_DICT_HIT",
    "WORD_IS_HOMOGRAPH",
]
