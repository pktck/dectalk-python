"""ARPABET → USPhoneme alias coverage for ``_arpabet_to_us_allophone``.

Issue #62 / audit ``docs/parity-divergence-audit.md`` §"Top 3 divergence
root causes" #1: the CMU-style ARPABET symbols ``HH``, ``L`` and ``NG``
have no DECtalk-allophone enum entry of the same name (the FONIX scheme
calls them ``HX`` / ``LL`` / ``NX``) and were silently dropped by
:func:`dectalk.api.speak._arpabet_to_us_allophone` before #62.

The audit on ``"hello world"`` measured a 38% phone loss from this gap
alone, so the regression bar is high: every ARPABET symbol that the LTS
rules + bundled US lexicon can emit must resolve to a non-``None``
allophone code, and the three named aliases must point at their
audit-defined targets.

Cross-reference: ``${DECTALK_SRC}/src/dapi/src/include/l_us_ph.h``
(authoritative DECtalk allophone-name list) and
``src/dectalk/include/phoneme_codes.py`` (USPhoneme enum).
"""

from __future__ import annotations

import pytest

from dectalk.api.speak import _ARPABET_ALIAS, _arpabet_to_us_allophone, text_to_phonemes
from dectalk.include.phoneme_codes import PFUSA, USPhoneme


def _expected_code(member: USPhoneme) -> int:
    """Mirror ``_arpabet_to_us_allophone``'s packing convention."""
    return (PFUSA << 8) | int(member)


@pytest.mark.parametrize(
    ("arpabet", "member"),
    [
        ("HH", USPhoneme.HX),
        ("L", USPhoneme.LL),
        ("NG", USPhoneme.NX),
    ],
)
def test_alias_resolves_to_audit_named_target(arpabet: str, member: USPhoneme) -> None:
    """The three aliases the audit calls out must hit their named targets."""
    assert _arpabet_to_us_allophone(arpabet) == _expected_code(member)


@pytest.mark.parametrize(
    ("arpabet", "member"),
    [
        ("HH0", USPhoneme.HX),
        ("HH1", USPhoneme.HX),
        ("HH2", USPhoneme.HX),
        ("L0", USPhoneme.LL),
        ("NG1", USPhoneme.NX),
    ],
)
def test_alias_is_robust_to_stress_suffix(arpabet: str, member: USPhoneme) -> None:
    """LTS appends a stress digit to vowels; aliasing must strip it too.

    Consonants don't normally carry a stress digit in CMUdict, but we
    accept the suffix on the aliased symbol because the stress-stripping
    happens before any alias lookup.
    """
    assert _arpabet_to_us_allophone(arpabet) == _expected_code(member)


def test_alias_table_does_not_shadow_existing_members() -> None:
    """No alias keys should match a USPhoneme name (they'd be redundant)
    EXCEPT the deliberate overrides flagged below.

    Overrides reflect cases where CMU ARPABET and the DECtalk FONIX
    enum happen to share a name but mean different allophones:

    * ``ER``: CMU ``ER`` is the rhotacized vowel of "bird", which the
      DECtalk source US dictionary writes as ``R`` (= USPhoneme.RR /
      syllabic R), **not** as ``K`` (= USPhoneme.ER). Without the
      override the bare-name lookup would emit the wrong allophone.
      Issue #156 / parity re-audit §2.
    """
    deliberate_overrides = {"ER"}
    for arpabet in _ARPABET_ALIAS:
        if arpabet in deliberate_overrides:
            continue
        assert arpabet not in USPhoneme.__members__, (
            f"alias key {arpabet!r} is already a USPhoneme name; remove it"
        )


def test_bare_name_lookup_still_works_for_shared_symbols() -> None:
    """ARPABET symbols whose name matches a USPhoneme entry skip the alias."""
    # Sample a few CMU symbols that share their FONIX name.
    assert _arpabet_to_us_allophone("AA") == _expected_code(USPhoneme.AA)
    assert _arpabet_to_us_allophone("IY") == _expected_code(USPhoneme.IY)
    assert _arpabet_to_us_allophone("CH") == _expected_code(USPhoneme.CH)
    assert _arpabet_to_us_allophone("SIL") == _expected_code(USPhoneme.SIL)


def test_unknown_arpabet_returns_none() -> None:
    """Symbols not in the alias table and not in USPhoneme still return None.

    The caller (``_speak_via_python_full``) relies on this contract to
    silently skip stray markers like ``"BLOCKRULES"`` that may appear in
    the phoneme stream.
    """
    assert _arpabet_to_us_allophone("NOTAPHONE") is None
    assert _arpabet_to_us_allophone("XQZ") is None


def test_every_arpabet_symbol_from_hello_world_resolves() -> None:
    """The audit's headline case: every ARPABET from ``"hello world"``
    must resolve to a non-None US allophone code.

    Before the alias table this dropped 3 / 8 phones (HH + 2xL), a
    38% loss. After the fix all 8 ARPABET symbols resolve.
    """
    arpabet = text_to_phonemes("hello world")
    assert arpabet  # sanity: tokenizer / lexicon produces phones
    codes = [_arpabet_to_us_allophone(p) for p in arpabet]
    assert all(c is not None for c in codes), (
        f"some phones drop: {[p for p, c in zip(arpabet, codes, strict=True) if c is None]}"
    )


def test_lts_emitted_symbols_all_resolve() -> None:
    """Run a broad sweep through the LTS fallback and assert that every
    ARPABET symbol it emits resolves through the alias / enum path.

    The LTS rules in ``dectalk.lts.rules_us`` are the only path that can
    emit out-of-lexicon ARPABET symbols; the lexicon itself is curated
    to CMU-39 ARPABET. Mixing a battery of nonsense words exercises
    every rule.
    """
    from dectalk.lts import lts  # noqa: PLC0415

    # Words chosen to hit every consonant rule + every vowel rule at
    # least once. The point isn't intelligibility; it's coverage of the
    # symbol set the LTS module can produce.
    probes = [
        "high",  # IGH -> AY; H -> HH
        "rough",  # OUGH variant -> AH F
        "beautiful",  # EAU -> Y UW
        "neighbour",  # EIGH -> EY
        "sing",  # NG -> NG
        "thought",  # OUGH+T -> AO
        "yellow",  # Y + EH + L + OW
        "quick",  # QU -> K W
        "phone",  # PH -> F
        "azure",  # Z (and maybe ZH via lexicon)
        "judge",  # J -> JH
        "examine",  # X -> K S
        "shrimp",  # SH + R + IH + M + P
        "thwart",  # TH + W
        "near",  # EAR -> IY R
        "stair",  # AIR -> EH R
        "hour",  # OUR -> AW ER
        "cheer",  # EER -> IY R
        "moor",  # OOR -> UH R
        "buoy",  # OY -> OY
        "fluke",  # magic-E
    ]
    seen: set[str] = set()
    for word in probes:
        for symbol in lts(word):
            seen.add(symbol)

    unresolved = sorted({s for s in seen if _arpabet_to_us_allophone(s) is None})
    assert not unresolved, f"LTS emits unmapped ARPABET symbol(s): {unresolved}"
