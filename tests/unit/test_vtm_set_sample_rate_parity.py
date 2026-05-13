"""C-source parity test for :func:`set_sample_rate` against vtm_i.c.

Re-parses the C body and asserts:

- ``void SetSampleRate(unsigned int)`` is the signature in vtm_i.c
  (one-arg form -- the active ``vtm3.c`` build has a two-arg form
  with the TTS handle threaded through, but the inventory still
  tracks the original).
- The fixed-point magic constants ``18063``, ``29722``, ``71`` for
  the 11 kHz branch and ``26214``, ``20480``, ``51`` for the 8 kHz
  branch appear in the body.
- The branch keys are ``PC_SAMPLE_RATE`` and ``MULAW_SAMPLE_RATE``.
- The fall-through path sets ``uiSampleRateChange = NO_SAMPLE_RATE_CHANGE``.
- ``bEightKHz`` is FALSE on the 11 kHz path, TRUE on the 8 kHz path.

Plus behavioural tests for the Python port:

- ``set_sample_rate(11025)`` populates the 11 kHz branch values.
- ``set_sample_rate(8000)`` populates the 8 kHz branch values.
- ``set_sample_rate(22050)`` (any unrecognised rate) takes the
  ``NO_CHANGE`` path while still computing ``sample_period``.
- ``sample_period`` always equals ``1 / sample_rate``.
- The :class:`VtmSampleRate` dataclass is frozen.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import dataclasses
import math
import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.set_sample_rate import (
    MULAW_SAMPLE_RATE,
    PC_SAMPLE_RATE,
    SampleRateChange,
    VtmSampleRate,
    set_sample_rate,
)


def _close(a: float, b: float, eps: float = 1e-9) -> bool:
    """Manual epsilon comparison (avoiding pytest.approx for pyright)."""
    return abs(a - b) < eps


_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/vtm_i.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_vtm_i_c() -> str:
    """Read vtm_i.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_set_sample_rate_body() -> str:
    """Return everything between the opening ``{`` and the closing ``}``.

    Uses a brace-counting scan because regex alone can't track nested
    blocks. Skips over any prototype declaration (``;``-terminated) and
    only matches the actual definition (``{``-terminated).
    """
    text = _read_vtm_i_c()
    # Find every ``void SetSampleRate(...)`` occurrence and pick the
    # one followed by ``{`` (the definition, not a prototype).
    sig_re = re.compile(r"\bvoid\s+SetSampleRate\s*\(")
    body_start: int | None = None
    for match in sig_re.finditer(text):
        # Skip past the parameter list.
        paren_depth = 1
        idx = match.end()
        while idx < len(text) and paren_depth > 0:
            if text[idx] == "(":
                paren_depth += 1
            elif text[idx] == ")":
                paren_depth -= 1
            idx += 1
        # Skip whitespace.
        while idx < len(text) and text[idx] in " \t\n\r":
            idx += 1
        if idx < len(text) and text[idx] == "{":
            body_start = idx + 1
            break
    assert body_start is not None, "couldn't find SetSampleRate() definition in vtm_i.c"
    # Brace-count to the matching ``}``.
    brace_depth = 1
    idx = body_start
    while idx < len(text) and brace_depth > 0:
        if text[idx] == "{":
            brace_depth += 1
        elif text[idx] == "}":
            brace_depth -= 1
        idx += 1
    assert brace_depth == 0, "couldn't find closing brace of SetSampleRate()"
    return text[body_start : idx - 1]


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_signature_matches() -> None:
    """The C signature is ``void SetSampleRate(unsigned int uiSampRate)``."""
    text = _read_vtm_i_c()
    assert re.search(
        r"void\s+SetSampleRate\s*\(\s*unsigned\s+int\s+uiSampRate\s*\)\s*\n\s*\{",
        text,
    ), "SetSampleRate signature not found in vtm_i.c"


def test_magic_constants_in_body() -> None:
    """The body contains the Q14/Q15 magic constants and per-frame sample counts."""
    body = _extract_set_sample_rate_body()
    for value in ("18063", "29722", "71", "26214", "20480", "51"):
        assert value in body, f"magic constant {value} missing from SetSampleRate body"


def test_pc_sample_rate_branch_keys_on_pc_constant() -> None:
    """The 11 kHz path is gated by ``uiSampleRate == PC_SAMPLE_RATE``."""
    body = _extract_set_sample_rate_body()
    assert re.search(r"uiSampleRate\s*==\s*PC_SAMPLE_RATE", body)


def test_mulaw_sample_rate_branch_keys_on_mulaw_constant() -> None:
    """The 8 kHz path is gated by ``uiSampleRate == MULAW_SAMPLE_RATE``."""
    body = _extract_set_sample_rate_body()
    assert re.search(r"uiSampleRate\s*==\s*MULAW_SAMPLE_RATE", body)


def test_eight_khz_flag_polarity() -> None:
    """``bEightKHz = FALSE`` on the 11 kHz path, ``TRUE`` on the 8 kHz path."""
    body = _extract_set_sample_rate_body()
    assert re.search(r"bEightKHz\s*=\s*FALSE", body)
    assert re.search(r"bEightKHz\s*=\s*TRUE", body)


def test_rate_change_assignments_use_enum_constants() -> None:
    """The three rate-change paths use the named ``viport.h`` constants."""
    body = _extract_set_sample_rate_body()
    assert "SAMPLE_RATE_INCREASE" in body
    assert "SAMPLE_RATE_DECREASE" in body
    assert "NO_SAMPLE_RATE_CHANGE" in body


def test_sample_period_formula() -> None:
    """The body computes ``SamplePeriod = 1.0 / SampleRate``."""
    body = _extract_set_sample_rate_body()
    assert re.search(r"SamplePeriod\s*=\s*1\.0\s*/\s*SampleRate", body)


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def test_pc_sample_rate_branch_values() -> None:
    """``set_sample_rate(11025)`` matches the 11 kHz branch constants."""
    state = set_sample_rate(PC_SAMPLE_RATE)
    assert state.sample_rate == 11025
    assert _close(state.sample_period, 1.0 / 11025.0)
    assert state.is_eight_khz is False
    assert state.rate_change is SampleRateChange.INCREASE
    assert state.rate_scale == 18063
    assert state.inv_rate_scale == 29722
    assert state.samples_per_frame == 71


def test_mulaw_sample_rate_branch_values() -> None:
    """``set_sample_rate(8000)`` matches the 8 kHz branch constants."""
    state = set_sample_rate(MULAW_SAMPLE_RATE)
    assert state.sample_rate == 8000
    assert _close(state.sample_period, 1.0 / 8000.0)
    assert state.is_eight_khz is True
    assert state.rate_change is SampleRateChange.DECREASE
    assert state.rate_scale == 26214
    assert state.inv_rate_scale == 20480
    assert state.samples_per_frame == 51


def test_unsupported_sample_rate_takes_no_change_branch() -> None:
    """``set_sample_rate(22050)`` falls through to NO_CHANGE.

    The C source only assigns ``uiSampleRateChange`` in that branch
    and leaves the other globals at their previous values; the Python
    port reports the ``vismprat.h`` static-init defaults so the
    caller still gets a fully-populated dataclass.
    """
    state = set_sample_rate(22050)
    assert state.sample_rate == 22050
    assert _close(state.sample_period, 1.0 / 22050.0)
    assert state.rate_change is SampleRateChange.NO_CHANGE


def test_sample_period_is_one_over_rate_for_all_branches() -> None:
    """``sample_period`` matches ``1 / sample_rate`` regardless of branch."""
    for rate in (PC_SAMPLE_RATE, MULAW_SAMPLE_RATE, 22050, 16000, 44100):
        state = set_sample_rate(rate)
        assert _close(state.sample_period, 1.0 / float(rate))


def test_vtm_sample_rate_is_frozen() -> None:
    """The dataclass is frozen so callers can't accidentally mutate VTM state."""
    state = set_sample_rate(PC_SAMPLE_RATE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        # ``frozen=True`` dataclasses raise FrozenInstanceError on
        # any ``__setattr__`` -- this also covers the ``slots=True``
        # path which would raise AttributeError on an unknown attr.
        state.rate_scale = 0  # type: ignore[misc]


def test_q14_q15_fixed_point_values_are_consistent() -> None:
    """The fixed-point constants approximate the documented ratios.

    Sanity check that the literal values aren't transposed or fat-
    fingered: 18063 is roughly ``1.1 * 16384`` (Q14), 29722 is roughly
    ``0.909 * 32768`` (Q15), 26214 is ``0.8 * 32768`` to one Q15
    ULP, and 20480 == ``1.25 * 16384`` (Q14 exact).
    """
    state_11k = set_sample_rate(PC_SAMPLE_RATE)
    state_8k = set_sample_rate(MULAW_SAMPLE_RATE)
    assert math.isclose(state_11k.rate_scale / 16384.0, 1.1, abs_tol=0.01)
    assert math.isclose(state_11k.inv_rate_scale / 32768.0, 0.909, abs_tol=0.01)
    # 26214 / 32768 == 0.79998779... -- the C source's 1-bit
    # rounding-down of 0.8 in Q15. Use a loose tolerance.
    assert math.isclose(state_8k.rate_scale / 32768.0, 0.8, abs_tol=0.001)
    # 20480 / 16384 == 1.25 exactly in Q14.
    assert _close(state_8k.inv_rate_scale / 16384.0, 1.25)


def test_returns_vtm_sample_rate_dataclass() -> None:
    """The return type is :class:`VtmSampleRate` -- not a tuple or dict."""
    state = set_sample_rate(PC_SAMPLE_RATE)
    assert isinstance(state, VtmSampleRate)


def test_enum_values_match_viport_constants() -> None:
    """``SampleRateChange`` values match ``viport.h``: 0 / 1 / 2."""
    assert SampleRateChange.INCREASE == 0
    assert SampleRateChange.DECREASE == 1
    assert SampleRateChange.NO_CHANGE == 2
