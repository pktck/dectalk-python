"""Issue #248: ``[:phoneme on]`` is a state-only directive.

DECtalk's ``[:phoneme on/off/asky/arpabet/speak/silent]`` mutate the
``pKsd_t->phoneme_mode`` bitfield (``cmd/cm_copt.c`` ``cm_cmd_phoneme``,
faithfully modelled by :func:`dectalk.cmd.commands._cmd_phoneme`). The
bitfield only selects how ``[...]`` bracket blocks are interpreted
(``cmd/cm_pars.c:361`` / ``:1454``); plain text OUTSIDE brackets is always
run through LTS. So a segment body after a ``[:phoneme ...]`` directive is
spoken normally, never re-interpreted as a raw phoneme stream.

Before this fix the Python front-end flipped a boolean ``phoneme_mode`` on
``[:phoneme on]`` and then treated the whole following body as raw
phonemes — emitting an EMPTY phoneme stream (and mangled/short audio) for
ordinary text like ``[:phoneme on] hello``.

These are fast-lane pins (no C oracle needed): the expected DECtalk
phoneme byte strings were captured from ``CAPI.convert_to_phonemes`` on the
shipped 4.3 oracle and are byte-identical to the Python front-end. The
byte-exact WAV equality vs the oracle is asserted separately by
``tests/parity/test_vtm1_pcm_parity.py`` (c_oracle lane).
"""

from __future__ import annotations

from dectalk.api.speak import text_to_dectalk_phonemes


def _phon(text: str) -> bytes:
    return text_to_dectalk_phonemes(text, lang="us", lts_fallback=True)


def test_phoneme_on_speaks_following_text_normally() -> None:
    # ``[:phoneme on] hello`` -> the WORD "hello" (oracle stream
    # ``hxaxll' ow``), exactly like bare ``hello``. Pre-#248 this was b"".
    assert _phon("[:phoneme on] hello") == b"hxaxll' ow"
    assert _phon("[:phoneme on] hello") == _phon("hello")
    assert _phon("[:phoneme on] hello world") == _phon("hello world")


def test_phoneme_directives_are_stream_invariant_for_plain_text() -> None:
    # Every ``[:phoneme ...]`` keyword leaves a plain-text body's phoneme
    # stream identical to the un-prefixed text: the directive is state-only.
    for text in ("hello", "hello world", "the quick brown fox", "BBC"):
        base = _phon(text)
        assert base, f"expected non-empty stream for {text!r}"
        for directive in (
            "[:phoneme on] ",
            "[:phoneme off] ",
            "[:phoneme asky on] ",
            "[:phoneme arpabet on] ",
            "[:phoneme speak] ",
            "[:phoneme silent] ",
        ):
            assert _phon(directive + text) == base, (directive, text)


def test_phoneme_on_dectalk_phonemic_body_no_crash_and_mode_invariant() -> None:
    # Issue #248's original repro: ``[:phoneme on] hxeh4loh]``. The body is
    # NOT bracketed, so C (and now Python) LTS it as a literal token rather
    # than phonemes. The fix guarantees it (a) renders without an exception
    # and (b) is phoneme-mode-INVARIANT: identical to the bare token, with
    # or without the directive. (The residual C/Python *sample-count*
    # divergence on this token — C splits the embedded ``4`` into "four" —
    # is a digit-in-word LTS gap in the numeric lane, orthogonal to phoneme
    # state and reproducible with no ``[:phoneme]`` directive at all.)
    bare = _phon("hxeh4loh]")
    assert bare, "expected a non-empty (crash-free) stream"
    assert _phon("[:phoneme on] hxeh4loh]") == bare
    assert _phon("[:phoneme off] hxeh4loh]") == bare
