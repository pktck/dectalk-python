"""Pin the issue #346 §2 lexicon/abbreviation readings byte-exact.

Two front-end fixes land here, both verified byte-identical to the
shipped C oracle (phoneme stream *and* WAV):

1. **``example`` lexicon pin.** ``example`` has no ``Dic_us.txt`` row,
   so the C runtime speaks it from its own letter-to-sound rules as
   ``ixg z ' aem p el`` (``IX G Z AE1 M P EL``). The Python LTS diverged
   (``' ehk s aem p el``). Pinned in ``lexicon_us_corrections.txt`` and
   baked into ``lexicon_us_full.txt``; the ``-s`` / ``-'s`` suffix
   strips inherit the corrected stem, so ``examples`` / ``example's``
   follow without their own rows.

2. **``e.g.`` / ``i.e.`` dict expansion.** ``Dic_us.txt`` keys these
   (with both dots) to opaque expansions — ``fR|gz'@mpL`` ("for
   example") and ``D'IsIz`` ("this is"). The bare lower-case chunk is
   intercepted in ``text_to_dectalk_phonemes`` and re-injected as the
   expansion words, so the existing function-word (``for`` -> ``^ (``)
   and lexicon (``example``) paths reproduce the binary.

The C side is skipped unless a locally-built ``libtts_us.so`` is
present (``scripts/setup_c_oracle.sh``); the Python side runs
unconditionally as a regression gate. Corpus impact is nil —
``example`` / ``e.g.`` / ``i.e.`` / ``www`` appear in zero corpus
prompts (issue #346 §2).
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

import pytest

import dectalk
from dectalk._capi import CAPI

# Byte-exact Python == C readings established in issue #346 §2.
_EXPECTED: dict[str, bytes] = {
    "example": b"ixg z ' aem p el",
    "examples": b"ixg z ' aem p elz ",
    "example's": b"ixg z ' aem p elz ",
    "for example": b"^ ( f rr  ixg z ' aem p el",
    # The §2 representative: ``e.g.`` -> "for example", ``i.e.`` ->
    # "this is", with the pinned ``example`` reading in between.
    "e.g. apples, i.e. fruit": (
        b"^ ( f rr  ixg z ' aem p el  ' aep elz , dh` ihs   ihz   f r ' uwt "
    ),
}

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))


def _have_c_oracle() -> bool:
    """True iff a locally-built ``libtts_us.so`` exports the parity entry point."""
    candidates = sorted(_SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    if not candidates:
        return False
    try:
        lib = ctypes.CDLL(str(candidates[-1]))
        getattr(lib, "TextToSpeechConvertToPhonemes")  # noqa: B009
    except (OSError, AttributeError):
        return False
    return True


@pytest.mark.parametrize("prompt", list(_EXPECTED), ids=list(_EXPECTED))
def test_example_reading_python_pinned(prompt: str) -> None:
    """Pin Python's byte-exact output for the issue #346 §2 readings."""
    actual = dectalk.text_to_dectalk_phonemes(prompt)
    expected = _EXPECTED[prompt]
    assert actual == expected, (
        f"Python phoneme stream for {prompt!r} drifted:\n"
        f"  pinned (issue #346 §2): {expected!r}\n"
        f"  actual:                 {actual!r}\n"
    )


@pytest.mark.c_oracle
@pytest.mark.skipif(
    not _have_c_oracle(),
    reason="C library with convert_to_phonemes patch is required for this oracle pin",
)
@pytest.mark.parametrize("prompt", list(_EXPECTED), ids=list(_EXPECTED))
def test_example_reading_matches_c_oracle(prompt: str) -> None:
    """Assert the pinned readings are byte-identical to the C oracle."""
    actual = CAPI().convert_to_phonemes(prompt)
    expected = _EXPECTED[prompt]
    assert actual == expected, (
        f"C oracle phoneme stream for {prompt!r} drifted from the issue #346 pin:\n"
        f"  pinned: {expected!r}\n"
        f"  actual: {actual!r}\n"
    )
