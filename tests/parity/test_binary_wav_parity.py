"""End-to-end WAV bit-parity test: ``dectalk.to_wav`` vs the shipped binary.

This is the goalpost test for the C-to-Python port. It must remain
green from Phase B (when the public API routes through the C library
via :mod:`dectalk._capi`) all the way through Phase F (when every
module is a faithful Python translation and the C library is no
longer needed at runtime).

Renders the same text corpus through both:

- ``dectalk.to_wav(text, path)`` — the public Python API
- ``say -a text -fo path`` — the shipped DECtalk binary

…and asserts the two output WAVs are byte-identical.

Skips cleanly when either the shipped binary or the locally-built C
library is missing.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

import dectalk

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _have_artefacts() -> bool:
    """True when both the source-built libtts and the shipped binary exist."""
    has_lib = any(_SRC_ROOT.glob("src/dtalkml/build/*/us/release/libtts.so")) and any(
        _SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so")
    )
    has_bin = (_BIN_ROOT / "say").is_file() and (_BIN_ROOT / "DECtalk.conf").is_file()
    return has_lib and has_bin


pytestmark = pytest.mark.skipif(
    not _have_artefacts(),
    reason="locally-built libtts or shipped DECtalk binary not present",
)


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


def _binary_wav(text: str, out: Path) -> bytes:
    """Render ``text`` via the shipped binary and return the WAV bytes."""
    subprocess.run(
        [str(_BIN_ROOT / "say"), "-a", text, "-fo", str(out)],
        cwd=str(_BIN_ROOT),
        check=True,
        capture_output=True,
    )
    return out.read_bytes()


@pytest.mark.parametrize("text", _CORPUS, ids=list(_CORPUS))
def test_dectalk_to_wav_matches_binary(text: str) -> None:
    """``dectalk.to_wav`` output is byte-identical to ``say -fo``."""
    with tempfile.TemporaryDirectory() as td:
        py_path = Path(td) / "py.wav"
        bin_path = Path(td) / "bin.wav"
        dectalk.to_wav(text, py_path)
        bin_bytes = _binary_wav(text, bin_path)
        py_bytes = py_path.read_bytes()
    assert py_bytes == bin_bytes, (
        f"WAV mismatch for {text!r}: dectalk={len(py_bytes)} B, binary={len(bin_bytes)} B"
    )
