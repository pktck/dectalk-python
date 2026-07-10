"""Tests for the form-class homograph disambiguator (issue #295).

Covers the faithful ``ls_homo_homo`` port in
:mod:`dectalk.lts.homo_disambig`, the runtime form-class sidecar it
consumes (:func:`dectalk.dic.markers.load_formclass_lexicon`), the
suffix-engine form-class mimic
(:func:`dectalk.lts.suffix_formclass.suffix_form_class`), and the
end-to-end wiring in :func:`dectalk.api.speak.text_to_dectalk_phonemes`.

The end-to-end expectations are byte-for-byte captures of the C
oracle's ``TextToSpeechConvertToPhonemes`` output for each prompt
(fresh oracle, 2026-07-10, issue #295) — no oracle is needed at test
time.
"""

from __future__ import annotations

import pytest

from dectalk.api.speak import text_to_dectalk_phonemes
from dectalk.dic.form_class_bits import (
    FC_ADJ,
    FC_ADV,
    FC_BEV,
    FC_CHARACTER,
    FC_FUNC,
    FC_HOMOGRAPH,
    FC_ING,
    FC_NOUN,
    FC_PREP,
    FC_PRON,
    FC_TO,
    FC_VERB,
)
from dectalk.dic.markers import emits_vpstart, load_formclass_lexicon
from dectalk.lts.homo_disambig import (
    BATS705_DEFAULT_FC,
    resolved_form_class,
    select_homograph_entry,
)
from dectalk.lts.suffix_formclass import suffix_form_class

# Built masks of the runtime dictionary rows exercised below (values
# verified against both Dic_us.txt + the dic_comm.c homograph flags
# and the masks embedded in the shipped dtalk_us.dic binary).
_P = FC_CHARACTER | FC_HOMOGRAPH
_S = FC_HOMOGRAPH
CLOSE_P = FC_VERB | _P  # kl'oz
CLOSE_S = FC_ADJ | _S  # kl'os
WIND_P = FC_NOUN | _P  # w'Ind
WIND_S = FC_VERB | _S  # w'And
LEAD_P = FC_VERB | _P  # l'id
LEAD_S = FC_NOUN | _S  # l'Ed
TEAR_P = FC_VERB | _P  # t'er
TEAR_S = FC_NOUN | _S  # t'ir
WAS_FC = FC_BEV | FC_VERB | FC_FUNC
THE_FC = 0x00000004 | FC_FUNC  # FC_ART | FC_FUNC
TO_FC = FC_PREP | FC_TO | FC_FUNC
LIKE_FC = FC_ADV | FC_PREP | FC_VERB | FC_FUNC | 0x00000001  # + FC_ADJ
WE_FC = FC_PRON | FC_FUNC


# ---------------------------------------------------------------------------
# select_homograph_entry — the ls_homo_homo rule loop
# ---------------------------------------------------------------------------


def test_first_word_returns_primary() -> None:
    """The sentence's first word takes the P entry (fc_index==1 branch)."""
    reading, rule = select_homograph_entry(WIND_P, WIND_S, first_word=True)
    assert reading == "P"
    assert rule is None


def test_bev_context_selects_adjective_reading() -> None:
    """``was close`` → rule 8 ([+adj] / [bev]) picks the S (kl'os) entry."""
    reading, rule = select_homograph_entry(CLOSE_P, CLOSE_S, prev_fc=WAS_FC)
    assert reading == "S"
    assert rule is not None
    assert rule.h_select == FC_ADJ
    assert rule.h_context == FC_BEV


def test_article_context_eliminates_verb() -> None:
    """``the close`` → rule 22 (ART elim VERB) swaps to the S entry."""
    reading, rule = select_homograph_entry(CLOSE_P, CLOSE_S, prev_fc=THE_FC)
    assert reading == "S"
    assert rule is not None
    assert rule.h_elim == FC_VERB


def test_article_context_keeps_primary_when_secondary_is_verb() -> None:
    """``the wind`` → rule 22's elim bit matches the *secondary* → keep P."""
    reading, _rule = select_homograph_entry(WIND_P, WIND_S, prev_fc=THE_FC)
    assert reading == "P"


def test_to_context_selects_verb_reading() -> None:
    """``to wind`` → rule 10 (TO sel VERB): P lacks VERB, S carries it."""
    reading, rule = select_homograph_entry(WIND_P, WIND_S, prev_fc=TO_FC)
    assert reading == "S"
    assert rule is not None
    assert rule.h_context == FC_TO


def test_adverb_fall_through_uses_prev_prev_word() -> None:
    """``we like wind`` → ``like`` is an adverb, so rule 20 sees ``we``.

    Mirrors the GL 3/3/1997 fall-through (ls_homo.c lines 402-406):
    the PRON context two words back selects the verb reading.
    """
    reading, rule = select_homograph_entry(
        WIND_P, WIND_S, prev_fc=LIKE_FC, prev_prev_fc=WE_FC
    )
    assert reading == "S"
    assert rule is not None
    assert rule.h_context == FC_PRON


def test_adverb_fall_through_requires_third_word() -> None:
    """The fall-through needs ``fc_index >= 3`` — no prev-prev, no rule."""
    reading, _rule = select_homograph_entry(
        WIND_P, WIND_S, prev_fc=LIKE_FC, prev_prev_fc=None
    )
    assert reading == "P"


def test_unknown_previous_word_noun_defaults() -> None:
    """BATS#705: a zero prev mask reads as FC_NOUN (no rule keys on it)."""
    assert BATS705_DEFAULT_FC == FC_NOUN
    reading, rule = select_homograph_entry(TEAR_P, TEAR_S, prev_fc=0)
    assert reading == "P"
    assert rule is None


def test_verb_context_selects_noun_reading() -> None:
    """``roads lead`` → rule 26 (VERB sel NOUN) picks the S (l'Ed) entry.

    The ``-s`` suffix mask (FC_NOUN|FC_VERB) on ``roads`` carries the
    VERB bit that fires the rule.
    """
    roads_fc = FC_NOUN | FC_VERB
    reading, rule = select_homograph_entry(LEAD_P, LEAD_S, prev_fc=roads_fc)
    assert reading == "S"
    assert rule is not None
    assert rule.h_context == FC_VERB
    assert rule.h_select == FC_NOUN


def test_suffix_rule_gates_on_current_word_mask() -> None:
    """``winding`` → rule 2 (ING suffix, elim NOUN) picks w'And.

    With a zero current mask the suffix rules are skipped and the ART
    context keeps the primary instead.
    """
    reading, rule = select_homograph_entry(
        WIND_P, WIND_S, cur_fc=FC_ING, prev_fc=THE_FC
    )
    assert reading == "S"
    assert rule is not None
    assert rule.h_suffix == FC_ING
    reading2, _rule2 = select_homograph_entry(WIND_P, WIND_S, cur_fc=0, prev_fc=THE_FC)
    assert reading2 == "P"


def test_resolved_form_class_write_back_semantics() -> None:
    """Mirrors ls_dict/ls_homo fc_struct write-backs."""
    # Plain dictionary hit: takes the selected entry's mask.
    assert resolved_form_class(CLOSE_S, cur_fc=0, rule=None) == CLOSE_S
    # Suffix-derived hit with a context rule: keeps the suffix mask,
    # ORs in the homograph flag.
    sfx = FC_NOUN | FC_VERB
    assert resolved_form_class(TEAR_S, cur_fc=sfx, rule=None) == sfx | FC_HOMOGRAPH
    # Suffix-gated rule fired: overwritten with the selected mask.
    _, ing_rule = select_homograph_entry(WIND_P, WIND_S, cur_fc=FC_ING, prev_fc=THE_FC)
    assert ing_rule is not None
    assert resolved_form_class(WIND_S, cur_fc=FC_ING, rule=ing_rule) == WIND_S


# ---------------------------------------------------------------------------
# Form-class sidecar + VPSTART rule
# ---------------------------------------------------------------------------


def test_formclass_sidecar_carries_runtime_masks() -> None:
    """Spot-check sidecar masks against the shipped dtalk_us.dic values."""
    fc = load_formclass_lexicon(lang="us")
    assert fc["CLOSE|P"] == 0x82020000
    assert fc["CLOSE|S"] == 0x80000001
    assert fc["WIND|P"] == 0x82000400
    assert fc["WIND|S"] == 0x80020000
    assert fc["WAS"] == 0x00820020
    assert fc["CAME"] == 0x02020000
    assert fc["OURS"] == 0x00802000
    # Unpaired homograph-field rows surface under the bare key.
    assert fc["REPEAT"] == 0x80020000
    assert "REPEAT|S" not in fc


def test_emits_vpstart_on_built_masks() -> None:
    """The ls_dict.c VPSTART rule on built (flagged) masks.

    A pure-verb P row fires via VPHRASE containment; an S row never
    fires (the homograph flag breaks the equality); a VERB|CHARACTER
    ordinary row (``came``) fires; a plain pure-verb row (``hear``)
    fires via the equality.
    """
    assert emits_vpstart(LEAD_P)
    assert not emits_vpstart(WIND_P)
    assert not emits_vpstart(WIND_S)
    assert not emits_vpstart(CLOSE_S)
    assert emits_vpstart(0x02020000)  # came: VERB|CHARACTER
    assert emits_vpstart(FC_VERB)  # hear: exactly FC_VERB
    assert not emits_vpstart(FC_VERB | FC_NOUN)


# ---------------------------------------------------------------------------
# Suffix form-class mimic
# ---------------------------------------------------------------------------


def test_suffix_form_class_strip_rules() -> None:
    """-s / -ed / -ing strip rules carry the C table's masks."""
    fc = load_formclass_lexicon(lang="us")
    words = frozenset(k.split("|", 1)[0] for k in fc)
    assert suffix_form_class("roads", words) == (FC_NOUN | FC_VERB, "ROAD", "s")
    assert suffix_form_class("tears", words) == (FC_NOUN | FC_VERB, "TEAR", "s")
    assert suffix_form_class("winding", words) == (FC_ING, "WIND", "ing")
    assert suffix_form_class("laughed", words) == (0x00000080, "LAUGH", "ed")


def test_suffix_form_class_fc_rules() -> None:
    """FC-tag rules fire on the bare suffix match (no root lookup)."""
    fc = load_formclass_lexicon(lang="us")
    words = frozenset(k.split("|", 1)[0] for k in fc)
    # ``-man`` FC rule tags unknown compounds as nouns.
    assert suffix_form_class("postman", words) == (FC_NOUN, None, "man")
    # The whole word may not be consumed: the str_vowel guard stops
    # the match at the word's first vowel, so bare ``man`` stays 0
    # (and the BATS#705 noun default covers it at homograph time).
    assert suffix_form_class("man", words) == (0, None, None)


def test_suffix_form_class_no_match_returns_zero() -> None:
    """No applicable rule leaves the mask at 0 (BATS#705 handles it)."""
    fc = load_formclass_lexicon(lang="us")
    words = frozenset(k.split("|", 1)[0] for k in fc)
    assert suffix_form_class("swing", words)[0] == 0
    assert suffix_form_class("zzz", words) == (0, None, None)


# ---------------------------------------------------------------------------
# End-to-end phoneme streams (C oracle captures, 2026-07-10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Homograph entry selection + selected-entry VPSTART:
        ("the match was close", b"dhax  m ' aech  w axz   k ll' ows "),
        ("it was too close to hear", b"iht   w axz   t ' uw  k ll' ows   ^ ( t uh  ) hx' iyr "),
        ("wind", b"w ' ihn d "),
        ("the wind", b"dhax  w ' ihn d "),
        ("to wind", b"^ ( t uh  w ' ayn d "),
        ("all roads lead to rome", b"' aoll  r ' owd z   ll' ehd   ^ ( t uh  r ' owm "),
        ("blood and tears", b"b ll' ahd   ^ ( aen d   t ' iyr z "),
        (
            "the road is long and winding",
            b"dhax  r ' owd   ihz   ll' aonx  ^ ( aen d   w ' ayn d ixnx",
        ),
        ("i contrast", b"` ay  k axn t r ' aes t "),
        ("each object", b"` iych  axb jh' ehk t "),
        ("the produce", b"dhax  p r ' owd uws "),
        # Suffix-derived homograph roots keep their verb-phrase marker:
        ("he lives with her", b"hxiy  ) ll' ihv z   w ihth  hxrr"),
        # Lexicon-level fixes (issue #295 classes 2-3):
        ("this is ours", b"dh` ihs   ihz   aar z "),
        ("swing", b"s w ' ihnx"),
        ("the pasta is al dente", b"dhax  p ' aas t ax  ihz   ' aell  d ' ehn t "),
        (
            "fewer than five came in time",
            b"f ' yurr  dhehn   f ' ayv   ) k ` eym   ihn   t ' aym ",
        ),
    ],
)
def test_text_to_dectalk_phonemes_matches_c_oracle_capture(
    text: str, expected: bytes
) -> None:
    """Byte-for-byte parity with the captured C oracle stream."""
    assert text_to_dectalk_phonemes(text) == expected


def test_audit_144_article_noun_pronoun_verb() -> None:
    """Issue #144 acceptance shape still holds under the runtime masks.

    Article context → noun stress pattern; pronoun context → verb
    stress pattern, for the classic noun/verb minimal pairs.
    """
    cases: list[tuple[str, str, bytes, bytes]] = [
        ("a record", "I record", b"' ehk", b"' owr"),
        ("the object", "I object", b"' aab", b"jh' ehk"),
        ("a present", "I present", b"' ehz", b"' ehn"),
        ("the contract", "I contract", b"' aan", b"' aek"),
        ("the project", "I project", b"' aaj", b"' ehk"),
        ("the progress", "I progress", b"' aag", b"' ehs"),
        ("the protest", "I protest", b"' owt", b"' ehs"),
        ("the conduct", "I conduct", b"' aan", b"' ahk"),
    ]
    for art_ctx, pron_ctx, noun_stress, verb_stress in cases:
        noun_out = text_to_dectalk_phonemes(art_ctx)
        verb_out = text_to_dectalk_phonemes(pron_ctx)
        assert noun_stress in noun_out, (
            f"{art_ctx!r}: expected noun stress {noun_stress!r} in {noun_out!r}"
        )
        assert verb_stress in verb_out, (
            f"{pron_ctx!r}: expected verb stress {verb_stress!r} in {verb_out!r}"
        )
