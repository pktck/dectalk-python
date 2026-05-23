"""Per-stage parity (issue #150): CMD — parsed command token stream.

The CMD stage of the DECtalk pipeline consumes the KERNEL's text byte
stream, runs ``cm_pars_icommand``/``cm_text_getclause``/character
classifiers, and emits a stream of 16-bit tokens (ASCII bytes for
literal characters, plus PFONT-flagged language / command / phoneme
tokens) into the LTS stage's input pipe. The Phase-A.4 dump hook in
``tests/parity/c_patches/0003-cmd-stage-dump-hooks.patch`` captures
each token as it crosses that boundary into ``cmd.dump``.

This test asserts:
- the dump is well-formed and the per-prompt token count is plausible;
- repeated runs are byte-identical (no cross-call CMD state pollution);
- (xfail) Python CMD-stage tokens match the C oracle's tokens.

Today the Python port goes text→Python-tokenize→ARPABET, skipping the
intermediate CMD 16-bit token form. The strict equality check is
expected-fail and serves as the gate for the Phase-D CMD port: when a
Python CMD stage exists, flip ``_STRICT_TOKENS`` to ``True``.
"""

from __future__ import annotations

import pytest

from dectalk._capi import CAPI

from ._stage_helpers import STAGE_CORPUS, parse_token_dump, skipif_no_oracle

_STRICT_TOKENS: bool = False

pytestmark = [pytest.mark.c_oracle, skipif_no_oracle]


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI handle."""
    return CAPI()


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_cmd_dump_has_input_chars(text: str, capi: CAPI) -> None:
    """The CMD token stream begins with the input text's ASCII byte values.

    In SINGLE_THREADED builds (our oracle), ``lts_loop`` is called
    once per token by the CMD stage. The first N tokens for a plain
    ASCII input prompt are the ASCII code points of the input
    characters; subsequent tokens are the dispatcher's flush sentinels
    (``0x000b``, ``0x1f0a``/``0x1f0b`` PFONT-flagged markers).
    """
    payload = capi.dump_pipeline(text, ["cmd"])["cmd"]
    assert payload, "cmd dump empty — patch not applied?"
    tokens = parse_token_dump(payload, header_prefix=b"cmd_write")
    # Find ASCII letters/digits/spaces among the tokens; these come
    # from the input verbatim.
    ascii_tokens = [tok for tok in tokens if 0x20 <= tok < 0x7F]
    recovered = bytes(ascii_tokens).decode("ascii", errors="replace")
    for ch in text:
        if ch in " ":
            continue
        assert ch in recovered, (
            f"CMD dump for {text!r} missing input char {ch!r}; recovered: {recovered!r}"
        )


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_cmd_dump_has_pfont_markers(text: str, capi: CAPI) -> None:
    """Non-ASCII PFONT-flagged tokens appear after the literal text.

    The CMD stage frames each token with its PFONT (ASCII / PHONEME /
    LANGUAGE / COMMAND) classification in the upper nibble. The bit
    pattern ``0x1f00`` (PFNULL or similar dispatcher sentinels) shows
    up at end-of-text in our corpus. Asserting at least one non-ASCII
    token confirms the CMD stage actually classified — it didn't just
    pass bytes through.
    """
    payload = capi.dump_pipeline(text, ["cmd"])["cmd"]
    tokens = parse_token_dump(payload, header_prefix=b"cmd_write")
    non_ascii = [tok for tok in tokens if tok >= 0x100]
    assert non_ascii, f"CMD dump for {text!r} has no PFONT-flagged tokens; got {tokens!r}"


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_cmd_dump_is_deterministic(text: str, capi: CAPI) -> None:
    """Back-to-back CMD dumps for the same input are byte-identical."""
    a = capi.dump_pipeline(text, ["cmd"])["cmd"]
    b = capi.dump_pipeline(text, ["cmd"])["cmd"]
    assert a == b, f"CMD dump nondeterministic for {text!r}"


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_cmd_python_tokens_match_c(text: str, capi: CAPI) -> None:
    """Python CMD-stage 16-bit token stream matches the C oracle.

    Currently expected-fail: the Python port skips the CMD 16-bit
    token form. Flip ``_STRICT_TOKENS`` to ``True`` once a Python
    CMD stage exposes its token stream (Phase D CMD port).
    """
    if not _STRICT_TOKENS:
        pytest.xfail("Python CMD-stage 16-bit token form not yet ported (issue #150)")
    raise AssertionError("unreachable until _STRICT_TOKENS flips to True")
