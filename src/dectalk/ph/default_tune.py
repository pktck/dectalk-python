"""Default voice tuning tables from ph_vdefi.c.

Translated from ``src/dapi/src/ph/ph_vdefi.c`` lines 122-167.

:data:`default_tune` is the all-zero ``SPDEF``-sized vector the
PH module uses as the *neutral* starting point for voice tuning
before any per-voice ``us_*_tune`` overlay is applied. Every entry
is zero — picking it leaves every voice-definition slot at the
voice's ROM-table default.

:data:`fr_default_tune` is the French variant. It's identical to
``default_tune`` on the Linux build (all-zero) — the file declares
it conditionally under ``EPSON_ARM7``. Exposed for parity.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import SPDEF

default_tune: Final[tuple[int, ...]] = (0,) * SPDEF
"""``SPDEF``-entry (39) all-zero voice-tune default."""

fr_default_tune: Final[tuple[int, ...]] = (0,) * SPDEF
"""French variant — identical to :data:`default_tune` on Linux."""


__all__ = ["default_tune", "fr_default_tune"]
