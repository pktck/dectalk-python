"""Verify ``check_uncertain_phones`` matches cm_phon.c.

Re-parses the C ``uncertain_phones[][2]`` table and replays the
``check_uncertain_phones`` algorithm to confirm parity.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd import uncertain_phones as up

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/cmd/cm_phon.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_uncertain_phones() -> tuple[tuple[int, int], ...]:
    """Parse the C ``uncertain_phones[][2]`` initialiser."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"char\s+uncertain_phones\[\]\[2\]\s*=\s*\{(.+?)\};",
        text,
        re.DOTALL,
    )
    assert m is not None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    out: list[tuple[int, int]] = []
    for rec in re.finditer(r"\{\s*'(\\?.|.)'\s*,\s*'(\\?.|.)'\s*\}", body):
        out.append((ord(rec.group(1)), ord(rec.group(2))))
    return tuple(out)


def test_uncertain_phones_matches_c() -> None:
    """The 4 digraphs match the C source list."""
    assert up.uncertain_phones == _parse_uncertain_phones()


def test_uncertain_phones_count() -> None:
    """C source has 4 ambiguous digraphs."""
    expected_count = 4
    assert len(up.uncertain_phones) == expected_count


@pytest.mark.parametrize(
    ("ph1", "ph2"),
    [
        (ord("r"), ord("x")),
        (ord("r"), ord("e")),
        (ord("l"), ord("l")),
        (ord("l"), ord("y")),
    ],
)
def test_known_pair_returns_true(ph1: int, ph2: int) -> None:
    """Each listed pair is reported uncertain."""
    assert up.check_uncertain_phones(ph1, ph2) is True


def test_case_folding_uppercase_pair() -> None:
    """Uppercase pair RX folds to rx and matches."""
    assert up.check_uncertain_phones(ord("R"), ord("X")) is True


def test_case_folding_mixed_case() -> None:
    """Mixed-case Rx and rX both match."""
    assert up.check_uncertain_phones(ord("R"), ord("x")) is True
    assert up.check_uncertain_phones(ord("r"), ord("X")) is True


def test_non_uncertain_pair_returns_false() -> None:
    """A pair not in the list (e.g. 'k', 'a') returns False."""
    assert up.check_uncertain_phones(ord("k"), ord("a")) is False


def test_reversed_pair_returns_false() -> None:
    """Order matters — `xr` is not uncertain even though `rx` is."""
    assert up.check_uncertain_phones(ord("x"), ord("r")) is False


def test_high_byte_input_unchanged() -> None:
    """Bytes outside A..Z aren't folded — non-ASCII pair stays as-is."""
    high = 0xC0  # À, not a phoneme byte
    assert up.check_uncertain_phones(high, ord("x")) is False
