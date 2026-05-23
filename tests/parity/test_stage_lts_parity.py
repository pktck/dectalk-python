"""Per-stage parity (issue #150): LTS + dic — ARPABET phoneme stream.

LTS (letter-to-sound) + dic together produce DECtalk's ARPABET-style
phoneme stream. The C library exposes this via
``TextToSpeechConvertToPhonemes`` (added by
``tests/parity/c_patches/0001-expose-convert-to-phonemes-on-linux.patch``);
the Python port produces the same stream via
:func:`dectalk.text_to_dectalk_phonemes` and the byte-equality is
already enforced across the full bit-parity corpus by
``test_python_phonemes_vs_c_parity.py``.

This per-stage file is the narrow, fast version of that gate: a
handful of representative prompts run through both sides, byte-equal
asserted. The full-corpus test stays the authoritative regression
guard; this one slots into the per-stage parity dashboard so the LTS
stage shows green alongside its KERNEL / CMD / PH / VTM siblings.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

import pytest

import dectalk
from dectalk._capi import CAPI

from ._stage_helpers import STAGE_CORPUS, skipif_no_oracle

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))


def _convert_to_phonemes_exported() -> bool:
    """True iff libtts_us.so exports ``TextToSpeechConvertToPhonemes``.

    Mirrors the helper in ``test_python_phonemes_vs_c_parity.py`` so
    this test skips identically when the convert-to-phonemes patch is
    absent from the C build.
    """
    candidates = sorted(_SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    if not candidates:
        return False
    try:
        lib = ctypes.CDLL(str(candidates[-1]))
        getattr(lib, "TextToSpeechConvertToPhonemes")  # noqa: B009
    except (OSError, AttributeError):
        return False
    return True


pytestmark = [
    pytest.mark.c_oracle,
    skipif_no_oracle,
    pytest.mark.skipif(
        not _convert_to_phonemes_exported(),
        reason="libtts_us.so missing TextToSpeechConvertToPhonemes — apply C patches",
    ),
]


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI handle."""
    return CAPI()


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_python_arpabet_matches_c(text: str, capi: CAPI) -> None:
    """``dectalk.text_to_dectalk_phonemes`` matches ``CAPI.convert_to_phonemes``.

    Per-stage version of the LTS gate: small corpus, fast runtime,
    shows up in the per-stage parity dashboard. The full-corpus
    enforcement lives in ``test_python_phonemes_vs_c_parity.py`` and
    must also stay green; this test is the per-stage facet of the
    same invariant.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"LTS+dic phoneme stream mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )
