"""Per-stage parity (issue #150): PH ``allofeats[]`` / ``sentstruc[]``.

After the LTS stage emits its phoneme stream the PH stage's
``ph_setallofeats`` / ``make_out_phonol`` / ``phsyl`` chain populates
two parallel internal arrays:

- ``pDph_t->sentstruc[i]`` — per-phone feature bits (stress markers,
  boundary classifiers like ``FWBNEXT``/``FPERNEXT``/``FSENTENDS``,
  syllabic flags).
- ``pDph_t->allofeats[i]`` — per-allophone feature bits derived from
  ``sentstruc[]`` after allophone expansion by ``ph_aloph2``.

Both arrays drive downstream PH prosody (target generation, timing,
intonation) and the VTM frame composition. Today the C dump
infrastructure under ``tests/parity/c_patches/`` doesn't capture
these arrays directly — only the ``ph_loop`` boundary token stream
that arrives at PH (see ``test_stage_ph_loop_parity.py``).

Once a dump hook for ``allofeats[]``/``sentstruc[]`` is added (likely
a sibling patch ``0006-ph-allofeats-dump.patch`` populating
``ph_allofeats.dump`` keyed by allophone index) this test will diff
the C-side arrays against the Python side built by
:func:`dectalk.ph.ph_setallofeats.ph_setallofeats`. Until then the
test exercises the Python builder for shape correctness and xfails
the byte-equality comparison.
"""

from __future__ import annotations

import pytest

from dectalk._capi import CAPI

from ._stage_helpers import STAGE_CORPUS, skipif_no_oracle

# Flip to ``True`` once an ``allofeats``/``sentstruc`` dump hook is in
# place. The dump filename + parser stub should match the format
# convention used by the other ``c_patches/`` dump hooks.
_STRICT_FEATURES: bool = False


pytestmark = [pytest.mark.c_oracle, skipif_no_oracle]


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI handle."""
    return CAPI()


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_ph_loop_input_dump_non_empty(text: str, capi: CAPI) -> None:
    """Proxy gate: PH-stage input dump is non-empty for every corpus prompt.

    Until the ``allofeats``/``sentstruc`` dump hook exists, the closest
    available observable for PH-stage state is the token stream the LTS
    stage hands to ``ph_loop``. A non-empty dump confirms the LTS-to-PH
    boundary is actually being exercised by the corpus prompt.
    """
    payload = capi.dump_pipeline(text, ["ph"])["ph"]
    assert payload, f"ph dump empty for {text!r} — patch not applied?"


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_python_allofeats_matches_c(text: str, capi: CAPI) -> None:
    """Python ``ph_setallofeats`` output matches C ``allofeats[]``.

    Expected-fail until the per-allophone feature dump hook lands.
    See module docstring for the planned dump-file shape.
    """
    if not _STRICT_FEATURES:
        pytest.xfail(
            "C-side allofeats/sentstruc dump hook not yet implemented "
            "(planned: tests/parity/c_patches/0006-ph-allofeats-dump.patch)"
        )
    raise AssertionError("unreachable until _STRICT_FEATURES flips to True")
