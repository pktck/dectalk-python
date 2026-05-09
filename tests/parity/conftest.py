"""Shared fixtures for the parity test suite.

The parity tests build a tiny C harness (`c_harness/llsyn_dump.c`) around
the FONIX `LLSynthesize()` and run it side-by-side with our Python
:func:`dectalk.hlsyn.synthesize.ll_synthesize`. They depend on:

- a working ``gcc`` (or any C compiler exposed as ``CC`` in the env), and
- the C source tree shipped under ``tests/parity/c_harness/``.

Tests skip cleanly when those preconditions aren't met so the suite still
runs in environments without a compiler.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

C_HARNESS_DIR: Path = Path(__file__).parent / "c_harness"
HARNESS_BINARY: Path = C_HARNESS_DIR / "llsyn_dump"
HARNESS_SOURCES: list[Path] = [
    C_HARNESS_DIR / name for name in ("llsyn_dump.c", "reson.c", "voice.c", "sample.c", "frame.c")
]


def _which_cc() -> str | None:
    return os.environ.get("CC") or shutil.which("gcc") or shutil.which("cc")


@pytest.fixture(scope="session")
def llsyn_dump() -> Path:
    """Build the C parity harness if gcc is available; skip otherwise."""
    cc = _which_cc()
    if cc is None:
        pytest.skip("no C compiler available; skipping LLSynthesize parity tests")
    if HARNESS_BINARY.exists():
        return HARNESS_BINARY

    cmd = [cc, "-O2", "-o", str(HARNESS_BINARY), *(str(p) for p in HARNESS_SOURCES), "-lm"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        pytest.skip(f"could not build C harness: {result.stderr}")
    return HARNESS_BINARY
