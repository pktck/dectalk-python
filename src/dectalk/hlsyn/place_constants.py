"""HLSyn place-of-articulation constants from hlsyn.h.

Translated from ``src/dapi/src/hlsyn/hlsyn.h`` lines 173-176
and ``src/dapi/src/hlsyn/acxf1c.c`` line 32.

The ``loc`` field on :class:`~dectalk.ph.hlsyn_structs.HLState`
encodes the dominant constriction location:

- :data:`LIPS` (1)   — lip constriction.
- :data:`BLADE` (2)  — alveolar / tongue-blade constriction.
- :data:`DORSUM` (3) — dorsal (back-tongue) constriction.
- :data:`LIQUID` (4) — palato-alveolar (liquid) constriction.

``UNCOMPUTABLE`` is the sentinel returned by helpers that cannot
compute a meaningful area (e.g. ``HelmholtzConstriction``).
"""

from __future__ import annotations

from typing import Final

LIPS: Final[int] = 1
BLADE: Final[int] = 2
DORSUM: Final[int] = 3
LIQUID: Final[int] = 4

UNCOMPUTABLE: Final[float] = -1.0


__all__ = ["BLADE", "DORSUM", "LIPS", "LIQUID", "UNCOMPUTABLE"]
