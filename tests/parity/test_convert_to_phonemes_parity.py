"""Smoke + determinism tests for ``CAPI.convert_to_phonemes``.

Phase A.4 of the C-to-Python port. ``TextToSpeechConvertToPhonemes`` is
the C library's phoneme-stream oracle; the per-module parity tests for
KERNEL/CMD/LTS/dic (Phases C-D) will use it as the ground truth. This
file just exercises the wrapper itself: it must run without error,
return something sane, and be deterministic across repeated calls.

Skips when the locally-built C library is absent OR the
``0001-expose-convert-to-phonemes-on-linux.patch`` C-source patch
has not been applied (the symbol's still WIN32-only without it).
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

import pytest

from dectalk._capi import CAPI

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))


def _have_artefacts() -> bool:
    return any(_SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))


def _convert_to_phonemes_exported() -> bool:
    """True iff libtts_us.so exports ``TextToSpeechConvertToPhonemes``."""
    candidates = sorted(_SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    if not candidates:
        return False
    try:
        lib = ctypes.CDLL(str(candidates[-1]))
        getattr(lib, "TextToSpeechConvertToPhonemes")  # noqa: B009
    except (OSError, AttributeError):
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _have_artefacts() or not _convert_to_phonemes_exported(),
    reason=(
        "libtts_us.so or TextToSpeechConvertToPhonemes missing — "
        "run `uv run python scripts/apply_c_patches.py`"
    ),
)


_CORPUS: tuple[str, ...] = (
    "hello world",
    "the quick brown fox",
    "one two three four five",
    "supercalifragilisticexpialidocious",
    "this is a test, with a comma, and a period.",
)


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI instance."""
    return CAPI()


@pytest.mark.parametrize("text", _CORPUS, ids=list(_CORPUS))
def test_returns_non_empty_phonemes(text: str, capi: CAPI) -> None:
    """Every prompt yields a non-empty phoneme stream."""
    phonemes = capi.convert_to_phonemes(text)
    assert len(phonemes) > 0


@pytest.mark.parametrize("text", _CORPUS, ids=list(_CORPUS))
def test_deterministic_across_calls(text: str, capi: CAPI) -> None:
    """Repeated calls must produce identical output (no nondeterminism)."""
    first = capi.convert_to_phonemes(text)
    for _ in range(3):
        again = capi.convert_to_phonemes(text)
        assert again == first, f"non-deterministic output for {text!r}"


def test_known_output_hello_world(capi: CAPI) -> None:
    """Document the exact byte string the C library produces for a fixed input.

    If this changes, the C source or the patch's behaviour has changed.
    """
    expected = b"hxaxll' ow  w ' rrlld "
    assert capi.convert_to_phonemes("hello world") == expected


def test_different_inputs_yield_different_outputs(capi: CAPI) -> None:
    """Sanity: distinct words give distinct phoneme streams."""
    hello = capi.convert_to_phonemes("hello")
    world = capi.convert_to_phonemes("world")
    assert hello != world
