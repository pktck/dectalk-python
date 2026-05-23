"""Per-stage parity test: LTS + DIC output (ARPABET phoneme stream).

Sibling to :mod:`tests.parity.test_stage_parity_kernel` — see that
module's docstring for the rationale (issue #150).

The LTS-stage dump captures every 16-bit token that the C LTS
(letter-to-sound + dictionary) stage writes downstream — i.e. the
input to the PH stage. In ``SINGLE_THREADED`` builds the C hook is
installed at the entry of ``ph_loop`` (see
``tests/parity/c_patches/0004-ph-stage-dump-hooks.patch``). The file
on disk is named ``ph.dump`` because it captures the PH input
boundary, but it is the LTS *output* boundary as well — they're the
same boundary in a serial pipeline.

::

    ph_write <count>
    <space-separated %04x hex words>

Each token is an allophone code paired with a stress mark / sentence
boundary. A divergence here means the Python ``dectalk.lts`` package
(letter-to-sound rules) or ``dectalk.dic`` (lexicon lookup) is
producing different ARPABET output than the C oracle.

Asserts:

1. The LTS dump for each corpus prompt parses as a sequence of
   single-token chunks (the C hook is single-token, like CMD).
2. The dump is deterministic across two back-to-back runs.
3. Distinct prompts produce distinct LTS token streams.
4. The LTS stream length grows with input length (a one-word prompt
   should produce fewer tokens than a five-word prompt — a sanity
   check that catches the failure mode where the LTS stage stalls).

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
def test_lts_dump_is_well_formed(stage_capi: CAPI, text: str) -> None:
    """C-oracle LTS dump for ``text`` parses cleanly and is non-empty."""
    payload = stage_capi.dump_pipeline(text, ["ph"])["ph"]
    assert payload, f"empty lts/ph dump for {text!r}"
    chunks = parse_word_dump(payload, "ph_write")
    assert chunks, f"no lts chunks parsed from dump of {text!r}"
    for idx, chunk in enumerate(chunks):
        assert len(chunk) == 1, (
            f"chunk #{idx} in lts dump for {text!r} has {len(chunk)} tokens; "
            "expected 1 (ph hook is single-token)"
        )


@pytest.mark.parametrize("text", STAGE_PARITY_CORPUS, ids=list(STAGE_PARITY_CORPUS))
def test_lts_dump_is_deterministic(stage_capi: CAPI, text: str) -> None:
    """Back-to-back LTS dumps for the same input are byte-identical."""
    first = stage_capi.dump_pipeline(text, ["ph"])["ph"]
    second = stage_capi.dump_pipeline(text, ["ph"])["ph"]
    assert first == second, (
        f"lts dump diverged across runs for {text!r}: {len(first)} B vs {len(second)} B"
    )


def test_lts_dump_distinguishes_prompts(stage_capi: CAPI) -> None:
    """Two unrelated prompts must produce different LTS token streams."""
    a = stage_capi.dump_pipeline("cat", ["ph"])["ph"]
    b = stage_capi.dump_pipeline("dog", ["ph"])["ph"]
    assert a != b, "lts dump is constant across distinct prompts — hook misfiring?"


def test_lts_dump_grows_with_input_length(stage_capi: CAPI) -> None:
    """A five-word prompt produces more LTS tokens than a one-word prompt."""
    short_chunks = parse_word_dump(stage_capi.dump_pipeline("hi", ["ph"])["ph"], "ph_write")
    long_chunks = parse_word_dump(
        stage_capi.dump_pipeline("the quick brown fox jumps", ["ph"])["ph"],
        "ph_write",
    )
    short_total = sum(len(c) for c in short_chunks)
    long_total = sum(len(c) for c in long_chunks)
    assert short_total < long_total, (
        f"lts token count did not grow with input length: short={short_total}, long={long_total}"
    )
