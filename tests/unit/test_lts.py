"""Tests for the rule-based LTS fallback (`dectalk.lts.rules_us`)."""

from __future__ import annotations

import pytest

from dectalk.lts import lts


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        # LTS now annotates stress digits — primary on the first vowel.
        ("cat", ["K", "AE1", "T"]),
        ("dog", ["D", "AA1", "G"]),
        ("phone", ["F", "OW1", "N"]),
        ("thought", ["TH", "AO1", "T"]),
        ("rough", ["R", "AH1", "F"]),
        ("caught", ["K", "AO1", "T"]),
        ("eight", ["EY1", "T"]),
        ("high", ["HH", "AY1"]),
        ("nice", ["N", "AY1", "S"]),
    ],
)
def test_known_spelling_patterns(word: str, expected: list[str]) -> None:
    assert lts(word) == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        # Issue #140: vowel-picker rule gaps for common diphthong/schwa words.
        # ``hi`` -- word-final I after consonant is the long-i diphthong
        # (matches C oracle's ``hx' ay``), not the default short ``IH``.
        ("hi", ["HH", "AY1"]),
        ("pi", ["P", "AY1"]),
        ("ski", ["S", "K", "AY1"]),
        # ``ah`` -- word-final ``AH`` collapses to the open-back ``AA``
        # with a silent H (matches C oracle's ``' aa``).
        ("ah", ["AA1"]),
        ("bah", ["B", "AA1"]),
        # ``testing`` -- unstressed I in the word-final ``-ING`` suffix is
        # the centralised ``IX`` schwa (matches C oracle's ``ixnx``).
        ("testing", ["T", "EH1", "S", "T", "IX0", "NG"]),
    ],
)
def test_issue_140_vowel_mispredictions(word: str, expected: list[str]) -> None:
    """Frame-audit refresh §H: fix LTS picks of wrong vowels on common words."""
    assert lts(word) == expected


@pytest.mark.parametrize(
    "word",
    [
        # ``-ING`` rule only fires in non-monosyllables; bare ``sing`` /
        # ``ring`` / ``king`` keep the default ``IH`` short-i.
        "sing",
        "ring",
        "king",
        "ping",
        "wing",
    ],
)
def test_monosyllabic_ing_keeps_ih(word: str) -> None:
    """``-ING`` IX rule shouldn't fire on monosyllabic words."""
    out = lts(word)
    # Bare X+ING words should end in IH<digit> + NG.
    assert out[-1] == "NG"
    assert out[-2].startswith("IH"), f"{word!r} -> {out!r}; expected IH before NG"


def test_returns_list_of_strings() -> None:
    result = lts("hello")
    assert isinstance(result, list)
    assert all(isinstance(p, str) for p in result)


def test_case_insensitive() -> None:
    assert lts("hello") == lts("HELLO") == lts("Hello")


def test_empty_string_returns_empty() -> None:
    assert lts("") == []


def test_apostrophes_are_ignored() -> None:
    """Stray apostrophes shouldn't crash; they should be silently skipped."""
    out = lts("can't")
    assert "K" in out
    assert "T" in out
    assert "'" not in out


def test_c_before_e_is_soft() -> None:
    """Soft-c rule: 'cell' starts with S."""
    out = lts("cell")
    assert out[0] == "S"


def test_c_before_a_is_hard() -> None:
    """Hard-c rule: 'cat' starts with K."""
    assert lts("cat")[0] == "K"


def test_qu_pair() -> None:
    out = lts("queen")
    assert out[:2] == ["K", "W"]


def test_silent_e_in_magic_e_word() -> None:
    """Magic-E pattern: 'bake' should be B EY K, not B EY K E."""
    out = lts("bake")
    assert out == ["B", "EY1", "K"]


def test_first_vowel_gets_primary_stress() -> None:
    """Polysyllabic words should have stress 1 on the first vowel and 0 elsewhere."""
    out = lts("banana")
    # First vowel index gets digit 1, others get 0.
    digits = [p[-1] for p in out if p[-1].isdigit()]
    assert digits[0] == "1"
    assert all(d == "0" for d in digits[1:])


def test_x_expands_to_k_s() -> None:
    out = lts("box")
    assert "K" in out and "S" in out


@pytest.mark.parametrize(
    ("word", "first_phone"),
    [
        # Initial-cluster silent-letter rules. The C oracle silences
        # the leading consonant of these Greek/Latin clusters at word
        # start; the Python LTS must do the same so the first emitted
        # phoneme matches the C oracle.
        # gn- -> the G is silent, leaving N.
        ("gnaw", "N"),
        ("gnat", "N"),
        ("gnome", "N"),
        ("gnu", "N"),
        # pn- -> the P is silent, leaving N.
        ("pneumonia", "N"),
        ("pneumatic", "N"),
        # ps- -> the P is silent, leaving S.
        ("psychic", "S"),
        ("psalm", "S"),
        ("pseudo", "S"),
        # mn- -> the M is silent, leaving N.
        ("mnemonic", "N"),
    ],
)
def test_initial_cluster_silent_letter(word: str, first_phone: str) -> None:
    """``gn-/pn-/ps-/mn-`` word-initial clusters silence the leading letter."""
    out = lts(word)
    assert out, f"{word!r} produced no phonemes"
    # Strip any stress digit from the first phone for comparison.
    leading = out[0].rstrip("012")
    assert leading == first_phone, f"{word!r} -> {out!r}; expected first phone {first_phone}"


def test_initial_cluster_does_not_over_silence() -> None:
    """Silent-letter rules anchor at the word start only.

    Mid-word ``gn`` / ``pn`` / ``ps`` / ``mn`` clusters keep both letters
    (e.g. ``signal``'s G is emitted via the default G rule, not silenced
    by the gn- silent-letter rule).
    """
    # "signal" -> S IH G N AH L (the default G rule fires; gn- silent
    # rule is anchored at word start and so does not match the medial
    # GN cluster here).
    out = lts("signal")
    assert "G" in out, f"signal -> {out!r}; expected default G to be emitted"
