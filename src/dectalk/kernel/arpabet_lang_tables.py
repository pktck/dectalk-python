"""Arpabet / language-flag / language-font index tables from usa_init.c.

Translated from ``src/dapi/src/kernel/usa_init.c`` lines 138-172.

When the kernel installs the loaded language set, it builds five
parallel arrays — one entry per language — that the LTS/PH pipeline
indexes into when an inline ``[:lang xx]`` command switches the
active language. The arrays use the *same* slot ordering as
:data:`dectalk.cmd.language_lookup.language_prefixes`:

    slot 0 = US English
    slot 1 = UK English
    slot 2 = Castilian Spanish
    slot 3 = German
    slot 4 = Latin-American Spanish
    slot 5 = French

The actual ARPAbet *contents* are vendored under
``src/dectalk/data/`` already; this module only exposes the table of
``LANG_*`` and ``PF*`` codes that map a slot index to the runtime
identifiers the rest of the engine uses.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.phoneme_codes import PFFR, PFGR, PFLA, PFSP, PFUK, PFUSA
from dectalk.kernel.lang_codes import (
    LANG_british,
    LANG_english,
    LANG_french,
    LANG_german,
    LANG_latin_american,
    LANG_spanish,
)

arpabet_lang_flags: Final[tuple[int, ...]] = (
    LANG_english,
    LANG_british,
    LANG_spanish,
    LANG_german,
    LANG_latin_american,
    LANG_french,
)
"""``LANG_*`` identifier for each language slot (parallel to
``language_prefixes``)."""

arpabet_lang_fonts: Final[tuple[int, ...]] = (
    PFUSA,
    PFUK,
    PFSP,
    PFGR,
    PFLA,
    PFFR,
)
"""``PF*`` phoneme-font bits encoding each slot's language."""


__all__ = [
    "arpabet_lang_flags",
    "arpabet_lang_fonts",
]
