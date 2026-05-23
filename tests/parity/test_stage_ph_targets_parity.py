"""Per-stage parity (issue #150): PH ``allophons[]`` / ``allodurs[]`` / ``f0tar[]`` / ``f0tim[]``.

After ``ph_setallofeats`` lands the per-phone features (see the sibling
``test_stage_ph_allofeats_parity.py``), the PH prosody pass populates:

- ``pDph_t->allophons[i]`` — final per-allophone codes after expansion
  (the ``USP_*`` constants from ``us_phalloph``).
- ``pDph_t->allodurs[i]`` — per-allophone duration in centiseconds,
  produced by ``us_phtiming`` / ``shrdur`` / ``prdurs``.
- ``pDph_t->f0tar[j]`` -- F0 target array (Hz x 10) for the utterance,
  laid out by ``phinton`` and the f0-segtar walkers.
- ``pDph_t->f0tim[j]`` — sample time (centiseconds since utterance
  start) corresponding to each ``f0tar[j]``.

These four arrays are the complete prosody picture the PH stage hands
to the VTM stage's ``parstochip`` frame composition. Today the C dump
infrastructure under ``tests/parity/c_patches/`` doesn't capture these
arrays — only the inter-stage 16-bit token streams.

Once a dump hook for these four arrays lands (likely a sibling patch
``0007-ph-prosody-dump.patch`` populating ``ph_prosody.dump``) this
test will diff the C-side arrays against the Python side. Until then
the test exercises the C PH boundary observable and xfails the
byte-equality comparison.
"""

from __future__ import annotations

import pytest

from dectalk._capi import CAPI

from ._stage_helpers import STAGE_CORPUS, parse_token_dump, skipif_no_oracle

# Flip to ``True`` once a per-allophone duration + F0 target dump hook
# is in place. Until then, the strict comparison is expected-fail.
_STRICT_PROSODY: bool = False


pytestmark = [pytest.mark.c_oracle, skipif_no_oracle]


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI handle."""
    return CAPI()


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_ph_loop_input_token_count_is_sane(text: str, capi: CAPI) -> None:
    """Proxy gate: PH-stage input has at least one token per input character.

    Until the per-allophone prosody dump hook exists, the closest
    observable is the count of tokens the LTS stage handed to
    ``ph_loop``. A trivially short token count would mean the front
    end emitted nothing meaningful — a clear regression.
    """
    payload = capi.dump_pipeline(text, ["ph"])["ph"]
    tokens = parse_token_dump(payload, header_prefix=b"ph_write")
    # The PH stage receives PFONT-flagged ARPABET tokens plus boundary
    # / stress markers. A coarse lower bound: at least one PH token
    # per non-space input character (LTS expansion adds more in practice).
    nonspace = sum(1 for ch in text if not ch.isspace())
    assert len(tokens) >= nonspace, (
        f"PH input token count {len(tokens)} unexpectedly low for {text!r} "
        f"({nonspace} non-space chars)"
    )


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_python_prosody_arrays_match_c(text: str, capi: CAPI) -> None:
    """Python ``allophons``/``allodurs``/``f0tar``/``f0tim`` match C arrays.

    Expected-fail until a dump hook for these arrays lands. See the
    module docstring for the planned dump-file shape.
    """
    if not _STRICT_PROSODY:
        pytest.xfail(
            "C-side allophons/allodurs/f0tar/f0tim dump hook not yet implemented "
            "(planned: tests/parity/c_patches/0007-ph-prosody-dump.patch)"
        )
    raise AssertionError("unreachable until _STRICT_PROSODY flips to True")
