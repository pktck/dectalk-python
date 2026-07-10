"""Runtime stress-assignment parity for issue #280.

Two front-end behaviours the C engine applies at speak time, pinned
against byte-for-byte captures of ``TextToSpeechConvertToPhonemes``
(fresh oracle, 2026-07-10):

1. **Possessive ``its`` secondary stress.** The runtime dictionary
   source ``Dic_us.txt`` (the file the shipped ``dtalk_us.dic`` is
   compiled from — NOT ``Dic_us_2002.txt``) stores the possessive
   with a leading stress mark: ``its,N,`Its`` (line 7372). The
   contraction row ``it's,N,Its`` (line 7362) is unstressed. There is
   no positional rule — C emits ``` iht s`` in every sentence
   position. Mirrored by the ``ITS IH2 T S`` lexicon row.

2. **First-verbs stress is per-sentence, not per-utterance.** The
   ``ls_task.c`` ``verbs[6]`` table (lines 4606-4614) gives
   are/had/is/was/were/will an S2-stressed fixed phoneme sequence via
   ``ls_task_lookup_first_verbs`` (line 4642), which
   ``ls_task_set_what_state`` (line 1677) runs only while
   ``wstate == UNK_WH``. ``ls_task_do_right_punct`` resets
   ``wstate = UNK_WH`` after ``.`` / ``?`` / ``!`` (lines ~1250 /
   ~1275 / ~1291) — but NOT after ``,`` / ``;`` / ``:`` (the comma
   case only sends the COMMA phone). So the stressed form fires at
   the start of *every sentence* in an utterance, and never after a
   mere clause break.
"""

from __future__ import annotations

import pytest

from dectalk.api.speak import text_to_dectalk_phonemes

# ---------------------------------------------------------------------------
# Possessive ``its`` (S2 from the Dic_us.txt row) vs ``it's`` (unstressed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Position-invariant S2 on the possessive: isolated, sentence-
        # initial, medial (both former corpus-allowlist prompts).
        ("its", b"` iht s "),
        ("its color is red", b"` iht s   k ' ahllrr  ihz   r ' ehd "),
        ("every dog has its day", b"' ehv r iy  d ' aog   hxehz   ` iht s   d ' ey"),
        (
            "don't judge a book by its cover",
            b"d ' own t   jh' ahjh  ^ ax  b ' uhk   b ay  ` iht s   k ' ahv rr",
        ),
        # The contraction stays unstressed (``it's,N,Its`` — no mark).
        ("it's", b"iht s "),
        ("it's raining", b"iht s   r ' eyn ixnx"),
    ],
)
def test_possessive_its_carries_dictionary_s2(text: str, expected: bytes) -> None:
    """Possessive ``its`` renders ``` iht s`` in every position."""
    assert text_to_dectalk_phonemes(text) == expected


# ---------------------------------------------------------------------------
# First-verbs table: sentence-initial S2, including mid-utterance sentences
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Utterance-initial (the previously-covered case).
        ("is it raining", b"` ihz   iht   r ' eyn ixnx"),
        ("will you come", b"w ` ihlx  yx` uw  ) k ` ahm "),
        ("had he gone", b"hx` ehd   hxiy  g ` aon "),
        # Mid-utterance sentence starts: ``.`` / ``!`` / ``?`` reset
        # C's wstate, so the S2 form fires again.
        ("wait. will you come", b"w ' eyt . w ` ihlx  yx` uw  ) k ` ahm "),
        (
            "the dog is happy. is he friendly",
            b"dhax  d ' aog   ihz   hx' aep iy. ` ihz   hxiy  f r ' ehn d lliy",
        ),
        ("stop! are you there", b"s t ' aop ! ` aar   yx` uw  dheyr "),
        ("go now? are you sure", b") g ' ow  n ` aw? ` aar   yx` uw  sh' uwr "),
    ],
)
def test_first_verbs_stress_at_every_sentence_start(text: str, expected: bytes) -> None:
    """are/had/is/was/were/will take the verbs-table S2 form per sentence."""
    assert text_to_dectalk_phonemes(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Clause breaks do NOT reset wstate: the lexicon's unstressed
        # form is kept after ``,`` (and the medial form generally).
        ("yes, is it raining", b"yx' ehs , ihz   iht   r ' eyn ixnx"),
        ("however, was he there", b"hxaw` ehv rr, w axz   hxiy  dheyr "),
        ("he said, will you come", b"hxiy  ) s ` ehd , w ihll  yx` uw  ) k ` ahm "),
        ("he had gone", b"hxiy  hxehd   g ` aon "),
    ],
)
def test_first_verbs_stay_unstressed_after_clause_breaks(text: str, expected: bytes) -> None:
    """Commas/medial positions keep the unstressed dictionary form."""
    assert text_to_dectalk_phonemes(text) == expected
