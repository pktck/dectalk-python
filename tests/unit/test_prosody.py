"""Tests for the F0-contour prosody pass."""

from __future__ import annotations

from dectalk.ph.prosody import (
    duration_factors,
    f0_contour,
    looks_like_question,
    split_sentences,
)


def test_empty_phonemes_returns_empty() -> None:
    assert f0_contour([]) == []


def test_statement_contour_falls() -> None:
    """A statement should start above 1.0 and end below 1.0."""
    contour = f0_contour(["HH", "AH", "L", "OW", "W", "ER", "L", "D"])
    assert contour[0] > 1.0
    assert contour[-1] < 1.0


def test_question_contour_rises() -> None:
    """A question should end higher than it starts."""
    contour = f0_contour(["W", "EH", "R", "AH", "R", "Y", "UW"], question=True)
    assert contour[-1] > contour[0]


def test_silences_reset_to_unity() -> None:
    """SIL phonemes should be at the baseline (1.0)."""
    contour = f0_contour(["HH", "AH", "SIL", "W", "ER", "L", "D"])
    assert contour[2] == 1.0


def test_final_dip_applied_to_statement() -> None:
    """The last voiced segment of a statement gets an extra dip."""
    phonemes = ["HH", "AH", "L", "OW"]
    contour = f0_contour(phonemes)
    # The final voiced phoneme should be substantially below 1.0.
    assert contour[-1] < 0.9


def test_looks_like_question() -> None:
    assert looks_like_question("are you there?")
    assert looks_like_question("really?  ")
    assert not looks_like_question("hello.")
    assert not looks_like_question("hello")


def test_single_phoneme() -> None:
    """Edge case: contour for a 1-element segment."""
    contour = f0_contour(["AH"])
    assert len(contour) == 1


def test_stress_boosts_primary_vowel_f0() -> None:
    """Primary stress should yield higher F0 than nearby unstressed phonemes.

    Compared within roughly the same declination region: AE1 (i=3) vs
    its adjacent N consonants (i=2, i=4) and AH0 (i=5). Comparing
    against the utterance-start AH0 (i=1) is unsound because that
    position has a much higher declination boost which can outweigh
    the per-phoneme stress accent.
    """
    contour = f0_contour(["B", "AH0", "N", "AE1", "N", "AH0"])
    # AE1 (primary stress) should be higher than the trailing AH0
    # (unstressed, similar declination).
    assert contour[3] > contour[5]


def test_duration_factors_match_stress_digits() -> None:
    factors = duration_factors(["B", "AH0", "N", "AE1", "N", "AH0"])
    assert factors == [1.0, 0.85, 1.0, 1.20, 1.0, 0.85]


def test_duration_factor_unaffected_for_consonants_and_silence() -> None:
    factors = duration_factors(["S", "SIL", "T"])
    assert factors == [1.0, 1.0, 1.0]


def test_duration_factor_secondary_stress() -> None:
    factors = duration_factors(["AH2"])
    assert factors[0] == 1.05


def test_split_sentences_handles_three_terminators() -> None:
    """Period, question mark, and exclamation point each end a sentence."""
    out = split_sentences("This is one. Is this two? Three!")
    assert [s for s, _ in out] == ["This is one.", "Is this two?", "Three!"]
    assert [q for _, q in out] == [False, True, False]


def test_split_sentences_passes_through_unpunctuated_text() -> None:
    out = split_sentences("hello world")
    assert out == [("hello world", False)]


def test_split_sentences_ignores_blank_input() -> None:
    assert split_sentences("") == []
    assert split_sentences("   \n\t ") == []


def test_split_sentences_keeps_trailing_fragment_after_terminator() -> None:
    """A trailing fragment with no punctuation still becomes a statement."""
    out = split_sentences("First sentence. Trailing fragment with no punct")
    assert out == [
        ("First sentence.", False),
        ("Trailing fragment with no punct", False),
    ]


def test_contour_has_natural_dynamic_range() -> None:
    """The contour for a typical utterance must span a wide F0 range.

    A flat contour (max - min < 20 %) produces audibly mechanical
    "robot" intonation. Pre-fix the smoothed contour spanned only ~16 %
    on "hello world" and ~17 % on "the quick brown fox"; the binary
    output spans roughly 50 % on the same prompts. We aim for at least
    30 % to leave room for variation across phrases.

    Per-phoneme contour jumps are intentionally larger than the audible
    threshold here — the sequencer's linear frame interpolation across
    the first half of each segment smooths them at the audio level,
    which is the right place for the smoothing to happen.
    """
    import dectalk  # noqa: PLC0415

    phones = dectalk.text_to_phonemes("the quick brown fox")
    contour = f0_contour(phones)
    voiced = [contour[i] for i, c in enumerate(phones) if c != "SIL"]
    span = max(voiced) - min(voiced)
    assert span >= 0.30, f"F0 contour span {span:.3f} < 0.30 (sounds monotone)"
