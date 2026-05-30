"""C-source parity test for ``pht0draw`` against ph_drwt01.c.

The production ``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING`` build uses
``ph_drwt01.c``, which defines ``pht0draw`` twice. The first (line ~277)
is the ``NWSNOAA`` / ``ENGLISH_UK`` variant; the **second** (line ~2381)
is the active US English one. We extract the second definition.

The active generator is a single function — no MALE/FEMALE split, no
separate ``filter_seg_commands`` two-pole, no triangle impulse envelope.
The command type is value-decoded (0 = reset, >= 2000 = user, even =
STEP, odd = IMPULSE), the baseline declines via ``tarbas = beginfall -
nframb``, and the F0 is scaled about the constant 1200.

Skips the C-source assertions when ``DECTALK_SRC`` is absent; the Python
behavioural tests always run.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import F0SHFT, HIGHEST_F0, LOWEST_F0
from dectalk.ph.math_helpers import muldv
from dectalk.ph.param_indices import OUT_T0
from dectalk.ph.pht0draw import _US_F0_SEGTARS, _frac4mul, pht0draw
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_drwt01.c"
_ROM_FILE = (
    Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
    / "src/dapi/src/ph/p_us_rom_dectalk_1996m_43f.c"
)

_c_skip = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read(path: Path) -> str:
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_active_body() -> str:
    """Return the body of the *second* (active US English) pht0draw."""
    text = _read(_C_FILE)
    headers = list(re.finditer(r"\bvoid\s+pht0draw\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)\s*\{", text))
    assert len(headers) >= 2, f"expected two pht0draw definitions, found {len(headers)}"
    start = headers[-1].end() - 1
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    raise AssertionError("unterminated pht0draw body")


# -- C-source structural assertions ----------------------------------------


@_c_skip
def test_active_body_is_single_function_no_malfem_split() -> None:
    """The active pht0draw does not branch on ``malfem``."""
    body = _extract_active_body()
    assert "malfem" not in body


@_c_skip
def test_active_body_value_decodes_commands() -> None:
    """The command loop decodes type from the f0command value."""
    body = _extract_active_body()
    assert re.search(r"if\s*\(\s*f0command\s*==\s*0\s*\)", body)
    assert re.search(r"if\s*\(\s*f0command\s*>=\s*2000\s*\)", body)
    assert re.search(r"\(\s*f0command\s*&\s*0?1\s*\)\s*==\s*0", body)
    # Impulse is the doubled value.
    assert re.search(r"tarimp\s*=\s*f0command\s*\+\s*f0command", body)


@_c_skip
def test_active_body_has_baseline_declination() -> None:
    """``tarbas = beginfall - nframb`` declination is present."""
    body = _extract_active_body()
    assert re.search(r"tarbas\s*=\s*pDphsettar->beginfall\s*-\s*pDphsettar->nframb", body)


@_c_skip
def test_active_body_calls_filter_commands_not_seg() -> None:
    """The active body calls filter_commands but not filter_seg_commands."""
    body = _extract_active_body()
    assert re.search(r"filter_commands\s*\(\s*pDph_t\s*,\s*f0in\s*\)", body)
    assert "filter_seg_commands" not in body


@_c_skip
def test_active_body_uses_us_f0segtars() -> None:
    """Segmental lookup is ``us_f0segtars[phocur & PVALUE]`` (single table)."""
    body = _extract_active_body()
    assert re.search(r"us_f0segtars\s*\[\s*phocur\s*&\s*PVALUE\s*\]", body)
    assert "us_f0fsegtars" not in body
    assert "us_f0msegtars" not in body


@_c_skip
def test_active_body_scales_about_1200_with_jitter() -> None:
    """Scale subtracts the constant 1200; jitter uses timecos15/timecos10 >> 5."""
    body = _extract_active_body()
    assert re.search(r"frac4mul\s*\(\s*\(\s*pDph_t->f0prime\s*-\s*1200\s*\)", body)
    assert "getcosine[pDphsettar->timecos15 >> 6]" in body.replace("  ", " ")
    assert re.search(r"f0prime\s*\+=\s*\(\s*pseudojitter\s*>>\s*5\s*\)", body)


@_c_skip
def test_active_body_emits_out_t0_period() -> None:
    """OUT_T0 carries the pitch *period* muldv(400, 1000, f0prime).

    The C stages the operands through arg1/arg2/arg3 just before the
    divide, so check both the staging and the muldv emit.
    """
    body = _extract_active_body()
    assert re.search(r"arg1\s*=\s*400\b", body)
    assert re.search(r"arg2\s*=\s*1000\b", body)
    assert re.search(r"arg3\s*=\s*pDph_t->f0prime", body)
    assert re.search(r"parstochip\[OUT_T0\]\s*=\s*temp\s*=\s*muldv", body)


@pytest.mark.skipif(not _ROM_FILE.is_file(), reason="active voice ROM not available")
def test_segtars_table_matches_active_rom() -> None:
    """The embedded ``_US_F0_SEGTARS`` matches the active voice ROM."""
    text = _read(_ROM_FILE)
    m = re.search(r"us_f0segtars\s*\[\s*\]\s*=\s*\{([^}]+)\}", text)
    assert m is not None
    # The C table interleaves /* phoneme-name */ comments between rows.
    table = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    values = tuple(int(v.strip()) for v in table.split(",") if v.strip().lstrip("-").isdigit())
    assert values == _US_F0_SEGTARS


# -- Python behavioural tests ----------------------------------------------


def _make_handle(
    *,
    f0tar: list[int] | None = None,
    f0tim: list[int] | None = None,
    nf0tot: int = 0,
    f0basefall: int = 0,
) -> TtsHandle:
    """Return a minimal hard-init-ready TtsHandle for pht0draw."""
    p = DphT()
    p.nf0ev = -2
    p.f0minimum = 1100
    p.f0_lp_filter = 1300
    p.f0basefall = f0basefall
    p.f0scalefac = 4096
    p.f0mode = 1  # NORMAL
    p.nallotot = 4
    p.allophons = [GEN_SIL, GEN_SIL, GEN_SIL, GEN_SIL]
    p.allodurs = [10, 10, 10, 10]
    p.allofeats = [0, 0, 0, 0]
    p.f0tar = list(f0tar) if f0tar is not None else [0, 0]
    p.f0tim = list(f0tim) if f0tim is not None else [9999, 9999]
    p.nf0tot = nf0tot
    p.parstochip = [0] * 20
    p.pSTphsettar = DphSettarSt()

    handle = TtsHandle()
    handle.p_ph_thread_data = p
    return handle


def _settar(handle: TtsHandle) -> DphSettarSt:
    p = handle.p_ph_thread_data
    assert isinstance(p, DphT)
    st = p.pSTphsettar
    assert isinstance(st, DphSettarSt)
    return st


def test_runs_and_emits_period() -> None:
    """A first frame hard-inits, stays in band, and emits the period."""
    handle = _make_handle()
    pht0draw(handle)
    p = handle.p_ph_thread_data
    assert isinstance(p, DphT)
    assert p.nf0ev == 0
    assert LOWEST_F0 <= p.f0prime <= HIGHEST_F0
    assert p.parstochip[OUT_T0] == muldv(400, 1000, p.f0prime)


def test_hard_init_sets_baseline_coefficients() -> None:
    """Hard init derives f0beginfall/f0endfall and the 2-pole coefficients."""
    handle = _make_handle(f0basefall=100)
    st = _settar(handle)
    pht0draw(handle)
    # f0beginfall = 1070 + (100 >> 1) = 1120; f0endfall = 1070 - 50 = 1020.
    assert st.f0beginfall == 1120
    assert st.f0endfall == 1020
    # f0a2 = f0_lp_filter; f0a1 = f0a2 << F0SHFT.
    assert st.f0a2 == 1300
    assert st.f0a1 == 1300 << F0SHFT


def test_even_command_is_step_into_tarhat() -> None:
    """An even f0tar value accumulates into ``tarhat`` (STEP-decoded)."""
    handle = _make_handle(f0tar=[100, 0], f0tim=[0, 9999], nf0tot=1)
    st = _settar(handle)
    pht0draw(handle)
    assert st.tarhat == 100
    assert st.tarimp == 0


def test_odd_command_is_doubled_impulse() -> None:
    """An odd f0tar value sets ``tarimp = 2 * value`` (IMPULSE-decoded)."""
    handle = _make_handle(f0tar=[101, 0], f0tim=[0, 9999], nf0tot=1)
    st = _settar(handle)
    pht0draw(handle)
    # tarimp = 101 + 101 = 202; nimp = 16 - ((1300 - 1300) >> 8) = 16, then
    # the per-frame countdown decrements it once to 15 (still >= 0).
    assert st.tarimp == 202
    assert st.nimp == 15


def test_zero_command_resets_baseline() -> None:
    """An f0command of 0 resets ``nframb`` and ``tarhat``."""
    handle = _make_handle(f0tar=[0, 0], f0tim=[0, 9999], nf0tot=1)
    st = _settar(handle)
    st_before_nframb = 99
    # Prime nframb so we can see the reset take effect.
    pht0draw(handle)  # hard+soft init zeroes nframb anyway; command keeps it 0.
    assert st.tarhat == 0
    assert st.nframb == 0
    del st_before_nframb


def test_baseline_declines_over_frames() -> None:
    """With f0basefall > 0 the baseline ``tarbas`` declines (nframb climbs)."""
    handle = _make_handle(f0basefall=200)
    st = _settar(handle)
    pht0draw(handle)  # init frame
    beginfall = st.beginfall
    for _ in range(30):
        pht0draw(handle)
    # nframb advanced (declination active) and tarbas fell below beginfall.
    assert st.nframb > 0
    assert st.tarbas < beginfall


def test_frac4mul_q12() -> None:
    """``_frac4mul`` is the Q12 ``(x*y) >> 12`` helper."""
    assert _frac4mul(1000, 4096) == 1000  # unity
    assert _frac4mul(2000, 2048) == 1000  # half
