"""Per-stage parity test: CMD output (parsed command stream).

Sibling to :mod:`tests.parity.test_stage_parity_kernel` — see that
module's docstring for the rationale (issue #150).

The CMD-stage dump captures every 16-bit token that the C CMD stage
writes downstream — i.e. the input to the LTS stage. In
``SINGLE_THREADED`` builds the C hook is installed at the entry of
``lts_loop`` (see
``tests/parity/c_patches/0003-cmd-stage-dump-hooks.patch``):

::

    cmd_write <count>
    <space-separated %04x hex words>

This is the boundary where DECtalk's inline ``[:cmd ...]`` syntax has
been expanded into VTM-level escape codes, and ASCII characters
have been forwarded one-by-one as ``PVALUE`` words. A divergence here
means the Python ``dectalk.cmd`` package is producing a different
token stream than the C CMD module.

Asserts:

1. The CMD dump for each corpus prompt parses as a sequence of
   single-token chunks (the C hook always calls with ``count == 1``).
2. The dump is deterministic across two back-to-back runs.
3. Distinct prompts produce distinct CMD token streams.
4. The CMD stream for a plain ASCII prompt contains the input
   characters' code points (sanity check that the boundary isn't
   garbling input).

Skips cleanly when the C oracle is not present.
"""

from __future__ import annotations

import pytest

from dectalk._capi import CAPI

from ._stage_parity_corpus import STAGE_PARITY_CORPUS
from ._stage_parity_helpers import have_artefacts, parse_word_dump, stage_capi

_ = stage_capi


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not have_artefacts(),
        reason="locally-built libtts or shipped DECtalk binary not present",
    ),
]


@pytest.mark.parametrize("text", STAGE_PARITY_CORPUS, ids=list(STAGE_PARITY_CORPUS))
def test_cmd_dump_is_well_formed(stage_capi: CAPI, text: str) -> None:
    """C-oracle CMD dump for ``text`` parses cleanly and is non-empty."""
    payload = stage_capi.dump_pipeline(text, ["cmd"])["cmd"]
    assert payload, f"empty cmd dump for {text!r}"
    chunks = parse_word_dump(payload, "cmd_write")
    assert chunks, f"no cmd chunks parsed from dump of {text!r}"
    # Every CMD-write call passes a single token (the hook is installed
    # at lts_loop entry which reads input[0]); any chunk longer than 1
    # would be a hook regression.
    for idx, chunk in enumerate(chunks):
        assert len(chunk) == 1, (
            f"chunk #{idx} in cmd dump for {text!r} has {len(chunk)} tokens; "
            "expected 1 (cmd hook is single-token)"
        )


@pytest.mark.parametrize("text", STAGE_PARITY_CORPUS, ids=list(STAGE_PARITY_CORPUS))
def test_cmd_dump_is_deterministic(stage_capi: CAPI, text: str) -> None:
    """Back-to-back CMD dumps for the same input are byte-identical."""
    first = stage_capi.dump_pipeline(text, ["cmd"])["cmd"]
    second = stage_capi.dump_pipeline(text, ["cmd"])["cmd"]
    assert first == second, (
        f"cmd dump diverged across runs for {text!r}: {len(first)} B vs {len(second)} B"
    )


def test_cmd_dump_distinguishes_prompts(stage_capi: CAPI) -> None:
    """Two unrelated prompts must produce different CMD token streams."""
    a = stage_capi.dump_pipeline("hello", ["cmd"])["cmd"]
    b = stage_capi.dump_pipeline("world", ["cmd"])["cmd"]
    assert a != b, "cmd dump is constant across distinct prompts — hook misfiring?"


def test_cmd_dump_carries_ascii_codepoints(stage_capi: CAPI) -> None:
    """The CMD stream for plain ASCII text contains the input character codes.

    The C CMD stage forwards each ASCII character as a single
    ``PVALUE`` token (low byte == ASCII code, high byte == 0 for
    pre-tagged ASCII). Asserting the input chars appear among the
    low-byte tokens is a cheap sanity check that catches the
    boundary-garbling failure mode where the hook captures the wrong
    pipe.
    """
    text = "hello"
    chunks = parse_word_dump(stage_capi.dump_pipeline(text, ["cmd"])["cmd"], "cmd_write")
    tokens = [tok for chunk in chunks for tok in chunk]
    low_bytes = {tok & 0xFF for tok in tokens}
    for ch in text:
        assert ord(ch) in low_bytes, (
            f"cmd dump for {text!r} missing input char {ch!r} (0x{ord(ch):02x}) "
            f"among low-byte tokens"
        )
