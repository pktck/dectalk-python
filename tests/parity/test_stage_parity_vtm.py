"""Per-stage parity test: VTM input (``parstochip[]`` frame stream).

Sibling to :mod:`tests.parity.test_stage_parity_kernel` — see that
module's docstring for the rationale (issue #150).

The VTM-stage dump captures every 16-bit token that the C PH stage
writes downstream — i.e. the per-frame parameter stream the VTM
("vocal tract model") consumes to produce audio samples. In the C
nomenclature these tokens are the ``parstochip[]`` array (PH stage
output to the SPC chip / VTM input). The hook is installed at the
entry of ``vtm_loop`` in ``src/dapi/src/vtm/vtmiont.c`` (see
``tests/parity/c_patches/0005-vtm-stage-dump-hooks.patch``).

::

    vtm_write <count>
    <space-separated %04x hex words>

A frame is several consecutive tokens (formant frequencies / bandwidths,
gain, glottal-source parameters, etc.) but the hook records each
single-token call individually; the consumer reconstructs frames if
needed. A divergence here means the Python PH stage
(``dectalk.ph.sequencer``) is producing different per-frame VTM
parameters than the C oracle — the most likely cause of audio drift.

Asserts:

1. The VTM dump for each corpus prompt parses as a sequence of
   single-token chunks.
2. The dump is deterministic across two back-to-back runs.
3. Distinct prompts produce distinct VTM frame streams.
4. The VTM stream is substantially larger than the LTS stream for
   the same prompt — VTM emits ~30+ words per allophone, whereas
   LTS emits ~1 word per allophone. Catches the failure mode where
   the PH stage stalls and emits no frames.

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
def test_vtm_dump_is_well_formed(stage_capi: CAPI, text: str) -> None:
    """C-oracle VTM dump for ``text`` parses cleanly and is non-empty."""
    payload = stage_capi.dump_pipeline(text, ["vtm"])["vtm"]
    assert payload, f"empty vtm dump for {text!r}"
    chunks = parse_word_dump(payload, "vtm_write")
    assert chunks, f"no vtm chunks parsed from dump of {text!r}"
    for idx, chunk in enumerate(chunks):
        assert len(chunk) == 1, (
            f"chunk #{idx} in vtm dump for {text!r} has {len(chunk)} tokens; "
            "expected 1 (vtm hook is single-token)"
        )


@pytest.mark.parametrize("text", STAGE_PARITY_CORPUS, ids=list(STAGE_PARITY_CORPUS))
def test_vtm_dump_is_deterministic(stage_capi: CAPI, text: str) -> None:
    """Back-to-back VTM dumps for the same input are byte-identical."""
    first = stage_capi.dump_pipeline(text, ["vtm"])["vtm"]
    second = stage_capi.dump_pipeline(text, ["vtm"])["vtm"]
    assert first == second, (
        f"vtm dump diverged across runs for {text!r}: {len(first)} B vs {len(second)} B"
    )


def test_vtm_dump_distinguishes_prompts(stage_capi: CAPI) -> None:
    """Two unrelated prompts must produce different VTM frame streams."""
    a = stage_capi.dump_pipeline("hi there", ["vtm"])["vtm"]
    b = stage_capi.dump_pipeline("the quick brown fox", ["vtm"])["vtm"]
    assert a != b, "vtm dump is constant across distinct prompts — hook misfiring?"


def test_vtm_dump_dwarfs_lts_dump(stage_capi: CAPI) -> None:
    """VTM token count is much larger than LTS token count for the same prompt.

    Sanity-checks that the PH stage actually expands LTS allophones into
    multi-frame parameter streams. If this ratio collapses to ~1, the
    PH stage has likely stalled (no frames emitted between LTS tokens).
    """
    text = "hello world"
    lts_chunks = parse_word_dump(stage_capi.dump_pipeline(text, ["ph"])["ph"], "ph_write")
    vtm_chunks = parse_word_dump(stage_capi.dump_pipeline(text, ["vtm"])["vtm"], "vtm_write")
    lts_count = sum(len(c) for c in lts_chunks)
    vtm_count = sum(len(c) for c in vtm_chunks)
    # Empirically the ratio is ~80x for "hello world" (~20 LTS tokens
    # vs ~1700 VTM tokens). Use a conservative >5x threshold so the
    # test is robust to minor PH-stage tweaks but still catches a stall.
    assert vtm_count > lts_count * 5, (
        f"vtm/lts token ratio collapsed: lts={lts_count}, vtm={vtm_count}; "
        "ph stage may have stalled"
    )
