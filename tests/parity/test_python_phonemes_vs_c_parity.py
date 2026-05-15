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


# Module-scoped CAPI: each test creating its own instance exhausts file
# descriptors after a few thousand parametrised cases (libtts dlopens its
# own resources without closing). One process-level handle keeps the FD
# count flat regardless of corpus size.
_capi_handle: CAPI | None = None


def _get_capi() -> CAPI:
    """Return the lazily-initialised module-scoped CAPI handle."""
    global _capi_handle  # noqa: PLW0603
    if _capi_handle is None:
        _capi_handle = CAPI()
    return _capi_handle


@pytest.mark.parametrize("text", CORPUS, ids=list(CORPUS))
def test_python_phonemes_match_c_phonemes(text: str) -> None:
    """``dectalk.text_to_dectalk_phonemes`` matches ``CAPI.convert_to_phonemes``.

    The Python pipeline now emits DECtalk-native phoneme bytes that
    are byte-identical to the C ``TextToSpeechConvertToPhonemes``
    output across the bit-parity corpus. New prompts added to
    :data:`CORPUS` must keep this gate green; regressions here are
    pre-LTS-port divergence and need a Python-side fix (an entry in
    :func:`dectalk.text_to_dectalk_phonemes`'s ``word_phoneme_overrides``,
    a new sentinel rewriter, or a kernel-level expansion rule) -- not
    an xfail.
    """
    expected = _get_capi().convert_to_phonemes(text)
    actual = _python_phonemes(text)
    assert actual == expected, (
        f"phoneme mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Python): {actual!r}"
    )
