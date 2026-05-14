"""Stage-boundary parity test: Python `text_to_phonemes` vs C `convert_to_phonemes`.

This is the goalpost for the LTS + dic phase of the C-to-Python port.
The C library exposes ``TextToSpeechConvertToPhonemes`` (via the
``0001-expose-convert-to-phonemes-on-linux`` patch) which returns the
phoneme stream that drives the downstream PH/VTM stages. Once the
pure-Python LTS+dic implementation matches this output byte-for-byte
across the bit-parity corpus, the LTS phase of the port is complete
and we move on to PH/VTM.

Today the Python pipeline emits ARPABET-style phonemes (``HH AH0 L OW1
W ER1 L D``) while the C source emits DECtalk's native alphabet (``hxax
ll' ow w ' rrlld``). The test fails on every prompt until the LTS port
emits the DECtalk-native alphabet AND its rule outputs match the C's
byte-for-byte.

The stop-hook does NOT gate on this file -- it gates on the full
audio parity test. But this is a useful intermediate goalpost.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

import pytest

import dectalk
from dectalk._capi import CAPI

from ._corpus import CORPUS

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
    not (_have_artefacts() and _convert_to_phonemes_exported()),
    reason="C library with convert_to_phonemes patch is required for LTS parity",
)


def _python_phonemes(text: str) -> bytes:
    """Render Python's phoneme list in DECtalk's native ASCII format.

    Uses :func:`dectalk.text_to_dectalk_phonemes` which goes through
    ``encode_to_dectalk`` (the ARPABET -> DECtalk 2-letter encoder),
    so the result can be byte-compared against the C source's
    ``convert_to_phonemes`` output.

    Today the encoded byte string diverges on every prompt (different
    LTS rules, different schwa/stress placement, missing trailing
    spaces, no phrase/clause markers); each prompt that turns green
    here closes the gap by one corner.
    """
    return dectalk.text_to_dectalk_phonemes(text)


@pytest.mark.xfail(
    reason=(
        "Pure-Python LTS+dic port not yet complete; Python emits ARPABET, "
        "C emits DECtalk-native alphabet."
    ),
    strict=False,
)
@pytest.mark.parametrize("text", CORPUS, ids=list(CORPUS))
def test_python_phonemes_match_c_phonemes(text: str) -> None:
    """``dectalk.text_to_phonemes`` output matches ``CAPI.convert_to_phonemes``.

    Today: fails on every prompt (Python emits ARPABET, C emits the
    DECtalk-native alphabet). Stays red until the LTS port lands a
    faithful translation. Each prompt that turns green here is one
    closer to pure-Python bit parity.
    """
    capi = CAPI()
    expected = capi.convert_to_phonemes(text)
    actual = _python_phonemes(text)
    assert actual == expected, (
        f"phoneme mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Python): {actual!r}"
    )
