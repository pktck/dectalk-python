"""Linux/OSF volume codec from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 903-1018.

The kernel converts user-supplied volume values in the 0..99 range
(``MAX_VOLUME = 99``) into the 16-bit DAC settings the synthesiser
expects. The Linux/OSF build uses the table at lines 906-928 of
``services.c``; the Windows build uses a different curve and is
not used by ``libtts_us.so`` on Linux, so it isn't ported here.

- :func:`encode_dectalk_volume` clamps the input to ``[0, MAX_VOLUME]``
  and looks up the corresponding DAC code.
- :func:`decode_dectalk_volume` runs the inverse: a binary search
  matching the C source's ``DecodeDectalkVolume`` algorithm to find
  the lowest table index whose encoded value is ``>=`` the input.
"""

from __future__ import annotations

from typing import Final

MAX_VOLUME: Final[int] = 99

VOLUME_TABLE: Final[tuple[int, ...]] = (
    0,
    32768,
    32768,
    32768,
    33792,
    33792,
    33792,
    34816,
    34816,
    34816,
    35840,
    35840,
    35840,
    36864,
    36864,
    36864,
    37888,
    37888,
    37888,
    38912,
    38912,
    38912,
    39936,
    39936,
    39936,
    39936,
    40960,
    40960,
    40960,
    41984,
    41984,
    41984,
    43008,
    43008,
    43008,
    44032,
    44032,
    44032,
    45056,
    45056,
    45056,
    46080,
    46080,
    46080,
    47104,
    47104,
    47104,
    48128,
    48128,
    48128,
    48128,
    49152,
    49152,
    49152,
    50176,
    50176,
    50176,
    51200,
    51200,
    51200,
    52224,
    52224,
    52224,
    53248,
    53248,
    53248,
    54272,
    54272,
    54272,
    55296,
    55296,
    55296,
    55296,
    56320,
    56320,
    56320,
    57344,
    57344,
    57344,
    58368,
    58368,
    58368,
    59392,
    59392,
    59392,
    60416,
    60416,
    60416,
    61440,
    61440,
    61440,
    62464,
    62464,
    62464,
    63488,
    63488,
    63488,
    63488,
    64512,
    64512,
)


def encode_dectalk_volume(volume: int) -> int:
    """Map a 0..99 volume to its 16-bit DAC code.

    Faithful translation of:

    .. code-block:: c

        DWORD EncodeDectalkVolume(DWORD dwVolume) {
            if (dwVolume > MAX_VOLUME) dwVolume = MAX_VOLUME;
            return dwVolumeTable[dwVolume];
        }

    Args:
        volume: User-facing volume in ``0..MAX_VOLUME``. Values above
            ``MAX_VOLUME`` are clamped.

    Returns:
        The DAC code from :data:`VOLUME_TABLE`.
    """
    volume = min(volume, MAX_VOLUME)
    return VOLUME_TABLE[volume]


def decode_dectalk_volume(volume: int) -> int:
    """Map a 16-bit DAC code back to the closest 0..99 volume.

    Faithful translation of:

    .. code-block:: c

        DWORD DecodeDectalkVolume(DWORD dwVolume) {
            DWORD dwLow, dwMid, dwHigh;
            if (dwVolume > 65535) {
                dwMid = MAX_VOLUME;
            } else {
                dwLow = 0;
                dwHigh = MAX_VOLUME;
                while (dwLow <= dwHigh) {
                    dwMid = (dwLow + dwHigh) >> 1;
                    if (dwVolume < EncodeDectalkVolume(dwMid))
                        dwHigh = dwMid - 1;
                    else if (dwVolume > EncodeDectalkVolume(dwMid))
                        dwLow = dwMid + 1;
                    else
                        break;
                }
            }
            return dwMid;
        }

    Args:
        volume: 16-bit DAC code in ``0..65535``. Values above 65535
            are mapped to ``MAX_VOLUME``.

    Returns:
        The closest 0..MAX_VOLUME index whose encoded value is
        ``>= volume`` (matching the C binary search's final ``dwMid``).
    """
    if volume > 65535:  # noqa: PLR2004 — explicit C constant.
        return MAX_VOLUME

    low = 0
    high = MAX_VOLUME
    mid = 0
    while low <= high:
        mid = (low + high) >> 1
        encoded = encode_dectalk_volume(mid)
        if volume < encoded:
            high = mid - 1
        elif volume > encoded:
            low = mid + 1
        else:
            break
    return mid


__all__ = [
    "MAX_VOLUME",
    "VOLUME_TABLE",
    "decode_dectalk_volume",
    "encode_dectalk_volume",
]
