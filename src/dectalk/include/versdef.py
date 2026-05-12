"""DECtalk version-string fragments from versdef.h.

Translated from ``src/dapi/src/include/versdef.h``. Four
short string fragments concatenated by the version-reporting
code to form the user-visible "DECtalk 4.4A" string.

These match the values shipped with the develop-branch source
(4.4A); the actual shipped binary reports ``6.2.0-1015-azure``
from a different build pipeline.
"""

from __future__ import annotations

from typing import Final

REVMAJOR: Final[str] = "4"
"""Major revision number string."""

REVMINOR: Final[str] = "4"
"""Minor revision number string."""

REVTYPE: Final[str] = "A"
"""Revision type letter (A=Alpha, B=Beta, R=Release)."""

REVNO: Final[str] = "A"
"""Revision sub-number (matches :data:`REVTYPE` in this build)."""


__all__ = [
    "REVMAJOR",
    "REVMINOR",
    "REVNO",
    "REVTYPE",
]
