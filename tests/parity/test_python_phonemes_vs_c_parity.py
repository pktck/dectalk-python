"""Stage-boundary parity gate: Python `text_to_dectalk_phonemes` vs C `convert_to_phonemes`.

This is the floor of the parity ladder for the LTS + dic phase of the
C-to-Python port. The C library exposes ``TextToSpeechConvertToPhonemes``
(via the ``0001-expose-convert-to-phonemes-on-linux`` patch) which returns
the phoneme stream that drives the downstream PH/VTM stages. The pure
Python pipeline is byte-compared against it across a deterministic
subsample of the shared bit-parity corpus (``tests/parity/_corpus.py``).

**Current status (measured 2026-07-10, issue #295):** 133,639 / 133,641
corpus prompts are byte-identical (99.999%). The #295 homograph
burn-down closed the POS-resolution class (close/lead/tears/wind/
object/subject/contrast/produce via the faithful ``ls_homo_homo``
port), the ``ours``/``al``/``fewer`` lexicon rows, and the
swing/string IH-before-NG nuance. The 2 remaining divergent prompts
are possessive-``its`` secondary-stress residue owned by the #280
runtime stress-rules work; they are listed in
``tests/parity/data/corpus_phoneme_known_divergent.txt`` and xfailed
(non-strict) here. The gate enforced by this module is therefore: **no
prompt outside the known-divergent list may regress**. Shrink the list
as the backlog burns down — regenerate it with
``scripts/corpus_phoneme_sweep.py --update-known-list`` after a fix.

Sampling: parametrising all ~133K corpus prompts into every CI shard is
wasteful, and bulk-querying the C oracle from one process is impossible
anyway — the patched C library reliably segfaults after roughly 45-60
seconds of in-process use (a few thousand ``convert_to_phonemes`` calls),
regardless of handle recycling. ``DECTALK_CORPUS_GATE_SAMPLE`` controls
the deterministic evenly-strided subsample size (default 2000; ``0``
selects the full corpus). Full-corpus sweeps must run through
``scripts/corpus_phoneme_sweep.py``, which slices the work across fresh
subprocesses to sidestep the segfault window.

The C oracle is queried lazily per prompt (with periodic handle
recycling) so the per-process C-library residency stays proportional to
the tests actually selected — under ``pytest-shard`` + ``xdist`` each
worker only pays for its own slice.
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

_KNOWN_DIVERGENT_PATH = Path(__file__).parent / "data" / "corpus_phoneme_known_divergent.txt"

_SAMPLE_ENV = "DECTALK_CORPUS_GATE_SAMPLE"
_DEFAULT_SAMPLE = 2000


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


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not (_have_artefacts() and _convert_to_phonemes_exported()),
        reason="C library with convert_to_phonemes patch is required for LTS parity",
    ),
]


def _gate_prompts() -> tuple[str, ...]:
    """Deterministic evenly-strided subsample of the corpus.

    ``DECTALK_CORPUS_GATE_SAMPLE`` sets the target size (default 2000);
    ``0`` (or any value >= the corpus size) selects the full corpus.
    Striding keeps the sample stratified across the corpus's thematic
    sections, and the selection only shifts when the corpus itself is
    edited — never between runs.
    """
    target = int(os.environ.get(_SAMPLE_ENV, str(_DEFAULT_SAMPLE)))
    if target <= 0 or target >= len(CORPUS):
        return CORPUS
    step = -(-len(CORPUS) // target)  # ceil division
    return CORPUS[::step]


def _known_divergent() -> frozenset[str]:
    """Prompts currently allowed to diverge (the #281 burn-down list)."""
    if not _KNOWN_DIVERGENT_PATH.exists():
        return frozenset()
    return frozenset(
        line
        for line in _KNOWN_DIVERGENT_PATH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def _python_phonemes(text: str) -> bytes:
    """Render Python's phoneme list in DECtalk's native ASCII format.

    Uses :func:`dectalk.text_to_dectalk_phonemes` which goes through
    ``encode_to_dectalk`` (the ARPABET -> DECtalk 2-letter encoder),
    so the result can be byte-compared against the C source's
    ``convert_to_phonemes`` output.
    """
    return dectalk.text_to_dectalk_phonemes(text)


# Lazy per-prompt C oracle. One CAPI handle serves batches of lookups and
# is recycled every _RECYCLE_AFTER calls to keep the C library's cross-call
# state fresh (the historical full-corpus prebuild both wasted time under
# sharding and ran long enough to hit the C library's in-process segfault
# window — see the module docstring).
_RECYCLE_AFTER = 500
_C_ORACLE: dict[str, bytes] = {}
_capi_handle: CAPI | None = None
_capi_calls = 0


def _get_oracle(text: str) -> bytes:
    """Return the C output for ``text``, querying and caching lazily."""
    global _capi_handle, _capi_calls  # noqa: PLW0603 — module-level oracle cache
    cached = _C_ORACLE.get(text)
    if cached is not None:
        return cached
    if _capi_handle is None or _capi_calls >= _RECYCLE_AFTER:
        _capi_handle = CAPI()
        _capi_calls = 0
    _capi_calls += 1
    result = _capi_handle.convert_to_phonemes(text)
    _C_ORACLE[text] = result
    return result


def _params() -> list[object]:
    known = _known_divergent()
    xfail = pytest.mark.xfail(
        reason="known divergence — possessive-its stress residue, #280 "
        "(tests/parity/data/corpus_phoneme_known_divergent.txt)",
        strict=False,
    )
    return [
        pytest.param(text, marks=xfail, id=text) if text in known else pytest.param(text, id=text)
        for text in _gate_prompts()
    ]


@pytest.mark.parametrize("text", _params())
def test_python_phonemes_match_c_phonemes(text: str) -> None:
    """``dectalk.text_to_dectalk_phonemes`` matches ``CAPI.convert_to_phonemes``.

    Prompts outside the known-divergent list must match byte-for-byte;
    a mismatch there is a fresh regression in the Python front end and
    needs a Python-side fix, not an xfail. Prompts inside the list are
    the measured residue after the #295 homograph burn-down —
    possessive-``its`` secondary stress, owned by the #280 runtime
    stress-rules work; they xfail non-strictly so fixes can land
    incrementally, after which
    ``scripts/corpus_phoneme_sweep.py --update-known-list`` re-shrinks
    the list.
    """
    expected = _get_oracle(text)
    actual = _python_phonemes(text)
    assert actual == expected, (
        f"phoneme mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Python): {actual!r}"
    )
