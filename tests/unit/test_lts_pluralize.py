"""Verify ``ls_util_pluralize`` parity with ls_util.c."""

from __future__ import annotations

import pytest

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts.pluralize import ls_util_pluralize


@pytest.mark.parametrize(
    "sibilant",
    [USPhoneme.S, USPhoneme.Z, USPhoneme.SH, USPhoneme.CH, USPhoneme.JH],
)
def test_plural_after_sibilant_is_ix_z(sibilant: USPhoneme) -> None:
    """After a sibilant (S, Z, SH, CH, JH), plural is ``IX Z``."""
    assert ls_util_pluralize(int(sibilant)) == [int(USPhoneme.IX), int(USPhoneme.Z)]


@pytest.mark.parametrize(
    "voiceless_cons",
    [USPhoneme.T, USPhoneme.P, USPhoneme.K, USPhoneme.F, USPhoneme.TH],
)
def test_plural_after_voiceless_consonant_is_s(voiceless_cons: USPhoneme) -> None:
    """After a non-sibilant voiceless consonant, plural is ``S`` (e.g. "cats")."""
    assert ls_util_pluralize(int(voiceless_cons)) == [int(USPhoneme.S)]


@pytest.mark.parametrize(
    "voiced_cons",
    [USPhoneme.B, USPhoneme.D, USPhoneme.G, USPhoneme.V, USPhoneme.DH, USPhoneme.M],
)
def test_plural_after_voiced_consonant_is_z(voiced_cons: USPhoneme) -> None:
    """After a non-sibilant voiced consonant, plural is ``Z`` (e.g. "dogs")."""
    assert ls_util_pluralize(int(voiced_cons)) == [int(USPhoneme.Z)]


@pytest.mark.parametrize(
    "vowel",
    [USPhoneme.AA, USPhoneme.IY, USPhoneme.UW, USPhoneme.EH, USPhoneme.AY],
)
def test_plural_after_vowel_is_z(vowel: USPhoneme) -> None:
    """After a vowel, plural is ``Z`` (e.g. "boys", "trees")."""
    assert ls_util_pluralize(int(vowel)) == [int(USPhoneme.Z)]


def test_plural_after_out_of_range_phone() -> None:
    """A phoneme code >= US_TOT_ALLOPHONES is treated as featureless → Z."""
    # The C source's ``if (pLts_t->lphone < US_TOT_ALLOPHONES)`` guard
    # means out-of-range codes fall through with feats=0 → Z branch.
    assert ls_util_pluralize(200) == [int(USPhoneme.Z)]
