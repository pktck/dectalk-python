"""C-source parity test for ``sp_special_coartic`` against p_sp_st1.c.

Re-parses both the ``sp_special_coartic`` driver (lines 343-364)
and the ``span_spec_coart`` helper (lines 388-588) and asserts the
Spanish vowel-pair coarticulation table still matches: F1 ``E+M``
case, F2/F3 switch-per-vowel with place-of-articulation lookups,
and IX -> NH remapping.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.spp_codes import (
    SPP_A,
    SPP_E,
    SPP_F,
    SPP_GH,
    SPP_I,
    SPP_M,
    SPP_N,
    SPP_O,
    SPP_S,
    SPP_U,
    SPP_Y,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import F1, F2, F3
from dectalk.ph.sp_special_coartic import sp_special_coartic, span_spec_coart

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/p_sp_st1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(name: str) -> str:
    text = _read_c()
    match = re.search(
        rf"static\s+(?:short|int)\s+{re.escape(name)}\s*\([^)]*\)\s*(?:/\*[^*]*\*/\s*)*\{{",
        text,
    )
    assert match is not None, f"{name} not found in p_sp_st1.c"
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start : i - 1]


# -- C-source structural assertions ----------------------------------------


def test_signatures_match_c() -> None:
    text = _read_c()
    assert re.search(
        r"static\s+short\s+sp_special_coartic\s*\(\s*PDPH_T\s+\w+\s*,\s*"
        r"short\s+\w+\s*,\s*short\s+\w+\s*\)",
        text,
    )
    # The C source breaks the param list across lines with /* ... */
    # comments after each one; use DOTALL so whitespace eats them.
    assert re.search(
        r"static\s+int\s+span_spec_coart\s*\(\s*PDPH_T\s+\w+\s*,"
        r"[\s\S]*?short\s+\w+\s*,[\s\S]*?short\s+\w+\s*\)",
        text,
    )


def test_sp_special_calls_span_twice() -> None:
    """Driver calls ``span_spec_coart`` twice (vowel x prev, vowel x next)."""
    body = _extract_body("sp_special_coartic")
    assert body.count("span_spec_coart") >= 2


def test_ix_remap_present() -> None:
    """Helper remaps ``other == SPP_IX`` to ``SPP_NH``."""
    body = _extract_body("span_spec_coart")
    assert re.search(r"other\s*==\s*SPP_IX", body)
    assert re.search(r"other\s*=\s*SPP_NH", body)


def test_pf1_em_constant() -> None:
    """F1 branch has ``SPP_E`` + ``SPP_M`` returning -50."""
    body = _extract_body("span_spec_coart")
    assert re.search(r"SPP_E\s*\n\s*&&\s*other\s*==\s*SPP_M", body)
    assert "(-50)" in body


def test_eu_diphthong_constant() -> None:
    """F2 branch has the eu-diphthong -300 constant."""
    body = _extract_body("span_spec_coart")
    assert "-300" in body


def test_ie_diphthong_constant() -> None:
    """F3 branch has the ie-diphthong -250 constant."""
    body = _extract_body("span_spec_coart")
    assert "-250" in body


# -- Python behavioural assertions ----------------------------------------


def _make_state(phones: list[int], np_param: int, stress: int = 0) -> DphT:
    state = DphT()
    state.pSTphsettar = DphSettarSt()
    state.pSTphsettar.np = np_param
    state.allophons = list(phones) + [0] * (300 - len(phones))
    state.nallotot = len(phones)
    state.allofeats = [stress] * 300
    return state


def test_python_pf1_e_m_returns_minus_50() -> None:
    state = _make_state([SPP_M, SPP_E, 0], F1)
    assert span_spec_coart(state, SPP_E, SPP_M) == -50


def test_python_pf1_other_pair_returns_zero() -> None:
    state = _make_state([SPP_F, SPP_E, 0], F1)
    assert span_spec_coart(state, SPP_E, SPP_F) == 0


def test_python_pf2_e_plus_u_minus_300() -> None:
    state = _make_state([SPP_U, SPP_E, 0], F2)
    assert span_spec_coart(state, SPP_E, SPP_U) == -300


def test_python_pf2_i_plus_o_minus_200() -> None:
    state = _make_state([SPP_O, SPP_I, 0], F2)
    assert span_spec_coart(state, SPP_I, SPP_O) == -200


def test_python_pf2_u_plus_s_75() -> None:
    state = _make_state([SPP_S, SPP_U, 0], F2)
    assert span_spec_coart(state, SPP_U, SPP_S) == 75


def test_python_pf2_u_plus_m_minus_50() -> None:
    """SPP_U + SPP_M returns -50 (early-out before the dental-fall-through)."""
    state = _make_state([SPP_M, SPP_U, 0], F2)
    assert span_spec_coart(state, SPP_U, SPP_M) == -50


def test_python_pf3_a_plus_n_returns_200() -> None:
    state = _make_state([SPP_N, SPP_A, 0], F3)
    assert span_spec_coart(state, SPP_A, SPP_N) == 200


def test_python_pf3_e_plus_m_returns_300() -> None:
    state = _make_state([SPP_M, SPP_E, 0], F3)
    assert span_spec_coart(state, SPP_E, SPP_M) == 300


def test_python_pf3_u_plus_gh_returns_minus_75() -> None:
    state = _make_state([SPP_GH, SPP_U, 0], F3)
    assert span_spec_coart(state, SPP_U, SPP_GH) == -75


def test_python_pf3_o_plus_y_returns_100() -> None:
    state = _make_state([SPP_Y, SPP_O, 0], F3)
    assert span_spec_coart(state, SPP_O, SPP_Y) == 100


def test_python_pf3_no_match_returns_zero() -> None:
    state = _make_state([0, SPP_A, 0], F3)
    # SPP_F has FLABIAL place; A vs F at F3 with other != M hits the
    # FLABIAL branch (-100) -- pick a phoneme with no place flag instead.
    # Index 0 in sp_place is empty (no flag bits), and SPP_A is a vowel
    # not in any of the switch case constants for vowel=A at F3, so the
    # default arm fires with no return.
    # Use SPP_E which is a vowel: it's not in any of the A-vowel cases,
    # and has no place bits in sp_place beyond what the switch needs.
    # Simpler: test that an unmatched vowel+vowel pair returns 0.
    assert span_spec_coart(state, SPP_A, SPP_E) == 0


def test_python_driver_sums_both_sides_f1() -> None:
    """``sp_special_coartic`` adds the prev-side and next-side rules."""
    state = _make_state([SPP_M, SPP_E, SPP_M], F1)
    # E + M (las) -> -50; E + M (nex) -> -50; total -100.
    assert sp_special_coartic(state, 1, 0) == -100


def test_python_driver_sums_both_sides_f3() -> None:
    """E + M on both sides at F3: 300 + 300 = 600 (no clamp in this branch)."""
    state = _make_state([SPP_M, SPP_E, SPP_M], F3)
    assert sp_special_coartic(state, 1, 0) == 600
