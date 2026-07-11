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

# services.c lines 1023-1124: ``DBtable[100]`` maps a decoded 0..99 volume
# index to the dB gain offset the ``SOFTWARE_VOLUME`` build adds to the
# speaker-def voicing / frication / aspiration gains (``r1ca`` / ``afgain``
# / ``apgain``) in ``ph_vset.c`` lines 776-783 (each then floored at 0).
# Index 0 = -40 dB (near mute); indices >= 94 = 0 dB (unity). This is how
# ``[:volume set N]`` attenuates the ``say -fo`` WAV render: not a
# post-multiply of the output but a retune of the synth input gains, which
# is why the effect is non-linear across the spectrum (issue #331).
DB_TABLE: Final[tuple[int, ...]] = (
    -40, -34, -30, -28, -26, -24, -23, -22, -21, -20,
    -19, -18, -18, -17, -16, -16, -15, -15, -14, -14,
    -14, -13, -13, -12, -12, -12, -11, -11, -11, -10,
    -10, -10, -10, -9, -9, -9, -9, -8, -8, -8,
    -8, -8, -7, -7, -7, -7, -7, -6, -6, -6,
    -6, -6, -6, -5, -5, -5, -5, -5, -5, -4,
    -4, -4, -4, -4, -4, -4, -3, -3, -3, -3,
    -3, -3, -3, -3, -2, -2, -2, -2, -2, -2,
    -2, -2, -2, -2, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, 0, 0, 0, 0, 0, 0,
)  # fmt: skip


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


def software_volume_offset(volume: int) -> int:
    """Decibel gain offset (``pKsd_t->iSwVolume``) for ``[:volume set N]``.

    On the active Linux build ``SOFTWARE_VOLUME`` is defined, so
    ``[:volume set N]`` does **not** post-scale the output samples.
    Instead ``StereoVolumeControl`` (``services.c``) sets both stereo
    channels to ``EncodeDectalkVolume(N)``, averages them back to a 0..99
    index via ``DecodeDectalkVolume``, and looks the index up in
    :data:`DB_TABLE`; the resulting dB offset is added to three speaker-def
    chip gains at synth-def build time (``ph_vset.c`` lines 776-783). For a
    ``set`` (both channels to the same value) the L/R average collapses to
    ``DecodeDectalkVolume(EncodeDectalkVolume(N))``, which this reproduces.

    ``N`` is clamped to ``[0, MAX_VOLUME]`` by the encode step (values
    >= 100 saturate to unity, matching ``[:volume set 100]`` /
    ``set 140`` being no-ops). Empirically verified byte-exact against the
    shipped binary for ``set`` at ``0/10/25/40/50/60/75/90/100`` (issue
    #331).

    The ``up`` / ``down`` / ``lset`` / ``rset`` ops read-modify-write the
    device's *current* stereo volume, which is uninitialised for a fresh
    ``say`` handle — the shipped binary renders them **non-deterministically**
    (different WAV bytes every run), so they are intentionally not modelled.
    ``att`` / ``sset`` drive the hardware ``vol_att`` path, which the
    ``say -fo`` WAV render never applies (WAV no-ops).

    Args:
        volume: The ``[:volume set N]`` argument.

    Returns:
        The dB gain offset (<= 0) to add to the speaker chip gains.
    """
    idx = decode_dectalk_volume(encode_dectalk_volume(max(volume, 0)))
    return DB_TABLE[min(max(idx, 0), MAX_VOLUME)]


# Aliases under the original C-source names for inventory tests.
EncodeDectalkVolume = encode_dectalk_volume
DecodeDectalkVolume = decode_dectalk_volume

__all__ = [
    "DB_TABLE",
    "MAX_VOLUME",
    "VOLUME_TABLE",
    "DecodeDectalkVolume",
    "EncodeDectalkVolume",
    "decode_dectalk_volume",
    "encode_dectalk_volume",
    "software_volume_offset",
]
