"""C-source parity test for ``la_special_coartic`` against p_la_st1.c.

Verifies the LA driver still calls ``span_spec_coart`` (the symbol
defined in ``p_sp_st1.c`` after both files are included into the
same translation unit by ``ph_sttr1.c``), and that the Python port
delegates through :func:`~dectalk.ph.sp_special_coartic.span_spec_coart`
exactly the way the C linker resolves the call.

The dead-code ``la_spec_coart`` helper that also lives in
``p_la_st1.c`` (declared but never called from the active flow) is
explicitly *not* tested -- mirroring the linker's behaviour means
the Python port doesn't reimplement it.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.lap_codes import LAP_E, LAP_M
from dectalk.include.spp_codes import SPP_E, SPP_M
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.la_special_coartic import la_special_coartic
from dectalk.ph.numeric_constants import F1, F2
from dectalk.ph.sp_special_coartic import span_spec_coart

_C_FILE = (
    Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
    / "src/dapi/src/ph/p_la_st1.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(name: str) -> str:
    text = _read_c()
    match = re.search(
        rf"static\s+(?:short|int)\s+{re.escape(name)}\s*\([^)]*\)\s*\{{",
        text,
    )
    assert match is not None, f"{name} not found in p_la_st1.c"
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
    text = _read_c()
    assert re.search(
        r"static\s+short\s+la_special_coartic\s*\(\s*PDPH_T\s+\w+\s*,\s*"
        r"short\s+\w+\s*,\s*short\s+\w+\s*\)",
        text,
    )


def test_calls_span_spec_coart_twice() -> None:
    """LA driver invokes ``span_spec_coart`` (not ``la_spec_coart``) twice."""
    body = _extract_body("la_special_coartic")
    # The name in the call site is span_spec_coart -- the linker resolves
    # this to the SP file's definition.
    assert body.count("span_spec_coart") >= 2
    # No ``la_spec_coart`` call site in the driver body.
    assert "la_spec_coart" not in body


def test_la_spec_coart_is_dead_helper() -> None:
    """The local ``la_spec_coart`` is *declared* but never called from the driver."""
    text = _read_c()
    # Declared (definition present)...
    assert re.search(r"static\s+int\s+la_spec_coart\s*\(", text)
    # ...but the only call sites are the SP-resolved ``span_spec_coart``.
    body = _extract_body("la_special_coartic")
    assert "la_spec_coart(" not in body


# -- Python behavioural assertions ----------------------------------------


def _make_state(
    phones: list[int], np_param: int, stress: int = 0
) -> DphT:
    state = DphT()
    state.pSTphsettar = DphSettarSt()
    state.pSTphsettar.np = np_param
    state.allophons = list(phones) + [0] * (300 - len(phones))
    state.nallotot = len(phones)
    state.allofeats = [stress] * 300
    return state


def test_python_la_phones_yield_zero() -> None:
    """LA-font phones miss every SPP_x switch arm -- returns 0.

    This is the runtime behaviour produced by the C source: the LA
    driver passes LA-font phone codes to ``span_spec_coart``, but the
    SPP_x case constants only match SP-font values, so no rule fires.
    """
    state = _make_state([LAP_M, LAP_E, LAP_M], F1)
    assert la_special_coartic(state, 1, 0) == 0


def test_python_sp_phones_at_la_callsite_fire_rules() -> None:
    """If SP-font phones were fed through the LA driver, SP rules would fire.

    This documents that the delegation is faithful -- the Python port
    routes LA's ``span_spec_coart`` call to exactly the SP definition.
    """
    state = _make_state([SPP_M, SPP_E, SPP_M], F1)
    assert la_special_coartic(state, 1, 0) == -100


def test_python_delegation_matches_span_spec_coart_directly() -> None:
    """``la_special_coartic`` is the sum of two ``span_spec_coart`` calls."""
    state = _make_state([SPP_M, SPP_E, SPP_M], F2)
    expected = span_spec_coart(state, SPP_E, SPP_M) + span_spec_coart(
        state, SPP_E, SPP_M
    )
    assert la_special_coartic(state, 1, 0) == expected


def test_python_diphpos_unused() -> None:
    """The C body never reads diphpos -- varying it must not change the result."""
    state = _make_state([SPP_M, SPP_E, SPP_M], F1)
    r0 = la_special_coartic(state, 1, 0)
    r1 = la_special_coartic(state, 1, 1)
    r2 = la_special_coartic(state, 1, 99)
    assert r0 == r1 == r2 == -100
