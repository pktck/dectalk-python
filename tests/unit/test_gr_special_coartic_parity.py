"""C-source parity test for ``gr_special_coartic`` against p_gr_st1.c.

Re-parses the C body of the static helper and asserts the German
F2 coarticulation rules still match: GRP_L before/after lowers
front-vowel F2, GRP_AU/GRP_EU pairs with diphpos shift down,
GRP_UE/GRP_U paired with alveolars shifts up, unstressed
amplification, phrase-final halving, and the [-400, 400] clamp.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.grp_codes import (
    GRP_AU,
    GRP_E,
    GRP_EU,
    GRP_I,
    GRP_L,
    GRP_U,
    GRP_UE,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FSTRESS, FSTRESS_1, FVPNEXT
from dectalk.ph.gr_special_coartic import gr_special_coartic
from dectalk.ph.numeric_constants import F1, F2, F3

_C_FILE = (
    Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
    / "src/dapi/src/ph/p_gr_st1.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_c()
    match = re.search(
        r"static\s+short\s+gr_special_coartic\s*\([^)]*\)\s*\{",
        text,
    )
    assert match is not None, "gr_special_coartic not found in p_gr_st1.c"
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


def test_signature_matches_c() -> None:
    """C signature: ``static short gr_special_coartic(PDPH_T, short nfon, short diphpos)``."""
    text = _read_c()
    assert re.search(
        r"static\s+short\s+gr_special_coartic\s*\(\s*PDPH_T\s+\w+\s*,\s*"
        r"short\s+\w+\s*,\s*short\s+\w+\s*\)",
        text,
    )


def test_calls_get_phone_three_times() -> None:
    """Body grabs foncur, fonnex, fonlas via ``get_phone``."""
    body = _extract_body()
    assert body.count("get_phone(pDph_t,") == 3 or body.count("get_phone(pDph_t, ") == 3


def test_branches_on_pf2() -> None:
    """The active branch is gated on ``pDphsettar->np == &PF2``."""
    body = _extract_body()
    assert re.search(r"pDphsettar->np\s*==\s*&PF2", body)


def test_lowering_constants_present() -> None:
    """The -150 / -250 / -350 lowering deltas appear in the body."""
    body = _extract_body()
    for k in ("-150", "-250", "-350"):
        assert k in body, f"Missing constant {k}"


def test_uw_raising_constant_present() -> None:
    """The +200 UE-raising delta and the +400 unstressed-U clamp appear."""
    body = _extract_body()
    assert "200" in body
    assert "400" in body


def test_clamp_to_pm400_present() -> None:
    """Final clamp ``temp > 400 -> 400`` / ``temp < -400 -> -400``."""
    body = _extract_body()
    assert re.search(r"temp\s*>\s*400", body)
    assert re.search(r"temp\s*<\s*-400", body)


# -- Python behavioural assertions ----------------------------------------


def _make_state(
    phones: list[int], np_param: int, stress: int = 0, boundary: int = 0
) -> DphT:
    state = DphT()
    state.pSTphsettar = DphSettarSt()
    state.pSTphsettar.np = np_param
    state.allophons = list(phones) + [0] * (300 - len(phones))
    state.nallotot = len(phones)
    state.allofeats = [stress | boundary] * 300
    return state


def test_python_pf1_branch_is_zero() -> None:
    """German has no F1 special-case (US-only)."""
    state = _make_state([GRP_L, GRP_I, GRP_L], F1)
    assert gr_special_coartic(state, 1, 0) == 0


def test_python_pf3_branch_is_zero() -> None:
    """German has no F3 special-case (US-only)."""
    state = _make_state([GRP_L, GRP_I, GRP_L], F3)
    assert gr_special_coartic(state, 1, 0) == 0


def test_python_front_vowel_before_l_unstressed() -> None:
    """GRP_I before GRP_L unstressed: -150 amplified by 1.5 = -225."""
    state = _make_state([0, GRP_I, GRP_L], F2)
    assert gr_special_coartic(state, 1, 0) == -225


def test_python_front_vowel_after_l_unstressed() -> None:
    """GRP_I after GRP_L unstressed: -150 amplified by 1.5 = -225."""
    state = _make_state([GRP_L, GRP_I, 0], F2)
    assert gr_special_coartic(state, 1, 0) == -225


def test_python_au_diphpos1_before_l() -> None:
    """GRP_AU before GRP_L with diphpos==1: -250 unstressed * 1.5 = -375."""
    state = _make_state([0, GRP_AU, GRP_L], F2)
    assert gr_special_coartic(state, 1, 1) == -375


def test_python_au_diphpos2_before_l_clamped() -> None:
    """GRP_AU before GRP_L with diphpos>1: -350 unstressed * 1.5 = -525 -> -400."""
    state = _make_state([0, GRP_AU, GRP_L], F2)
    assert gr_special_coartic(state, 1, 2) == -400


def test_python_eu_diphpos2_clamped_to_minus400() -> None:
    """GRP_EU before GRP_L with diphpos>1: -525 clamped to -400."""
    state = _make_state([0, GRP_EU, GRP_L], F2)
    assert gr_special_coartic(state, 1, 5) == -400


def test_python_unstressed_u_diphpos_clamped_to_400() -> None:
    """Unstressed GRP_U with diphpos>0: hard-clamp to 400."""
    state = _make_state([0, GRP_U, 0], F2)
    assert gr_special_coartic(state, 1, 1) == 400


def test_python_phrase_final_stressed_halved() -> None:
    """Stressed + phrase-final (FBOUNDARY >= FVPNEXT) halves the delta."""
    state = _make_state([0, GRP_I, GRP_L], F2, stress=FSTRESS_1, boundary=FVPNEXT)
    # -150 stressed phrase-final: -150 >> 1 = -75
    assert gr_special_coartic(state, 1, 0) == -75


def test_python_stressed_non_phrase_final_keeps_full() -> None:
    """Stressed without phrase-final boundary keeps the raw -150."""
    state = _make_state([0, GRP_I, GRP_L], F2, stress=FSTRESS_1)
    assert gr_special_coartic(state, 1, 0) == -150


def test_python_no_match_returns_zero() -> None:
    """A vowel + consonant pair that fires no rule returns 0."""
    state = _make_state([0, GRP_E, 0], F2)
    assert gr_special_coartic(state, 1, 0) == 0
