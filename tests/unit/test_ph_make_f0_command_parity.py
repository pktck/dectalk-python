"""C-source parity test for ``make_f0_command`` against ph_inton0.c.

The production ``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING`` build uses
``ph_inton0.c``, which defines ``make_f0_command`` twice. The first
(line ~1159) is the ``NWSNOAA`` / ``ENGLISH_UK`` variant and carries a
``short type`` parameter and four-array stores. The **second** (line
~2049) is the active US English one: no ``type`` parameter, storing only
``f0tim`` and ``f0tar`` (the command type is encoded in ``tar`` and
decoded by ``pht0draw``). We extract the second definition.

Skips cleanly when ``DECTALK_SRC`` env / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_t import DphT
from dectalk.ph.make_f0_command import make_f0_command
from dectalk.ph.numeric_constants import NPHON_MAX

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_inton0.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_inton_c() -> str:
    """Read ph_inton0.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_active_def() -> tuple[str, str]:
    """Return ``(signature, body)`` for the *active* (US English) definition.

    Picks the ``make_f0_command`` definition whose signature has **no**
    ``type`` parameter — i.e. the second, production one.
    """
    text = _read_inton_c()
    for match in re.finditer(
        r"(static\s+void\s+make_f0_command\s*\([^)]*\))\s*([;{])",
        text,
        re.DOTALL,
    ):
        sig = match.group(1)
        collapsed = re.sub(r"\s+", " ", sig)
        # The active definition has a body and omits the `short type` param.
        if match.group(2) != "{" or re.search(r",\s*short\s+type\b", collapsed):
            continue
        start = match.end(2) - 1
        depth = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        assert end > start, "unterminated make_f0_command body"
        body = text[start + 1 : end]
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        body = re.sub(r"//.*", "", body)
        return collapsed, body
    raise AssertionError("active make_f0_command definition not found in ph_inton0.c")


def test_signature_drops_type_and_keeps_six_params() -> None:
    """The active C signature: ``(PDPH_T, rulenumber, tar, delay, length, *psCumdur)``."""
    sig, _ = _extract_active_def()
    assert re.search(
        r"static void make_f0_command\s*\(\s*"
        r"PDPH_T\s+\w+\s*,\s*"
        r"short\s+rulenumber\s*,\s*"
        r"short\s+tar\s*,\s*"
        r"short\s+delay\s*,\s*"
        r"short\s+length\s*,\s*"
        r"short\s*\*\s*psCumdur\s*\)",
        sig,
    ), f"unexpected signature: {sig!r}"
    # And crucially there is no `type` parameter.
    assert not re.search(r",\s*short\s+type\b", sig)


def test_writes_only_f0tim_and_f0tar() -> None:
    """The active body writes ``f0tim`` and ``f0tar`` only — no f0type/f0length."""
    _, body = _extract_active_def()
    writes = re.findall(
        r"pDph_t->(f0tim|f0tar|f0type|f0length)\s*\[\s*pDph_t->nf0tot\s*\]\s*=",
        body,
    )
    assert writes == ["f0tim", "f0tar"], f"expected f0tim, f0tar writes only; got {writes!r}"
    assert "f0type" not in body
    assert "f0length" not in body


def test_f0_rhs_matches_c() -> None:
    """``f0tim = *psCumdur + delay`` and ``f0tar = tar``."""
    _, body = _extract_active_def()
    assert re.search(
        r"pDph_t->f0tim\s*\[\s*pDph_t->nf0tot\s*\]\s*=\s*\*\s*psCumdur\s*\+\s*delay\s*;",
        body,
    )
    assert re.search(r"pDph_t->f0tar\s*\[\s*pDph_t->nf0tot\s*\]\s*=\s*tar\s*;", body)


def test_clamp_and_cumdur_and_cap_present() -> None:
    """Delay clamp, cumdur reset, and ``NPHON_MAX - 1`` cap are all present."""
    _, body = _extract_active_def()
    assert re.search(r"if\s*\(\s*\(\s*delay\s*\+\s*\*\s*psCumdur\s*\)\s*<\s*0\s*\)", body)
    assert re.search(r"delay\s*=\s*-\s*\(\s*\*\s*psCumdur\s*\)\s*;", body)
    assert re.search(r"\*\s*psCumdur\s*=\s*\(?\s*-\s*delay\s*\)?\s*;", body)
    assert re.search(r"if\s*\(\s*pDph_t->nf0tot\s*<\s*NPHON_MAX\s*-\s*1\s*\)", body)


# --- Behavioural parity -----------------------------------------------------


def test_python_first_command_populates_slot_zero() -> None:
    """From ``nf0tot == 0`` the first call writes slot [0] and bumps to 1."""
    state = DphT()
    cumdur = [0]
    make_f0_command(state, rulenumber=1, tar=1200, delay=5, length=10, ps_cumdur=cumdur)
    assert state.nf0tot == 1
    assert state.f0tim[0] == 5
    assert state.f0tar[0] == 1200
    assert cumdur[0] == -5


def test_python_negative_delay_clamps_against_cumdur() -> None:
    """``cumdur=5, delay=-10`` → effective delay clamps to -5."""
    state = DphT()
    cumdur = [5]
    make_f0_command(state, rulenumber=0, tar=0, delay=-10, length=0, ps_cumdur=cumdur)
    assert state.f0tim[0] == 0
    assert cumdur[0] == 5


def test_python_nf0tot_caps_at_nphon_max_minus_one() -> None:
    """``nf0tot`` stops bumping once it reaches ``NPHON_MAX - 1``."""
    state = DphT()
    state.nf0tot = NPHON_MAX - 1
    cumdur = [0]
    make_f0_command(state, rulenumber=0, tar=0, delay=0, length=0, ps_cumdur=cumdur)
    assert state.nf0tot == NPHON_MAX - 1
