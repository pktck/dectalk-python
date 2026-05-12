"""ISO Latin-1 case-folding tables for the kernel character-typer.

Translated from ``src/dapi/src/kernel/iso_char.c``. The kernel builds
two 256-entry byte tables at startup, ``iso_to_upper`` and
``iso_to_lower``, that fold any input byte to its case-equivalent.
ASCII A..Z ↔ a..z, plus 30 Latin-1 accented letters (À ↔ à, etc.).

The C source builds these tables at runtime via ``iso_case_map()``;
the Python port precomputes them once at import time using the same
``case_table`` data, then exposes them as immutable tuples.

Two faithful bugs from the C source are preserved:

- The Ñ entry is ``(C_TL_N, C_TL_N)`` — i.e. Ñ → Ñ (a no-op fold)
  rather than ``(C_TL_N, C_TL_n)`` mapping to ñ. Almost certainly a
  C-source typo, but matching it byte-for-byte is required for parity.
- The Þ (thorn) entry is ``(C_THORN, C_THORN)`` — same issue.

Without these, the binary's case-folding output would differ on Latin-1
input bytes 0xD1 (Ñ) and 0xDE (Þ).
"""

from __future__ import annotations

from typing import Final

# ``case_table`` from iso_char.c: 56 (upper, lower) pairs.
_CASE_PAIRS: Final[tuple[tuple[int, int], ...]] = (
    (0x41, 0x61),  # A / a
    (0x42, 0x62),  # B / b
    (0x43, 0x63),  # C / c
    (0x44, 0x64),  # D / d
    (0x45, 0x65),  # E / e
    (0x46, 0x66),  # F / f
    (0x47, 0x67),  # G / g
    (0x48, 0x68),  # H / h
    (0x49, 0x69),  # I / i
    (0x4A, 0x6A),  # J / j
    (0x4B, 0x6B),  # K / k
    (0x4C, 0x6C),  # L / l
    (0x4D, 0x6D),  # M / m
    (0x4E, 0x6E),  # N / n
    (0x4F, 0x6F),  # O / o
    (0x50, 0x70),  # P / p
    (0x51, 0x71),  # Q / q
    (0x52, 0x72),  # R / r
    (0x53, 0x73),  # S / s
    (0x54, 0x74),  # T / t
    (0x55, 0x75),  # U / u
    (0x56, 0x76),  # V / v
    (0x57, 0x77),  # W / w
    (0x58, 0x78),  # X / x
    (0x59, 0x79),  # Y / y
    (0x5A, 0x7A),  # Z / z
    # Latin-1 accented letters.
    (0xC0, 0xE0),  # À / à
    (0xC1, 0xE1),  # Á / á
    (0xC2, 0xE2),  # Â / â
    (0xC3, 0xE3),  # Ã / ã
    (0xC4, 0xE4),  # Ä / ä
    (0xC5, 0xE5),  # Å / å
    (0xC6, 0xE6),  # Æ / æ
    (0xC7, 0xE7),  # Ç / ç
    (0xC8, 0xE8),  # È / è
    (0xC9, 0xE9),  # É / é
    (0xCA, 0xEA),  # Ê / ê
    (0xCB, 0xEB),  # Ë / ë
    (0xCC, 0xEC),  # Ì / ì
    (0xCD, 0xED),  # Í / í
    (0xCE, 0xEE),  # Î / î
    (0xCF, 0xEF),  # Ï / ï
    (0xD0, 0xF0),  # Ð / ð (eth)
    (0xD1, 0xD1),  # Ñ / Ñ — preserved bug from C source (should be 0xF1)
    (0xD2, 0xF2),  # Ò / ò
    (0xD3, 0xF3),  # Ó / ó
    (0xD4, 0xF4),  # Ô / ô
    (0xD5, 0xF5),  # Õ / õ
    (0xD6, 0xF6),  # Ö / ö
    (0xD9, 0xF9),  # Ù / ù
    (0xDA, 0xFA),  # Ú / ú
    (0xDB, 0xFB),  # Û / û
    (0xDC, 0xFC),  # Ü / ü
    (0xDE, 0xDE),  # Þ / Þ — preserved bug from C source (should be 0xFE)
)


def _build_tables() -> tuple[bytes, bytes]:
    """Run ``iso_case_map()`` — identity initialise + per-pair overwrite."""
    upper = bytearray(range(256))
    lower = bytearray(range(256))
    for upper_byte, lower_byte in _CASE_PAIRS:
        lower[upper_byte] = lower_byte
        upper[lower_byte] = upper_byte
    return bytes(upper), bytes(lower)


_upper, _lower = _build_tables()
iso_to_upper: Final[bytes] = _upper
iso_to_lower: Final[bytes] = _lower


__all__ = ["iso_to_lower", "iso_to_upper"]
