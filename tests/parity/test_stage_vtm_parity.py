"""Per-stage parity (issue #150): VTM ``parstochip[]`` frame stream.

The VTM (vocal tract model) stage's ``vtmiont.c::vtm_loop`` receives
``parstochip[]`` 16-bit control words from the PH stage and converts
them into the per-frame Klatt synthesizer parameters that drive
``ll_synthesize``. The Phase-A.4 dump hook in
``tests/parity/c_patches/0005-vtm-stage-dump-hooks.patch`` captures
each control-word token at that boundary as ``vtm.dump``.

This test asserts:
- the VTM dump is well-formed and non-empty for every corpus prompt;
- repeated runs are byte-identical;
- (xfail) the Python ``parstochip_to_llframe`` chain produces a
  matching control-word stream.

Today the C dump captures only the packet *control word*, not the
full ``VOICE_PARS`` payload — issue #151 tracks extending the patch
to dump the complete payload so quantitative per-frame VTM parity is
possible. Until that extension lands the strict comparison is
expected-fail and this test serves as the monitoring gate.
"""

from __future__ import annotations

import pytest

from dectalk._capi import CAPI

from ._stage_helpers import STAGE_CORPUS, parse_token_dump, skipif_no_oracle

# Flip to ``True`` once the VTM dump captures full ``VOICE_PARS``
# payload frames (issue #151) and a Python ``parstochip`` stream
# accessor is wired up.
_STRICT_FRAMES: bool = False


pytestmark = [pytest.mark.c_oracle, skipif_no_oracle]


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI handle."""
    return CAPI()


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_vtm_dump_non_empty(text: str, capi: CAPI) -> None:
    """VTM control-word dump is non-empty for every corpus prompt."""
    payload = capi.dump_pipeline(text, ["vtm"])["vtm"]
    assert payload, f"vtm dump empty for {text!r} — patch not applied?"
    tokens = parse_token_dump(payload, header_prefix=b"vtm_write")
    # Each input prompt produces ~100s of control words (per audit notes
    # the typical hello-world dump is ~430 tokens); below 10 is a clear
    # sign the VTM stage didn't actually receive anything.
    min_tokens = 10
    assert len(tokens) >= min_tokens, (
        f"VTM dump for {text!r} suspiciously short ({len(tokens)} tokens, min {min_tokens})"
    )


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_vtm_dump_is_deterministic(text: str, capi: CAPI) -> None:
    """Back-to-back VTM dumps for the same input are byte-identical."""
    a = capi.dump_pipeline(text, ["vtm"])["vtm"]
    b = capi.dump_pipeline(text, ["vtm"])["vtm"]
    assert a == b, f"VTM dump nondeterministic for {text!r}"


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_python_parstochip_matches_c(text: str, capi: CAPI) -> None:
    """Python ``parstochip`` control-word + frame stream matches the C oracle.

    Expected-fail until issue #151 extends the VTM dump hook to
    capture the full ``VOICE_PARS`` payload (the current hook only
    captures the control word at the PH→VTM boundary, blocking
    quantitative per-frame comparison).
    """
    if not _STRICT_FRAMES:
        pytest.xfail(
            "VTM full-frame payload dump not yet implemented (issue #151); "
            "Python parstochip stream accessor also pending wiring"
        )
    raise AssertionError("unreachable until _STRICT_FRAMES flips to True")
