"""Stage-boundary parity test: Python `text_to_phonemes` vs C `convert_to_phonemes`.

This is the goalpost for the LTS + dic phase of the C-to-Python port.
The C library exposes ``TextToSpeechConvertToPhonemes`` (via the
``0001-expose-convert-to-phonemes-on-linux`` patch) which returns the
phoneme stream that drives the downstream PH/VTM stages. Once the
pure-Python LTS+dic implementation matches this output byte-for-byte
across the bit-parity corpus, the LTS phase of the port is complete
and we move on to PH/VTM.

To keep the parametrised pytest run under the OS file-descriptor
ceiling (the C library leaks a few FDs per ``TextToSpeechStartup``
/ ``Shutdown`` cycle), the C oracle is computed once at session
start and cached in :data:`_C_ORACLE`. Subsequent test invocations
look up the cached bytes instead of re-querying the C library.
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
    """
    return dectalk.text_to_dectalk_phonemes(text)


# Bulk-precompute the C oracle once per session. Each
# ``convert_to_phonemes`` call goes through ``TextToSpeechStartup``
# / ``TextToSpeechShutdown``; doing it 3000+ times during the
# parametrised test run exhausts the 4096-FD ulimit. Caching the
# results up-front decouples corpus size from FD usage.
_C_ORACLE: dict[str, bytes] = {}


def _build_oracle() -> dict[str, bytes]:
    """Compute ``convert_to_phonemes`` for every CORPUS entry once.

    The C library accumulates a tiny amount of cross-call state that
    can cause flaky differences once you've made thousands of calls
    against a single handle. Cycling the handle every 1000 calls
    keeps the state fresh without blowing past the FD ceiling
    (each Startup leaks a handful of FDs; 30 cycles fits easily).
    """
    chunk = 1000
    capi = CAPI()
    result: dict[str, bytes] = {}
    for i, text in enumerate(CORPUS):
        if i > 0 and i % chunk == 0:
            capi = CAPI()
        result[text] = capi.convert_to_phonemes(text)
    return result


def _get_oracle(text: str) -> bytes:
    """Return the cached C output for ``text`` (populating the cache lazily)."""
    if not _C_ORACLE:
        _C_ORACLE.update(_build_oracle())
    return _C_ORACLE[text]


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
    expected = _get_oracle(text)
    actual = _python_phonemes(text)
    assert actual == expected, (
        f"phoneme mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Python): {actual!r}"
    )
