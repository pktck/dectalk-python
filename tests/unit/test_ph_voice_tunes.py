"""Verify the voice-tuning offset tables match p_us_vdf_tuneint.c.

Re-parses every ``const short us_<voice>_tune[]`` array from the
autotuner-generated C source and asserts the Python literal matches
byte-for-byte.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import voice_tunes as vt

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/ph/p_us_vdf_tuneint.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_TUNE_NAMES: tuple[str, ...] = (
    "us_paul_8_tune", "us_betty_8_tune", "us_harry_8_tune", "us_frank_8_tune",
    "us_kit_8_tune", "us_ursula_8_tune", "us_rita_8_tune", "us_wendy_8_tune",
    "us_dennis_8_tune",
    "us_paul_tune", "us_betty_tune", "us_harry_tune", "us_frank_tune",
    "us_kit_tune", "us_ursula_tune", "us_rita_tune", "us_wendy_tune",
    "us_dennis_tune",
    "us_val_tune",
)  # fmt: skip


def _parse_tune(name: str) -> tuple[int, ...]:
    """Parse one ``const short us_*_tune[]`` initialiser, stripping #ifdef MSDOS."""
    text = _C_FILE.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    pat = rf"const\s+short\s+{re.escape(name)}\s*\[\]\s*=\s*\{{(.+?)\}};"
    m = re.search(pat, text, re.DOTALL)
    assert m is not None, f"missing {name}"
    body = m.group(1)
    out: list[int] = []
    skip_depth = 0
    in_ifndef_msdos = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#ifndef MSDOS"):
            in_ifndef_msdos = True
            continue
        if stripped.startswith("#ifdef MSDOS") or (
            stripped.startswith("#if") and "MSDOS" in stripped and "ndef" not in stripped
        ):
            skip_depth += 1
            continue
        if stripped.startswith("#else") and in_ifndef_msdos and skip_depth == 0:
            skip_depth += 1
            in_ifndef_msdos = False
            continue
        if stripped.startswith("#endif"):
            if skip_depth > 0:
                skip_depth -= 1
            elif in_ifndef_msdos:
                in_ifndef_msdos = False
            continue
        if skip_depth > 0:
            continue
        if stripped.startswith("#"):
            continue
        for tok in line.split(","):
            t = tok.strip()
            if re.fullmatch(r"-?\d+", t):
                out.append(int(t))
    return tuple(out)


@pytest.mark.parametrize("name", _TUNE_NAMES)
def test_tune_matches_c_source(name: str) -> None:
    """Each tune array matches the C source initialiser exactly."""
    expected = _parse_tune(name)
    assert getattr(vt, name) == expected


def test_tune_count() -> None:
    """All 19 tune arrays are exposed (9 legacy + 9 modern + val)."""
    expected_count = 19
    assert len(_TUNE_NAMES) == expected_count
    for name in _TUNE_NAMES:
        assert hasattr(vt, name)


def test_tune_arrays_have_40_entries() -> None:
    """Each tune array has 40 entries (matching SPDEF + 1 fp_vtm trailing zero)."""
    expected = 40
    for name in _TUNE_NAMES:
        assert len(getattr(vt, name)) == expected, name
