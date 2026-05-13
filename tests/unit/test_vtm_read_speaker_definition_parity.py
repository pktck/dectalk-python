"""C-source parity test for ``read_speaker_definition`` against vtm_i.c.

Re-parses the C body via brace-depth tracking and asserts the noise-
filter coefficient constants and the rate-change-keyed switch match
the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from dectalk.vtm.read_speaker_definition import SpeakerDefinition, read_speaker_definition
from dectalk.vtm.set_sample_rate import SampleRateChange

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/vtm_i.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_vtm_i_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``read_speaker_definition`` via brace tracking."""
    text = _read_vtm_i_c()
    match = re.search(r"\bvoid\s+read_speaker_definition\s*\(\s*\)\s*\n\{", text)
    assert match is not None, "read_speaker_definition definition not found"
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    assert depth == 0, "read_speaker_definition body had unbalanced braces"
    return text[start : i - 1]


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``void read_speaker_definition()``."""
    text = _read_vtm_i_c()
    assert re.search(r"\bvoid\s+read_speaker_definition\s*\(\s*\)", text)


def test_body_initialises_lcg_constants() -> None:
    """Body sets ``ranmul = 20077`` and ``ranadd = 12345``."""
    body = _extract_body()
    assert re.search(r"ranmul\s*=\s*20077\s*;", body)
    assert re.search(r"ranadd\s*=\s*12345\s*;", body)


def test_body_keys_noiseb_on_sample_rate_change() -> None:
    """Body switches noiseb between -2913 (INCREASE / NO_CHANGE) and -1873 (DECREASE)."""
    body = _extract_body()
    assert re.search(r"noiseb\s*=\s*-?2913\s*;", body)
    assert re.search(r"noiseb\s*=\s*-?1873\s*;", body)
    assert re.search(r"switch\s*\(\s*uiSampleRateChange\s*\)", body)


def test_body_sets_noisec_to_1499() -> None:
    """Every branch sets ``noisec = 1499``."""
    body = _extract_body()
    assert body.count("noisec = 1499") >= 2, (
        f"expected noisec = 1499 in at least 2 branches, found {body.count('noisec = 1499')}"
    )


def test_body_sets_r6pb_and_r6pc() -> None:
    """Body sets parallel 6th formant constants ``r6pb = -5702`` / ``r6pc = -1995``."""
    body = _extract_body()
    assert re.search(r"r6pb\s*=\s*-?5702\s*;", body)
    assert re.search(r"r6pc\s*=\s*-?1995\s*;", body)


def test_body_dispatches_on_three_rate_change_arms() -> None:
    """The C switch has SAMPLE_RATE_INCREASE / DECREASE / NO_SAMPLE_RATE_CHANGE arms."""
    body = _extract_body()
    assert "SAMPLE_RATE_INCREASE" in body
    assert "SAMPLE_RATE_DECREASE" in body
    assert "NO_SAMPLE_RATE_CHANGE" in body


# -- Python behavioural tests ---------------------------------------------


def test_increase_branch_returns_negative_2913() -> None:
    """``SampleRateChange.INCREASE`` -> ``noiseb == -2913``."""
    sd = read_speaker_definition(SampleRateChange.INCREASE)
    assert sd.noiseb == -2913


def test_decrease_branch_returns_negative_1873() -> None:
    """``SampleRateChange.DECREASE`` -> ``noiseb == -1873``."""
    sd = read_speaker_definition(SampleRateChange.DECREASE)
    assert sd.noiseb == -1873


def test_no_change_branch_returns_negative_2913() -> None:
    """``SampleRateChange.NO_CHANGE`` -> ``noiseb == -2913`` (defaults match INCREASE)."""
    sd = read_speaker_definition(SampleRateChange.NO_CHANGE)
    assert sd.noiseb == -2913


def test_noisec_is_constant_across_branches() -> None:
    """``noisec`` is 1499 in every rate-change arm."""
    for rc in (
        SampleRateChange.INCREASE,
        SampleRateChange.DECREASE,
        SampleRateChange.NO_CHANGE,
    ):
        assert read_speaker_definition(rc).noisec == 1499


def test_lcg_constants_match_c_source() -> None:
    """``ranmul`` / ``ranadd`` are 20077 / 12345 for every branch."""
    for rc in (
        SampleRateChange.INCREASE,
        SampleRateChange.DECREASE,
        SampleRateChange.NO_CHANGE,
    ):
        sd = read_speaker_definition(rc)
        assert sd.ranmul == 20077
        assert sd.ranadd == 12345


def test_parallel_6th_formant_constants_match_c() -> None:
    """``r6pb`` / ``r6pc`` are -5702 / -1995 for every branch."""
    for rc in (
        SampleRateChange.INCREASE,
        SampleRateChange.DECREASE,
        SampleRateChange.NO_CHANGE,
    ):
        sd = read_speaker_definition(rc)
        assert sd.r6pb == -5702
        assert sd.r6pc == -1995


def test_speaker_definition_is_frozen() -> None:
    """:class:`SpeakerDefinition` is a frozen dataclass."""
    sd = read_speaker_definition(SampleRateChange.INCREASE)
    with pytest.raises(FrozenInstanceError):
        sd.noiseb = 0  # type: ignore[misc]


def test_returns_speaker_definition_instance() -> None:
    """The function returns a :class:`SpeakerDefinition`."""
    sd = read_speaker_definition(SampleRateChange.INCREASE)
    assert isinstance(sd, SpeakerDefinition)
