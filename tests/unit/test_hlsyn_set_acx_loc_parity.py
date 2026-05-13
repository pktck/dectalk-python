"""C-source parity test for ``Set_acx_loc`` against acxf1c.c.

Re-parses the C body and asserts:

- The function picks the smaller of (Liquid/Dorsum) and
  (Lips/Blade) and writes ``state.acx`` / ``state.loc``.
- The ``acl == UNCOMPUTABLE`` short-circuit collapses to dorsum.
- Ties go to the back (the ``<=`` chain).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.place_constants import BLADE, DORSUM, LIPS, LIQUID, UNCOMPUTABLE
from dectalk.hlsyn.set_acx_loc import set_acx_loc
from dectalk.ph.hlsyn_structs import HLFrame, HLState

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn/acxf1c.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_acxf1c_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_acxf1c_c()
    # Match the definition (not the prototype), so anchor on the
    # opening brace at the start of a line.
    match = re.search(
        r"void\s+Set_acx_loc\s*\([^)]*\)\s*\n\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "Set_acx_loc() definition not found in acxf1c.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """Signature is ``void Set_acx_loc(HLFrame *, HLState *)``."""
    text = _read_acxf1c_c()
    sig = re.search(
        r"void\s+Set_acx_loc\s*\(\s*HLFrame\s*\*\s*\w+\s*,\s*HLState\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_uncomputable_acl_short_circuits_to_dorsum() -> None:
    """``state->acl == UNCOMPUTABLE`` -> back area = ``acd``, place = DORSUM."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*state->acl\s*==\s*UNCOMPUTABLE\s*\)",
        body,
    )
    # Inside the then-branch, LiquidDorsumPlace = DORSUM.
    if_then = re.search(
        r"if\s*\(\s*state->acl\s*==\s*UNCOMPUTABLE\s*\)\s*\{[^}]+\}",
        body,
        re.DOTALL,
    )
    assert if_then is not None
    assert "LiquidDorsumPlace = DORSUM" in if_then.group(0)


def test_acd_le_acl_picks_dorsum() -> None:
    """``state->acd <= state->acl`` -> place = DORSUM (else-if branch)."""
    body = _extract_body()
    assert re.search(
        r"else\s+if\s*\(\s*state->acd\s*<=\s*state->acl\s*\)",
        body,
    )


def test_ab_le_al_picks_blade() -> None:
    """``frame->ab <= frame->al`` -> place = BLADE."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*frame->ab\s*<=\s*frame->al\s*\)", body)


def test_final_pick_writes_state_acx_loc() -> None:
    """The smaller-of comparison writes ``state->acx`` and ``state->loc``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*LiquidDorsumArea\s*<=\s*LipsBladeArea\s*\)",
        body,
    )
    assert re.search(r"state->acx\s*=\s*LiquidDorsumArea", body)
    assert re.search(r"state->loc\s*=\s*LiquidDorsumPlace", body)
    assert re.search(r"state->acx\s*=\s*LipsBladeArea", body)
    assert re.search(r"state->loc\s*=\s*LipsBladePlace", body)


def test_python_uncomputable_acl_picks_dorsum() -> None:
    """``acl=UNCOMPUTABLE`` => loc=DORSUM, acx=acd regardless of acl value."""
    frame = HLFrame(ab=10.0, al=10.0)
    state = HLState(acl=UNCOMPUTABLE, acd=0.5)
    set_acx_loc(frame, state)
    assert state.loc == DORSUM
    assert abs(state.acx - 0.5) < 1e-9


def test_python_acd_le_acl_picks_dorsum() -> None:
    """``acd <= acl`` (and acl is computable) => loc=DORSUM."""
    frame = HLFrame(ab=10.0, al=10.0)
    state = HLState(acl=0.4, acd=0.3)
    set_acx_loc(frame, state)
    assert state.loc == DORSUM
    assert abs(state.acx - 0.3) < 1e-9


def test_python_acl_lt_acd_picks_liquid() -> None:
    """``acl < acd`` => loc=LIQUID."""
    frame = HLFrame(ab=10.0, al=10.0)
    state = HLState(acl=0.3, acd=0.4)
    set_acx_loc(frame, state)
    assert state.loc == LIQUID
    assert abs(state.acx - 0.3) < 1e-9


def test_python_ab_le_al_picks_blade() -> None:
    """``ab <= al`` and front wins => loc=BLADE."""
    frame = HLFrame(ab=0.1, al=0.2)
    state = HLState(acl=10.0, acd=10.0)
    set_acx_loc(frame, state)
    assert state.loc == BLADE
    assert abs(state.acx - 0.1) < 1e-9


def test_python_al_lt_ab_picks_lips() -> None:
    """``al < ab`` and front wins => loc=LIPS."""
    frame = HLFrame(ab=0.2, al=0.1)
    state = HLState(acl=10.0, acd=10.0)
    set_acx_loc(frame, state)
    assert state.loc == LIPS
    assert abs(state.acx - 0.1) < 1e-9


def test_python_tie_at_front_back_prefers_back() -> None:
    """Equal back / front areas => the back wins (``<=`` chain)."""
    frame = HLFrame(ab=0.5, al=0.5)
    state = HLState(acl=0.5, acd=0.5)
    set_acx_loc(frame, state)
    # acd <= acl picks DORSUM. Then LiquidDorsumArea (0.5) <= LipsBladeArea (0.5)
    # picks DORSUM.
    assert state.loc == DORSUM
    assert abs(state.acx - 0.5) < 1e-9
