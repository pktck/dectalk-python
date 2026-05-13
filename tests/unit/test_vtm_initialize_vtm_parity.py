"""C-source parity test for :func:`initialize_vtm` against vtm_i.c / vtm3.c.

Re-parses ``src/dapi/src/vtm/vtm_i.c`` (the original SPC-era body
that seeds ``parambuff``) and ``src/dapi/src/vtm/vtm3.c`` (the
active Linux body that zeroes the per-handle filter state), and
asserts the Python port captures the union of both.

Structural assertions:

- The signature ``void InitializeVTM(...)`` appears in vtm_i.c.
- The vtm_i.c body aliases ``variabpars = &parambuff[1]`` and
  writes the 17 OUT_* parameter slots with the documented init
  values (formant freqs at 2000 Hz, bandwidths at 2000 Hz, amps
  at 0, T0=100, FZ=290, TLT=18).
- The vtm_i.c body calls ``speech_waveform_generator()`` four
  times after seeding the parambuff (to let the resonator delays
  decay).
- The vtm3.c body zeroes the per-handle filter state cluster
  (every ``r__d1`` / ``r__d2`` pair, ``ablas1/2``, ``vlast``,
  ``one_minus_decay``, ``rampdown``) and seeds ``lastf1`` and
  ``lastfnp`` at 500.

Behavioural assertions:

- :func:`initialize_vtm` returns a fresh :class:`VtmState`.
- ``parambuff`` is a length-33 list, zeroed except at the OUT_*+1
  offsets seeded by the C body.
- All filter-state fields start at 0.
- ``lastf1 == lastfnp == 500`` per vtm3.c.
- ``cas_count == par_count == rampdown == 0`` per vtm3.c.
- Successive calls return independent dataclass instances (no
  shared mutable parambuff).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_AP,
    OUT_AV,
    OUT_B1,
    OUT_B2,
    OUT_B3,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_T0,
    OUT_TLT,
)
from dectalk.vtm.initialize_vtm import (
    PARAMBUFF_SIZE,
    InitializeVTM,
    VtmState,
    initialize_vtm,
)

_C_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_VTM_I_C = _C_SRC / "src/dapi/src/vtm/vtm_i.c"
_VTM3_C = _C_SRC / "src/dapi/src/vtm/vtm3.c"

pytestmark = pytest.mark.skipif(
    not (_VTM_I_C.is_file() and _VTM3_C.is_file()),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c(path: Path) -> str:
    """Read a C source file with CRLF endings normalised."""
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(text: str, signature_re: str) -> str:
    """Return the body of a function definition matched by ``signature_re``.

    Uses brace-depth tracking because nested blocks can fool regex.
    Picks the first match whose argument list is followed by ``{``
    (skipping prototype declarations that end with ``;``).
    """
    sig = re.compile(signature_re)
    for match in sig.finditer(text):
        idx = match.end()
        # Skip the parameter list (after the opening paren at match.end()).
        paren_depth = 1
        while idx < len(text) and paren_depth > 0:
            if text[idx] == "(":
                paren_depth += 1
            elif text[idx] == ")":
                paren_depth -= 1
            idx += 1
        while idx < len(text) and text[idx] in " \t\n\r":
            idx += 1
        if idx < len(text) and text[idx] == "{":
            body_start = idx + 1
            brace_depth = 1
            j = body_start
            while j < len(text) and brace_depth > 0:
                if text[j] == "{":
                    brace_depth += 1
                elif text[j] == "}":
                    brace_depth -= 1
                j += 1
            assert brace_depth == 0, "couldn't find closing brace of function body"
            return text[body_start : j - 1]
    raise AssertionError(f"couldn't locate a definition matching {signature_re!r}")


def _vtm_i_body() -> str:
    return _extract_body(_read_c(_VTM_I_C), r"\bvoid\s+InitializeVTM\s*\(")


def _vtm3_body() -> str:
    return _extract_body(_read_c(_VTM3_C), r"\bvoid\s+InitializeVTM\s*\(")


# --------------------------------------------------------------------------
# C-source structural tests (vtm_i.c -- the parambuff-seeding body).
# --------------------------------------------------------------------------


def test_vtm_i_c_signature_present() -> None:
    """``void InitializeVTM()`` appears in vtm_i.c."""
    text = _read_c(_VTM_I_C)
    assert re.search(r"\bvoid\s+InitializeVTM\s*\(\s*\)\s*\n\s*\{", text), (
        "InitializeVTM() definition not found in vtm_i.c"
    )


def test_vtm_i_c_aliases_parambuff_at_offset_1() -> None:
    """The body aliases ``variabpars = &parambuff[1]``."""
    body = _vtm_i_body()
    assert re.search(r"variabpars\s*=\s*&\s*parambuff\s*\[\s*1\s*\]\s*;", body), (
        "variabpars = &parambuff[1] aliasing missing from vtm_i.c InitializeVTM"
    )


@pytest.mark.parametrize(
    "out_name,value",
    [
        ("OUT_T0", 100),
        ("OUT_F1", 2000),
        ("OUT_F2", 2000),
        ("OUT_F3", 2000),
        ("OUT_FZ", 290),
        ("OUT_B1", 2000),
        ("OUT_B2", 2000),
        ("OUT_B3", 2000),
        ("OUT_AV", 0),
        ("OUT_AP", 0),
        ("OUT_A2", 0),
        ("OUT_A3", 0),
        ("OUT_A4", 0),
        ("OUT_A5", 0),
        ("OUT_A6", 0),
        ("OUT_AB", 0),
        ("OUT_TLT", 18),
    ],
)
def test_vtm_i_c_seeds_parameter_slot(out_name: str, value: int) -> None:
    """The vtm_i.c body seeds each OUT_* slot with the documented value."""
    body = _vtm_i_body()
    pattern = rf"variabpars\s*\[\s*{out_name}\s*\]\s*=\s*{value}\s*;"
    assert re.search(pattern, body), (
        f"vtm_i.c InitializeVTM does not seed variabpars[{out_name}] = {value}"
    )


def test_vtm_i_c_calls_speech_waveform_generator_four_times() -> None:
    """The body calls ``speech_waveform_generator()`` four times (filter decay)."""
    body = _vtm_i_body()
    calls = re.findall(r"speech_waveform_generator\s*\(\s*\)\s*;", body)
    assert len(calls) == 4, (
        f"expected 4 speech_waveform_generator() calls in vtm_i.c InitializeVTM, got {len(calls)}"
    )


# --------------------------------------------------------------------------
# C-source structural tests (vtm3.c -- the active Linux per-handle reset).
# --------------------------------------------------------------------------


def test_vtm3_c_signature_takes_tts_handle() -> None:
    """The vtm3.c body's signature takes the per-call TTS handle."""
    text = _read_c(_VTM3_C)
    assert re.search(
        r"void\s+InitializeVTM\s*\(\s*LPTTS_HANDLE_T\s+phTTS\s*\)\s*\n\s*\{",
        text,
    ), "vtm3.c InitializeVTM(LPTTS_HANDLE_T) signature not found"


def test_vtm3_c_seeds_lastf1_and_lastfnp() -> None:
    """vtm3.c primes ``lastf1 = lastfnp = 500``."""
    body = _vtm3_body()
    assert re.search(r"lastf1\s*=\s*500\s*;", body)
    assert re.search(r"lastfnp\s*=\s*500\s*;", body)


@pytest.mark.parametrize(
    "field_name",
    [
        # Resonator delay-line pairs.
        "r2pd1",
        "r2pd2",
        "r3pd1",
        "r3pd2",
        "r4pd1",
        "r4pd2",
        "r5pd1",
        "r5pd2",
        "r6pd1",
        "r6pd2",
        "r1cd1",
        "r1cd2",
        "r2cd1",
        "r2cd2",
        "r3cd1",
        "r3cd2",
        "r4cd1",
        "r4cd2",
        "r5cd1",
        "r5cd2",
        "rnpd1",
        "rnpd2",
        "rnzd1",
        "rnzd2",
        "rlpd1",
        "rlpd2",
        # Nasal anti-resonator delay-line.
        "ablas1",
        "ablas2",
        # Tilt-filter state.
        "vlast",
        "one_minus_decay",
        # Pitch / ramp / counter state.
        "cas_count",
        "par_count",
        "rampdown",
    ],
)
def test_vtm3_c_zeroes_filter_state_field(field_name: str) -> None:
    """vtm3.c InitializeVTM zeroes each filter-state / counter field."""
    body = _vtm3_body()
    pattern = rf"\b{field_name}\s*=\s*0\s*;"
    assert re.search(pattern, body), f"vtm3.c InitializeVTM does not zero the {field_name!r} field"


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def test_returns_vtm_state_dataclass() -> None:
    """``initialize_vtm()`` returns an instance of :class:`VtmState`."""
    state = initialize_vtm()
    assert isinstance(state, VtmState)


def test_parambuff_size_is_33() -> None:
    """``parambuff`` is allocated at the C ``DT_PIPE_T parambuff[33]`` size."""
    state = initialize_vtm()
    assert PARAMBUFF_SIZE == 33
    assert len(state.parambuff) == PARAMBUFF_SIZE


def test_parambuff_seeded_values() -> None:
    """The OUT_*+1 offsets carry the documented initial values."""
    state = initialize_vtm()
    expected = {
        OUT_T0 + 1: 100,
        OUT_F1 + 1: 2000,
        OUT_F2 + 1: 2000,
        OUT_F3 + 1: 2000,
        OUT_FZ + 1: 290,
        OUT_B1 + 1: 2000,
        OUT_B2 + 1: 2000,
        OUT_B3 + 1: 2000,
        OUT_AV + 1: 0,
        OUT_AP + 1: 0,
        OUT_A2 + 1: 0,
        OUT_A3 + 1: 0,
        OUT_A4 + 1: 0,
        OUT_A5 + 1: 0,
        OUT_A6 + 1: 0,
        OUT_AB + 1: 0,
        OUT_TLT + 1: 18,
    }
    for offset, value in expected.items():
        assert state.parambuff[offset] == value, (
            f"parambuff[{offset}] should be {value}, got {state.parambuff[offset]}"
        )


def test_parambuff_header_slot_is_zero() -> None:
    """``parambuff[0]`` (the packet header) is left at zero by the bring-up shim."""
    state = initialize_vtm()
    assert state.parambuff[0] == 0


def test_parambuff_unused_tail_is_zero() -> None:
    """Indices past the OUT_* payload (18..32) are zero."""
    state = initialize_vtm()
    # OUT_TLT + 1 == 9 in old SPC ordering; the highest seeded index
    # is OUT_B3 + 1 == 17. Everything from 18 onwards is unused.
    for i in range(18, PARAMBUFF_SIZE):
        assert state.parambuff[i] == 0, f"parambuff[{i}] should be zero, got {state.parambuff[i]}"


def test_filter_state_starts_at_zero() -> None:
    """Every per-handle filter-delay / counter field starts at zero."""
    state = initialize_vtm()
    zeroed_fields = [
        "r2pd1",
        "r2pd2",
        "r3pd1",
        "r3pd2",
        "r4pd1",
        "r4pd2",
        "r5pd1",
        "r5pd2",
        "r6pd1",
        "r6pd2",
        "r1cd1",
        "r1cd2",
        "r2cd1",
        "r2cd2",
        "r3cd1",
        "r3cd2",
        "r4cd1",
        "r4cd2",
        "r5cd1",
        "r5cd2",
        "rnpd1",
        "rnpd2",
        "rnzd1",
        "rnzd2",
        "rlpd1",
        "rlpd2",
        "ablas1",
        "ablas2",
        "vlast",
        "one_minus_decay",
        "cas_count",
        "par_count",
        "rampdown",
    ]
    for name in zeroed_fields:
        assert getattr(state, name) == 0, f"{name} should be zero, got {getattr(state, name)}"


def test_lastf1_and_lastfnp_seeded_at_500() -> None:
    """``lastf1`` and ``lastfnp`` start at 500 Hz per vtm3.c."""
    state = initialize_vtm()
    assert state.lastf1 == 500
    assert state.lastfnp == 500


def test_successive_calls_return_independent_instances() -> None:
    """Two calls produce independent dataclass instances (no shared parambuff)."""
    a = initialize_vtm()
    b = initialize_vtm()
    assert a is not b
    assert a.parambuff is not b.parambuff
    # Mutating one must not affect the other.
    a.parambuff[0] = 42
    assert b.parambuff[0] == 0
    a.r2pd1 = 99
    assert b.r2pd1 == 0


def test_takes_no_required_arguments() -> None:
    """The factory takes no required arguments; the C-side speaker-def
    inputs are pinned to bring-up defaults."""
    # Calling with no args must succeed.
    state = initialize_vtm()
    assert isinstance(state, VtmState)


def test_pep8_alias_is_same_object() -> None:
    """``InitializeVTM`` is the PEP8-rename alias of ``initialize_vtm``."""
    assert InitializeVTM is initialize_vtm
