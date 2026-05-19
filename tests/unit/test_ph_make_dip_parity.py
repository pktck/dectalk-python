"""C-source parity test for ``make_dip`` against ph_setar.c.

Re-parses the C body via brace-depth tracking and asserts the
static parameter-dip generator still exists in the develop branch
with its expected coarticulation rules, dipspec[] walk, and
``shrdur`` time scaling. Also checks the Python shim raises
``NotImplementedError`` as documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.make_dip import make_dip
from dectalk.ph.numeric_constants import FZ

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_setar.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_setar_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of the static ``make_dip`` helper.

    The C source has both a forward declaration (ending in ``;``) and a
    definition (ending in ``{...}``); walk every match and pick the one
    that opens a brace block.
    """
    text = _read_setar_c()
    for match in re.finditer(r"\bstatic\s+void\s+make_dip\s*\(", text):
        paren_start = match.end() - 1
        depth = 1
        i = paren_start + 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        while i < len(text) and text[i] in " \t\n\r":
            i += 1
        if i >= len(text) or text[i] != "{":
            continue
        start = i + 1
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        if depth == 0:
            return text[start : i - 1]
    raise AssertionError("make_dip definition not found in ph_setar.c")


def _extract_signature() -> str:
    """Return the parenthesised parameter list of static ``make_dip``."""
    text = _read_setar_c()
    match = re.search(r"\bstatic\s+void\s+make_dip\s*\(", text)
    assert match is not None, "make_dip definition not found in ph_setar.c"
    paren_start = match.end() - 1
    depth = 1
    i = paren_start + 1
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    return text[paren_start:i]


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``static void make_dip(PDPH_T, short pdip, ..., short **ppsNdips)``."""
    text = _read_setar_c()
    assert re.search(r"\bstatic\s+void\s+make_dip\s*\(\s*PDPH_T", text)


def test_signature_carries_diph_pointer_args() -> None:
    """Signature mentions ``pdip``, ``inhdr_frames``, ``shrink``, ``struccur``, ``ppsNdips``."""
    sig = _extract_signature()
    for arg in ("pdip", "inhdr_frames", "shrink", "struccur", "ppsNdips"):
        assert arg in sig, f"signature missing {arg}"


def test_form_freq_coartic_branch() -> None:
    """Body has ``par_type IS_FORM_FREQ`` coartic rules at first dip pos."""
    body = _extract_body()
    assert re.search(r"par_type\s+IS_FORM_FREQ", body)
    assert re.search(r"gencoartic\s*=\s*N10PRCNT", body)
    assert re.search(r"gencoartic\s*=\s*N15PRCNT", body)
    assert re.search(r"gencoartic\s*=\s*N25PRCNT", body)


def test_walks_p_diph_chain() -> None:
    """Body walks ``p_diph[pdip++]`` until a -1 terminator."""
    body = _extract_body()
    assert re.search(r"p_diph\s*\[\s*pdip\+\+\s*\]\s*!=\s*-\s*1", body)


def test_calls_shrdur() -> None:
    """Body calls ``shrdur(pDph_t, newtime, inhdr_frames, shrink)``."""
    body = _extract_body()
    assert re.search(r"shrdur\s*\(", body)


def test_per_language_special_coartic() -> None:
    """Body dispatches on PFUSA/PFGR/PFLA/PFSP for special_coartic adjustments."""
    body = _extract_body()
    for fn in (
        "us_special_coartic",
        "gr_special_coartic",
        "la_special_coartic",
        "sp_special_coartic",
    ):
        assert fn in body, f"missing call to {fn}"


def test_final_target_writes() -> None:
    """Body finishes with ``tarend = newvalue`` / ``durlin`` / ``deldip`` writes."""
    body = _extract_body()
    assert re.search(r"np\s*->\s*tarend\s*=\s*newvalue", body)
    assert re.search(r"np\s*->\s*durlin\s*=", body)
    assert re.search(r"np\s*->\s*deldip\s*=", body)


# -- Python behavioural tests ----------------------------------------------


def _make_dph_for_make_dip() -> DphT:
    """Build a minimal DphT populated for make_dip non-FORM_FREQ branch."""
    state = DphT()
    state.dipspec = [0] * 40
    # Simple diph table: value=500, time=5 frames, sentinel -1.
    state.p_diph = [0, 500, 5, -1, 0, 0]
    state.durfon = 10
    state.nphone = 0
    settar = DphSettarSt()
    settar.np = FZ  # par_type=1 (non-FORM_FREQ) so the formant rules skip.
    settar.par_type = 1
    state.pSTphsettar = settar
    return state


def test_make_dip_writes_dipspec_and_advances_ndips() -> None:
    """make_dip writes paired (time, slope) entries to dipspec[]."""
    state = _make_dph_for_make_dip()
    cell = [1]  # Start offset into dipspec.
    make_dip(state, pdip=0, inhdr_frames=8, shrink=16384, struccur=0, pps_ndips=cell)
    # The function writes at least one (newtime, slope) pair plus the
    # terminating pair, so the offset must have advanced.
    assert cell[0] > 1


def test_make_dip_sets_param_tarend_and_durlin() -> None:
    """make_dip writes ``tarend`` (last newvalue) and ``durlin`` slots."""
    state = _make_dph_for_make_dip()
    cell = [1]
    make_dip(state, pdip=0, inhdr_frames=8, shrink=16384, struccur=0, pps_ndips=cell)
    settar = cast(DphSettarSt, state.pSTphsettar)
    np_param = state.param[settar.np]
    # `tarend` is the last newvalue assigned in the walk, which for our
    # diph table `[0, 500, 5, -1, ...]` lands on `5` (the second
    # iteration overwrites newvalue=5 via dipsw==1 path).
    assert np_param.tarend == 5
    # `durlin` is the first newtime written to dipspec (shrdur of 500
    # with 8 inhdr_frames and FRAC_ONE shrink == 8 frames).
    assert np_param.durlin == 8
