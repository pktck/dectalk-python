"""Audio-file header structs from tts.h.

Translated from ``src/dapi/src/api/tts.h``. Two file-header
dataclasses used by the C TTS engine's wave / au file writers:

- :class:`WaveFileHdr` — Microsoft RIFF/WAVE header (12 fields,
  44-byte fixed layout via ``RIFF_HEADER_OFFSET`` + 8 magic bytes).
- :class:`AuFileHdr` — Sun/NeXT AU header (7 fields).

These are pure data records. The Python port's ``dectalk.nt``
audio I/O uses the stdlib :mod:`wave` module rather than packing
these structs directly; the dataclasses are present here for
symbol parity with the C API.

Field names match the C struct exactly (Hungarian notation like
``dwRiffChunkSize`` / ``psWaveFmt``) so per-attribute access
mirrors the C source one-for-one.
"""

# ruff: noqa: N815

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class WaveFileHdr:
    """Microsoft WAVE file header (matches C ``WAVE_FILE_HDR_T``).

    Faithful translation of:

    .. code-block:: c

        typedef struct WAVE_FILE_HDR_TAG {
            char  psRiff[4];                /* "RIFF"                 */
            DWORD dwRiffChunkSize;
            char  psWaveFmt[8];             /* "WAVEfmt "             */
            DWORD dwWaveChunkSize;
            WORD  wFormatTag;               /* 1 = PCM                */
            WORD  wNumberOfChannels;
            DWORD dwSamplesPerSecond;       /* e.g. 11025             */
            DWORD dwAvgBytesPerSecond;
            WORD  wNumberBlockAlign;
            WORD  wBitsPerSample;           /* 8 or 16                */
            char  psData[4];                /* "data"                 */
            DWORD dwDataChunkSize;
        } WAVE_FILE_HDR_T;

    Default values produce a valid 11025 Hz mono 16-bit PCM header
    (DECtalk's native output rate) with zero-length data chunk.
    """

    psRiff: bytes = b"RIFF"
    dwRiffChunkSize: int = 0
    psWaveFmt: bytes = b"WAVEfmt "
    dwWaveChunkSize: int = 16
    wFormatTag: int = 1
    wNumberOfChannels: int = 1
    dwSamplesPerSecond: int = 11025
    dwAvgBytesPerSecond: int = 22050
    wNumberBlockAlign: int = 2
    wBitsPerSample: int = 16
    psData: bytes = b"data"
    dwDataChunkSize: int = 0


@dataclass(slots=True)
class AuFileHdr:
    """Sun/NeXT AU file header (matches C ``AU_FILE_HDR_T``).

    Faithful translation of:

    .. code-block:: c

        typedef struct AU_FILE_HDR_TAG {
            char  magic[4];           /* ".snd"               */
            DWORD hdr_size;
            DWORD data_size;
            DWORD encoding;           /* 1 = µ-law, 3 = 16-bit linear */
            DWORD sample_rate;
            DWORD channels;
            char  comment[8];
        } AU_FILE_HDR_T;

    Default values produce a valid 8 kHz mono µ-law AU header
    (the DECtalk default for MULAW output).
    """

    magic: bytes = b".snd"
    hdr_size: int = 32
    data_size: int = 0
    encoding: int = 1
    sample_rate: int = 8000
    channels: int = 1
    comment: bytes = field(default_factory=lambda: b"\x00" * 8)


__all__ = [
    "AuFileHdr",
    "WaveFileHdr",
]
