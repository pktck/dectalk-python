"""LTS rule-engine phoneme aliases from ls_defs.h.

Translated from ``src/dapi/src/lts/ls_defs.h`` lines 67-74.

The LTS rule engine reads phoneme codes from a *parallel* alias
namespace so the same codes the parser emits do double duty as
morpheme/syllable boundary markers in the LHS of rule strings.
The aliases:

- :data:`DASH`  = :data:`SBOUND`  — ``[-]`` syllable boundary.
- :data:`STAR`  = :data:`MBOUND`  — ``[*]`` morpheme boundary.
- :data:`HASH`  = :data:`HYPHEN`  — ``[#]`` noun-compound hyphen.
- :data:`PLUS`  = :data:`PERIOD`  — ``[+]`` "hides over" period.
- :data:`EQUAL` = :data:`COMMA`   — ``[=]`` "hides over" comma.

The two overloads (``PLUS`` ↔ ``PERIOD``, ``EQUAL`` ↔ ``COMMA``)
are explicitly noted as intentional by the original author:
*"These two just hide overtop of two impossible ones."* — the
rule engine never sees a real ``PERIOD``/``COMMA`` phoneme code,
so re-using their numeric values for boundary markers is safe.

:data:`NPHONE` is the loop limit used when walking the phoneme
inventory for rule-table lookups.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.phoneme_codes import (
    COMMA,
    HYPHEN,
    MBOUND,
    PERIOD,
    PHO_SYM_TOT,
    SBOUND,
)

DASH: Final[int] = SBOUND
"""``[-]`` boundary marker — same code as :data:`SBOUND`."""

STAR: Final[int] = MBOUND
"""``[*]`` boundary marker — same code as :data:`MBOUND`."""

HASH: Final[int] = HYPHEN
"""``[#]`` boundary marker — same code as :data:`HYPHEN`."""

PLUS: Final[int] = PERIOD
"""``[+]`` boundary marker — re-uses the :data:`PERIOD` code (safe overlap)."""

EQUAL: Final[int] = COMMA
"""``[=]`` boundary marker — re-uses the :data:`COMMA` code (safe overlap)."""

NPHONE: Final[int] = PHO_SYM_TOT
"""Loop limit for phoneme-inventory walks (= :data:`PHO_SYM_TOT`)."""


__all__ = [
    "DASH",
    "EQUAL",
    "HASH",
    "NPHONE",
    "PLUS",
    "STAR",
]
