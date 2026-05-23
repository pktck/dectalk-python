"""Per-stage parity test: KERNEL output (text-normalized byte stream).

This is one of six per-stage parity tests (kernel / cmd / lts /
ph-allofeats / ph-allophons / vtm) added under issue #150 to localize
divergence between the Python pipeline and the C oracle. When the
end-to-end :mod:`tests.parity.test_binary_wav_parity` test fails for
~80 % of the corpus, "still failing" is poor signal — these per-stage
tests pinpoint *which* stage is responsible.

The kernel-stage dump captures every byte chunk that the C kernel
emits downstream (the input to the CMD stage). The dump format is
defined by ``tests/parity/c_patches/0002-stage-boundary-dumps.patch``:

::

    kernel_write <length>
    <space-separated %02x bytes>

This test asserts:

1. The dump for each corpus prompt is non-empty and structurally
   well-formed (every header has a matching payload of the declared
   length).
2. The dump is deterministic — two back-to-back calls with the same
   input yield byte-identical dumps.
3. Distinct prompts produce distinct kernel byte streams — i.e. the
   kernel actually depends on the input. (This catches the failure
   mode where the dump hook captures only a constant prefix.)

The Python-side kernel emits text-normalized tokens via
:func:`dectalk.kernel.text.tokenize`, but the byte-level boundary with
the CMD stage doesn't yet have a Python equivalent dump, so a direct
Python-vs-C byte equality assertion is left as a follow-up (it requires
either a Python-side ``DECTALK_DUMP_DIR`` hook or a reimplementation
of the kernel→CMD framing). The structural / determinism asserts here
are the monitoring signal in the meantime.

Skips cleanly when the C oracle (source-built libtts + shipped
binary) is not present.
"""

from __future__ import annotations

import pytest

from dectalk._capi import CAPI

from ._stage_parity_corpus import STAGE_PARITY_CORPUS
from ._stage_parity_helpers import have_artefacts, parse_byte_dump, stage_capi

# Re-export so pytest finds the fixture in this module's namespace.
_ = stage_capi


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not have_artefacts(),
        reason="locally-built libtts or shipped DECtalk binary not present",
    ),
]


@pytest.mark.parametrize("text", STAGE_PARITY_CORPUS, ids=list(STAGE_PARITY_CORPUS))
def test_kernel_dump_is_well_formed(stage_capi: CAPI, text: str) -> None:
    """C-oracle kernel dump for ``text`` parses cleanly and is non-empty."""
    payload = stage_capi.dump_pipeline(text, ["kernel"])["kernel"]
    assert payload, f"empty kernel dump for {text!r}"
    chunks = parse_byte_dump(payload, "kernel_write")
    assert chunks, f"no kernel chunks parsed from dump of {text!r}"
    # Every chunk should have at least one byte — empty writes would be
    # a hook bug.
    for idx, chunk in enumerate(chunks):
        assert chunk, f"chunk #{idx} in kernel dump for {text!r} is empty"


@pytest.mark.parametrize("text", STAGE_PARITY_CORPUS, ids=list(STAGE_PARITY_CORPUS))
def test_kernel_dump_is_deterministic(stage_capi: CAPI, text: str) -> None:
    """Back-to-back kernel dumps for the same input are byte-identical."""
    first = stage_capi.dump_pipeline(text, ["kernel"])["kernel"]
    second = stage_capi.dump_pipeline(text, ["kernel"])["kernel"]
    assert first == second, (
        f"kernel dump diverged across runs for {text!r}: {len(first)} B vs {len(second)} B"
    )


def test_kernel_dump_distinguishes_prompts(stage_capi: CAPI) -> None:
    """Two unrelated prompts must produce different kernel byte streams."""
    a = stage_capi.dump_pipeline("hello world", ["kernel"])["kernel"]
    b = stage_capi.dump_pipeline("the quick brown fox", ["kernel"])["kernel"]
    assert a != b, "kernel dump is constant across distinct prompts — hook misfiring?"
