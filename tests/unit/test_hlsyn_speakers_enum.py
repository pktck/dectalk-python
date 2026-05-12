"""Verify the HLSyn ``Speakers`` enum matches hlsynapi.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.hlsyn.speakers_enum import NUMSPEAKERS, Speakers
from dectalk.include.dectalk import Voice

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/hlsynapi.h")


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_speakers_enum_matches_c() -> None:
    """All 10 entries match ``hlsynapi.h``'s ``Speakers`` enum order."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+enum\s+Speakers\s*\{([^}]*)\}\s*currentSpeaker\s*;",
        text,
    )
    assert match is not None
    names = [n.strip() for n in match.group(1).split(",") if n.strip()]
    assert len(names) == NUMSPEAKERS
    for index, c_name in enumerate(names):
        assert Speakers(index).name == c_name


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_numspeakers_matches_c() -> None:
    """``NUMSPEAKERS`` matches the ``#define`` in hlsynapi.h."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(r"#define\s+NUMSPEAKERS\s+(\d+)\b", text)
    assert match is not None
    assert int(match.group(1)) == NUMSPEAKERS


def test_speaker_count() -> None:
    """``NUMSPEAKERS`` is exactly the enum length (10)."""
    assert NUMSPEAKERS == 10
    assert len(list(Speakers)) == NUMSPEAKERS


def test_speaker_values_dense() -> None:
    """Speakers IDs form a dense 0..9 set."""
    assert {int(s) for s in Speakers} == set(range(10))


def test_wendy_at_slot_8_not_willy() -> None:
    """HLSyn calls slot 8 ``Wendy`` even though dectalk.h calls it ``Willy``.

    Both refer to the same female voice; the rename is a known
    historical inconsistency between the public DECtalk API and the
    HLSyn API and must be preserved for parity.
    """
    assert Speakers.Wendy == 8
    assert Voice.WHISPERY_WILLY == 8


def test_first_eight_match_voice_enum() -> None:
    """``Paul``..``Rita`` mirror DECtalk's ``Voice`` enum 0..7."""
    pairs = [
        (Speakers.Paul, Voice.PERFECT_PAUL),
        (Speakers.Betty, Voice.BEAUTIFUL_BETTY),
        (Speakers.Harry, Voice.HUGE_HARRY),
        (Speakers.Frank, Voice.FRAIL_FRANK),
        (Speakers.Dennis, Voice.DOCTOR_DENNIS),
        (Speakers.Kit, Voice.KIT_THE_KID),
        (Speakers.Ursula, Voice.UPPITY_URSULA),
        (Speakers.Rita, Voice.ROUGH_RITA),
    ]
    for hl, voice in pairs:
        assert int(hl) == int(voice)


def test_chris_at_slot_9() -> None:
    """Slot 9 is Chris in HLSyn; matches Voice.CRAFTY_CHRIS."""
    assert Speakers.Chris == 9
    assert Voice.CRAFTY_CHRIS == 9
