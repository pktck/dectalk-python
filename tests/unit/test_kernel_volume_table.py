"""Verify volume codec matches kernel/services.c."""

from __future__ import annotations

import os
import re
from itertools import pairwise
from pathlib import Path

import pytest

from dectalk.kernel.volume_table import (
    DB_TABLE,
    MAX_VOLUME,
    VOLUME_TABLE,
    decode_dectalk_volume,
    encode_dectalk_volume,
    software_volume_offset,
)

_C_SRC_ENV = "DECTALK_SRC"
_C_TABLE_RE = re.compile(
    r"static\s+int\s+dwVolumeTable\[MAX_VOLUME\+1\]\s*=\s*\{([^}]*)\}",
    re.DOTALL,
)


def _c_source_path() -> Path | None:
    """Locate ``services.c`` on the local checkout, if present."""
    root = os.environ.get(_C_SRC_ENV)
    candidate = Path("/tmp/dectalk-src") if root is None else Path(root)
    path = candidate / "src/dapi/src/kernel/services.c"
    return path if path.is_file() else None


def _parse_linux_volume_table(text: str) -> tuple[int, ...]:
    """Extract the Linux/OSF ``dwVolumeTable`` from services.c.

    The C source has two ``static int dwVolumeTable[]`` definitions
    guarded by ``#if`` blocks. We want the one under
    ``defined (__linux__)`` (the first match in file order).
    """
    match = _C_TABLE_RE.search(text)
    if match is None:
        msg = "Could not find dwVolumeTable in services.c"
        raise AssertionError(msg)
    body = match.group(1)
    return tuple(int(n) for n in re.findall(r"-?\d+", body))


def test_volume_table_matches_c_source() -> None:
    """The Python ``VOLUME_TABLE`` matches the C-source table verbatim."""
    src = _c_source_path()
    if src is None:
        pytest.skip("DECTALK_SRC not available; cannot reparse services.c")
    parsed = _parse_linux_volume_table(src.read_text(encoding="latin-1"))
    assert parsed == VOLUME_TABLE


def test_table_length_is_max_volume_plus_one() -> None:
    """The table has ``MAX_VOLUME + 1`` entries (one per index)."""
    assert len(VOLUME_TABLE) == MAX_VOLUME + 1


def test_encode_clamps_above_max() -> None:
    """Encoding above MAX_VOLUME returns the last table entry."""
    assert encode_dectalk_volume(MAX_VOLUME + 1) == VOLUME_TABLE[MAX_VOLUME]
    assert encode_dectalk_volume(9999) == VOLUME_TABLE[MAX_VOLUME]


def test_encode_zero_is_zero() -> None:
    """Volume 0 always encodes to 0 (silence)."""
    assert encode_dectalk_volume(0) == 0


def test_encode_max_is_64512() -> None:
    """Volume 99 encodes to 64512 in the Linux table."""
    assert encode_dectalk_volume(MAX_VOLUME) == 64512


def test_decode_round_trip_lands_on_matching_index() -> None:
    """``decode(encode(v))`` lands on *some* index with the same value.

    Many table entries are duplicated, so the C binary search can
    converge on any of them depending on the search path. The Python
    port runs the identical binary search; this test just asserts
    the result reproduces the encoded value.
    """
    for v in (0, 1, 2, 25, 50, 75, 99):
        encoded = encode_dectalk_volume(v)
        decoded = decode_dectalk_volume(encoded)
        assert VOLUME_TABLE[decoded] == encoded


def test_decode_above_65535_returns_max() -> None:
    """Inputs above 65535 short-circuit to MAX_VOLUME."""
    assert decode_dectalk_volume(65536) == MAX_VOLUME
    assert decode_dectalk_volume(1_000_000) == MAX_VOLUME


def test_decode_zero_returns_zero() -> None:
    """A DAC code of 0 decodes to volume 0."""
    assert decode_dectalk_volume(0) == 0


def test_table_monotonic_non_decreasing() -> None:
    """The table is non-decreasing across all indices."""
    for prev, cur in pairwise(VOLUME_TABLE):
        assert cur >= prev


def test_db_table_shape() -> None:
    """DBtable is the 100-entry services.c dB-offset curve (issue #331)."""
    assert len(DB_TABLE) == 100
    assert DB_TABLE[0] == -40
    assert DB_TABLE[49] == -6
    assert DB_TABLE[94] == 0  # unity from index 94 on
    assert DB_TABLE[99] == 0
    # Monotonic non-decreasing (louder index => less attenuation), all <= 0.
    for prev, cur in pairwise(DB_TABLE):
        assert prev <= cur <= 0


def test_software_volume_offset_known_values() -> None:
    """``[:volume set N]`` dB offsets match the values verified byte-exact.

    Anchors from the issue #331 oracle probe: ``set 0`` -> -40 dB,
    ``set 50`` -> -6 dB, ``set 100`` (and any N >= 100) -> 0 dB (unity).
    """
    assert software_volume_offset(0) == -40
    assert software_volume_offset(25) == -12
    assert software_volume_offset(50) == -6
    assert software_volume_offset(75) == -2
    assert software_volume_offset(90) == -1
    assert software_volume_offset(100) == 0
    # N >= 100 saturates to unity (Encode clamps to MAX_VOLUME).
    assert software_volume_offset(140) == 0
    assert software_volume_offset(1000) == 0
    # Never amplifies.
    for n in range(0, 200):
        assert software_volume_offset(n) <= 0
