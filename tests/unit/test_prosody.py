"""Tests for the F0-contour prosody pass."""

from __future__ import annotations

from dectalk.ph.prosody import duration_factors, f0_contour, looks_like_question


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


def test_no_large_adjacent_f0_jumps_in_typical_utterance() -> None:
    """Adjacent phonemes must not differ by more than ~7 % of F0.

    Larger adjacent steps are heard as choppy because each phoneme
    latches a fixed F0 for its glottal cycles. Pre-smoothing this same
    "hello world" contour had adjacent jumps up to 19 %.
    """
    from itertools import pairwise  # noqa: PLC0415  # local import keeps prosody tests light

    import dectalk  # noqa: PLC0415

    phones = dectalk.text_to_phonemes("hello world")
    contour = f0_contour(phones)
    voiced = [contour[i] for i, c in enumerate(phones) if c != "SIL"]
    max_jump = max(abs(b - a) for a, b in pairwise(voiced))
    assert max_jump <= 0.07, f"max adjacent F0 jump {max_jump:.3f} > 7 %"
