"""Tests for the F0-contour prosody pass."""

from __future__ import annotations

from dectalk.ph.prosody import f0_contour, looks_like_question


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
