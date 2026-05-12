"""HLSyn ``Speakers`` enum from hlsynapi.h.

Translated from ``src/dapi/src/ph/hlsynapi.h``. The HLSyn API uses
its own ordering of the 10 canonical voice slots — almost identical
to the master ``Voice`` enum from ``dectalk.h``, but with **Wendy**
at slot 8 instead of "Whispery Willy". The two names refer to the
same female voice; DECtalk renamed the speaker between versions.
The HLSynthesizer-side functions
(``InitializeHLSynthesizer`` / ``HLSynthesizeLLFrame`` /
``changeSpeakerValues``) all take this enum, so its values must
match the C source byte-for-byte.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final


class Speakers(IntEnum):
    """The 10 HLSyn voice slots — ``hlsynapi.h`` ``currentSpeaker`` enum.

    Each value is the int passed to ``HLSyn`` API entry points
    (``InitializeHLSynthesizer(... IsMale)`` keys on these names'
    male/female grouping). Slot 8 is ``Wendy`` in the HLSyn API
    even though the public DECtalk API at the same index is named
    ``WHISPERY_WILLY``; they're the same speaker.
    """

    Paul = 0
    Betty = 1
    Harry = 2
    Frank = 3
    Dennis = 4
    Kit = 5
    Ursula = 6
    Rita = 7
    Wendy = 8
    Chris = 9


NUMSPEAKERS: Final[int] = 10
"""Total number of HLSyn voice slots (``NUMSPEAKERS`` in hlsynapi.h)."""


__all__ = [
    "NUMSPEAKERS",
    "Speakers",
]
