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


# Pre-captured ``CAPI.convert_to_phonemes(text)`` outputs from the
# locally-built libtts_us.so. Locked in as the byte-identical golden
# target any future pure-Python LTS implementation must reproduce.
_KNOWN_OUTPUTS: tuple[tuple[str, bytes], ...] = (
    ("hello world", b"hxaxll' ow  w ' rrlld "),
    ("the quick brown fox", b"dhax  k w ' ihk   b r ' awn   f ' aak s "),
    ("she sells sea shells", b"sh` iy  ) s ' ehllz   s ' iy  sh' ehllz "),
    ("one two three four five", b"w ' ahn   t ' uw  thr ' iy  f ' owr   f ' ayv "),
    (
        "supercalifragilisticexpialidocious",
        b"s uwp rrk aellihf r aejhihllihs t ihs ehk s p ihaellihd aashixs ",
    ),
    (
        "DECtalk version 6.2.0",
        b"d ' ehk # t aok   v ' rrzhen  s ' ihk s   p ' oyn t   t ' uw  p ' oyn t   z ' iyr ow",
    ),
    (
        "this is a test, with a comma, and a period.",
        b"dh` ihs   ihz   ^ ax  t ' ehs t , w ihth  ^ ax  k ' aam ax,"
        b" ^ ( aen d   ^ ax  p ' iyr iyaxd . ",
    ),
    ("the answer is 42", b"dhax  ' aen s rr  ihz   f ' ort iy  t ' uw"),
    ("3 point 14", b"thr ' iy  p ' oyn t   f ' or* t ' iyn "),
    (
        "one hundred and one dalmatians",
        b"w ' ahn   hx' ahn d r axd   ^ ( aen d   w ' ahn   d axllm ' aeshixn z ",
    ),
    ("hello! how are you?", b"hxaxll' ow! hx` aw  aar   yx` uw. "),
    ("wait... what just happened?", b"w ' eyt . w ` aht   jh' ahs t   ) hx' aep axn d . "),
    ("FBI", b"' ehf   b iy  ' ay"),
    ("NASA", b"n ' aes ax"),
    ("USA", b"` yuehs ' ey"),
    ("MIT", b"` ehm ayt ' iy"),
    ("judge thought rhythms", b"jh' ahjh  th' aot   r ' ihdhaxm z "),
    ("knight light right", b"n ' ayt   ll' ayt   r ' ayt "),
    ("Dr. Smith said hello.", b"d aak t rr  s m ' ihth  ) s ` ehd   hxaxll' ow. "),
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


@pytest.mark.parametrize(
    ("text", "expected"),
    _KNOWN_OUTPUTS,
    ids=[t for t, _ in _KNOWN_OUTPUTS],
)
def test_known_outputs(text: str, expected: bytes, capi: CAPI) -> None:
    """The C library's phoneme stream for each input matches the locked golden value.

    These 19 (text → phonemes) pairs are pre-captured from the
    locally-built libtts_us.so. They serve as the byte-identical
    target a pure-Python LTS implementation must reproduce when
    Phase D translation lands.
    """
    assert capi.convert_to_phonemes(text) == expected, (
        f"phoneme stream changed for {text!r}: did the C source or patch change?"
    )


def test_different_inputs_yield_different_outputs(capi: CAPI) -> None:
    """Sanity: distinct words give distinct phoneme streams."""
    hello = capi.convert_to_phonemes("hello")
    world = capi.convert_to_phonemes("world")
    assert hello != world
