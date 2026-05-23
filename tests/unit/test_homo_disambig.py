"""Tests for the form-class homograph disambiguator.

Covers :mod:`dectalk.lts.homo_disambig` (issue #144 / LTS audit §2).

The data table :data:`~dectalk.lts.homo_disambig.HOMOGRAPH_FC_BITS`
encodes the per-entry FC bits (noun / verb / adj) for every word
that ships both a ``,P,`` and ``,S,`` row in ``Dic_us_2002.txt``.
The disambiguator threads those bits through the 27-rule
:data:`~dectalk.lts.homo_table.homo_table` from ``ls_homo.h`` to
pick the right reading from sentence context.

The acceptance criterion in issue #144 is the noun/verb minimal-pair
audit (10 word pairs * 2 contexts each = 20 utterances) hitting the
right stress pattern under the article (``a`` / ``the``) -> noun
context and the pronoun (``I``) -> verb context.
"""

from __future__ import annotations

import pytest

from dectalk.api.speak import text_to_dectalk_phonemes
from dectalk.dic.form_class_bits import (
    FC_ART,
    FC_AUX,
    FC_BE,
    FC_NOUN,
    FC_POS,
    FC_PREP,
    FC_PRON,
    FC_TO,
    FC_VERB,
)
from dectalk.lts.homo_disambig import (
    HOMOGRAPH_FC_BITS,
    disambiguate,
    form_class_of,
    homograph_fc_masks,
)


def test_homograph_table_covers_audit_words() -> None:
    """The audit §2 names 10 noun/verb pairs; all must be in the table."""
    audit_words = (
        "RECORD",
        "OBJECT",
        "PRESENT",
        "INCREASE",
        "DESERT",
        "CONTRACT",
        "PROJECT",
        "PERMIT",
        "REBEL",
        "PROGRESS",
        "PROTEST",
        "SUSPECT",
        "SUBJECT",
        "CONDUCT",
    )
    for word in audit_words:
        assert word in HOMOGRAPH_FC_BITS, f"audit word {word!r} missing from table"


def test_homograph_table_has_distinct_p_s_roles() -> None:
    """Every entry should encode different P vs S roles.

    A homograph that ships two entries with identical FC masks would
    indicate a data-collection bug (both readings would carry the
    same POS).
    """
    same: list[str] = []
    for word, (p_mask, s_mask) in HOMOGRAPH_FC_BITS.items():
        if p_mask == s_mask and p_mask != 0:
            same.append(word)
    # ``BATON`` and ``READ`` legitimately have identical noun roles
    # because both ``baton,P,...`` and ``baton,S,...`` are noun
    # entries in the source dict (they're stress-pattern variants
    # of the same POS, not minimal pairs). Allow that.
    legit_dupes = {"BATON", "READ"}
    unexpected = [w for w in same if w not in legit_dupes]
    assert not unexpected, f"unexpected identical P/S masks for: {unexpected}"


def test_homograph_fc_masks_expand_to_full_fc_bits() -> None:
    """``homograph_fc_masks`` returns full FC_NOUN / FC_VERB bitfields."""
    p_fc, s_fc = homograph_fc_masks("RECORD") or (0, 0)
    # RECORD,P is noun (mask=1) → FC_NOUN expansion.
    assert p_fc == FC_NOUN
    # RECORD,S is verb (mask=2) → FC_VERB expansion.
    assert s_fc == FC_VERB


def test_homograph_fc_masks_returns_none_for_non_homograph() -> None:
    """A regular non-homograph word returns ``None`` (no entry)."""
    assert homograph_fc_masks("HELLO") is None
    assert homograph_fc_masks("DOG") is None


def test_form_class_of_known_function_words() -> None:
    """Common articles / pronouns / prepositions get the right FC bit."""
    assert form_class_of("a") & FC_ART
    assert form_class_of("the") & FC_ART
    assert form_class_of("an") & FC_ART
    assert form_class_of("I") & FC_PRON
    assert form_class_of("you") & FC_PRON
    assert form_class_of("to") & FC_TO
    assert form_class_of("will") & FC_AUX
    assert form_class_of("is") & FC_BE
    assert form_class_of("of") & FC_PREP
    assert form_class_of("my") & FC_POS


def test_form_class_of_unknown_defaults_to_noun() -> None:
    """Unknown words default to FC_NOUN per the C BATS#705 fallback."""
    assert form_class_of("aardvark") == FC_NOUN
    assert form_class_of("xyzzy") == FC_NOUN


def test_form_class_of_none_returns_zero() -> None:
    """``None`` (no previous word, sentence boundary) returns 0."""
    assert form_class_of(None) == 0


def test_disambiguate_article_picks_noun_reading() -> None:
    """``a record`` / ``the record`` → primary entry (noun reading)."""
    assert disambiguate("RECORD", prev_word="a") == "P"
    assert disambiguate("RECORD", prev_word="the") == "P"
    assert disambiguate("RECORD", prev_word="an") == "P"


def test_disambiguate_pronoun_picks_verb_reading() -> None:
    """``I record`` / ``you record`` → secondary entry (verb reading)."""
    assert disambiguate("RECORD", prev_word="I") == "S"
    assert disambiguate("RECORD", prev_word="you") == "S"
    assert disambiguate("RECORD", prev_word="we") == "S"


def test_disambiguate_handles_reversed_p_s_assignment() -> None:
    """``present`` ships P=verb / S=noun (opposite of ``record``).

    The disambiguator should pick S for ``a present`` (article →
    noun) and P for ``I present`` (pronoun → verb), regardless
    of which letter happens to encode which reading in the source
    dictionary.
    """
    assert disambiguate("PRESENT", prev_word="a") == "S"
    assert disambiguate("PRESENT", prev_word="I") == "P"


def test_disambiguate_to_infinitive_picks_verb() -> None:
    """``to record`` / ``to permit`` → verb (FC_TO context rule).

    Note PERMIT ships P=verb / S=noun (opposite letter-assignment from
    RECORD), so the "verb" letter is ``P``.
    """
    assert disambiguate("RECORD", prev_word="to") == "S"
    assert disambiguate("PERMIT", prev_word="to") == "P"


def test_disambiguate_auxiliary_picks_verb() -> None:
    """``will record`` / ``can present`` → verb (FC_AUX context rule)."""
    assert disambiguate("RECORD", prev_word="will") == "S"
    # PRESENT has reversed P/S, so verb = P.
    assert disambiguate("PRESENT", prev_word="will") == "P"


def test_disambiguate_adverb_fall_through() -> None:
    """When prev is an adverb, look at prev-prev word.

    Mirrors the GL 3/3/1997 rule in ``ls_homo.c`` (lines 397-400).
    ``I never record`` → verb (the pronoun is two back, not one).
    """
    assert disambiguate("RECORD", prev_word="never", prev_prev_word="I") == "S"


def test_disambiguate_sentence_initial_returns_primary() -> None:
    """Sentence-initial word returns P (mirrors C ``cur_word_index==1``)."""
    assert disambiguate("RECORD", prev_word=None, is_sentence_initial=True) == "P"


def test_disambiguate_unknown_word_returns_primary() -> None:
    """Words not in the homograph table default to P (no-op)."""
    assert disambiguate("HELLO", prev_word="I") == "P"


def test_text_to_dectalk_phonemes_emits_noun_after_article() -> None:
    """End-to-end: ``a record`` / ``the object`` use the noun reading."""

    # ``a record`` should use RECORD|P (noun = stress on first syllable).
    out = text_to_dectalk_phonemes("a record")
    # Primary stress (encoded as ``'``) precedes the first vowel of
    # ``record`` → ``r ' ehk rrd`` rather than ``r ehk ' owr d``.
    assert b"' ehk" in out, f"expected noun-form stress in {out!r}"

    out = text_to_dectalk_phonemes("the object")
    # OBJECT|P = AA1 B JH EH0 K T → ``' aab jhehk t``.
    assert b"' aab" in out, f"expected noun-form stress in {out!r}"


def test_text_to_dectalk_phonemes_emits_verb_after_pronoun() -> None:
    """End-to-end: ``I record`` / ``I object`` use the verb reading."""

    # ``I record`` should use RECORD|S (verb = stress on second syllable).
    out = text_to_dectalk_phonemes("I record")
    # Verb stress falls on the second vowel ``ow`` (R AH0 K OW1 R D).
    assert b"' owr d" in out, f"expected verb-form stress in {out!r}"

    out = text_to_dectalk_phonemes("I object")
    # OBJECT|S = AH0 B JH EH1 K T → ``axb jh' ehk t``.
    assert b"jh' ehk" in out, f"expected verb-form stress in {out!r}"


def test_text_to_dectalk_phonemes_emits_verb_after_to() -> None:
    """``to permit`` should use the verb reading (FC_TO rule)."""

    out = text_to_dectalk_phonemes("to permit")
    # PERMIT|S = P ER1 M IH0 T → ``p ' rrm iht`` (P) vs
    # PERMIT|P = P ER0 M IH1 T → ``p rrm ' iht`` (S, verb).
    assert b"' iht" in out, f"expected verb-form stress in {out!r}"


def test_text_to_dectalk_phonemes_audit_15_match() -> None:
    """Acceptance: the 14 articles+pronouns ↔ noun/verb pairs from issue #144.

    The audit document lists 10 noun/verb minimal pairs; this test
    asserts that for each, the article-context picks the noun stress
    pattern and the pronoun-context picks the verb stress pattern.
    The 15-utterance acceptance criterion from issue #144 reflects
    the audit's "15/20 diverge" baseline — after this fix, all 20
    articulate correctly at the form-class level (the remaining
    leading-marker fingerprint is tracked in separate audit items).
    """

    # (word, article_context, pronoun_context, noun_stress_fingerprint,
    # verb_stress_fingerprint). Stress fingerprints are the ASCII
    # ``' <vowel>`` (primary stress) substring that should appear in
    # the output of each context.
    cases: list[tuple[str, str, str, bytes, bytes]] = [
        ("record", "a record", "I record", b"' ehk", b"' owr"),
        ("object", "the object", "I object", b"' aab", b"' ehk"),
        ("present", "a present", "I present", b"' ehz", b"' ehn"),
        ("desert", "the desert", "I desert", b"' ehz", b"' rrt"),
        ("contract", "the contract", "I contract", b"' aan", b"' aek"),
        ("project", "the project", "I project", b"' aaj", b"' ehk"),
        ("rebel", "the rebel", "I rebel", b"' ehb", b"' ehll"),
        ("progress", "the progress", "I progress", b"' aag", b"' ehs"),
        ("protest", "the protest", "I protest", b"' owt", b"' ehs"),
        ("conduct", "the conduct", "I conduct", b"' aan", b"' ahk"),
    ]
    for _word, art_ctx, pron_ctx, noun_stress, verb_stress in cases:
        noun_out = text_to_dectalk_phonemes(art_ctx)
        verb_out = text_to_dectalk_phonemes(pron_ctx)
        assert noun_stress in noun_out, (
            f"{art_ctx!r}: expected noun stress {noun_stress!r} in {noun_out!r}"
        )
        assert verb_stress in verb_out, (
            f"{pron_ctx!r}: expected verb stress {verb_stress!r} in {verb_out!r}"
        )


def test_homograph_fc_bits_table_size() -> None:
    """At least 138 entries (the count called out in issue #144)."""
    # The Dic_us_2002.txt scan finds 140 unique words shipping both
    # ``,P,`` and ``,S,`` rows. The issue body conservatively quotes
    # "138 noun/verb minimal-pair P/S homographs" — well within the
    # actual count. Guard against accidental data loss.
    min_expected = 138
    assert len(HOMOGRAPH_FC_BITS) >= min_expected, (
        f"expected ≥{min_expected} homograph entries, found {len(HOMOGRAPH_FC_BITS)}"
    )


@pytest.mark.parametrize(
    ("word", "article", "pronoun"),
    [
        ("record", "a", "I"),
        ("object", "the", "I"),
        ("present", "a", "I"),
        ("contract", "the", "I"),
        ("project", "the", "I"),
        ("permit", "the", "I"),
        ("rebel", "the", "I"),
        ("progress", "the", "I"),
        ("protest", "the", "I"),
        ("suspect", "the", "I"),
        ("subject", "the", "I"),
        ("conduct", "the", "I"),
        ("desert", "the", "I"),
    ],
)
def test_disambiguate_picks_different_entries_per_context(
    word: str, article: str, pronoun: str
) -> None:
    """The disambiguator picks DIFFERENT readings for article vs pronoun.

    Whichever letter (P or S) encodes the noun in this entry, the
    pronoun context should pick the opposite letter (the verb).
    """
    article_choice = disambiguate(word, prev_word=article)
    pronoun_choice = disambiguate(word, prev_word=pronoun)
    assert article_choice != pronoun_choice, (
        f"{word!r}: article and pronoun contexts picked the same form"
    )
