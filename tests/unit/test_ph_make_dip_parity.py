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

import pytest

from dectalk.ph.dph_t import DphT
from dectalk.ph.make_dip import make_dip

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


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract."""
    state = DphT()
    cell = [0]
    with pytest.raises(NotImplementedError, match=r"dectalk\._capi"):
        make_dip(state, pdip=0, inhdr_frames=0, shrink=0, struccur=0, pps_ndips=cell)


def test_python_shim_error_mentions_phase_plan() -> None:
    """Error message points at the plan file so callers can find context."""
    state = DphT()
    cell = [0]
    with pytest.raises(NotImplementedError) as exc_info:
        make_dip(state, pdip=1, inhdr_frames=2, shrink=3, struccur=4, pps_ndips=cell)
    assert "Phase E" in str(exc_info.value)
