"""Digit stems under inflectional suffix stripping must not crash.

Issue #316 discovery-sweep regression: decade shapes (``the '90s``,
``1990s``) hit the ``-s``/``-'s`` suffix-strip path with a digit-only
stem, whose LTS fallback yields an *empty* phoneme list; the epenthesis
logic then crashed on ``stem_phones[-1]``. The fix treats an empty LTS
stream as no-stem. Byte-parity for these shapes is tracked separately
(the mixed-alphanumeric divergence class) — this suite only pins the
no-crash contract.
"""

from __future__ import annotations

import pytest

import dectalk

_DECADE_SHAPES = ("the '90s", "1990s", "70s", "the '90's", "007s")


@pytest.mark.parametrize("text", _DECADE_SHAPES)
def test_digit_suffix_stem_does_not_crash(text: str) -> None:
    out = dectalk.text_to_dectalk_phonemes(text)
    assert isinstance(out, bytes)
