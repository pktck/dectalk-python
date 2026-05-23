"""Per-stage parity (issue #150): KERNEL — text-normalised byte stream.

KERNEL is the first stage of the DECtalk pipeline. The C source's
``ttsapi.c::TextToSpeechThreadMain`` chunks the input text into
``MAX_TEXT_WRITE_LENGTH`` blocks and writes each into ``pKsd_t->cmd_pipe``
(or its single-threaded inline equivalent). The Phase-A.4 dump hook in
``tests/parity/c_patches/0002-stage-boundary-dumps.patch`` captures the
exact bytes written at that boundary as ``kernel.dump``.

This test compares the C oracle's kernel dump for each corpus prompt
against the same byte stream the Python front end would emit if it had
a byte-stream KERNEL stage. Today the Python port routes text through
:func:`dectalk.kernel.text.tokenize` (token-level, not byte-stream) so
the test currently asserts only *structural* properties (presence of
the input ASCII chars, deterministic chunking) rather than exact byte
equality.

Once a byte-stream Python KERNEL is in place (the Phase-D KERNEL port),
flip ``_STRICT_BYTES`` to ``True`` and the test will then assert
byte-identical KERNEL output. Until then this test serves as a
monitoring gate: it succeeds when the C hook is present and the dump
parses, fails loudly when the dump format changes, and provides the
xfail surface the Phase-D port needs to flip to strict equality.
"""

from __future__ import annotations

import pytest

from dectalk._capi import CAPI

from ._stage_helpers import STAGE_CORPUS, parse_token_dump, skipif_no_oracle

# Flip to ``True`` once a byte-stream Python KERNEL stage exists.
# When ``False`` the test asserts structural properties only.
_STRICT_BYTES: bool = False


pytestmark = [pytest.mark.c_oracle, skipif_no_oracle]


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI handle; reused across the stage's per-prompt tests."""
    return CAPI()


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_kernel_dump_contains_input_bytes(text: str, capi: CAPI) -> None:
    """Every ASCII char in ``text`` appears in the C oracle's kernel dump.

    The KERNEL stage writes the input text verbatim into the cmd pipe
    (plus a trailing 0x0B force-flush byte the dispatcher appends to
    every Speak() call). Asserting each input char shows up confirms the
    hook fired and captured a meaningful chunk.
    """
    payload = capi.dump_pipeline(text, ["kernel"])["kernel"]
    assert payload, "kernel dump empty — patch not applied?"
    tokens = parse_token_dump(payload, header_prefix=b"kernel_write")
    # Pull just the printable ASCII bytes (skip the force-flush 0x0B).
    chars = bytes(tok for tok in tokens if 0x20 <= tok < 0x7F).decode("ascii")
    for ch in text:
        if ch == " ":
            continue
        assert ch in chars, (
            f"input character {ch!r} missing from kernel dump for {text!r}; "
            f"recovered chars: {chars!r}"
        )


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_kernel_dump_is_deterministic(text: str, capi: CAPI) -> None:
    """Two back-to-back kernel dumps for the same input must be byte-identical.

    Nondeterminism here would mean the C library carries mutable state
    across speak() calls in a way that affects KERNEL output — a
    blocker for any byte-parity port. The shared-handle reuse pattern
    in ``CAPI`` cycles state aggressively so this should always hold.
    """
    first = capi.dump_pipeline(text, ["kernel"])["kernel"]
    second = capi.dump_pipeline(text, ["kernel"])["kernel"]
    assert first == second, (
        f"kernel dump nondeterministic for {text!r}: {len(first)} B vs {len(second)} B"
    )


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_kernel_python_matches_c(text: str, capi: CAPI) -> None:
    """Python KERNEL stage byte-stream matches the C oracle's kernel dump.

    Currently expected-fail: the Python port doesn't yet have a
    byte-stream KERNEL stage (it tokenises directly). Will become a
    strict equality check when the Phase-D KERNEL port lands and
    ``_STRICT_BYTES`` flips to ``True``.
    """
    if not _STRICT_BYTES:
        pytest.xfail("Python KERNEL byte-stream stage not yet ported (issue #150)")
    # When the Python KERNEL port lands, this branch becomes the assertion.
    raise AssertionError("unreachable until _STRICT_BYTES flips to True")
