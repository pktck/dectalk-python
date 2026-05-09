"""Convert numbers to spelled-out English words.

The bundled lexicon has individual digit names (zero..nine) and the
group names (ten, twenty, …, hundred, thousand, million). This module
combines them so a token like ``"2024"`` becomes ``"TWO THOUSAND TWENTY
FOUR"`` rather than digit-by-digit ``"TWO ZERO TWO FOUR"``.

Supports unsigned integers up to ``10**12 - 1``; that's enough for the
common cases (years, prices, quantities). Larger numbers fall back to
digit-by-digit reading.
"""

from __future__ import annotations

from typing import Final

# Digit names for the units position 0 to 9.
_UNITS: Final[tuple[str, ...]] = (
    "ZERO", "ONE", "TWO", "THREE", "FOUR",
    "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
)  # fmt: skip

# Special names for 10 to 19.
_TEENS: Final[tuple[str, ...]] = (
    "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN",
    "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN",
)  # fmt: skip

# Tens-place names for 20, 30, ..., 90.
_TENS: Final[tuple[str, ...]] = (
    "", "", "TWENTY", "THIRTY", "FORTY",
    "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY",
)  # fmt: skip

_SCALE_HUNDRED: Final[int] = 100
_SCALE_THOUSAND: Final[int] = 1_000
_SCALE_MILLION: Final[int] = 1_000_000
_SCALE_BILLION: Final[int] = 1_000_000_000
_MAX_SUPPORTED: Final[int] = 1_000_000_000_000  # 10**12


def number_to_words(value: int) -> list[str]:
    """Convert a non-negative integer to spelled-out word tokens.

    Args:
        value: Non-negative integer. Negative inputs raise ``ValueError``.

    Returns:
        Upper-case word list (e.g. ``["TWO", "THOUSAND", "TWENTY", "FOUR"]``).

    Raises:
        ValueError: If ``value`` is negative.
    """
    if value < 0:
        raise ValueError(f"number_to_words requires a non-negative int, got {value}")
    if value >= _MAX_SUPPORTED:
        # Beyond a trillion, fall back to digit-by-digit. The bundled lexicon
        # doesn't have BILLION/TRILLION group names yet.
        return [_UNITS[int(d)] for d in str(value)]
    if value == 0:
        return ["ZERO"]

    out: list[str] = []
    if value >= _SCALE_BILLION:
        out.extend(number_to_words(value // _SCALE_BILLION))
        # No BILLION word in the bundled lexicon yet; spell it.
        out.extend(["B", "IH1", "L", "Y", "AH0", "N"])  # phonemic fallback
        value %= _SCALE_BILLION
    if value >= _SCALE_MILLION:
        out.extend(number_to_words(value // _SCALE_MILLION))
        out.append("MILLION")
        value %= _SCALE_MILLION
    if value >= _SCALE_THOUSAND:
        out.extend(number_to_words(value // _SCALE_THOUSAND))
        out.append("THOUSAND")
        value %= _SCALE_THOUSAND
    if value >= _SCALE_HUNDRED:
        out.append(_UNITS[value // _SCALE_HUNDRED])
        out.append("HUNDRED")
        value %= _SCALE_HUNDRED

    if value >= 20:  # noqa: PLR2004 - 20 is a clear linguistic boundary
        out.append(_TENS[value // 10])
        if value % 10:
            out.append(_UNITS[value % 10])
    elif value >= 10:  # noqa: PLR2004 - 10..19 are the teens block
        out.append(_TEENS[value - 10])
    elif value > 0:
        out.append(_UNITS[value])

    return out
