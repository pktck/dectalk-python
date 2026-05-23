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


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        # The orthographic suffix -OUGH has six different pronunciations
        # in English. Each row is one of them, with the expected ARPABET
        # phoneme stream taken from the C oracle
        # (``CAPI.convert_to_phonemes`` on the DECtalk 4.2CD library).
        # See issue #135 / PR #123 §4 (LTS audit).
        ("cough", ["K", "AO1", "F"]),  # OUGH -> AO F after C
        ("though", ["DH", "OW1"]),  # voiced TH + silent GH
        ("through", ["TH", "R", "UW1"]),  # OUGH -> UW after THR
        ("thought", ["TH", "AO1", "T"]),  # OUGH -> AO before T
        ("rough", ["R", "AH1", "F"]),  # OUGH -> AH F (default)
        ("bough", ["B", "AW1"]),  # OUGH alone -> AW after B
    ],
)
def test_ough_lexical_variants(word: str, expected: list[str]) -> None:
    """All six -OUGH pronunciations resolve correctly via LTS rules.

    The C oracle for these six words returns six phonetically distinct
    pronunciations of the same orthographic suffix. The LTS fallback
    must replicate each one — see :mod:`dectalk.lts.rules_us` for the
    ordered rule set.
    """
    assert lts(word) == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        # Latinate stress-shift rules ported from
        # ``src/dapi/src/lts/l_us_suf.c``. Each entry's expected list
        # asserts both the phoneme sequence (unchanged from the
        # grapheme rules) AND the stress digit, so a regression in
        # either dimension would fail.
        # -IC: primary stress on the vowel before the suffix.
        ("atomic", ["AE0", "T", "AA1", "M", "IH0", "K"]),
        ("magnetic", ["M", "AE0", "G", "N", "EH1", "T", "IH0", "K"]),
        ("electric", ["EH0", "L", "EH1", "K", "T", "R", "IH0", "K"]),
        ("fantastic", ["F", "AE0", "N", "T", "AE1", "S", "T", "IH0", "K"]),
        # -ITY: primary stress two vowel groups before the end of word
        # (i.e. on the last vowel of the stem before -ITY).
        ("ability", ["AE0", "B", "IH1", "L", "IH0", "T", "IY0"]),
        ("velocity", ["V", "EH0", "L", "AA1", "S", "IH0", "T", "IY0"]),
        # -ICAL: primary on the last stem vowel (stem before -ICAL).
        ("classical", ["K", "L", "AE1", "S", "S", "IH0", "K", "AE0", "L"]),
        # -ION / -IONAL: primary on the last stem vowel before -ION.
        ("tradition", ["T", "R", "AE1", "D", "IH0", "T", "IH0", "AA0", "N"]),
        ("national", ["N", "AE1", "T", "IH0", "AA0", "N", "AE0", "L"]),
    ],
)
def test_latinate_stress_shift(word: str, expected: list[str]) -> None:
    """Latinate-suffix stress-shift rules from C ``l_us_suf.c`` (issue #132).

    Without these rules ``rules_us.lts`` defaulted to "primary stress
    on the first vowel" which gave the wrong accent for words like
    ``atomic``/``ability``/``classical``/``tradition`` (where English
    shifts primary stress to the stem syllable immediately preceding
    the Latinate suffix).
    """
    assert lts(word) == expected


def test_latinate_does_not_misfire_on_short_stems() -> None:
    """Latinate stress shift only applies when the stem has a vowel.

    Words like ``ic`` (stem empty), ``it`` (no Latinate suffix) and
    monosyllables like ``tic`` (stem ``t`` has no vowel) must fall
    back to the default first-vowel stress, not crash or stress a
    non-existent stem vowel.
    """
    assert lts("ic") == ["IH1", "K"]  # whole word is the "suffix"
    assert lts("tic")[-1] == "K"  # ends in -IC but stem ``T`` has no vowel
    # Banana doesn't end in a Latinate suffix.
    out = lts("banana")
    digits = [p[-1] for p in out if p[-1].isdigit()]
    assert digits[0] == "1"


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


@pytest.mark.parametrize(
    ("word", "tail"),
    [
        # -TURE palatalisation: t->ch / _ U at the end of Latinate nouns
        # (`l_us_suf.c` suffix tables in the C source; missing from
        # this Python rule list before issue #131).
        ("nature", ["CH", "ER0"]),
        ("fixture", ["CH", "ER0"]),
        ("future", ["CH", "ER0"]),
        ("picture", ["CH", "ER0"]),
        ("culture", ["CH", "ER0"]),
        ("creature", ["CH", "ER0"]),
        # -TION palatalisation: t->sh / _ I O N $
        ("nation", ["SH", "AH0", "N"]),
        ("station", ["SH", "AH0", "N"]),
        ("motion", ["SH", "AH0", "N"]),
        # -SSION (mission, expression) -> single SH cluster
        ("mission", ["SH", "AH0", "N"]),
        ("passion", ["SH", "AH0", "N"]),
        ("session", ["SH", "AH0", "N"]),
        # -SION after consonant -> SH AH N
        ("mansion", ["SH", "AH0", "N"]),
        ("pension", ["SH", "AH0", "N"]),
        # -SION after vowel -> ZH AH N (voiced)
        ("vision", ["ZH", "AH0", "N"]),
        ("fusion", ["ZH", "AH0", "N"]),
        # -CIAN palatalisation: c->sh / _ I A N $
        ("musician", ["SH", "AH0", "N"]),
        ("physician", ["SH", "AH0", "N"]),
        ("electrician", ["SH", "AH0", "N"]),
        # -CIAL palatalisation: c->sh / _ I A L $
        ("social", ["SH", "AH0", "L"]),
        ("special", ["SH", "AH0", "L"]),
        ("official", ["SH", "AH0", "L"]),
        # -TIAL palatalisation: t->sh / _ I A L $
        ("partial", ["SH", "AH0", "L"]),
        ("initial", ["SH", "AH0", "L"]),
        # -CIOUS / -TIOUS palatalisation
        ("delicious", ["SH", "AH0", "S"]),
        ("gracious", ["SH", "AH0", "S"]),
        ("cautious", ["SH", "AH0", "S"]),
    ],
)
def test_latinate_suffix_palatalisation(word: str, tail: list[str]) -> None:
    """Latinate `-TURE`/`-TION`/`-CIAN`/`-CIAL`/`-SION` palatalise to SH/ZH/CH.

    Without these rules, ``rules_us.lts`` emits literal T/S/C clusters
    (e.g. ``nature -> N AE1 T Y UW0 R`` instead of ``N AE1 CH ER0``).
    See ``docs/c_audit/lts.md`` §5.3-5.4 for the audit gap; see the C
    suffix tables in ``l_us_suf.c`` for the reference behaviour.
    """
    out = lts(word)
    assert out[-len(tail) :] == tail, f"{word!r} -> {out!r}; expected suffix {tail!r}"
