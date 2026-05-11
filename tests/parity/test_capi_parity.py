"""Parity tests for the :mod:`dectalk._capi` ctypes wrapper.

Asserts that calling ``CAPI.speak`` produces WAV bytes byte-identical to
running the shipped ``say`` binary with the same text. This validates
that the C library we load and the C binary the user ships were built
from the same source — without that, every downstream parity test is
chasing a moving target.

Skips cleanly when either the source-built C library or the shipped
binary is missing.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from dectalk._capi import CAPI

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _have_artefacts() -> bool:
    """True if both the source-built libtts.so and the shipped binary exist."""
    has_lib = any(_SRC_ROOT.glob("src/dtalkml/build/*/us/release/libtts.so")) and any(
        _SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so")
    )
    has_bin = (_BIN_ROOT / "say").is_file() and (_BIN_ROOT / "DECtalk.conf").is_file()
    return has_lib and has_bin


pytestmark = pytest.mark.skipif(
    not _have_artefacts(),
    reason="locally-built libtts or shipped DECtalk binary not present",
)


def _binary_wav(text: str) -> bytes:
    """Render `text` via the shipped binary and return the WAV bytes."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        out_path = Path(fh.name)
    try:
        subprocess.run(
            [str(_BIN_ROOT / "say"), "-a", text, "-fo", str(out_path)],
            cwd=str(_BIN_ROOT),
            check=True,
            capture_output=True,
        )
        return out_path.read_bytes()
    finally:
        out_path.unlink(missing_ok=True)


_CORPUS: tuple[str, ...] = (
    "hello world",
    "the quick brown fox",
    "she sells sea shells",
    "one two three four five",
    "supercalifragilisticexpialidocious",
    "[:rate 250] testing one two three",
    "DECtalk version 6.2.0",
    "this is a test, with a comma, and a period.",
)


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI instance — Startup/Shutdown happens per ``speak`` call."""
    return CAPI(src_root=_SRC_ROOT, data_root=_BIN_ROOT)


@pytest.mark.parametrize("text", _CORPUS, ids=list(_CORPUS))
def test_capi_matches_binary(text: str, capi: CAPI) -> None:
    """``CAPI.speak`` must produce bytes identical to ``say`` for each prompt."""
    capi_wav = capi.speak(text)
    bin_wav = _binary_wav(text)
    assert capi_wav == bin_wav, (
        f"WAV mismatch for {text!r}: capi={len(capi_wav)} B, binary={len(bin_wav)} B"
    )
