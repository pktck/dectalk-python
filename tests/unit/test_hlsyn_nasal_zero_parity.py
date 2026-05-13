"""C-source parity test for ``NasalZero`` against nasalf1x.c.

Re-parses the C body and the static tables / constants defined in
``inithl.c`` and ``hlsyn.h``, then asserts the Python port matches
both structurally (regex checks on the C body) and numerically
(end-to-end ``nasal_zero`` calls reproduce the C formulas).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.compute_fm import compute_fm
from dectalk.hlsyn.interpolate import interpolate_table
from dectalk.hlsyn.nasal_tables import (
    ANFN_TABLE,
    ANFN_TABLE_FNO,
    F1_LOVER_A_TABLE,
    MAX_ANFN,
    MAX_F1_LOVER_A,
    NASAL_BANDWIDTH,
)
from dectalk.hlsyn.nasal_zero import nasal_zero
from dectalk.hlsyn.sqrt_table import dt_f_sqrt
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState

_C_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_NASALF1X = _C_ROOT / "src/dapi/src/hlsyn/nasalf1x.c"
_C_INITHL = _C_ROOT / "src/dapi/src/hlsyn/inithl.c"
_C_HLSYN_H = _C_ROOT / "src/dapi/src/hlsyn/hlsyn.h"

pytestmark = pytest.mark.skipif(
    not (_C_NASALF1X.is_file() and _C_INITHL.is_file() and _C_HLSYN_H.is_file()),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read(path: Path) -> str:
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_nasalzero_body() -> str:
    text = _read(_C_NASALF1X)
    match = re.search(
        r"NasalZero\s*\([^)]*\)\s*\n\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "NasalZero() definition not found in nasalf1x.c"
    return match.group(1)


# ---------------------------------------------------------------------------
# Structural parity: signature, predicate, formulas in the C body.
# ---------------------------------------------------------------------------


def test_signature_matches_c() -> None:
    """Signature is ``static void NasalZero(HLFrame*, HLSpeaker*, HLState*, float*, float*)``."""
    text = _read(_C_NASALF1X)
    sig = re.search(
        r"static\s+void\s*\n\s*NasalZero\s*\(\s*HLFrame\s*\*\s*\w+\s*,\s*"
        r"HLSpeaker\s*\*\s*\w+\s*,\s*HLState\s*\*\s*\w+\s*,\s*"
        r"float\s*\*\s*\w+\s*,\s*float\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_an_clamped_to_zero_floor() -> None:
    """C body opens with ``an = MAX(0.0f, frame->an)``."""
    body = _extract_nasalzero_body()
    assert re.search(r"an\s*=\s*MAX\s*\(\s*0\.0f?\s*,\s*frame->an\s*\)", body)


def test_fn_uses_anfn_table_with_fno_scale() -> None:
    """``fn = InterpolateTable(anfnTable, MAXANFN, an) * (speaker->fno / anfnTable_fno);``."""
    body = _extract_nasalzero_body()
    assert re.search(
        r"fn\s*=\s*InterpolateTable\s*\(\s*anfnTable\s*,\s*MAXANFN\s*,\s*an\s*\)\s*\*"
        r"\s*\(\s*speaker->fno\s*/\s*anfnTable_fno\s*\)",
        body,
    )


def test_fm_uses_compute_fm() -> None:
    """``fm = Compute_fm(frame, speaker);``."""
    body = _extract_nasalzero_body()
    assert re.search(r"fm\s*=\s*Compute_fm\s*\(\s*frame\s*,\s*speaker\s*\)", body)


def test_lover_a_uses_f1c() -> None:
    """``LOverA = InterpolateTable(f1LOverATable, MAXF1LOVERA, state->f1c);``."""
    body = _extract_nasalzero_body()
    assert re.search(
        r"LOverA\s*=\s*InterpolateTable\s*\(\s*f1LOverATable\s*,\s*MAXF1LOVERA\s*,\s*"
        r"\n?\s*state->f1c\s*\)",
        body,
    )


def test_mm_over_mn_formula() -> None:
    """``MmOverMn = LOverA * an / (3.7 * an + 100)``."""
    body = _extract_nasalzero_body()
    assert re.search(
        r"MmOverMn\s*=\s*\(\s*float\s*\)\s*\(\s*LOverA\s*\*\s*an\s*/\s*"
        r"\(\s*3\.7f?\s*\*\s*an\s*\+\s*100\.f?\s*\)\s*\)",
        body,
    )


def test_fnz_uses_dtsqrt() -> None:
    """``*pFNZ = fn * DTsqrt((1 + MmOverMn) / (1 + MmOverMn * fn * fn / (fm * fm)))``."""
    body = _extract_nasalzero_body()
    assert re.search(
        r"\*pFNZ\s*=\s*fn\s*\*\s*\(\s*float\s*\)\s*DTsqrt\s*\(\s*"
        r"\(\s*1\.f?\s*\+\s*MmOverMn\s*\)\s*\n?\s*/\s*"
        r"\(\s*1\.f?\s*\+\s*MmOverMn\s*\*\s*fn\s*\*\s*fn\s*/\s*\(\s*fm\s*\*\s*fm\s*\)\s*\)\s*\)",
        body,
    )


def test_bnz_branch_predicate() -> None:
    """``if (state->f1c < speaker->BNZ_f1BreakPoint)`` selects the floor branch."""
    body = _extract_nasalzero_body()
    assert re.search(
        r"if\s*\(\s*state->f1c\s*<\s*speaker->BNZ_f1BreakPoint\s*\)",
        body,
    )


def test_bnz_floor_value_is_nasalbandwidth() -> None:
    """Below the break point, ``*pBNZ = NasalBandwidth``."""
    body = _extract_nasalzero_body()
    assert re.search(r"\*pBNZ\s*=\s*NasalBandwidth\s*;", body)


def test_bnz_above_breakpoint_adds_mm_term() -> None:
    """Above the break point, ``*pBNZ = NasalBandwidth + 100.0 * MmOverMn``."""
    body = _extract_nasalzero_body()
    assert re.search(
        r"\*pBNZ\s*=\s*NasalBandwidth\s*\+\s*100\.0f?\s*\*\s*MmOverMn",
        body,
    )


# ---------------------------------------------------------------------------
# Embedded-data parity: tables and constants must match the C source verbatim.
# ---------------------------------------------------------------------------


def test_max_anfn_matches_hlsyn_h() -> None:
    """``MAX_ANFN`` matches ``#define MAXANFN 9`` in hlsyn.h."""
    text = _read(_C_HLSYN_H)
    match = re.search(r"#define\s+MAXANFN\s+(\d+)", text)
    assert match is not None
    assert int(match.group(1)) == MAX_ANFN


def test_max_f1_lover_a_matches_hlsyn_h() -> None:
    """``MAX_F1_LOVER_A`` matches ``#define MAXF1LOVERA 11`` in hlsyn.h."""
    text = _read(_C_HLSYN_H)
    match = re.search(r"#define\s+MAXF1LOVERA\s+(\d+)", text)
    assert match is not None
    assert int(match.group(1)) == MAX_F1_LOVER_A


def test_nasal_bandwidth_matches_hlsyn_h() -> None:
    """``NASAL_BANDWIDTH`` matches ``#define NasalBandwidth 200.0f`` in hlsyn.h."""
    text = _read(_C_HLSYN_H)
    match = re.search(r"#define\s+NasalBandwidth\s+([\d.]+)f?", text)
    assert match is not None
    assert float(match.group(1)) == NASAL_BANDWIDTH


def test_anfn_table_fno_matches_inithl() -> None:
    """``ANFN_TABLE_FNO`` matches ``anfnTable_fno = 500.f`` in inithl.c."""
    text = _read(_C_INITHL)
    match = re.search(r"anfnTable_fno\s*=\s*([\d.]+)f?", text)
    assert match is not None
    assert float(match.group(1)) == ANFN_TABLE_FNO


def _parse_inithl_anfn_table() -> list[tuple[float, float]]:
    """Re-parse ``anfnTable`` from inithl.c (one row per ``anfnTable[i].FIELD = ...;``)."""
    text = _read(_C_INITHL)
    an_rows = re.findall(
        r"anfnTable\[(\d+)\]\.ANFN_AN\s*=\s*([\d.]+)f?",
        text,
    )
    fn_rows = re.findall(
        r"anfnTable\[(\d+)\]\.ANFN_FN\s*=\s*([\d.]+)f?",
        text,
    )
    ans = {int(i): float(v) for i, v in an_rows}
    fns = {int(i): float(v) for i, v in fn_rows}
    assert set(ans.keys()) == set(fns.keys()), "anfnTable index sets out of sync"
    return [(ans[i], fns[i]) for i in sorted(ans.keys())]


def test_anfn_table_matches_inithl() -> None:
    """Every ``ANFN_TABLE`` row matches its ``inithl.c`` counterpart."""
    c_rows = _parse_inithl_anfn_table()
    assert len(c_rows) == MAX_ANFN
    assert len(ANFN_TABLE) == MAX_ANFN
    for (c_an, c_fn), (py_an, py_fn) in zip(c_rows, ANFN_TABLE, strict=True):
        assert c_an == py_an
        assert c_fn == py_fn


def _parse_inithl_f1_lover_a_table() -> list[tuple[float, float]]:
    """Re-parse ``f1LOverATable`` from inithl.c."""
    text = _read(_C_INITHL)
    f1_rows = re.findall(
        r"f1LOverATable\[(\d+)\]\.F1LOVERA_F1\s*=\s*([\d.]+)f?",
        text,
    )
    lov_rows = re.findall(
        r"f1LOverATable\[(\d+)\]\.F1LOVERA_LOVERA\s*=\s*([\d.]+)f?",
        text,
    )
    f1s = {int(i): float(v) for i, v in f1_rows}
    lovs = {int(i): float(v) for i, v in lov_rows}
    assert set(f1s.keys()) == set(lovs.keys()), "f1LOverATable index sets out of sync"
    return [(f1s[i], lovs[i]) for i in sorted(f1s.keys())]


def test_f1_lover_a_table_matches_inithl() -> None:
    """Every ``F1_LOVER_A_TABLE`` row matches its ``inithl.c`` counterpart."""
    c_rows = _parse_inithl_f1_lover_a_table()
    assert len(c_rows) == MAX_F1_LOVER_A
    assert len(F1_LOVER_A_TABLE) == MAX_F1_LOVER_A
    for (c_f1, c_lov), (py_f1, py_lov) in zip(c_rows, F1_LOVER_A_TABLE, strict=True):
        assert c_f1 == py_f1
        assert c_lov == py_lov


# ---------------------------------------------------------------------------
# Numerical parity: the Python port reproduces the C formula end-to-end.
# ---------------------------------------------------------------------------


def _reference_nasal_zero(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
) -> tuple[float, float]:
    """Reference re-implementation of ``NasalZero`` driven straight off the C formula."""
    an = max(0.0, frame.an)
    fn = interpolate_table(ANFN_TABLE, an) * (speaker.fno / ANFN_TABLE_FNO)
    fm = compute_fm(frame, speaker)
    l_over_a = interpolate_table(F1_LOVER_A_TABLE, state.f1c)
    mm_over_mn = l_over_a * an / (3.7 * an + 100.0)
    fnz = fn * dt_f_sqrt((1.0 + mm_over_mn) / (1.0 + mm_over_mn * fn * fn / (fm * fm)))
    if state.f1c < speaker.BNZ_f1BreakPoint:
        bnz = NASAL_BANDWIDTH
    else:
        bnz = NASAL_BANDWIDTH + 100.0 * mm_over_mn
    return fnz, bnz


def _typical_speaker() -> HLSpeaker:
    """A loosely-MV1-shaped speaker for the numeric checks."""
    return HLSpeaker(
        fno=500.0,
        fm_f1BreakPoint=500.0,
        BNZ_f1BreakPoint=350.0,
    )


def test_python_matches_reference_typical() -> None:
    """Standard mid-range case: an=20 mm^2, f1c=300 Hz."""
    frame = HLFrame(an=20.0, f1=400.0, f2=1500.0, f3=2500.0)
    speaker = _typical_speaker()
    state = HLState(f1c=300.0)
    py_fnz, py_bnz = nasal_zero(frame, speaker, state)
    ref_fnz, ref_bnz = _reference_nasal_zero(frame, speaker, state)
    assert math.isclose(py_fnz, ref_fnz, rel_tol=0.0, abs_tol=0.0)
    assert math.isclose(py_bnz, ref_bnz, rel_tol=0.0, abs_tol=0.0)


def test_python_matches_reference_low_f1c() -> None:
    """``f1c`` below ``BNZ_f1BreakPoint`` -> BNZ floors to ``NASAL_BANDWIDTH``."""
    frame = HLFrame(an=30.0, f1=350.0, f2=1700.0, f3=2600.0)
    speaker = _typical_speaker()
    state = HLState(f1c=200.0)
    py_fnz, py_bnz = nasal_zero(frame, speaker, state)
    ref_fnz, ref_bnz = _reference_nasal_zero(frame, speaker, state)
    assert py_bnz == NASAL_BANDWIDTH
    assert math.isclose(py_fnz, ref_fnz, rel_tol=0.0, abs_tol=0.0)
    assert math.isclose(py_bnz, ref_bnz, rel_tol=0.0, abs_tol=0.0)


def test_python_matches_reference_high_f1c() -> None:
    """``f1c`` above ``BNZ_f1BreakPoint`` -> BNZ adds the MmOverMn term."""
    frame = HLFrame(an=40.0, f1=600.0, f2=1900.0, f3=2700.0)
    speaker = _typical_speaker()
    state = HLState(f1c=500.0)
    py_fnz, py_bnz = nasal_zero(frame, speaker, state)
    ref_fnz, ref_bnz = _reference_nasal_zero(frame, speaker, state)
    assert py_bnz > NASAL_BANDWIDTH
    assert math.isclose(py_fnz, ref_fnz, rel_tol=0.0, abs_tol=0.0)
    assert math.isclose(py_bnz, ref_bnz, rel_tol=0.0, abs_tol=0.0)


def test_negative_an_clamped_to_zero() -> None:
    """``frame.an < 0`` is clamped to zero before the table lookup."""
    speaker = _typical_speaker()
    state = HLState(f1c=300.0)
    pos = HLFrame(an=0.0, f1=400.0, f2=1500.0, f3=2500.0)
    neg = HLFrame(an=-5.0, f1=400.0, f2=1500.0, f3=2500.0)
    assert nasal_zero(pos, speaker, state) == nasal_zero(neg, speaker, state)


def test_fno_rescales_fn_proportionally() -> None:
    """A speaker with ``fno = 2 * ANFN_TABLE_FNO`` doubles the ``fn`` contribution."""
    frame = HLFrame(an=20.0, f1=400.0, f2=1500.0, f3=2500.0)
    state = HLState(f1c=300.0)
    base = HLSpeaker(fno=ANFN_TABLE_FNO, fm_f1BreakPoint=500.0, BNZ_f1BreakPoint=350.0)
    scaled = HLSpeaker(
        fno=2.0 * ANFN_TABLE_FNO,
        fm_f1BreakPoint=500.0,
        BNZ_f1BreakPoint=350.0,
    )
    fnz_base, _ = nasal_zero(frame, base, state)
    fnz_scaled, _ = nasal_zero(frame, scaled, state)
    # Scaled fn doubles the ``fn`` factor everywhere; FNZ also depends on
    # the square-root mixing with fm, so we just check the doubled-speaker
    # value derives from the same reference path.
    ref_base = _reference_nasal_zero(frame, base, state)[0]
    ref_scaled = _reference_nasal_zero(frame, scaled, state)[0]
    assert math.isclose(fnz_base, ref_base, rel_tol=0.0, abs_tol=0.0)
    assert math.isclose(fnz_scaled, ref_scaled, rel_tol=0.0, abs_tol=0.0)
    assert fnz_scaled > fnz_base


def test_bnz_at_breakpoint_is_high_branch() -> None:
    """``state.f1c == BNZ_f1BreakPoint`` -> high branch (the C uses ``<``)."""
    frame = HLFrame(an=25.0, f1=400.0, f2=1500.0, f3=2500.0)
    speaker = _typical_speaker()
    state = HLState(f1c=speaker.BNZ_f1BreakPoint)
    _, bnz = nasal_zero(frame, speaker, state)
    # On the high branch BNZ = NASAL_BANDWIDTH + 100 * MmOverMn > floor.
    assert bnz > NASAL_BANDWIDTH


def test_fnz_lies_between_fn_and_fm() -> None:
    """When ``fn < fm`` the C source asserts ``fn < FNZ < fm`` (and vice versa)."""
    frame = HLFrame(an=20.0, f1=400.0, f2=1500.0, f3=2500.0)
    speaker = _typical_speaker()
    state = HLState(f1c=300.0)
    fn = interpolate_table(ANFN_TABLE, max(0.0, frame.an)) * (speaker.fno / ANFN_TABLE_FNO)
    fm = compute_fm(frame, speaker)
    fnz, _ = nasal_zero(frame, speaker, state)
    lo, hi = (fn, fm) if fn < fm else (fm, fn)
    assert lo <= fnz <= hi
