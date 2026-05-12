"""Verify ``sonequivindex`` matches ph_setar.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph.sonor_tables import sonequivindex

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_setar.c")


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_sonequivindex_matches_c_source() -> None:
    """The 6 entries match the C ``static char sonequivindex[]`` block."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"static\s+char\s+sonequivindex\s*\[\s*\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    values = [int(v) for v in re.findall(r"-?\d+", body)]
    assert len(values) == 6
    assert tuple(values) == sonequivindex


def test_sonequivindex_size() -> None:
    """6-entry table covering the C-source sonorant classes."""
    assert len(sonequivindex) == 6


def test_sonequivindex_groups() -> None:
    """Three group values: 0 (unused / obstruent / back-unrounded),
    2 (front vowel), 4 (back rounded / rounded sonorant cons).
    """
    assert sonequivindex[0] == 0  # Unused
    assert sonequivindex[1] == 2  # Front vowel
    assert sonequivindex[2] == 0  # Back unrounded
    assert sonequivindex[3] == 4  # Back rounded
    assert sonequivindex[4] == 0  # Obstruent
    assert sonequivindex[5] == 4  # Rounded sonorant cons
